"""
core/cost_report.py
───────────────────
Single parser for the LLM cost log written by
``core.llm_factory._track_cost_callback`` (output/cost_tracking.txt).

Previously server.py and calculate_totals.py each carried their own copy of this
regex and aggregation logic, which meant a change to the log format had to be
made in two places. Both now call into this module.

Public API:
    parse_cost_log()        -> aggregated metrics dict (consumed by the API)
    totals_by_key_phase()   -> {key_alias: {phase: metrics}} (consumed by the CLI)
    render_totals_report()  -> human-readable text report
"""

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Optional

from core import constants as const
from core.logger import logger

# Number of most recent log entries returned to API clients.
RECENT_ENTRIES_LIMIT = 100


def _empty_metrics() -> Dict[str, Any]:
    """The zero-value metrics payload used when no cost log exists yet."""
    return {
        "total_cost": 0.0,
        "total_cost_formatted": "$0.000000",
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tokens": 0,
        "total_calls": 0,
        "phases": [],
        "entries": [],
    }


def _iter_log_entries(log_file: Path):
    """
    Yields one parsed dict per recognisable line in the cost log.

    Unparsable lines are skipped silently — the log is append-only from a
    callback and a partially written final line is normal, not an error.
    """
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                match = const.REGEX_COST_LINE.search(line)
                if not match:
                    continue
                yield {
                    "timestamp": match.group(1),
                    # Older log lines predate the phase tag; default to Generator.
                    "phase": match.group(2) or "Generator",
                    "model": match.group(3),
                    "key_alias": match.group(4),
                    "input_tokens": int(match.group(5)),
                    "output_tokens": int(match.group(6)),
                    "cost": float(match.group(7)),
                }
    except OSError as exc:
        logger.error("Cannot read cost log %s: %s", log_file, exc)


def parse_cost_log(log_file: Optional[Path] = None) -> Dict[str, Any]:
    """
    Parses the cost log into aggregated metrics grouped by phase and API key.

    Args:
        log_file: Cost log path. Defaults to constants.FILE_COST_LOG.

    Returns:
        Metrics dict with grand totals, a per-phase breakdown (each including a
        per-key sub-breakdown), and the most recent RECENT_ENTRIES_LIMIT entries.
        Zero-valued if the log does not exist.
    """
    log_file = log_file or const.FILE_COST_LOG

    if not log_file.exists():
        return _empty_metrics()

    phases_map = defaultdict(lambda: {
        "in": 0, "out": 0, "cost": 0.0, "calls": 0,
        "models": set(), "keys": set(),
        "key_breakdown": defaultdict(lambda: {"in": 0, "out": 0, "cost": 0.0, "calls": 0}),
    })

    entries = []
    total_cost = 0.0
    total_in = 0
    total_out = 0

    for entry in _iter_log_entries(log_file):
        phase = phases_map[entry["phase"]]
        phase["in"] += entry["input_tokens"]
        phase["out"] += entry["output_tokens"]
        phase["cost"] += entry["cost"]
        phase["calls"] += 1
        phase["models"].add(entry["model"])
        phase["keys"].add(entry["key_alias"])

        key_bucket = phase["key_breakdown"][entry["key_alias"]]
        key_bucket["in"] += entry["input_tokens"]
        key_bucket["out"] += entry["output_tokens"]
        key_bucket["cost"] += entry["cost"]
        key_bucket["calls"] += 1

        total_cost += entry["cost"]
        total_in += entry["input_tokens"]
        total_out += entry["output_tokens"]
        entries.append(entry)

    phases_list = [
        {
            "phase": phase_name,
            "input_tokens": data["in"],
            "output_tokens": data["out"],
            "total_tokens": data["in"] + data["out"],
            "cost": data["cost"],
            "calls": data["calls"],
            "models": sorted(data["models"]),
            "keys": sorted(data["keys"]),
            "cost_formatted": f"${data['cost']:.6f}",
            "key_breakdown": [
                {
                    "key_alias": alias,
                    "input_tokens": kb["in"],
                    "output_tokens": kb["out"],
                    "total_tokens": kb["in"] + kb["out"],
                    "cost": kb["cost"],
                    "calls": kb["calls"],
                    "cost_formatted": f"${kb['cost']:.6f}",
                }
                for alias, kb in sorted(data["key_breakdown"].items())
            ],
        }
        for phase_name, data in phases_map.items()
    ]

    return {
        "total_cost": total_cost,
        "total_cost_formatted": f"${total_cost:.6f}",
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "total_calls": len(entries),
        "phases": phases_list,
        "entries": entries[-RECENT_ENTRIES_LIMIT:],
    }


def totals_by_key_phase(log_file: Optional[Path] = None) -> Dict[str, Dict[str, dict]]:
    """
    Aggregates the cost log as {key_alias: {phase: {"in", "out", "cost"}}}.

    This is the key-first view used by the standalone totals report, as opposed
    to the phase-first view returned by parse_cost_log().
    """
    log_file = log_file or const.FILE_COST_LOG
    totals: Dict[str, Dict[str, dict]] = defaultdict(
        lambda: defaultdict(lambda: {"in": 0, "out": 0, "cost": 0.0})
    )

    if not log_file.exists():
        return totals

    for entry in _iter_log_entries(log_file):
        bucket = totals[entry["key_alias"]][entry["phase"]]
        bucket["in"] += entry["input_tokens"]
        bucket["out"] += entry["output_tokens"]
        bucket["cost"] += entry["cost"]

    return totals


def render_totals_report(totals: Dict[str, Dict[str, dict]]) -> str:
    """Formats the key/phase totals as the human-readable cost_totals.txt body."""
    divider = "=" * 50
    lines = [divider, "           COST & TOKEN TOTALS", divider, ""]

    grand_cost = 0.0
    for key, phases in totals.items():
        lines.append(f"--- {key} ---")
        key_cost = 0.0
        for phase, metrics in phases.items():
            lines.extend([
                f"  [{phase}]",
                f"    Input Tokens : {metrics['in']:,}",
                f"    Output Tokens: {metrics['out']:,}",
                f"    Phase Cost   : ${metrics['cost']:.6f}",
                "",
            ])
            key_cost += metrics["cost"]
        lines.extend([f"  > Total {key} Cost: ${key_cost:.6f}", ""])
        grand_cost += key_cost

    lines.extend([divider, f"GRAND TOTAL COST: ${grand_cost:.6f}", divider, ""])
    return "\n".join(lines)


def write_totals_report(
    log_file: Optional[Path] = None, out_file: Optional[Path] = None
) -> Optional[Path]:
    """
    Writes the aggregated cost totals report to disk.

    Returns:
        The output path, or None if there was nothing to aggregate.
    """
    log_file = log_file or const.FILE_COST_LOG
    out_file = out_file or const.FILE_COST_TOTALS

    if not log_file.exists():
        logger.warning("Cost log not found: %s", log_file)
        return None

    totals = totals_by_key_phase(log_file)
    if not totals:
        logger.warning("No parsable cost data found in %s", log_file)
        return None

    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(render_totals_report(totals), encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to write cost totals report %s: %s", out_file, exc)
        return None

    logger.info("Cost totals written to %s", out_file)
    return out_file
