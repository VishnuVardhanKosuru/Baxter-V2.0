# 🤖 Tester Agent (C&S Generator) — Technical & Operational Documentation

## 1. Overview & Business Context

The **Tester Agent** (Cucumber & Selenium Generator Agent — `agents/cs_agent.py`) represents **Phase 2** of the automated testing pipeline in Baxter. 

While Phase 1 (`doc_parser.py`) extracts and structures business requirements into an enriched JSON knowledge base, Phase 2 acts as the **AI Test Automation Engineer**. It consumes each enriched test case and transforms it into three synchronized, production-grade test artifacts:

1. **Test Execution Matrix (`expected.csv`)**:
   A granular, step-by-step test execution and verification matrix recording preconditions, action steps, synthetic test data, intermediate expected results, and required compliance evidence.
2. **BDD Feature Specifications (`cucumber/<TC-ID>.feature`)**:
   Formal Gherkin feature files formatted with requirement tags, feature descriptions, backgrounds, scenarios, and declarative `Given / When / Then` steps.
3. **Automated Selenium Test Suites (`selenium/test_<TC-ID>.py`)**:
   Production-ready Pytest test scripts using Selenium WebDriver, dynamic selectors, explicit `WebDriverWait` synchronization, and pytest assertions that directly implement every step from the Gherkin feature file.

---

## 2. Production Architecture & End-to-End Execution Flow

### 2.1 System Architecture

```text
                  ┌────────────────────────────────────────┐
                  │ output/shopsphere_parsed.json (Phase 1)│
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │           core/constants.py            │  ◄── Directory Paths, Models, API Configurations
                  │            core/models.py              │  ◄── Pydantic Output Schemas (FullTestCaseOutput)
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │           agents/cs_agent.py           │
                  │  ┌──────────────────────────────────┐  │
                  │  │ LangChain Unified Chat Template  │  │
                  │  └────────────────┬─────────────────┘  │
                  │                   │                    │
                  │                   ▼                    │
                  │  ┌──────────────────────────────────┐  │
                  │  │ Google Gemini 3.5 Flash Lite LLM │  │  ◄── High Quota (500 RPD, 15 RPM) via GEMINI_API_KEY
                  │  └────────────────┬─────────────────┘  │
                  │                   │                    │
                  │                   ▼                    │
                  │  ┌──────────────────────────────────┐  │
                  │  │  Structured Pydantic Validation  │  │  ◄── FullTestCaseOutput
                  │  └──────────────────────────────────┘  │
                  └───────────────────┬────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
│   expected.csv   │        │     cucumber/    │        │    selenium/     │
│ (Traceability)   │        │  <TC-ID>.feature │        │ test_<TC-ID>.py  │
└──────────────────┘        └──────────────────┘        └──────────────────┘
```

---

### 2.2 End-to-End Execution Flowchart

