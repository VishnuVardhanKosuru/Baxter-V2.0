"""
core/frd_worker.py
──────────────────
Async parallel worker for a single FRD.

Replaces the sequential `for` loop in c&s_agent.py with `chain.abatch()`,
enabling 50 TCs to be processed in parallel using a single LiteLLM LLM instance.

Key behaviour:
  - Uses LangChain's chain.abatch(inputs, config={"max_concurrency": N})
  - return_exceptions=True ensures one failed TC doesn't abort the whole batch
  - Writes CSV rows, .feature files, and Selenium scripts as each TC completes
  - Calls CheckpointManager.mark_done() after each successful TC (crash recovery)
  - Calls progress_cb(frd_id, done_count, total) after each TC (SSE updates)

Usage:
    worker = FRDWorker(...)
    result = await worker.run()
"""

import csv
import json
import asyncio
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Awaitable

from core.checkpoint import CheckpointManager
from core.cs_agent import _strip_fences
from core.logger import logger


# ── Result container ──────────────────────────────────────────────────────────

@dataclass
class FRDWorkerResult:
    """Summary of what was processed for one FRD."""
    frd_id:    str
    frd_name:  str
    total:     int
    completed: int
    failed:    List[str] = field(default_factory=list)


# ── FRD Worker ────────────────────────────────────────────────────────────────

class FRDWorker:
    """
    Processes all test cases for a single FRD using async parallel abatch().

    Args:
        frd_id:      Identifier like "FRD-001"
        frd_name:    Human-readable name like "UserAuth"
        test_cases:  List of TC dicts (output of doc_parser.parse_documents)
        output_dir:  Path where expected.csv, cucumber/, selenium/ will be written
        chain:       LangChain chain: UNIFIED_PROMPT | llm.with_structured_output(...)
        checkpoint:  CheckpointManager instance for this FRD
        concurrency: Max TCs to process simultaneously (default: 50)
        progress_cb: Async callback(frd_id, done_count, total) → None for SSE updates
    """

    def __init__(
        self,
        frd_id:      str,
        frd_name:    str,
        test_cases:  List[Dict[str, Any]],
        output_dir:  Path,
        chain:       Any,
        checkpoint:  CheckpointManager,
        concurrency: int = 50,
        progress_cb: Optional[Callable[[str, int, int], Awaitable[None]]] = None,
        base_url:    str = "http://localhost",
    ):
        self.frd_id      = frd_id
        self.frd_name    = frd_name
        self.test_cases  = test_cases
        self.output_dir  = Path(output_dir)
        self.chain       = chain
        self.checkpoint  = checkpoint
        self.concurrency = concurrency
        self.progress_cb = progress_cb
        self.base_url    = base_url

    async def run(self) -> FRDWorkerResult:
        """
        Run the full FRD processing pipeline:
          1. Set up output directories and CSV header
          2. Filter out already-done TCs (crash recovery)
          3. abatch() all remaining TCs in parallel (max_concurrency=self.concurrency)
          4. Write CSV rows, .feature, and Selenium scripts for each successful TC
          5. Mark each TC done in checkpoint + fire SSE progress callback

        Returns:
            FRDWorkerResult with counts of completed and failed TCs.
        """
        # ── Output directories ────────────────────────────────────────────────
        csv_path = self.output_dir / "expected.csv"
        cuc_dir  = self.output_dir / "cucumber"
        sel_dir  = self.output_dir / "selenium"
        cuc_dir.mkdir(parents=True, exist_ok=True)
        sel_dir.mkdir(parents=True, exist_ok=True)

        # Write CSV header only if file doesn't already exist (crash-resume safe)
        if not csv_path.exists():
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    "testcase", "description", "category", "preconditions",
                    "stepname", "expected result", "testdata", "evidence required",
                ])

        # ── Crash recovery: skip already-done TCs ─────────────────────────────
        remaining  = self.checkpoint.get_remaining(self.test_cases)
        total      = len(self.test_cases)
        done_count = self.checkpoint.done_count   # from previous run, if any
        failed: List[str] = []

        logger.info(
            "[FRD] %s (%s): %d total TCs, %d remaining, %d already done.",
            self.frd_id, self.frd_name, total, len(remaining), done_count
        )

        if not remaining:
            logger.info("[FRD] %s: All TCs already complete. Skipping.", self.frd_id)
            return FRDWorkerResult(self.frd_id, self.frd_name, total, total)

        # ── Build input dicts for abatch ──────────────────────────────────────
        inputs = [
            {
                "tc_json":  json.dumps(tc, separators=(',', ':')),  # compact: no whitespace = fewer tokens
                "base_url": self.base_url,
            }
            for tc in remaining
        ]

        logger.info(
            "[FRD] %s: Launching abatch (%d TCs, max_concurrency=%d)...",
            self.frd_id, len(remaining), self.concurrency
        )

        # ── THE CORE: abatch processes N TCs in parallel ──────────────────────
        results = await self.chain.abatch(
            inputs,
            config={"max_concurrency": self.concurrency},
            return_exceptions=True,   # failed TCs don't abort the whole batch
        )
        # ─────────────────────────────────────────────────────────────────────

        # ── Write outputs ─────────────────────────────────────────────────────
        for tc, result in zip(remaining, results):
            tc_id = tc.get("tc_id", "UNKNOWN")

            if isinstance(result, Exception):
                logger.error("[FAIL] %s: %s", tc_id, result)
                failed.append(tc_id)
                continue

            # Write CSV rows (append mode — file may have rows from previous run)
            try:
                with open(csv_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    for row in result.csv_rows:
                        writer.writerow([
                            row.testcase, row.description, row.category,
                            row.preconditions, row.stepname,
                            row.expected_result, row.testdata, row.evidence_required,
                        ])
            except Exception as exc:
                logger.warning("%s: CSV write error — %s", tc_id, exc)

            # Write Gherkin feature file
            try:
                (cuc_dir / f"{tc_id}.feature").write_text(
                    _strip_fences(result.cucumber_feature), encoding="utf-8"
                )
            except Exception as exc:
                logger.warning("%s: Feature write error — %s", tc_id, exc)

            # Write Selenium script
            try:
                (sel_dir / f"test_{tc_id}.py").write_text(
                    _strip_fences(result.selenium_script), encoding="utf-8"
                )
            except Exception as exc:
                logger.warning("%s: Selenium write error — %s", tc_id, exc)

            # Mark TC as done in checkpoint (persisted to disk)
            await self.checkpoint.mark_done(tc_id)
            done_count += 1

            # Push progress update to SSE stream
            if self.progress_cb:
                try:
                    await self.progress_cb(self.frd_id, done_count, total)
                except Exception:
                    pass   # never crash the worker on a callback failure

        logger.info(
            "[FRD] %s: Done — %d/%d completed, %d failed.",
            self.frd_id, done_count, total, len(failed)
        )

        return FRDWorkerResult(
            frd_id=self.frd_id,
            frd_name=self.frd_name,
            total=total,
            completed=done_count,
            failed=failed,
        )
