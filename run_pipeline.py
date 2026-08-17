"""
run_pipeline.py
---------------
Command-line entry-point that runs the full Baxter pipeline end to end, without
the FastAPI server.

Stages
------
  1. Parse every module in input_modules/  -> output/knowledge/*.json
  2. Generate artifacts per module         -> output/tests/<module>/
  3. Aggregate token usage and cost        -> output/cost_totals.txt

Usage
-----
  python run_pipeline.py
"""

import sys

from dotenv import load_dotenv

# Entry-point responsibility: load .env before any module reads configuration.
load_dotenv()

from agents.cs_agent import run_agent
from agents.doc_parser import parse_documents
from core import constants as const
from core.cost_report import write_totals_report
from core.logger import logger


def _set_phase(phase: str) -> None:
    """Tags the pipeline phase so logged LLM costs are attributed correctly."""
    import litellm

    litellm.current_phase = phase


def main() -> int:
    """
    Runs all three pipeline stages.

    Returns:
        Process exit code: 0 on success, 1 if Stage 1 produced nothing, and 2 if
        every module failed during Stage 2.
    """
    modules_dir = const.DIR_MODULES_INPUT
    out_dir = const.DIR_OUTPUT

    if not modules_dir.is_dir() or not any(modules_dir.rglob(f"*{const.SUPPORTED_DOC_EXT}")):
        logger.error(
            "No %s documents found in %s. Add module folders containing an FRD and a "
            "test case document, then re-run.",
            const.SUPPORTED_DOC_EXT, modules_dir,
        )
        return 1

    # ── Stage 1: parse all modules ────────────────────────────────────────────
    logger.info("=" * const.SEPARATOR_WIDTH)
    logger.info("  Stage 1: Parsing Documents")
    logger.info("=" * const.SEPARATOR_WIDTH)
    _set_phase("Parser")

    try:
        json_paths = parse_documents(str(modules_dir), str(out_dir))
    except Exception as exc:
        logger.error("Stage 1 failed: %s", exc, exc_info=True)
        return 1

    if not json_paths:
        logger.error("Stage 1 produced no output. Aborting.")
        return 1

    logger.info("Parsed %d module JSON file(s).", len(json_paths))

    # ── Stage 2: generate artifacts per module ────────────────────────────────
    logger.info("=" * const.SEPARATOR_WIDTH)
    logger.info("  Stage 2: Generating Artifacts")
    logger.info("=" * const.SEPARATOR_WIDTH)
    _set_phase("Generator")

    succeeded, failed = 0, []
    for json_path in json_paths:
        module_slug = (
            json_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            .replace("_knowledge.json", "").replace(".json", "")
        )
        module_out_dir = const.DIR_TESTS / module_slug

        logger.info("Module: %s -> %s", module_slug, module_out_dir)
        try:
            result = run_agent(stage1_json_path=json_path, out_dir_path=str(module_out_dir))
            if result.succeeded:
                succeeded += 1
            else:
                logger.error("Module %s generated no artifacts.", module_slug)
                failed.append(module_slug)
        except Exception as exc:
            # Keep going so one bad module cannot cost the whole run.
            logger.error("Module %s failed: %s", module_slug, exc, exc_info=True)
            failed.append(module_slug)

    if failed:
        logger.warning("Stage 2 completed with %d failed module(s): %s", len(failed), ", ".join(failed))

    # ── Stage 3: cost totals ──────────────────────────────────────────────────
    logger.info("=" * const.SEPARATOR_WIDTH)
    logger.info("  Stage 3: Calculating Cost Totals")
    logger.info("=" * const.SEPARATOR_WIDTH)
    write_totals_report()

    if not succeeded:
        logger.error("Pipeline finished but no module generated artifacts.")
        return 2

    logger.info("Pipeline complete — %d module(s) generated, %d failed.", succeeded, len(failed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