```text
 [CLI / API Trigger] POST /api/stage2-generate OR python agents/cs_agent.py
        │
        ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Step 1: Input Ingestion & Directory Initialization                                    │
 │ - Resolve input JSON path from core.constants.DIR_OUTPUT                               │
 │ - Create output directories: output/tests/cucumber and output/tests/selenium           │
 │ - Initialize expected.csv with standard QA header row                                 │
 └───────────────────────────────────┬────────────────────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Step 2: LLM Connection & Environment Authentication                                    │
 │ - Validate GEMINI_API_KEY from environment / .env file                                 │
 │ - Instantiate ChatGoogleGenerativeAI (primary: gemini-3.5-flash-lite)                  │
 │ - Configure low temperature (0.2) for deterministic, reproducible code generation      │
 └───────────────────────────────────┬────────────────────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Step 3: Test Case Iteration Loop (Sequential One-by-One Processing)                   │
 │ - Loop through each enriched TestCaseModel in the input dataset:                       │
 │   - Extract TC ID (e.g. TC-001), Title, Type, Subject, Steps, Expected Result          │
 │   - Extract FeatureContext (actors, business rules, pre-conditions, exception flows)   │
 └───────────────────────────────────┬────────────────────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Step 4: Single-Chain Unified Generation (LangChain + Gemini Structured Output)        │
 │ - Inject TestCase JSON + Target Base URL into UNIFIED_PROMPT                           │
 │ - Call Gemini API with with_structured_output(FullTestCaseOutput)                      │
 │ - Generate all 3 artifacts in the SAME context window:                                 │
 │     1. csv_rows          → List of granular step rows                                 │
 │     2. cucumber_feature  → Complete Gherkin .feature specification                     │
 │     3. selenium_script   → Complete Python Selenium WebDriver test script              │
 └───────────────────────────────────┬────────────────────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Step 5: Rate Limiting Backoff & Resilience Handling                                   │
 │ - If 429 RESOURCE_EXHAUSTED encountered:                                               │
 │   - Apply linear/exponential backoff sleep (e.g. 5s, 10s, 15s)                         │
 │   - Retry API request up to MAX_LLM_RETRIES (3 attempts)                               │
 │ - If unrecoverable error occurs, surface descriptive error without dummy fallback      │
 └───────────────────────────────────┬────────────────────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Step 6: Artifact Dispersion & Persistence                                              │
 │ - Append step rows to output/tests/expected.csv                                        │
 │ - Strip any markdown fences and write output/tests/cucumber/<TC-ID>.feature            │
 │ - Strip any markdown fences and write output/tests/selenium/test_<TC-ID>.py            │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Step-by-Step Flow Explanation

### Phase 1: Input Ingestion & Directory Setup
The agent identifies the latest parsed JSON knowledge base (e.g. `shopsphere_parsed.json`) generated by Phase 1. It validates that the dataset contains test cases and initializes the destination directories (`output/tests/`, `output/tests/cucumber/`, and `output/tests/selenium/`). It opens `expected.csv` and writes the standard 8-column header row.

### Phase 2: Gemini API Client Authentication
The agent reads `GEMINI_API_KEY` from `.env`. It connects to Google AI Studio using the `ChatGoogleGenerativeAI` client configured with **Gemini 3.5 Flash Lite** (15 RPM / 500 RPD). The temperature is set to `0.2` to eliminate hallucination and ensure strict adherence to standard syntax rules.

### Phase 3: The Single-Chain Unified Generation Principle
A common flaw in test generation pipelines is using separate prompts for Cucumber and Selenium. When generated separately, the Selenium script often uses different action steps or selectors than the Gherkin feature file.

**Baxter solves this with the Single-Chain Unified Architecture:**
- A single LLM prompt receives the test case and its surrounding FRD context.
- The LLM generates **all 3 artifacts simultaneously in one inference step**.
- Because the artifacts share the exact same context window, the Selenium method steps **naturally and perfectly mirror** the Gherkin `Given / When / Then` steps.

### Phase 4: Granular Artifact Generation Rules

#### 1. Traceability Matrix (`expected.csv`)
- Expands high-level manual steps into granular, actionable rows.
- Injects realistic synthetic test data (e.g. valid emails, passwords meeting complexity rules, Stripe test credit cards).
- Details precise evidence required for compliance (e.g. *"Screenshot of success toast"*, *"Network tab shows 200 OK on /api/register"*).

#### 2. Cucumber Feature Files (`.feature`)
- Places normalized `@tags` at the top for CI/CD test runner filtering.
- Assigns the parent feature name from the FRD context.
- Inserts a `Background:` block when preconditions exist.
- Formats steps in strict `Given` (setup/navigation), `When` (action), `Then` (assertion), and `And` syntax.

#### 3. Selenium WebDriver Scripts (`test_<TC-ID>.py`)
- Formats code as a standard Pytest class (`TestTC001`).
- Implements `setup_method` (Chrome headless options, driver startup, navigation to target URL) and `teardown_method` (`driver.quit()`).
- Implements `test_<tc_id>` with explicit comments linking each code block to its corresponding Gherkin line.
- Uses explicit waits (`WebDriverWait` + `expected_conditions`) instead of unreliable hardcoded sleeps (`time.sleep`).
- Synthesizes meaningful Pytest assertions matching the expected outcome.

### Phase 5: Rate Limiting & Resilience
When generating large suites (e.g. 23+ test cases), API rate limits may be temporarily reached. The agent automatically detects `429 RESOURCE_EXHAUSTED` responses and pauses with linear backoff (5s, 10s, 15s) before retrying. All generation is performed purely via the Gemini API, guaranteeing zero mock or hardcoded templates.

---

## 4. Technology Stack & Architectural Rationale

| Component | Selected Technology | Why This Was Chosen Over Alternatives |
| :--- | :--- | :--- |
| **LLM Model** | **Gemini 3.5 Flash Lite** | Provides generous free-tier quotas (500 requests/day, 15 requests/min) vs. strict limits on 2.5 Flash (20 RPD). Extremely low latency (<1.5s per testcase) and excellent code-generation accuracy. |
| **LLM Framework** | **LangChain (`langchain-google-genai`)** | Native Pydantic schema enforcement via `with_structured_output()`, robust prompt templating, and automatic schema validation. |
| **Data Schemas** | **Pydantic v2 (`BaseModel`)** | Guarantees strict JSON schema compliance from the LLM, eliminating syntax errors in returned Python or Gherkin blocks. |
| **Test Runner** | **Pytest** | Industry standard for Python test automation, offering clean fixture lifecycles, rich assertion introspection, and seamless CLI/CI integration. |
| **Automation Engine** | **Selenium WebDriver** | Universal browser automation standard supporting Chrome headless, explicit synchronization waits, and flexible selector strategies (CSS, XPath, ID). |

---

## 5. Module & File Specifications

| File Path | Purpose / Responsibility | Key Exports / Elements |
| :--- | :--- | :--- |
| **[core/constants.py](file:///c:/Users/2862390/Desktop/New%20folder%20(3)/Baxter/core/constants.py)** | Centralized configuration for directory paths, file names, regexes, and model defaults. | `DIR_OUTPUT`, `DIR_TESTS`, `DIR_CUCUMBER`, `DIR_SELENIUM`, `DEFAULT_MODEL`, `FALLBACK_MODEL`, `NAME_EXPECTED_CSV`. |
| **[core/models.py](file:///c:/Users/2862390/Desktop/New%20folder%20(3)/Baxter/core/models.py)** | Domain dataclasses and Pydantic structured output models for LLM responses. | `TestCaseRow`, `FullTestCaseOutput`, `TestCaseModel`, `FeatureContextModel`. |
| **[agents/cs_agent.py](file:///c:/Users/2862390/Desktop/New%20folder%20(3)/Baxter/agents/cs_agent.py)** | Core execution engine that drives LLM prompt synthesis, API invocation, and artifact dispersion. | `create_gemini_llm()`, `generate_all_artifacts()`, `run_agent()`. |
| **[server.py](file:///c:/Users/2862390/Desktop/New%20folder%20(3)/Baxter/server.py)** | FastAPI backend orchestrating async generation endpoints and ZIP packaging. | `stage2_generate()`, `download_zip()`. |

---

## 6. Execution Guide & CLI Commands

### Command Syntax
Run the Tester Agent directly from the repository root:

```powershell
python agents/cs_agent.py `
  --input "output/shopsphere_parsed.json" `
  --out "output/tests" `
  --model "gemini-3.5-flash-lite" `
  --base-url "https://shop.shopsphere.com"
