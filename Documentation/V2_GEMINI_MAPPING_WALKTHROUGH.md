# 🏗️ Baxter Version 2 Parser — Full AST Extraction & Gemini Mapping Walkthrough

## Executive Summary

Stage 1 (Document Parser) processes Functional Requirements Documents (FRD) and Manual Test Case Suites into a self-contained, 100% complete **JSON Knowledge Artifact** (`shopsphere_parsed.json`).

**Key Architectural Guarantees:**
1. **Zero LLM Hallucination for Parsing**: 100% of document content is extracted deterministically using `python-docx` heading-level XML tree traversal.
2. **100% Document Coverage**: Extracts all 15 tables and 89 paragraphs (Scope, References, 10 Functional Requirements, Performance SLAs, System Interfaces, 7 NFR categories, Glossary, and Attachments).
3. **1 Batched Gemini API Call for Mapping**: Instead of calling Gemini for every test case, the entire test suite is mapped in **one batched API call** using a ~1,000 token Compact Section Index.
4. **Rate Limit Compliant**: Uses only **1** call of the 500 RPD (Requests Per Day) free quota for `gemini-3.5-flash-lite` / `gemini-3.1-flash-lite`.

---

## 1. End-to-End Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Full AST Extraction (Python Code — 0 LLM Calls)                     │
│                                                                             │
│ • python-docx traverses XML element hierarchy in document order.            │
│ • Extracts all 32 sections into a structured DocumentAST tree.             │
│ • Classifies tables into key_value (FRs) and data_grid (Interfaces/Perf).   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Compact Section Index Construction (Python Code — 0 LLM Calls)      │
│                                                                             │
│ • Extracts high-density fields (FR description + business rules, NFR text)  │
│ • Constructs a ~1,000 token Compact Section Index summarizing all 32 ids.  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Single Batched Gemini Mapping Call (1 LLM Call)                     │
│                                                                             │
│ • Model: gemini-3.5-flash-lite / gemini-3.1-flash-lite                      │
│ • Input: Compact Section Index + All Test Cases (~5,000 tokens input)        │
│ • Output: Structured Pydantic Response mapping each TC -> List[ref_id]      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Post-Processing & Tag Synthesis (Python Code — 0 LLM Calls)         │
│                                                                             │
│ • Python looks up ref_ids in DocumentAST and embeds FULL section text.      │
│ • Auto-synthesizes Cucumber tags (@fr_001, @nfr_sec, @sendgrid, etc.).       │
│ • Writes final self-contained knowledge_artifact.json (shopsphere_parsed).  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Detailed Step Specifications & AST Structure

### Step 1: Full AST Extraction (Deterministic Code)

Every `.docx` element is evaluated sequentially by its XML heading style:
- `Heading 1` / `Heading 2` with `"Requirement ID:"` → `functional_requirements[]`
- `Heading 2` with `"8.1 Security"`, `"8.2 Usability"`, etc. → `non_functional_requirements{}`
- `Heading 1` with `"6. Performance"` / Table 13 → `performance_requirements[]`
- `Heading 1` with `"7. Interfaces"` / Table 14 → `system_interfaces[]`
- `Heading 1` with `"9. Glossary"` / Table 15 → `glossary{}`

**Extracted Sections (32 Total):**
`META`, `SEC-1 (Purpose)`, `SEC-2 (Scope)`, `SEC-3 (References)`, `SEC-4 (Overview)`, `FR-001` to `FR-010`, `NFR-PERF`, `NFR-SEC`, `NFR-USAB`, `NFR-REL`, `NFR-SCAL`, `NFR-MAINT`, `NFR-COMP`, `NFR-AUDIT`, `INTF-STRIPE`, `INTF-FEDEX`, `INTF-SENDGRID`, `INTF-TWILIO`, `INTF-OAUTH`, `INTF-S3`, `INTF-ELASTIC`, `INTF-ANALYTICS`, `GLOSS`, `ATTACHMENTS`.

---

### Step 2: Compact Section Index (Deterministic Code)

Python builds a high-density index (~1,000 tokens total) used strictly for mapping:

