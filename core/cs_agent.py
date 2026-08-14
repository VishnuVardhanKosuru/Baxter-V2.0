"""
Cucumber & Selenium (C&S) Test Case Generator Agent using LangChain & Gemini.

Processes each test case from the Stage 1 parsed JSON individually — one at a time.
For each test case a SINGLE LangChain chain generates all 3 artifacts in one LLM call:
  - CSV step rows   → appended to expected.csv
  - Gherkin code    → saved as cucumber/<TC-ID>.feature
  - Selenium Python → saved as selenium/test_<TC-ID>.py

All 3 are generated in the same LLM context window so the Selenium steps
naturally align with the Gherkin steps with no manual context passing needed.
"""

import os
import json
import csv
import re
import time
from pathlib import Path
from typing import List, Dict, Any

from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    from langchain_core.prompts import ChatPromptTemplate
except ImportError as _e:
    raise ImportError(
        f"Missing dependency: {_e}.\n"
        "Run: pip install langchain-google-genai python-dotenv"
    ) from _e


# ==============================================================================
# CONFIGURATION CONSTANTS
# All tuneable defaults live here — never repeated elsewhere in the file.
# Override via environment variables.
# ==============================================================================

def _get_env_or_default(default: str, *keys: str) -> str:
    """Returns first non-empty value from the given env var names, or the default."""
    for key in keys:
        val = os.environ.get(key)
        if val:
            return val
    return default

DEFAULT_MODEL:          str = _get_env_or_default("gemini-3.1-flash-lite", "LLM_MODEL", "GEMINI_MODEL")  # LLM_MODEL preferred, GEMINI_MODEL for backward compat
DEFAULT_BASE_URL:       str = os.environ.get("BASE_URL", "http://localhost")
DEFAULT_INPUT_PATH:     str = "output/parsed_output.json"
DEFAULT_OUTPUT_PATH:    str = "output"
MAX_LLM_RETRIES:        int = 5
RATE_LIMIT_BASE_WAIT_S: int = 30
NETWORK_BASE_WAIT_S:    int = 5
LLM_TEMPERATURE:      float = 0.2   # low = consistent, structured output
SEPARATOR_WIDTH:        int = 62     # width of ===... banner lines in console output


# ==============================================================================
# 1. PYDANTIC SCHEMAS — single structured output for all 3 artifacts
# ==============================================================================

class TestCaseRow(BaseModel):
    """One row in expected.csv — represents a single test step."""
    testcase:          str = Field(description="Test case ID and title, e.g. 'TC-001 - User Registration'")
    description:       str = Field(description="Detailed objective of the test case")
    category:          str = Field(description="Test type/category e.g. 'UI Form Validation'")
    preconditions:     str = Field(description="Pre-requisites before executing this step")
    stepname:          str = Field(description="The exact action/step being performed")
    expected_result:   str = Field(description="Expected system response or outcome for this step")
    testdata:          str = Field(description="Specific input data, e.g. 'email: test@example.com | password: Test@123'")
    evidence_required: str = Field(description="Proof needed, e.g. 'Screenshot of success toast', '200 OK in Network tab'")


class FullTestCaseOutput(BaseModel):
    """
    Single structured response from the LLM containing all 3 generated artifacts.
    One model call = all artifacts share context, so Selenium aligns with Gherkin.
    """
    csv_rows: List[TestCaseRow] = Field(
        description="Ordered step-by-step rows to write into expected.csv"
    )
    cucumber_feature: str = Field(
        description=(
            "Complete raw Gherkin .feature file content. "
            "No markdown fences. Start directly with tags/Feature keyword."
        )
    )
    selenium_script: str = Field(
        description=(
            "Complete raw Python Selenium test script implementing every Gherkin step. "
            "No markdown fences. Start directly with the module docstring or import."
        )
    )


# ==============================================================================
# 2. LLM INITIALISATION (Moved to core/llm_factory.py)
# ==============================================================================


# ==============================================================================
# 3. HELPER — strip markdown code fences from LLM text fields
# ==============================================================================

