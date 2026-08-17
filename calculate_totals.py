"""
calculate_totals.py
-------------------
Post-run cost aggregation entry-point for the Baxter platform.

Reads the per-call cost log written by ``core.llm_factory._track_cost_callback``
(output/cost_tracking.txt) and writes a human-readable summary of total tokens
and cost, grouped by API key alias and pipeline phase (Parser / Generator).

The parsing and formatting live in ``core.cost_report`` so this script and the
/api/cost/* endpoints share one implementation.

Output: output/cost_totals.txt

Usage
-----
  python calculate_totals.py     # standalone
  # also invoked automatically as Stage 3 of run_pipeline.py
"""

from dotenv import load_dotenv

load_dotenv()

from core.cost_report import write_totals_report
from core.logger import logger


def main() -> None:
    """Aggregates the cost log and writes output/cost_totals.txt."""
    out_file = write_totals_report()
    if out_file is None:
        logger.info("No cost totals generated — the cost log is missing or empty.")


if __name__ == "__main__":
    main()
