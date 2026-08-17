"""
core/checkpoint.py
──────────────────
Crash-recovery checkpoint manager.

Saves the set of completed TC-IDs to a JSON file after each TC is processed.
On restart/resume, already-done TCs are skipped — only remaining TCs run.

Usage:
    checkpoint = CheckpointManager(frd_dir)
    remaining  = checkpoint.get_remaining(all_test_cases)

    # After processing each TC:
    await checkpoint.mark_done(tc_id)
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from core import constants as const
from core.logger import logger


class CheckpointManager:
    """
    Tracks completed TC-IDs for a single FRD output directory.

    Thread-safety: uses asyncio.Lock — safe for concurrent async writers.
    File format: checkpoint.json → ["TC-001", "TC-002", ...]
    """

    def __init__(self, frd_dir: Path):
        """
        Args:
            frd_dir: Path to the FRD output directory (e.g. output/jobs/<id>/FRD-001_Name/).
                     checkpoint.json is created inside this directory.
        """
        self._path = Path(frd_dir) / const.NAME_CHECKPOINT
        self._lock = asyncio.Lock()
        self._done: set = set()

        # Load existing checkpoint (crash-resume scenario)
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    self._done = set(loaded)
                    logger.info(
                        "[CHECKPOINT] Loaded %d already-completed TCs from %s",
                        len(self._done), self._path.name,
                    )
                else:
                    logger.warning(
                        "[CHECKPOINT] %s is not a JSON list — starting fresh.", self._path.name
                    )
            except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
                logger.warning(
                    "[CHECKPOINT] Could not read %s (%s) — starting fresh.", self._path.name, exc
                )

    def is_done(self, tc_id: str) -> bool:
        """Returns True if this TC-ID has already been processed."""
        return tc_id in self._done

    async def mark_done(self, tc_id: str) -> None:
        """
        Marks a TC-ID as done and persists the checkpoint to disk.

        Writes to a temporary file and then replaces the real one, so a crash
        mid-write leaves the previous valid checkpoint intact rather than a
        truncated file. asyncio.Lock serialises concurrent writers.

        A write failure is logged but not raised: losing a checkpoint entry only
        costs re-work on resume, whereas failing here would discard a test case
        whose artifacts are already on disk.
        """
        async with self._lock:
            self._done.add(tc_id)
            tmp_path = self._path.with_suffix(".json.tmp")
            try:
                tmp_path.write_text(json.dumps(sorted(self._done), indent=2), encoding="utf-8")
                os.replace(tmp_path, self._path)
            except OSError as exc:
                logger.warning("[CHECKPOINT] Could not persist %s: %s", self._path.name, exc)

    def get_remaining(self, all_tcs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filters out TCs that are already done.

        First run  → returns all TCs (checkpoint is empty).
        After crash → returns only the unprocessed TCs.

        Args:
            all_tcs: Full list of test case dicts (must have a 'tc_id' key).

        Returns:
            List of test case dicts not yet marked done.
        """
        return [tc for tc in all_tcs if not self.is_done(tc.get("tc_id", ""))]

    @property
    def done_count(self) -> int:
        """Number of TCs already marked done (useful for progress initialisation)."""
        return len(self._done)
