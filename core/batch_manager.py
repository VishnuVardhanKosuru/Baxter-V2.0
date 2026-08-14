"""
core/batch_manager.py
─────────────────────
Sequential FRD orchestrator + job state manager.

Responsibilities:
  - Creates and tracks batch jobs (in-memory, per server lifetime)
  - Runs FRDs one at a time (sequential) — FRD-2 starts only after FRD-1 is done
  - Each FRD runs FRDWorker.run() which internally uses abatch() for parallelism
  - Maintains real-time job state (FRDProgress) consumed by SSE stream endpoint
  - Uses a single shared LLM instance (LiteLLM manages all key quotas centrally)

Architecture:
    batch_manager = BatchJobManager()      ← singleton in server.py

    job_id = batch_manager.create_job()
    asyncio.create_task(
        batch_manager.run_batch(job_id, frd_inputs)
    )

SSE consumers call batch_manager.get_job(job_id) to read live state.
"""

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from core.constants import DIR_JOBS
from typing import Dict, List, Optional, Any




# ── Job/FRD status enum ───────────────────────────────────────────────────────

class JobStatus(str, Enum):
    QUEUED  = "queued"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"


# ── Data models for SSE consumption ──────────────────────────────────────────

@dataclass
class FRDProgress:
    """Live progress state for one FRD — read by SSE stream."""
    frd_id:    str
    frd_name:  str
    status:    JobStatus = JobStatus.QUEUED
    total:     int = 0
    completed: int = 0
    failed:    List[str] = field(default_factory=list)

    @property
    def percent(self) -> float:
        """Completion percentage, rounded to 1 decimal place."""
        return round(self.completed / self.total * 100, 1) if self.total else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frd_id":    self.frd_id,
            "frd_name":  self.frd_name,
            "status":    self.status.value,
            "total":     self.total,
            "completed": self.completed,
            "percent":   self.percent,
            "failed":    self.failed,
        }


@dataclass
class BatchJob:
    """Top-level job state for a multi-FRD batch run."""
    job_id:      str
    status:      JobStatus = JobStatus.QUEUED
    frds:        Dict[str, FRDProgress] = field(default_factory=dict)
    output_root: Optional[Path] = None
    error:       str = ""


# ── Batch Manager ─────────────────────────────────────────────────────────────

