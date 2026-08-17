from dotenv import load_dotenv
load_dotenv()

import os
import sys
import litellm
from pathlib import Path

from core.logger import logger

# Ensure agents is in path
BASE_DIR = Path(__file__).parent.resolve()
AGENTS_DIR = BASE_DIR / "agents"
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from doc_parser import parse_documents
from core.cs_agent import run_agent


def main():
    modules_dir = str(BASE_DIR / "input_modules")
    out_dir = "output"
    tests_dir = os.path.join(out_dir, "tests")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(tests_dir, exist_ok=True)

    # ── Stage 1: Parse all modules ────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  Stage 1: Parsing Documents")
    logger.info("=" * 60)
    litellm.current_phase = "Parser"

    # parse_documents returns a list of knowledge JSON paths (one per module)
    json_paths = parse_documents(modules_dir, out_dir)

    if not json_paths:
        logger.error("Stage 1 produced no output. Aborting.")
        return

    logger.info("Parsed %d module JSON file(s).", len(json_paths))

    # ── Stage 2: Generate artifacts per module ────────────────────────────────
    logger.info("=" * 60)
    logger.info("  Stage 2: Generating Artifacts")
    logger.info("=" * 60)
    litellm.current_phase = "Generator"

    for json_path in json_paths:
        if not json_path:
            continue

        # Derive per-module output dir: output/tests/<module_slug>/
        basename = os.path.basename(json_path)
        module_slug = basename.replace("_knowledge.json", "").replace(".json", "")
        module_out_dir = os.path.join(tests_dir, module_slug)

        logger.info("Processing Module : %s", module_slug)
        logger.info("Output directory  : %s", module_out_dir)

        run_agent(stage1_json_path=json_path, out_dir_path=module_out_dir)

    logger.info("Pipeline Complete!")

    # ── Stage 3: Cost totals ──────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  Stage 3: Calculating Cost Totals")
    logger.info("=" * 60)
    try:
        import calculate_totals
        calculate_totals.main()
    except Exception as e:
        logger.error("Failed to calculate totals: %s", e)


if __name__ == "__main__":
    main()
