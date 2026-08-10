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
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import ChatPromptTemplate
    load_dotenv()
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

DEFAULT_MODEL:          str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-lite")
DEFAULT_BASE_URL:       str = os.environ.get("BASE_URL", "http://localhost")
DEFAULT_INPUT_PATH:     str = "output/parsed_output.json"
DEFAULT_OUTPUT_PATH:    str = "output/tests"
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
# 2. LLM INITIALISATION
# ==============================================================================

def create_gemini_llm(model_name: str = DEFAULT_MODEL) -> ChatGoogleGenerativeAI:
    """
    Creates a LangChain ChatGoogleGenerativeAI instance.
    Reads GEMINI_API_KEY (or GOOGLE_API_KEY) from environment / .env file.
    Raises RuntimeError if the key is not found.
    """
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "\n[ERROR] GEMINI_API_KEY is not set.\n"
            "  Add it to your .env file:  GEMINI_API_KEY=your_key_here\n"
            "  Then re-run the agent."
        )
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=key,
        temperature=LLM_TEMPERATURE,
    )


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

UNIFIED_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a senior QA Automation Engineer expert in BDD, Cucumber, and Selenium WebDriver.\n\n"
        "Given a test case JSON, generate ALL THREE of the following in a single response:\n\n"

        "━━ ARTIFACT 1 — csv_rows ━━\n"
        "Expand the test case into step-by-step CSV rows (one row per step).\n"
        "Rules:\n"
        "- First row carries full pre-conditions; subsequent rows use 'Previous step passed'.\n"
        "- testdata: realistic, specific values (e.g. 'email: user@test.com | password: Secure@123').\n"
        "  For payment steps use Stripe test cards (e.g. '4242 4242 4242 4242, exp 12/26, CVC 123').\n"
        "- evidence_required: specific proof (e.g. 'Screenshot of success toast', '200 OK on /api/auth/login').\n"
        "- expected_result per step: granular intermediate outcome, not just the final result.\n\n"

        "━━ ARTIFACT 2 — cucumber_feature ━━\n"
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
        "- Raw .feature content only — NO markdown fences.\n\n"

        "━━ ARTIFACT 3 — selenium_script ━━\n"
        "Write a complete Python Selenium WebDriver test script that implements\n"
        "EVERY Gherkin step from the cucumber_feature you just wrote.\n"
        "Rules:\n"
        "- Use pytest as the test runner.\n"
        "- Class name: Test<TCID> (e.g. TestTC001).\n"
        "- setup_method: ChromeOptions, driver init, navigate to BASE_URL (from context or {base_url}).\n"
        "- teardown_method: driver.quit() in try/finally.\n"
        "- Test method: test_<tc_id_lowercase> (e.g. test_tc_001).\n"
        "- Comment each block with its matching Gherkin line.\n"
        "- Use WebDriverWait + expected_conditions — NO time.sleep().\n"
        "- Infer realistic CSS selectors from the test case context and subject area.\n"
        "- Add meaningful pytest assert statements matching expected_result.\n"
        "- Base URL for navigation: {base_url}\n"
        "- Raw Python code only — NO markdown fences.",
    ),
    (
        "human",
        "Test Case JSON:\n{tc_json}\n\n"
        "Generate all three artifacts (csv_rows, cucumber_feature, selenium_script) now.",
    ),
])