class BatchJobManager:
    """
    Singleton orchestrator for multi-FRD batch jobs.

    Lifecycle:
      1. create_job()          → returns job_id, creates output directory
      2. run_batch(job_id, …)  → background task, updates job state as it runs
      3. get_job(job_id)       → read-only access for SSE and download endpoints
    """

    def __init__(self):
        self._jobs: Dict[str, BatchJob] = {}

    def create_job(self) -> str:
        """
        Allocates a new job ID, creates its output directory, and registers it.
        Returns the job_id string.
        """
        job_id  = str(uuid.uuid4())[:8]
        job_dir = DIR_JOBS / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        self._jobs[job_id] = BatchJob(job_id=job_id, output_root=job_dir)
        print(f"[BATCH] Job created: {job_id} → {job_dir}")
        return job_id

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Returns the BatchJob for the given ID, or None if not found."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[Dict[str, Any]]:
        """Returns a summary list of all known jobs (for debugging/admin)."""
        return [
            {
                "job_id": j.job_id,
                "status": j.status.value,
                "frd_count": len(j.frds),
            }
            for j in self._jobs.values()
        ]

    async def run_batch(self, job_id: str, frd_inputs: List[Dict[str, Any]]) -> None:
        """
        Main batch execution coroutine — run as a background asyncio Task.

        frd_inputs format:
            [
              {
                "frd_id":    "FRD-001",
                "frd_name":  "UserAuth",
                "test_cases": [ {...tc_dict...}, ... ],
              },
              ...
            ]

        Execution model:
          - FRDs are processed SEQUENTIALLY (one at a time)
          - Within each FRD, TCs are processed in PARALLEL via chain.abatch()
        """
        # Late imports to avoid circular dependency and allow server to start fast
        from core.llm_factory import create_llm
        from core.checkpoint import CheckpointManager
        from core.frd_worker import FRDWorker
        from core.cs_agent import build_chain, SYSTEM_PROMPT_TEXT

        job        = self._jobs[job_id]
        job.status = JobStatus.RUNNING

        # ── ONE shared LLM bundle — provider-aware, multi-key load balanced ──
        try:
            bundle = create_llm()
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error  = str(exc)
            print(f"[BATCH] {job_id}: LLM init failed — {exc}")
            return

        base_url = os.getenv("BASE_URL", "http://localhost")

        # ── Compute optimal concurrency automatically ──────────────────────────
        # If WORKER_CONCURRENCY is explicitly set, use it.
        # Otherwise compute from RPM × number of active keys so abatch fully
        # utilises available quota without under- or over-shooting.
        if os.getenv("WORKER_CONCURRENCY"):
            concurrency = int(os.getenv("WORKER_CONCURRENCY"))
        else:
            from core.llm_factory import _collect_keys
            provider    = bundle.provider
            rpm_env     = "GEMINI_RPM" if provider == "gemini" else (
                          "OPENAI_RPM" if provider == "openai" else "ANTHROPIC_RPM")
            key_prefix  = "GEMINI_API_KEY" if provider == "gemini" else (
                          "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY")
            rpm         = int(os.getenv(rpm_env, "50"))
            num_keys    = len(_collect_keys(key_prefix))
            concurrency = min(rpm * num_keys, 500)   # cap at 500 to avoid memory pressure
            print(f"[BATCH] Auto-concurrency: {rpm} RPM × {num_keys} keys = {concurrency}")

        # ── SEQUENTIAL: one FRD fully completes before the next starts ───────
        for frd in frd_inputs:
            frd_id   = frd["frd_id"]
            frd_name = frd["frd_name"]
            frd_dir  = job.output_root / f"{frd_id}_{frd_name}"
            frd_dir.mkdir(parents=True, exist_ok=True)

            tc_list = frd.get("test_cases", [])

            # Register FRD progress (visible to SSE stream immediately)
            job.frds[frd_id] = FRDProgress(
                frd_id=frd_id,
                frd_name=frd_name,
                status=JobStatus.RUNNING,
                total=len(tc_list),
            )

            print(f"\n[BATCH] {job_id}: Starting FRD {frd_id} ({frd_name}) — {len(tc_list)} TCs")

            # Async callback called after each TC is done — updates SSE state
            async def _progress_cb(fid: str, done: int, total: int, _id: str = frd_id):
                if _id in job.frds:
                    job.frds[_id].completed = done
                    job.frds[_id].status = (
                        JobStatus.DONE if done >= total else JobStatus.RUNNING
                    )

            # ── Build provider-aware chain for this FRD ───────────────────────────────────────
            # Resolve {base_url} BEFORE caching — base_url is embedded in the system prompt
            # and can differ per FRD, so each FRD gets its own correctly-resolved cache.
            # Gemini: setup_cache() creates explicit CachedContent before batch.
            # OpenAI: no-op (auto-caches >= 1024 token prefixes automatically).
            # Anthropic: no-op (cache_control already embedded in build_chain() messages).
            resolved_system_prompt = SYSTEM_PROMPT_TEXT.replace("{base_url}", base_url)
            bundle.setup_cache(resolved_system_prompt)
            chain = build_chain(bundle)

            checkpoint = CheckpointManager(frd_dir)
            worker = FRDWorker(
                frd_id=frd_id,
                frd_name=frd_name,
                test_cases=tc_list,
                output_dir=frd_dir,
                chain=chain,
                checkpoint=checkpoint,
                concurrency=concurrency,
                progress_cb=_progress_cb,
                base_url=base_url,
            )

            try:
                result = await worker.run()   # blocks until this FRD is fully done
                job.frds[frd_id].status    = JobStatus.DONE
                job.frds[frd_id].completed = result.completed
                job.frds[frd_id].failed    = result.failed
                print(f"[BATCH] {job_id}: FRD {frd_id} complete — "
                      f"{result.completed}/{result.total} TCs, {len(result.failed)} failed.")
            except Exception as exc:
                job.frds[frd_id].status = JobStatus.FAILED
                print(f"[BATCH] {job_id}: FRD {frd_id} FAILED — {exc}")
            finally:
                bundle.teardown_cache()  # delete Gemini cache (no-op for OpenAI/Anthropic)
        # ── END SEQUENTIAL LOOP ───────────────────────────────────────────────

        job.status = JobStatus.DONE
        print(f"\n[BATCH] {job_id}: All FRDs complete. Job done ✅")


# ── Singleton — shared across all FastAPI requests ────────────────────────────
batch_manager = BatchJobManager()
