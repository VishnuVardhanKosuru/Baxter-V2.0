# 📚 Document Parser Agent — Technical & Operational Documentation

## 1. Overview & Business Context

The **Document Parser Agent** is Phase 1 of the automated test generation pipeline in `TestCaseGeneratorAgent`. It parses unstructured/semi-structured Word documents (`.docx`) containing:
1. **Functional Requirements Documents (FRD)**
2. **Manual Test Case Specification Suites**

It extracts, categorizes, links, and serializes these business requirements and manual test scenarios into a standardized, production-grade **JSON Knowledge Base** (`shopsphere_parsed.json`).

This JSON Knowledge Base serves as the single source of truth for Phase 2 automation, driving the automatic generation of **Cucumber `.feature` Gherkin specifications** and **Selenium WebDriver Java test suites**.

---

## 2. Production Architecture & End-to-End Process Flow

### 2.1 System Architecture

```
                  ┌────────────────────────┐
                  │   FRD & Manual TCs     │
                  │     (.docx files)      │
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │    agents/constants.py │  ◄── Regex, Tags, Keys, XML Tokens
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │     agents/models.py   │  ◄── Strict Dataclasses & Response DTOs
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │  agents/doc_parser.py  │  ◄── Dynamic AST/Table Parsing Engine
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │ output/shopsphere_     │  ◄── Enriched Test Cases JSON
                  │       parsed.json      │
                  └────────────────────────┘
```

---

### 2.2 End-to-End Detailed Execution Flowchart

```
 [CLI Invocation] python agents/doc_parser.py --frd <path> --tc <path> --out <dir> --skip-types "Security,Performance"
        │
        ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Step 1: Input Validation & CLI Argument Parsing                                       │
 │ - Parse --frd, --tc, --out, and --skip-types                                           │
 │ - Reconfigure stdout to UTF-8 for cross-platform console safety                        │
 └───────────────────────────────────┬────────────────────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Step 2: FRD Parsing Engine (parse_frd)                                                 │
 │ - Read FRD .docx via python-docx                                                       │
 │ - Traverse raw body XML elements sequentially (iter_body_elements)                     │
 │ - Detect "Requirement ID:" paragraph signals via REGEX_REQUIREMENT_ID                   │
 │ - Extract feature_id (e.g., FR-001) and feature_name                                    │
 │ - Extract 2-column requirement table (Description, Actors, Pre-conditions,             │
 │   Trigger, Main Flow, Exception Flow, Post-conditions, Business Rules, Priority)       │
 │ - Instantiate FeatureModel dataclass and build features_by_id dictionary               │
 └───────────────────────────────────┬────────────────────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Step 3: Manual Test Case Parsing Engine (parse_test_cases)                             │
 │ - Read Manual Test Cases .docx via python-docx                                         │
 │ - Read Table Header Row 0 to build dynamic col_index mapping                           │
 │   (Test Name, Type, Subject, Description, Expected Result, Status)                     │
 └───────────────────────────────────┬────────────────────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Step 4: Row-by-Row Filtering & Multi-Tier Fuzzy Matching                               │
 │ - For each test case row:                                                              │
 │   1. Check if Type contains any --skip-types keyword → [SKIP] if matched               │
 │   2. Extract TC ID (e.g., TC-001) via REGEX_TC_ID                                       │
 │   3. Pass Subject to match_subject_to_feature():                                       │
 │      - Tier 1: Substring match against feature_name_map                                │
 │      - Tier 2: Stemmed partial word-overlap tokenization                               │
 │      - Tier 3: Levenshtein distance fallback (difflib)                                 │
 └───────────────────────────────────┬────────────────────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Step 5: FRD Context Enrichment & Tag Synthesis                                         │
 │ - Look up parent FeatureModel in features_by_id using resolved feature_ref             │
 │ - Instantiate FeatureContextModel containing:                                          │
 │   - feature_name, description, actors, pre_conditions, business_rules, exception_flows │
 │ - Synthesize Cucumber @tags (@type, @subject, @feature_ref)                            │
 │ - Instantiate enriched TestCaseModel dataclass                                         │
 └───────────────────────────────────┬────────────────────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Step 6: Response DTO Construction & JSON Serialization                                 │
 │ - Instantiate ParsedDocumentResponse DTO containing:                                    │
 │   - project ("ShopSphere"), version ("2.0"), summary, test_cases                       │
 │ - Write formatted JSON payload to output/shopsphere_parsed.json                        │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Step-by-Step Flow Explanation

### Phase 1: Input Setup & CLI Parsing
The script reads command-line flags via `parse_args()` and initializes logging parameters. Console encoding is reconfigured to UTF-8 to ensure clean terminal output across platforms.

### Phase 2: Dynamic FRD Document Parsing
1. **Document Loading**: Opens the FRD `.docx` document.
2. **Block-Level Element Traversal**: `iter_body_elements()` traverses raw XML elements (`p` paragraphs and `tbl` tables) sequentially.
3. **Heading Signal Detection**: Scans paragraph text for `Requirement ID:`. When matched, it extracts `feature_id` (e.g. `FR-001`) and `feature_name` using `REGEX_REQUIREMENT_ID`.
4. **KeyValue Table Extraction**: Traverses the 2-column table following each heading. Cells are dynamically mapped to attributes (`description`, `actors`, `pre_conditions`, `trigger`, `main_flow`, `exception_flow`, `post_conditions`, `business_rules`, `priority`).
5. **Lookup Dictionary Construction**: Stores parsed features in a `features_by_id` dictionary (`FR-001` $\rightarrow$ `FeatureModel`).

### Phase 3: Test Case Extraction & Filtering
1. **Header Row Discovery**: Scans table header row 0 to discover column positions (`Test Name`, `Type`, `Subject`, `Description`, `Expected Result`).
2. **Configurable Skip Filter**: Evaluates test type strings against `--skip-types` keywords. Any matching row (e.g., `Security`, `Performance`) is logged and skipped.
3. **Step Tokenization**: Splits numbered description text into clean step arrays via `split_numbered_steps()`.

### Phase 4: Multi-Tier Fuzzy Matching
To link manual test subjects to FRD requirements (e.g. subject `"Coupons & Discounts"` to requirement `"FR-010 — Coupon & Discount Engine"`), `match_subject_to_feature()` executes a 3-tiered matching strategy:
- **Tier 1 (Substring)**: Direct string containment check.
- **Tier 2 (Word Overlap / Stemming)**: Non-alphanumeric tokenization and partial word stem matching.
- **Tier 3 (Fuzzy Fallback)**: Levenshtein distance similarity matching (`difflib.get_close_matches`).

### Phase 5: FRD Context Enrichment & Tag Generation
1. **Context Embedding**: Constructs a `FeatureContextModel` from the parent feature and attaches it to the test case.
2. **Cucumber Tag Synthesis**: Generates unique, normalized tags (e.g., `@ui_form_validation`, `@registration`, `@fr_001`).

### Phase 6: JSON Serialization
The parser instantiates `ParsedDocumentResponse` and serializes the complete dataset to `output/shopsphere_parsed.json`.

---

## 4. Module & File Specifications

| File Path | Purpose / Responsibility | Key Exports / Elements |
| :--- | :--- | :--- |
| **[agents/constants.py](file:///c:/Users/2862390/Desktop/New%20folder%20%283%29/vishnu%20branch/agents/constants.py)** | Single source of truth for static string signals, regexes, and keys. | Precompiled regexes (`REGEX_REQUIREMENT_ID`, `REGEX_TC_ID`, `REGEX_NUMBERED_STEPS`), XML tags, table keys, and default schema keys. |
| **[agents/models.py](file:///c:/Users/2862390/Desktop/New%20folder%20%283%29/vishnu%20branch/agents/models.py)** | Strongly typed Data Transfer Objects (DTOs) ensuring output compliance. | `FeatureModel`, `FeatureContextModel`, `TestCaseModel`, `ParserSummaryModel`, `ParsedDocumentResponse`. |
| **[agents/doc_parser.py](file:///c:/Users/2862390/Desktop/New%20folder%20%283%29/vishnu%20branch/agents/doc_parser.py)** | Core execution script that reads `.docx` files and writes `shopsphere_parsed.json`. | `parse_frd()`, `parse_test_cases()`, `match_subject_to_feature()`, `main()`. |

---

## 5. Execution Guide & CLI Commands

### Command Syntax
Run the parser from the repository root:

```powershell
python agents/doc_parser.py `
  --frd "ShopSphere_Functional_Requirements_Document.docx" `
  --tc "ShopSphere_Manual_Testcases.docx" `
  --out "output" `
  --skip-types "Security,Performance"
