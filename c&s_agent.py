"""
Cucumber & Selenium (C&S) Test Case Generator Agent using LangChain & Gemini 2.5

Processes each test case from `stage1_output.json` individually — one at a time.

For each test case a SINGLE LangChain chain generates all 3 artifacts in one LLM call:
  - CSV step rows   → appended to expected.csv
  - Gherkin code    → saved as cucumber/TC-001.feature
  - Selenium Python → saved as selenium/test_TC-001.py

Because all 3 are generated in the same LLM context window, the Selenium steps
naturally align with the Gherkin steps with no manual context passing needed.

Usage:
  python c&s_agent.py

"""

import os
import json
import csv
import re
import time
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

# Load GEMINI_API_KEY from .env file
load_dotenv()


# ==============================================================================
# 1. PYDANTIC SCHEMAS — single structured output for all 3 artifacts
# ==============================================================================

class TestCaseRow(BaseModel):
    """One row in expected.csv — represents a single test step."""
    testcase: str = Field(description="Test case ID and title, e.g. 'TC-001 - User Registration'")
    description: str = Field(description="Detailed objective of the test case")
    category: str = Field(description="Test type/category e.g. 'UI Form Validation'")
    preconditions: str = Field(description="Pre-requisites before executing this step")
    stepname: str = Field(description="The exact action/step being performed")
    expected_result: str = Field(description="Expected system response or outcome for this step")
    testdata: str = Field(description="Specific input data, e.g. 'email: test@example.com | password: Test@123'")
    evidence_required: str = Field(description="Proof needed, e.g. 'Screenshot of success toast', '200 OK in Network tab'")


class FullTestCaseOutput(BaseModel):
    """
    Single structured response from the LLM containing all 3 generated artifacts.
    Using one model means the LLM generates everything in one shared context —
    so the Selenium script is naturally aligned with the Gherkin steps.
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

def create_gemini_llm(model_name: str = "gemini-2.5-flash") -> ChatGoogleGenerativeAI:
    """
    Creates and returns a LangChain ChatGoogleGenerativeAI instance.
    Reads GEMINI_API_KEY from environment / .env file.
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
        temperature=0.2,  # low temperature = consistent, structured output
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
        "- setup_method: ChromeOptions, driver init, navigate to BASE_URL.\n"
        "- teardown_method: driver.quit() in try/finally.\n"
        "- Test method: test_<tc_id_lowercase> (e.g. test_tc_001).\n"
        "- Comment each block with its matching Gherkin line.\n"
        "- Use WebDriverWait + expected_conditions — NO time.sleep().\n"
        "- Infer realistic CSS selectors from context. Common ShopSphere patterns:\n"
        "    email    → input[name='email']\n"
        "    password → input[name='password']\n"
        "    submit   → button[type='submit'], .btn-primary\n"
        "    error    → .error-message, [data-testid='error']\n"
        "    cart     → .cart-badge, [data-testid='cart-count']\n"
        "- Add meaningful pytest assert statements matching expected_result.\n"
        "- Base URL: https://shop.shopsphere.com\n"
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
    max_retries: int = 5,
) -> FullTestCaseOutput:
    """
    Single unified chain: UNIFIED_PROMPT | llm.with_structured_output(FullTestCaseOutput)

    One LLM call generates all 3 artifacts in the same context window, so:
    - The Selenium script steps are naturally aligned with the Gherkin steps.
    - CSV rows, Gherkin, and Selenium share the same understanding of the test case.
    Retries automatically on 429 RESOURCE_EXHAUSTED (rate limit) errors.
    """
    chain = UNIFIED_PROMPT | llm.with_structured_output(FullTestCaseOutput)
    for attempt in range(1, max_retries + 1):
        try:
            return chain.invoke({"tc_json": json.dumps(tc, indent=2)})
        except Exception as exc:
            err = str(exc)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = 30 * attempt  # 30s, 60s, 90s ...
                print(f"         [WAIT] Rate limit hit. Retrying in {wait}s (attempt {attempt}/{max_retries})...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Failed after {max_retries} retries for TC: {tc.get('tc_id')}")


# ==============================================================================
# 5. MAIN PIPELINE — one test case at a time, one LLM call per test case
# ==============================================================================

