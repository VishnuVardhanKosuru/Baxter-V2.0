"""
agents/cs_agent.py
──────────────────
Stage 2 of the Baxter pipeline: the Cucumber & Selenium test generator agent.

Processes each test case from the Stage 1 parsed JSON. For each test case a
SINGLE LangChain chain generates all 3 artifacts in one LLM call:
  - CSV step rows   -> appended to expected.csv
  - Gherkin code    -> saved as cucumber/<TC-ID>.feature
  - Selenium Python -> saved as selenium/test_<TC-ID>.py

All three come from the same LLM context window, so the Selenium steps align
with the Gherkin steps without any manual context passing.

This module runs test cases sequentially. For parallel execution over a large
FRD, use agents.frd_worker.FRDWorker, which shares the same chain via build_chain().
"""

import csv
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate

from core import constants as const
from core.logger import logger
from core.models import FullTestCaseOutput


# ==============================================================================
# HELPER — strip markdown code fences from LLM text fields
# ==============================================================================

_FENCE_START = re.compile(r"^```[a-zA-Z]*\r?\n", flags=re.MULTILINE)
_FENCE_END = re.compile(r"\r?\n```\s*$", flags=re.MULTILINE)


def _strip_fences(text: str) -> str:
    """
    Remove ```python / ```gherkin / ``` wrappers that LLMs sometimes add.

    Returns an empty string for None/empty input so callers can always write the
    result to a file without a null check.
    """
    if not text:
        return ""
    text = _FENCE_START.sub("", text)
    text = _FENCE_END.sub("", text)
    return text.strip()


# ==============================================================================
# UNIFIED PROMPT + CHAIN
#    One ChatPromptTemplate -> one LLM call -> FullTestCaseOutput (all 3 artifacts)
# ==============================================================================

# Standalone constant so Gemini cache creation and Anthropic cache_control
# injection both reference the exact same text.
SYSTEM_PROMPT_TEXT = (
    "You are a senior QA Automation Engineer expert in BDD, Cucumber, and Selenium WebDriver.\n\n"
    "Given a test case JSON, generate ALL THREE of the following in a single response:\n\n"

    "-- ARTIFACT 1: csv_rows --\n"
    "Expand the test case into step-by-step CSV rows (one row per step).\n"
    "Rules:\n"
    "- First row carries full pre-conditions; subsequent rows use 'Previous step passed'.\n"
    "- testdata: realistic, specific values (e.g. 'email: user@test.com | password: Secure@123').\n"
    "  For payment steps use Stripe test cards (e.g. '4242 4242 4242 4242, exp 12/26, CVC 123').\n"
    "- evidence_required: specific proof (e.g. 'Screenshot of success toast', '200 OK on /api/auth/login').\n"
    "- expected_result per step: granular intermediate outcome, not just the final result.\n\n"

    "-- ARTIFACT 2: cucumber_feature --\n"
    "Write a complete, production-quality Gherkin .feature file.\n"
    "Rules:\n"
    "- Include all cucumber_tags at the top (before Feature:).\n"
    "- Feature name = feature_context.feature_name.\n"
    "- Add a Background: section if there are pre_conditions.\n"
    "- Write a Scenario (or Scenario Outline + Examples table for data-driven tests).\n"
    "- Strict Given / When / Then / And format:\n"
    "    Given = state setup / navigation\n"
    "    When  = user action\n"
    "    Then  = assertion / expected outcome\n"
    "- Use Gherkin data tables for form inputs where appropriate.\n"
    "- For negative scenarios, include the exact error message text.\n"
    "- Raw .feature content only -- NO markdown fences.\n\n"

    "-- ARTIFACT 3: selenium_script --\n"
    "Write a complete Python Selenium WebDriver test script that implements\n"
    "EVERY Gherkin step from the cucumber_feature you just wrote.\n"
    "Rules:\n"
    "- Use pytest as the test runner.\n"
    "- Class name: Test<TCID> (e.g. TestTC001).\n"
    "- setup_method: ChromeOptions, driver init, navigate to BASE_URL (from context or {base_url}).\n"
    "- teardown_method: driver.quit() in try/finally.\n"
    "- Test method: test_<tc_id_lowercase> (e.g. test_tc_001).\n"
    "- Comment each block with its matching Gherkin line.\n"
    "- Use WebDriverWait + expected_conditions -- NO time.sleep().\n"
    "- Infer realistic CSS selectors from the test case context and subject area.\n"
    "- Add meaningful pytest assert statements matching expected_result.\n"
    "- Base URL for navigation: {base_url}\n"
    "- Raw Python code only -- NO markdown fences."
)

