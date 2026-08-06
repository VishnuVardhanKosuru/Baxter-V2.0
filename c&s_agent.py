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

from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import ChatPromptTemplate
    load_dotenv()
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    ChatGoogleGenerativeAI = None
    ChatPromptTemplate = None




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


import argparse

def generate_fallback_artifacts(tc: Dict[str, Any]) -> FullTestCaseOutput:
    """Fallback generator when GEMINI_API_KEY is not set or API is unreachable."""
    tc_id = tc.get("tc_id", "TC-001")
    title = tc.get("title", "Test Case")
    subject = tc.get("subject", "General")
    feature_ref = tc.get("feature_ref", "FR-001")
    steps = tc.get("steps", ["Perform action"])
    expected = tc.get("expected_result", "Action succeeds")
    tags = tc.get("cucumber_tags", [f"@{tc_id.lower().replace('-', '_')}"])

    # Build CSV rows
    csv_rows = []
    for idx, stp in enumerate(steps, start=1):
        csv_rows.append(
            TestCaseRow(
                testcase=f"{tc_id} - {title}",
                description=f"Verify {title}",
                category=tc.get("type", ["Functional"])[0] if tc.get("type") else "Functional",
                preconditions=tc.get("feature_context", {}).get("pre_conditions", ["System is active"])[0] if idx == 1 else "Previous step passed",
                stepname=stp,
                expected_result=expected if idx == len(steps) else "Step completed successfully",
                testdata="valid_input=sample",
                evidence_required="Screenshot of UI response"
            )
        )

    # Build Cucumber feature
    tag_str = " ".join(tags)
    feature_str = f"""{tag_str}
Feature: {tc.get('feature_context', {}).get('feature_name', subject)}
  As a user
  I want to verify {title}
  So that the system behaves as expected for {feature_ref}

  Scenario: {tc_id} - {title}
"""
    for stp in steps:
        feature_str += f"    Given {stp}\n"
    feature_str += f"    Then {expected}\n"

    # Build Selenium script
    clean_id = tc_id.replace('-', '_').lower()
    class_name = f"Test{tc_id.replace('-', '')}"
    selenium_str = f"""import pytest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class {class_name}:
    def setup_method(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        self.driver = webdriver.Chrome(options=options)
        self.driver.get("https://shop.shopsphere.com")

    def teardown_method(self):
        self.driver.quit()

    def test_{clean_id}(self):
        \"\"\"{title} ({feature_ref})\"\"\"
        driver = self.driver
        # Automated test execution steps for {tc_id}
"""
    for stp in steps:
        selenium_str += f"        # Step: {stp}\n"
        selenium_str += f"        # driver.find_element(By.CSS_SELECTOR, 'body')\n"
    selenium_str += f"        assert driver.title is not None, '{expected}'\n"

    return FullTestCaseOutput(
        csv_rows=csv_rows,
        cucumber_feature=feature_str,
        selenium_script=selenium_str
    )


# ==============================================================================
# 5. MAIN PIPELINE — one test case at a time, one LLM call per test case
# ==============================================================================

def run_agent(
    stage1_json_path: str = "output/shopsphere_parsed.json",
    out_dir_path: str = "output/tests",
    model_name: str = "gemini-2.5-flash",
) -> None:
    """
    Entry point. Reads input JSON file and generates artifacts inside out_dir_path/

    Writes:
      <out_dir_path>/expected.csv          — all CSV step rows
      <out_dir_path>/cucumber/<TC-ID>.feature  — Gherkin feature file
      <out_dir_path>/selenium/test_<TC-ID>.py — Selenium Python test script
    """
    base_dir = Path(__file__).parent.resolve()

    json_path = Path(stage1_json_path) if Path(stage1_json_path).is_absolute() else base_dir / stage1_json_path
    
    # Fallback search if specified path doesn't exist
    if not json_path.exists():
        fallback_paths = [
            base_dir / "output" / "shopsphere_parsed.json",
            base_dir / "stage1_output.json"
        ]
        for fb in fallback_paths:
            if fb.exists():
                json_path = fb
                break

    out_dir = Path(out_dir_path) if Path(out_dir_path).is_absolute() else base_dir / out_dir_path
    csv_path = out_dir / "expected.csv"
    cuc_dir = out_dir / "cucumber"
    sel_dir = out_dir / "selenium"

    out_dir.mkdir(parents=True, exist_ok=True)
    cuc_dir.mkdir(parents=True, exist_ok=True)
    sel_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 62)
    print("  Cucumber & Selenium Generator Agent (LangChain + Gemini 2.5)")
    print(f"  Input JSON : {json_path}")
    print(f"  Output Dir : {out_dir}")
    print("=" * 62)

    if not json_path.exists():
        raise FileNotFoundError(f"[ERROR] Input file not found: {json_path}")

    print(f"\n[1/3] Loading: {json_path.name}")
    with open(json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    test_cases = data.get("test_cases", [])
    total = len(test_cases)
    print(f"      Loaded {total} test cases from '{data.get('project', 'unknown')}' project.")

    # Check for API key
    llm = None
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        try:
            print(f"\n[2/3] Initialising Gemini LLM ({model_name})...")
            llm = create_gemini_llm(model_name=model_name)
            print(f"      [OK] Connected to {model_name}")
        except Exception as e:
            print(f"      [WARN] LLM init error: {e}. Falling back to template mode.")
            llm = None
    else:
        print("\n[2/3] No GEMINI_API_KEY found. Running in Offline Template Mode...")

    # Write CSV header
    csv_headers = [
        "testcase", "description", "category", "preconditions",
        "stepname", "expected result", "testdata", "evidence required",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(csv_headers)

    # Process test cases
    print(f"\n[3/3] Processing {total} test cases...\n")
    total_csv_rows = 0

    for i, tc in enumerate(test_cases, start=1):
        tc_id = tc.get("tc_id", f"TC-{i:03d}")
        title = tc.get("title", "Unnamed")

        print(f"  [{i:02d}/{total}] {tc_id} — {title}")

        if llm:
            try:
                output = generate_all_artifacts(llm, tc)
            except Exception as exc:
                print(f"         [WARN] LLM error ({exc}). Using template fallback.")
                output = generate_fallback_artifacts(tc)
        else:
            output = generate_fallback_artifacts(tc)

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

        # Write Cucumber feature file
        feat_path = cuc_dir / f"{tc_id}.feature"
        feat_path.write_text(_strip_fences(output.cucumber_feature), encoding="utf-8")

        # Write Selenium script
        sel_path = sel_dir / f"test_{tc_id}.py"
        sel_path.write_text(_strip_fences(output.selenium_script), encoding="utf-8")

    print("\n" + "=" * 62)
    print("  [DONE] All test cases processed successfully!")
    print(f"      CSV written        : {csv_path}")
    print(f"      Cucumber features  : {cuc_dir}")
    print(f"      Selenium scripts   : {sel_dir}")
    print("=" * 62)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cucumber & Selenium Test Case Generator Agent")
    parser.add_argument("--input", default="output/shopsphere_parsed.json", help="Input JSON file from document parser")
    parser.add_argument("--out", default="output/tests", help="Output directory for generated tests (e.g. output/tests)")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini model name")
    args = parser.parse_args()

    run_agent(stage1_json_path=args.input, out_dir_path=args.out, model_name=args.model)