```

### Console Log Output Sample
```text
[INFO] FRD File : ShopSphere_Functional_Requirements_Document.docx
[INFO] TC File  : ShopSphere_Manual_Testcases.docx
[INFO] Out Dir  : output
[INFO] Skip     : ['Security', 'Performance']

[PARSING] Parsing FRD...
  [FRD] FR-001 - User Registration & Authentication
  [FRD] FR-002 - Product Catalog & Search
  [FRD] FR-003 - Shopping Cart Management
  ...

[PARSING] Parsing & Enriching Manual Test Cases with FRD Context...
  [TC] TC-001 - User Registration — Valid Details [-> FR-001 (Enriched)]
  [TC] TC-002 - User Registration — Duplicate Email [-> FR-001 (Enriched)]
  ...
  [SKIP] Skipping TC-025 (type: UI Field-Level Validation — Security)

[SUCCESS] Document Parsing Complete!
  Features parsed              : 10
  Test cases parsed & enriched : 22
  Output saved to              : output\shopsphere_parsed.json
```

---

## 6. Output Schema Specification (`shopsphere_parsed.json`)

```json
{
  "project": "ShopSphere",
  "version": "2.0",
  "summary": {
    "total_test_cases": 22,
    "skipped_types": [
      "Security",
      "Performance"
    ]
  },
  "test_cases": [
    {
      "tc_id": "TC-001",
      "title": "User Registration — Valid Details",
      "type": [
        "UI Form Validation"
      ],
      "subject": "Registration",
      "feature_ref": "FR-001",
      "execution_status": "Pass",
      "steps": [
        "Navigate to shop.shopsphere.com and click \"Sign Up.\"",
        "Enter a unique valid email, full name, and a password meeting complexity rules.",
        "Click \"Create Account.\""
      ],
      "expected_result": "Account is created, welcome email is sent via SendGrid, and the user is auto-logged-in and redirected to the homepage.",
      "cucumber_tags": [
        "@ui_form_validation",
        "@registration",
        "@fr_001"
      ],
      "feature_context": {
        "feature_name": "User Registration & Authentication",
        "description": "Allow new customers to create an account using email/password or federated OAuth 2.0 login...",
        "actors": [
          "Guest User",
          "Registered Customer"
        ],
        "pre_conditions": [
          "User has a valid, unused email address (for email/password registration) or an existing Google/Facebook account."
        ],
        "business_rules": [
          "Passwords must meet complexity rules",
          "OAuth-created accounts do not require a password",
          "duplicate emails are rejected at the database and API validation layers."
        ],
        "exception_flows": [
          "If the email already exists, the system displays \"An account with this email already exists\" and offers a login link."
        ]
      }
    }
  ]
}
```