# Standard ChatPromptTemplate used by the Gemini and OpenAI chains.
UNIFIED_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT_TEXT),
    (
        "human",
        "Test Case JSON:\n{tc_json}\n\n"
        "Generate all three artifacts (csv_rows, cucumber_feature, selenium_script) now.",
    ),
])

_HUMAN_INSTRUCTION = (
    "Generate all three artifacts (csv_rows, cucumber_feature, selenium_script) now."
)


def build_chain(bundle: Any) -> Any:
    """
    Builds the LangChain chain for the given LLMBundle.

    - Gemini / OpenAI: UNIFIED_PROMPT | llm.with_structured_output()
      (Gemini cache injected via setup_cache() before the batch; OpenAI auto-caches)

    - Anthropic: a manual chain that sets cache_control: ephemeral on the system
      message content block. LiteLLM forwards the flag to Anthropic, which caches
      the system prompt server-side for ~5 min, auto-renewing on each hit
      (~90% saving on cached tokens).
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain_core.runnables import RunnableLambda

    llm = bundle.llm

    if bundle.provider == "anthropic":
        structured_llm = llm.with_structured_output(FullTestCaseOutput)

        def _anthropic_chain_fn(inputs: dict) -> FullTestCaseOutput:
            messages = [
                SystemMessage(content=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT_TEXT.replace("{base_url}", inputs.get("base_url", "")),
                        "cache_control": {"type": "ephemeral"},
                    }
                ]),
                HumanMessage(
                    content=f"Test Case JSON:\n{inputs['tc_json']}\n\n{_HUMAN_INSTRUCTION}"
                ),
            ]
            return structured_llm.invoke(messages)

        return RunnableLambda(_anthropic_chain_fn)

    return UNIFIED_PROMPT | llm.with_structured_output(FullTestCaseOutput)


def generate_all_artifacts(
    bundle: Any,
    tc: Dict[str, Any],
    max_retries: int = const.MAX_LLM_RETRIES,
    base_url: str = "",
) -> FullTestCaseOutput:
    """
    Generates all 3 artifacts for one test case in a single LLM call.

    Retries on 429 RESOURCE_EXHAUSTED (rate limit) and transient network errors
    with a progressive backoff; any other error is raised immediately since
    retrying a malformed request cannot help.

    Args:
        bundle:      LLMBundle from create_llm().
        tc:          Test case dict from the Stage 1 knowledge JSON.
        max_retries: Attempts before giving up.
        base_url:    Base URL injected into the generated Selenium script.

    Returns:
        FullTestCaseOutput with csv_rows, cucumber_feature, and selenium_script.

    Raises:
        RuntimeError: if every retry is exhausted.
    """
    chain = build_chain(bundle)
    payload = {
        # Compact separators: no whitespace = fewer input tokens.
        "tc_json": json.dumps(tc, separators=(",", ":")),
        "base_url": base_url or const.DEFAULT_BASE_URL,
    }

    for attempt in range(1, max_retries + 1):
        try:
            return chain.invoke(payload)
        except Exception as exc:
            err = str(exc).lower()
            is_rate_limit = "429" in err or "resource_exhausted" in err
            is_network_err = any(t in err for t in ("timeout", "connection", "httpcore", "httpx", "ssl"))

            if attempt >= max_retries or not (is_rate_limit or is_network_err):
                raise

            wait = (
                const.RATE_LIMIT_BASE_WAIT_S if is_rate_limit else const.NETWORK_BASE_WAIT_S
            ) * attempt
            logger.warning(
                "%s error for %s. Retrying in %ds (attempt %d/%d)...",
                "Rate limit" if is_rate_limit else "Network/Timeout",
                tc.get("tc_id", "unknown"), wait, attempt, max_retries,
            )
            time.sleep(wait)

    raise RuntimeError(f"Failed after {max_retries} retries for TC: {tc.get('tc_id')}")


# ==============================================================================
# MAIN PIPELINE — one test case at a time, one LLM call per test case
# ==============================================================================

@dataclass
class GenerationResult:
    """
    Outcome of a run_agent() call.

    Returned so callers can distinguish "generated everything", "generated some",
    and "generated nothing" — a per-test-case LLM failure is logged and skipped
    inside the loop, so without this the caller would see a silent success.
    """
    total:     int
    generated: int
    failed:    List[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        """True when at least one artifact was produced (or there was no work)."""
        return self.generated > 0 or self.total == 0


def _write_csv_rows(csv_path: Path, rows) -> None:
    """Appends generated step rows to expected.csv in a single file open."""
    with open(csv_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        for row in rows:
            writer.writerow([
                row.testcase, row.description, row.category,
                row.preconditions, row.stepname, row.expected_result,
                row.testdata, row.evidence_required,
            ])


def run_agent(
    stage1_json_path: str = const.DEFAULT_INPUT_PATH,
    out_dir_path: str = const.DEFAULT_OUTPUT_PATH,
    base_url: str = "",
) -> GenerationResult:
    """
    Public API — called by server.py and run_pipeline.py (no CLI/subprocess).

    Reads the Stage 1 knowledge JSON and generates artifacts into out_dir_path.
    A failure on one test case is logged and skipped; it never aborts the run.

    Writes:
      <out_dir_path>/expected.csv              — all CSV step rows
      <out_dir_path>/cucumber/<TC-ID>.feature  — Gherkin feature file
      <out_dir_path>/selenium/test_<TC-ID>.py  — Selenium Python test script

    Returns:
        GenerationResult with per-test-case counts, so the caller can report a
        partial or total generation failure instead of an unqualified success.

    Raises:
        FileNotFoundError: if the Stage 1 JSON does not exist.
        ValueError:        if the Stage 1 JSON is malformed.
        RuntimeError:      if the LLM cannot be initialised.
    """
    app_base_url = base_url or const.DEFAULT_BASE_URL
    project_root = const.WORKSPACE_ROOT

    json_path = Path(stage1_json_path)
    if not json_path.is_absolute():
        json_path = project_root / json_path

    out_dir = Path(out_dir_path)
    if not out_dir.is_absolute():
        out_dir = project_root / out_dir

    if not json_path.is_file():
        raise FileNotFoundError(
            f"Stage 1 input JSON not found: {json_path}. Run Stage 1 (parsing) first."
        )

    csv_path = out_dir / const.NAME_EXPECTED_CSV
    cuc_dir = out_dir / "cucumber"
    sel_dir = out_dir / "selenium"
    for d in (out_dir, cuc_dir, sel_dir):
        d.mkdir(parents=True, exist_ok=True)

    logger.info("=" * const.SEPARATOR_WIDTH)
    logger.info("  Cucumber & Selenium Generator Agent")
    logger.info("  Input JSON : %s", json_path)
    logger.info("  Output Dir : %s", out_dir)
    logger.info("  Base URL   : %s", app_base_url)
    logger.info("=" * const.SEPARATOR_WIDTH)

    logger.info("[1/3] Loading %s", json_path.name)
    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Stage 1 JSON is not valid JSON ({json_path}): {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Cannot read Stage 1 JSON ({json_path}): {exc}") from exc

    test_cases = data.get("test_cases", [])
    if not isinstance(test_cases, list):
        raise ValueError(f"'test_cases' in {json_path.name} must be a list.")

    total = len(test_cases)
    logger.info("      Loaded %d test case(s) from project '%s'.", total, data.get("project", "unknown"))

    if not total:
        logger.warning("No test cases to process — nothing to generate.")
        return GenerationResult(total=0, generated=0)

    logger.info("[2/3] Initialising LLM router...")
    try:
        from core.llm_factory import create_llm
        bundle = create_llm()
    except Exception as exc:
        raise RuntimeError(f"LLM init failed: {exc}. A valid API key is required.") from exc
    logger.info("      Connected — provider=%s, model=%s", bundle.provider, bundle.model)

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(const.CSV_HEADERS)

    logger.info("[3/3] Processing %d test case(s)...", total)

    generated = 0
    failed = []

    for i, tc in enumerate(test_cases, start=1):
        tc_id = tc.get("tc_id", f"TC-{i:03d}")
        logger.info("  [%02d/%d] %s — %s", i, total, tc_id, tc.get("title", "Unnamed"))

        try:
            output = generate_all_artifacts(bundle, tc, base_url=app_base_url)
        except Exception as exc:
            logger.error("  [SKIP] %s — LLM error: %s", tc_id, exc)
            failed.append(tc_id)
            continue

        try:
            _write_csv_rows(csv_path, output.csv_rows)
            (cuc_dir / f"{tc_id}.feature").write_text(
                _strip_fences(output.cucumber_feature), encoding="utf-8"
            )
            (sel_dir / f"test_{tc_id}.py").write_text(
                _strip_fences(output.selenium_script), encoding="utf-8"
            )
            generated += 1
        except OSError as exc:
            logger.error("  [SKIP] %s — write error: %s", tc_id, exc)
            failed.append(tc_id)

    logger.info("=" * const.SEPARATOR_WIDTH)
    logger.info("  [DONE] %d/%d test case(s) generated, %d failed.", generated, total, len(failed))
    if failed:
        logger.warning("  Failed test cases: %s", ", ".join(failed))
    logger.info("      CSV written       : %s", csv_path)
    logger.info("      Cucumber features : %s", cuc_dir)
    logger.info("      Selenium scripts  : %s", sel_dir)
    logger.info("=" * const.SEPARATOR_WIDTH)

    return GenerationResult(total=total, generated=generated, failed=failed)