```text
[FR-001] User Registration & Auth: Email/password, OAuth 2.0 (Google, FB). Password complexity. Duplicate email rejection at DB + API. Reset link 30m via SendGrid. JWT 15m. Rate limit 100/min.
[FR-002] Product Catalog & Search: Keyword search via Elasticsearch, category/price/brand filters, zero results suggestions, Postgres fallback.
[FR-003] Shopping Cart Management: Persistent cart, Redis cache, real-time stock check, max 10 per SKU.
...
[NFR-SEC] Security: TLS 1.3, AES-256, PCI-DSS SAQ-A via Stripe.js, OWASP Top 10 (parameterized queries, input sanitization, CSRF), WAF, JWT 15m.
[NFR-PERF] Performance: Page load ≤1.5s, Cart API ≤500ms, Checkout ≤3s, Search ≤300ms, 5K concurrent checkouts.
[INTF-SENDGRID] SendGrid: Transactional email content, delivery status webhooks.
[INTF-STRIPE] Stripe: Payment intents, client tokenization, charge & refund status.
[GLOSS] Glossary: SKU, JWT, OAuth 2.0, PCI-DSS, SLA, WAF, Idempotency Key, Webhook, RTO/RPO, p95.
```

---

### Step 3: Single Batched Gemini Mapping API Call

We make **one single API call** using LangChain / `google-generativeai` with a Pydantic schema:

#### Pydantic Schema
```python
from pydantic import BaseModel, Field
from typing import List

class MappedRef(BaseModel):
    ref_id: str = Field(description="ID of mapped section e.g. FR-001, NFR-SEC, INTF-SENDGRID")
    confidence: float = Field(description="Confidence score 0.0 to 1.0")
    reason: str = Field(description="1-sentence reason for mapping")

class TestCaseMapping(BaseModel):
    tc_id: str = Field(description="Test case ID e.g. TC-001")
    mapped_refs: List[MappedRef]

class BatchMappingResponse(BaseModel):
    mappings: List[TestCaseMapping]
```

#### Gemini Prompt Structure
```text
SYSTEM PROMPT:
You are a Senior QA Requirements Traceability Expert.
Given the Compact Document Index and a batch of Test Cases, map each Test Case to ALL relevant Section IDs (Functional, NFRs, System Interfaces).

COMPACT DOCUMENT INDEX:
{compact_index}

BATCH OF TEST CASES:
TC-001: "User Registration — Valid Details" | Steps: Navigate to Sign Up, enter email/pass, Submit | Expected: Account created, welcome email via SendGrid, auto-logged-in
TC-014: "Guest Checkout — Full Flow" | Steps: Add product, Proceed to Checkout, enter address, Pay via card | Expected: Order placed without account, email received
TC-025: "Security — SQL Injection Attempt on Search" | Steps: Enter ' OR '1'='1 in search bar | Expected: Query parameterized, safe response, attempt logged for security monitoring
...

Return JSON adhering strictly to the BatchMappingResponse schema.
```

---

## 3. Real Example Walkthroughs on ShopSphere Sample Documents

Let me walk through **4 specific test cases** from `ShopSphere_Manual_Testcases.docx` to demonstrate how mapping functions in practice:

### Example 1: TC-001 — Simple, Obvious Mapping

**Input Test Case:**
- **TC-001**: `"User Registration — Valid Details"`
- **Steps**: Navigate to `shop.shopsphere.com` → Click `Sign Up` → Enter email/pass → Submit
- **Expected**: Account created, welcome email sent via SendGrid, user auto-logged-in

**Gemini Mapping Result:**
- `FR-001` (Primary: 0.95) — Direct registration flow
- `INTF-SENDGRID` (Secondary: 0.90) — Verifies welcome email delivery
- `NFR-SEC` (Secondary: 0.75) — Password complexity & email uniqueness rules

**Enriched Artifact Output:**
- `mapped_context`: Full text of `FR-001`, `INTF-SENDGRID`, and `NFR-SEC` embedded.
- `cucumber_tags`: `["@ui_form_validation", "@registration", "@fr_001", "@nfr_sec", "@sendgrid"]`.

---

### Example 2: TC-014 — Cross-Cutting, Multi-Requirement Test

**Input Test Case:**
- **TC-014**: `"Guest Checkout — Full Flow"`
- **Steps**: Add product to cart without login → Proceed to Checkout → Enter shipping → Pay via card → Confirm
- **Expected**: Order placed without account creation, confirmation email received, order appears in guest order lookup

**Gemini Mapping Result:**
- `FR-004` (Primary: 0.95) — 2-step checkout & payment
- `FR-003` (Secondary: 0.85) — Cart management & stock validation
- `FR-001` (Secondary: 0.80) — Guest checkout registration bypass
- `FR-009` (Secondary: 0.80) — Order confirmation notification
- `INTF-STRIPE` (Secondary: 0.90) — Card payment tokenization