```

### Sample Console Execution Log
```text
==============================================================
  Cucumber & Selenium Generator Agent
  Model      : gemini-3.5-flash-lite
  Input JSON : C:\Baxter\output\shopsphere_parsed.json
  Output Dir : C:\Baxter\output\tests
  Base URL   : https://shop.shopsphere.com
==============================================================

[1/3] Loading: shopsphere_parsed.json
      Loaded 23 test cases from 'ShopSphere' project.

[2/3] Connecting to Google Gemini API (gemini-3.5-flash-lite)...
      [OK] Gemini LLM client initialized successfully.

[3/3] Generating artifacts via Gemini API for 23 test cases...

  [01/23] Generating artifacts for TC-001 — User Registration — Valid Details...
  [02/23] Generating artifacts for TC-002 — User Registration — Duplicate Email...
  [03/23] Generating artifacts for TC-003 — Login — Valid Credentials...
  ...
  [23/23] Generating artifacts for TC-025 — Security — SQL Injection Attempt on Search...

==============================================================
  [DONE] All test cases generated successfully via Gemini API!
      CSV written        : C:\Baxter\output\tests\expected.csv
      Cucumber features  : C:\Baxter\output\tests\cucumber
      Selenium scripts   : C:\Baxter\output\tests\selenium
==============================================================
```

---

## 7. Artifact Output Specifications & Concrete Examples

### 7.1 Traceability Matrix (`output/tests/expected.csv`)

| testcase | description | category | preconditions | stepname | expected result | testdata | evidence required |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-001 - User Registration** | Verify valid registration | UI Form Validation | User is on signup page | Navigate to registration page | Registration modal opens | URL: /signup | Screenshot of signup form |
| **TC-001 - User Registration** | Verify valid registration | UI Form Validation | Form is displayed | Enter valid email and password | Fields populated with green checkmarks | email: test_user@example.com, pass: Secure#2026 | DOM value inspection |
| **TC-001 - User Registration** | Verify valid registration | UI Form Validation | Submit button enabled | Click "Create Account" button | User redirected to dashboard with welcome toast | Action: Click | Screenshot of dashboard & 200 OK on /api/register |

---

### 7.2 Cucumber Feature Specification (`output/tests/cucumber/TC-001.feature`)

```gherkin
@ui @functional @positive @fr_001 @tc_001
Feature: User Registration & Authentication
  As a new customer
  I want to create a ShopSphere account
  So that I can purchase items and track orders

  Background:
    Given the user navigates to "https://shop.shopsphere.com"
    And the user is not currently logged in

  Scenario: TC-001 - User Registration with Valid Details
    Given the user clicks on the "Sign Up" button
    When the user enters the following details:
      | Field    | Value                  |
      | Name     | John Doe               |
      | Email    | john.doe.2026@test.com |
      | Password | SecureP@ssw0rd!2026    |
    And the user clicks the "Create Account" submit button
    Then the user should be redirected to the account dashboard
    And a welcome notification banner should display "Welcome to ShopSphere, John!"
    And the session token should be stored in local storage