def generate_all_artifacts(
    llm: ChatGoogleGenerativeAI,
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
    chain = UNIFIED_PROMPT | llm.with_structured_output(FullTestCaseOutput)
    for attempt in range(1, max_retries + 1):
        try:
            return chain.invoke({"tc_json": json.dumps(tc, indent=2), "base_url": base_url or DEFAULT_BASE_URL})
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


def generate_fallback_artifacts(tc: Dict[str, Any], base_url: str = "") -> FullTestCaseOutput:
    """Fallback generator when GEMINI_API_KEY is not set or API is unreachable.
    Builds valid Cucumber & Selenium artifacts directly from parsed test case data.
    """
    tc_id       = tc.get("tc_id", "TC-001")
    title       = tc.get("title", "Test Case")
    subject     = tc.get("subject", "General")
    feature_ref = tc.get("feature_ref", "FR-001")
    steps       = tc.get("steps", ["Perform action"])
    expected    = tc.get("expected_result", "Action succeeds")
    tags        = tc.get("cucumber_tags", [f"@{tc_id.lower().replace('-', '_')}"])
    app_url     = base_url or DEFAULT_BASE_URL
    pre_cond_list = (tc.get("feature_context") or {}).get("pre_conditions") or []
    first_precondition = pre_cond_list[0] if pre_cond_list else "System is accessible"

    # Build CSV rows
    csv_rows = [
        TestCaseRow(
            testcase=f"{tc_id} - {title}",
            description=f"Verify {title}",
            category=(tc.get("type") or ["Functional"])[0],
            preconditions=first_precondition if idx == 1 else "Previous step passed",
            stepname=stp,
            expected_result=expected if idx == len(steps) else "Step completed successfully",
            testdata="valid_input=sample",
            evidence_required="Screenshot of UI response",
        )
        for idx, stp in enumerate(steps, start=1)
    ]

    # Build Cucumber feature
    feature_name = (tc.get("feature_context") or {}).get("feature_name") or subject
    tag_str = " ".join(tags)
    feature_str = (
        f"{tag_str}\n"
        f"Feature: {feature_name}\n"
        f"  As a user\n"
        f"  I want to verify {title}\n"
        f"  So that the system behaves as expected for {feature_ref}\n\n"
        f"  Scenario: {tc_id} - {title}\n"
    )
    for stp in steps:
        feature_str += f"    Given {stp}\n"
    feature_str += f"    Then {expected}\n"

    # Build Selenium script
    clean_id   = tc_id.replace("-", "_").lower()
    class_name = f"Test{tc_id.replace('-', '')}"
    selenium_lines = [
        "import pytest",
        "from selenium import webdriver",
        "from selenium.webdriver.common.by import By",
        "from selenium.webdriver.support.ui import WebDriverWait",
        "from selenium.webdriver.support import expected_conditions as EC",
        "",
        f"class {class_name}:",
        "    def setup_method(self):",
        "        options = webdriver.ChromeOptions()",
        "        options.add_argument('--headless')",
        "        self.driver = webdriver.Chrome(options=options)",
        f"        self.driver.get('{app_url}')",
        "",
        "    def teardown_method(self):",
        "        try:",
        "            self.driver.quit()",
        "        except Exception:",
        "            pass",
        "",
        f"    def test_{clean_id}(self):",
        f'        """{title} ({feature_ref})"""',
        "        driver = self.driver",
        f"        # Automated test execution steps for {tc_id}",
    ]
    for stp in steps:
        selenium_lines.append(f"        # Step: {stp}")
        selenium_lines.append("        # TODO: implement selector for this step")
    selenium_lines.append(f"        assert driver.title is not None, '{expected}'")

    return FullTestCaseOutput(
        csv_rows=csv_rows,
        cucumber_feature=feature_str,
        selenium_script="\n".join(selenium_lines),
    )


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
    agent_base_dir = Path(__file__).parent.resolve()

    json_path = (
        Path(stage1_json_path)
        if Path(stage1_json_path).is_absolute()
        else agent_base_dir / stage1_json_path
    )

    # Fallback: pick the newest JSON in output/ if the exact path is missing
    if not json_path.exists():
        output_dir = agent_base_dir / "output"
        candidates = sorted(output_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            json_path = candidates[0]

    out_dir  = (
        Path(out_dir_path)
        if Path(out_dir_path).is_absolute()
        else agent_base_dir / out_dir_path
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

    # Initialise LLM if API key is present
    llm = None
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        try:
            print(f"\n[2/3] Initialising Gemini LLM ({model_name})...")
            llm = create_gemini_llm(model_name=model_name)
            print(f"      [OK] Connected to {model_name}")
        except Exception as e:
            print(f"      [WARN] LLM init error: {e}. Falling back to template mode.")
    else:
        print("\n[2/3] No API key found. Running in Offline Template Mode...")

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

        if llm:
            try:
                output = generate_all_artifacts(llm, tc, base_url=app_base_url)
            except Exception as exc:
                print(f"         [WARN] LLM error ({exc}). Using template fallback.")
                output = generate_fallback_artifacts(tc, base_url=app_base_url)
        else:
            output = generate_fallback_artifacts(tc, base_url=app_base_url)

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