**Why this matters:**
A guest checkout test touches 5 functional requirements and 2 non-functional areas. V1 gave context from only 1 (FR-004). V2 gives the full picture, so Cucumber/Selenium generation receives complete pre-conditions, payment rules, and email verification points.

---

### Example 3: TC-025 — NFR Security Test

**Input Test Case:**
- **TC-025**: `"Security — SQL Injection Attempt on Search"`
- **Steps**: Enter `' OR '1'='1` in search bar → Submit
- **Expected**: Query parameterized, no data exposed, normal "no results" response, attempt logged for security monitoring

**Gemini Mapping Result:**
- `NFR-SEC` (Primary: 0.95) — OWASP Top 10 input sanitization & parameterized queries
- `FR-002` (Secondary: 0.75) — Search bar feature component
- `NFR-AUDIT` (Secondary: 0.65) — Logging security monitoring attempt

**Why this matters:**
V1 mapped this to `FR-002 (Product Catalog & Search)` because of the word "Search". V2 correctly identifies `NFR-SEC` as the primary requirement being tested.

---

### Example 4: TC-004 — Negative Authentication Test

**Input Test Case:**
- **TC-004**: `"Login — Invalid Password"`
- **Steps**: Navigate to Login → Enter registered email with wrong password → Submit
- **Expected**: System displays "Invalid email or password" without revealing which field is wrong, increments failed-attempt counter for rate limiting

**Gemini Mapping Result:**
- `FR-001` (Primary: 0.95) — Direct login authentication flow
- `NFR-SEC` (Secondary: 0.90) — Rate limiting details (100 req/min per IP on auth endpoints) & generic error messages
- `NFR-AUDIT` (Secondary: 0.70) — Failed login attempt audit logging

---

## 4. Final Output JSON Schema (`shopsphere_parsed.json`)

```json
{
  "project": "ShopSphere",
  "version": "2.0",
  "summary": {
    "total_test_cases": 23,
    "frd_coverage": "100%",
    "frd_sections_extracted": 32,
    "mapping_api_calls": 1
  },
  "test_cases": [
    {
      "tc_id": "TC-001",
      "title": "User Registration — Valid Details",
      "type": ["UI Form Validation"],
      "subject": "Registration",
      "execution_status": "Pass",
      "steps": [
        "Navigate to shop.shopsphere.com and click 'Sign Up.'",
        "Enter a unique valid email, full name, and a password meeting complexity rules.",
        "Click 'Create Account.'"
      ],
      "expected_result": "Account is created, welcome email is sent via SendGrid, and user is auto-logged-in.",
      "cucumber_tags": [
        "@ui_form_validation",
        "@registration",
        "@fr_001",
        "@nfr_sec",
        "@sendgrid"
      ],
      "mapped_context": {
        "primary_feature": {
          "feature_id": "FR-001",
          "feature_name": "User Registration & Authentication",
          "description": "Allow new customers to create an account using email/password or OAuth 2.0...",
          "actors": ["Guest User", "Registered Customer"],
          "pre_conditions": ["User has a valid, unused email address or OAuth account"],
          "business_rules": [
            "Passwords must meet complexity rules",
            "OAuth-created accounts do not require a password",
            "Duplicate emails rejected at database and API validation layers"
          ],
          "exception_flows": ["If email exists, display error and link to login"]
        },
        "secondary_nfrs": [
          {
            "category": "security",
            "rules": [
              "TLS 1.3 in transit, AES-256 at rest",
              "OWASP Top 10 mitigations enforced",
              "JWT access tokens expire after 15 minutes",
              "Rate limiting: 100 req/min per IP on auth endpoints"
            ]
          }
        ],
        "secondary_interfaces": [
          {
            "system": "SendGrid",
            "interface_type": "REST API",
            "direction": "Outbound",
            "data_exchanged": "Transactional email content & delivery status webhooks"
          }
        ]
      }
    }
  ]
}
```

---

## 5. API Quota & Efficiency Summary

| Metric | Value |
|---|---|
| FRD Content Extracted | 100% (15 tables, 89 paragraphs, 32 sections) |
| Extraction LLM Calls | **0** (100% deterministic code) |
| Mapping LLM Calls | **1** (Batched Gemini call for all 23 TCs) |
| Free Quota Consumption | **1 / 500 RPD** (0.2% of daily limit) |
| Prompt Input Tokens | ~5,000 tokens total |
| Response Output Tokens | ~600 tokens total |
| Execution Time | ~1.5 seconds total for mapping |