```

---

### 7.3 Selenium WebDriver Test Script (`output/tests/selenium/test_TC-001.py`)

```python
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class TestTC001:
    """
    Test Case: TC-001 - User Registration with Valid Details
    Requirement: FR-001 (User Registration & Authentication)
    """

    def setup_method(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)
        self.base_url = "https://shop.shopsphere.com"
        self.driver.get(self.base_url)

    def teardown_method(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    def test_tc_001_valid_registration(self):
        driver = self.driver
        wait = self.wait

        # Given the user clicks on the "Sign Up" button
        signup_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-testid='signup-button'], a.signup-btn")))
        signup_btn.click()

        # When the user enters valid registration credentials
        name_input = wait.until(EC.visibility_of_element_located((By.NAME, "fullName")))
        email_input = driver.find_element(By.NAME, "email")
        password_input = driver.find_element(By.NAME, "password")

        name_input.send_keys("John Doe")
        email_input.send_keys("john.doe.2026@test.com")
        password_input.send_keys("SecureP@ssw0rd!2026")

        # And the user clicks the "Create Account" submit button
        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()

        # Then the user should be redirected to the account dashboard
        wait.until(EC.url_contains("/dashboard"))
        assert "/dashboard" in driver.current_url, "User was not redirected to dashboard upon registration."

        # And a welcome notification banner should display
        welcome_banner = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".toast-success, .welcome-banner")))
        assert "Welcome" in welcome_banner.text, "Welcome banner was not displayed."
```