def run_agent(
    stage1_json_path: str = "stage1_output.json",
    output_csv_path: str  = "expected.csv",
    cucumber_dir: str     = "cucumber",
    selenium_dir: str     = "selenium",
    model_name: str       = "gemini-2.5-flash",
) -> None:
    """
    Entry point. For each test case in stage1_output.json, makes ONE LLM call
    that returns csv_rows + cucumber_feature + selenium_script together.

    Writes:
      expected.csv          — all CSV step rows
      cucumber/<TC-ID>.feature  — Gherkin feature file
      selenium/test_<TC-ID>.py — Selenium Python test script
    """
    base_dir  = Path(__file__).parent
    json_path = base_dir / stage1_json_path
    csv_path  = base_dir / output_csv_path
    cuc_dir   = base_dir / cucumber_dir
    sel_dir   = base_dir / selenium_dir

    cuc_dir.mkdir(parents=True, exist_ok=True)
    sel_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 62)
    print("  Cucumber & Selenium Generator Agent (LangChain + Gemini 2.0)")
    print("  Mode: Unified single-chain (1 LLM call per test case)")
    print("=" * 62)

    # ── Load test cases ──────────────────────────────────────────────────────
    if not json_path.exists():
        raise FileNotFoundError(f"[ERROR] Input file not found: {json_path}")

    print(f"\n[1/3] Loading: {json_path.name}")
    with open(json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    test_cases = data.get("test_cases", [])
    total = len(test_cases)
    print(f"      Loaded {total} test cases from '{data.get('project', 'unknown')}' project.")

    # ── Initialise LLM ───────────────────────────────────────────────────────
    print(f"\n[2/3] Initialising Gemini LLM ({model_name})...")
    llm = create_gemini_llm(model_name=model_name)
    print(f"      [OK] Connected to {model_name}")

    # ── Write CSV header (fresh file) ────────────────────────────────────────
    csv_headers = [
        "testcase", "description", "category", "preconditions",
        "stepname", "expected result", "testdata", "evidence required",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(csv_headers)

    # ── Process each test case: one LLM call → all 3 artifacts ──────────────
    print(f"\n[3/3] Processing {total} test cases...\n")
    total_csv_rows = 0

    for i, tc in enumerate(test_cases, start=1):
        tc_id = tc.get("tc_id", f"TC-{i:03d}")
        title = tc.get("title", "Unnamed")

        print(f"  [{i:02d}/{total}] {tc_id} — {title}")
        print(f"         → Calling LLM (generating CSV + Cucumber + Selenium in one shot)...")

        output: FullTestCaseOutput = generate_all_artifacts(llm, tc)

        # Write CSV rows
        with open(csv_path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            for row in output.csv_rows:
                writer.writerow([
                    row.testcase, row.description, row.category,
                    row.preconditions, row.stepname, row.expected_result,
                    row.testdata, row.evidence_required,
                ])
        total_csv_rows += len(output.csv_rows)
        print(f"         [OK] {len(output.csv_rows)} CSV row(s) appended to expected.csv")

        # Write Cucumber feature file
        feat_path = cuc_dir / f"{tc_id}.feature"
        feat_path.write_text(_strip_fences(output.cucumber_feature), encoding="utf-8")
        print(f"         [OK] Saved: cucumber/{tc_id}.feature")

        # Write Selenium script
        sel_path = sel_dir / f"test_{tc_id}.py"
        sel_path.write_text(_strip_fences(output.selenium_script), encoding="utf-8")
        print(f"         [OK] Saved: selenium/test_{tc_id}.py")

        print()  # blank line between test cases

    # ── Summary ──────────────────────────────────────────────────────────────
    print("=" * 62)
    print("  [DONE]  All test cases processed!")
    print(f"      LLM calls made    : {total}  (1 per test case)")
    print(f"      CSV rows written  : {total_csv_rows}  →  {csv_path.name}")
    print(f"      Cucumber features : {total}  →  {cuc_dir.name}/")
    print(f"      Selenium scripts  : {total}  →  {sel_dir.name}/")
    print("=" * 62)


# ==============================================================================
if __name__ == "__main__":
    run_agent()