def _strip_fences(text: str) -> str:
    """Remove ```python / ```gherkin / ``` wrappers that LLMs sometimes add."""
    text = re.sub(r"^```[a-zA-Z]*\r?\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"\r?\n```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


# ==============================================================================
# 4. UNIFIED PROMPT + CHAIN
#    One ChatPromptTemplate → one LLM call → FullTestCaseOutput (all 3 artifacts)
# ==============================================================================

# Extracted as a standalone constant so Gemini cache creation and Anthropic
# cache_control injection can both reference the exact same text.
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

# Standard ChatPromptTemplate used by Gemini and OpenAI chains.
UNIFIED_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT_TEXT),
    (
        "human",
        "Test Case JSON:\n{tc_json}\n\n"
        "Generate all three artifacts (csv_rows, cucumber_feature, selenium_script) now.",
    ),
])


def build_chain(bundle: Any) -> Any:
    """
    Builds the LangChain chain for the given LLMBundle.

    - Gemini / OpenAI: UNIFIED_PROMPT | llm.with_structured_output()
      (Gemini cache is injected via setup_cache() before batch; OpenAI auto-caches)

    - Anthropic: Custom chain with cache_control: ephemeral on the system message.
      LiteLLM passes this flag to Anthropic, which caches the system prompt
      server-side for ~5 min (auto-renews on each hit). ~90% saving on cached tokens.
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain_core.runnables import RunnableLambda

    llm = bundle.llm

    if bundle.provider == "anthropic":
        # Anthropic requires cache_control on the system message content block.
        # We build the chain manually using a RunnableLambda to inject this.
        def _anthropic_chain_fn(inputs: dict) -> FullTestCaseOutput:
            messages = [
                SystemMessage(content=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT_TEXT.replace("{base_url}", inputs.get("base_url", "")),
                        "cache_control": {"type": "ephemeral"},  # tells Anthropic to cache this block
                    }
                ]),
                HumanMessage(content=(
                    f"Test Case JSON:\n{inputs['tc_json']}\n\n"
                    "Generate all three artifacts (csv_rows, cucumber_feature, selenium_script) now."
                )),
            ]
            return llm.with_structured_output(FullTestCaseOutput).invoke(messages)

        return RunnableLambda(_anthropic_chain_fn)

    # Gemini and OpenAI use the standard ChatPromptTemplate chain
    return UNIFIED_PROMPT | llm.with_structured_output(FullTestCaseOutput)


def generate_all_artifacts(
    bundle: Any,
    tc: Dict[str, Any],
    max_retries: int = MAX_LLM_RETRIES,
    base_url: str = "",
) -> FullTestCaseOutput:
    """
    Single unified chain: UNIFIED_PROMPT | llm.with_structured_output(FullTestCaseOutput)

    One LLM call generates all 3 artifacts in the same context window, so:
    - The Selenium script steps are naturally aligned with the Gherkin steps.
    - CSV rows, Gherkin, and Selenium share the same understanding of the test case.
    Retries automatically on 429 RESOURCE_EXHAUSTED (rate limit) or transient network errors.
    """
    chain = build_chain(bundle)
    for attempt in range(1, max_retries + 1):
        try:
            return chain.invoke({"tc_json": json.dumps(tc, separators=(',', ':')), "base_url": base_url or DEFAULT_BASE_URL})  # compact: no whitespace = fewer tokens
        except Exception as exc:
            err = str(exc).lower()
            is_rate_limit  = "429" in err or "resource_exhausted" in err
            is_network_err = any(t in err for t in ["timeout", "connection", "httpcore", "httpx", "ssl"])

            if is_rate_limit:
                wait = RATE_LIMIT_BASE_WAIT_S * attempt
                print(f"         [WAIT] Rate limit hit. Retrying in {wait}s (attempt {attempt}/{max_retries})...")
                time.sleep(wait)
            elif is_network_err and attempt < max_retries:
                wait = NETWORK_BASE_WAIT_S * attempt
                print(f"         [WAIT] Network/Timeout error. Retrying in {wait}s (attempt {attempt}/{max_retries})...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Failed after {max_retries} retries for TC: {tc.get('tc_id')}")



# ==============================================================================
# 5. MAIN PIPELINE — one test case at a time, one LLM call per test case
# ==============================================================================

def run_agent(
    stage1_json_path: str = DEFAULT_INPUT_PATH,
    out_dir_path: str = DEFAULT_OUTPUT_PATH,
    model_name: str = DEFAULT_MODEL,
    base_url: str = "",
) -> None:
    """
    Public API — called by server.py directly (no CLI / subprocess needed).
    Reads input JSON file and generates artifacts inside out_dir_path/.
    base_url is injected into the LLM prompt and fallback Selenium scripts.

    Writes:
      <out_dir_path>/expected.csv              — all CSV step rows
      <out_dir_path>/cucumber/<TC-ID>.feature  — Gherkin feature file
      <out_dir_path>/selenium/test_<TC-ID>.py  — Selenium Python test script
    """
    app_base_url  = base_url or DEFAULT_BASE_URL
    project_root = Path(__file__).parent.parent.resolve()

    json_path = (
        Path(stage1_json_path)
        if Path(stage1_json_path).is_absolute()
        else project_root / stage1_json_path
    )

    # Fallback: pick the newest JSON in output/ if the exact path is missing
    if not json_path.exists():
        output_dir = project_root / "output"
        candidates = sorted(output_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            json_path = candidates[0]

    out_dir  = (
        Path(out_dir_path)
        if Path(out_dir_path).is_absolute()
        else project_root / out_dir_path
    )
    csv_path = out_dir / "expected.csv"
    cuc_dir  = out_dir / "cucumber"
    sel_dir  = out_dir / "selenium"

    for d in (out_dir, cuc_dir, sel_dir):
        d.mkdir(parents=True, exist_ok=True)

    print("=" * SEPARATOR_WIDTH)
    print("  Cucumber & Selenium Generator Agent")
    print(f"  Model      : {model_name}")
    print(f"  Input JSON : {json_path}")
    print(f"  Output Dir : {out_dir}")
    print(f"  Base URL   : {app_base_url}")
    print("=" * SEPARATOR_WIDTH)

    if not json_path.exists():
        raise FileNotFoundError(f"[ERROR] Input file not found: {json_path}")

    print(f"\n[1/3] Loading: {json_path.name}")
    with open(json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    test_cases = data.get("test_cases", [])
    total      = len(test_cases)
    print(f"      Loaded {total} test cases from '{data.get('project', 'unknown')}' project.")

    # Initialise LLM via LiteLLM factory
    try:
        print(f"\n[2/3] Initialising LiteLLM ({model_name})...")
        os.environ["GEMINI_MODEL"] = model_name
        from core.llm_factory import create_llm
        bundle = create_llm()
        print(f"      [OK] Connected to LiteLLM router")
    except Exception as e:
        raise RuntimeError(f"[ERROR] LLM init failed: {e}. An API key is required.") from e

    # Write CSV header
    csv_headers = [
        "testcase", "description", "category", "preconditions",
        "stepname", "expected result", "testdata", "evidence required",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(csv_headers)

    print(f"\n[3/3] Processing {total} test cases...\n")

    for i, tc in enumerate(test_cases, start=1):
        tc_id = tc.get("tc_id", f"TC-{i:03d}")
        title = tc.get("title", "Unnamed")

        print(f"  [{i:02d}/{total}] {tc_id} — {title}")

        output = None
        max_retries = 4
        for attempt in range(1, max_retries + 1):
            try:
                output = generate_all_artifacts(bundle, tc, base_url=app_base_url)
                break
            except Exception as exc:
                err_msg = str(exc)
                is_rate_limit = any(k in err_msg.lower() for k in ("429", "rate", "cooldown", "resourceexhausted", "deployments"))
                if attempt < max_retries and is_rate_limit:
                    wait_sec = attempt * 3
                    print(f"         [RATE LIMIT] Waiting {wait_sec}s before retry ({attempt}/{max_retries})...")
                    time.sleep(wait_sec)
                else:
                    print(f"         [ERROR] LLM error ({exc}). Skipping test case.")
                    break

        if not output:
            continue

        # Write CSV rows
        with open(csv_path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            for row in output.csv_rows:
                writer.writerow([
                    row.testcase, row.description, row.category,
                    row.preconditions, row.stepname, row.expected_result,
                    row.testdata, row.evidence_required,
                ])

        # Write Cucumber feature file
        (cuc_dir / f"{tc_id}.feature").write_text(
            _strip_fences(output.cucumber_feature), encoding="utf-8"
        )

        # Write Selenium script
        (sel_dir / f"test_{tc_id}.py").write_text(
            _strip_fences(output.selenium_script), encoding="utf-8"
        )

    print("\n" + "=" * SEPARATOR_WIDTH)
    print("  [DONE] All test cases processed successfully!")
    print(f"      CSV written        : {csv_path}")
    print(f"      Cucumber features  : {cuc_dir}")
    print(f"      Selenium scripts   : {sel_dir}")
    print("=" * SEPARATOR_WIDTH)
