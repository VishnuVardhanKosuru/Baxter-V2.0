# 🎯 V2 Parser — Correct Architecture (Rethinking the Whole Pipeline)

## What We Got Wrong in the Previous Analysis

The previous docs (CONTENT_AWARE_MATCHING_APPROACHES.md) spent a lot of effort on how to **match test cases to requirements** using embeddings and LLMs. But that's solving the wrong problem.

**Baxter's actual job:**
```
Manual Test Cases (.docx) + FRD (.docx)
        ↓
  [ Parser (Stage 1) ]  →  knowledge_artifact.json
        ↓
  [ Code Generator (Stage 2) ]  →  Cucumber .feature + Selenium .py + CSV
```

The parser's output feeds directly into an **LLM prompt** in `cs_agent.py`. The LLM reads the test case JSON (including `feature_context`) and generates all three artifacts. **The LLM is the one that needs the context, not us.**

So the real question is NOT "how do we match TC-001 to FR-001?" — it's: **"how do we give the LLM code generator enough context from the FRD to generate accurate, production-quality Cucumber and Selenium code?"**

---

## How V1 Works Today (The Actual Data Flow)

```
                    V1 PIPELINE
                    ──────────

Parser extracts:
  TC-001:
    title: "User Registration — Valid Details"
    steps: ["Navigate to Sign Up", "Enter email/password", "Click Create Account"]
    expected: "Account is created, welcome email sent"
    feature_context:              ← THIS is what matching produces
      feature_name: "User Registration & Authentication"
      description: "Allow new customers to create an account..."
      actors: ["Guest User", "Registered Customer"]
      pre_conditions: [...]
      business_rules: ["Passwords must meet complexity rules", ...]
      exception_flows: [...]

Code Generator receives:
  json.dumps(tc)  ←  The ENTIRE test case dict (including feature_context)
                      is dumped as JSON and sent to the LLM prompt

LLM generates:
  1. CSV rows (step-by-step execution matrix)
  2. Cucumber .feature (Gherkin BDD scenarios)
  3. Selenium pytest script
```

**The `feature_context` is the ONLY FRD data the LLM sees.** And in V1, it's just the one FR requirement that the fuzzy matcher picked.

---

## Why This Matters: What the LLM is Missing

When the LLM generates Cucumber + Selenium for `TC-001 (User Registration)`, it needs to know:

| Context Needed | Available in V1? | Impact When Missing |
|---|---|---|
| FR-001 description, flows, business rules | ✅ Yes (via feature_context) | — |
| **What passwords "complexity rules" actually are** | ❌ No — just says "must meet complexity rules" | LLM guesses: `"Test@123"`. Real rule might be: min 12 chars, no dictionary words |
| **The OAuth flow** (Google/Facebook login) | ❌ Partial — mentioned in description but no steps | LLM skips OAuth test scenarios entirely |
| **URL structure** (`shop.shopsphere.com/signup`) | ❌ No — LLM guesses URLs | Selenium `driver.get()` uses wrong URLs |
| **API endpoints** (`POST /api/auth/register`) | ❌ No — not in FRD, would be in OpenAPI spec (Attachment C) | No API-level assertions in Selenium |
| **Error messages** ("An account with this email already exists") | ✅ Yes (in exception_flow) | — |
| **Tech stack** (React 18, Stripe.js, SendGrid) | ❌ No — Scope section not parsed | LLM can't generate framework-appropriate selectors |
| **Performance targets** (page load ≤1.5s) | ❌ No — Section 6 not parsed | No performance assertions in tests |
| **Security rules** (CSRF tokens, rate limiting) | ❌ No — Section 8 not parsed | Security test cases generated blindly |
| **WCAG requirements** (keyboard nav, screen reader) | ❌ No — Section 8.2 not parsed | Accessibility tests impossible |
| **Glossary** (what "SKU" or "idempotency key" means) | ❌ No — Section 9 not parsed | LLM may misinterpret domain terms |

**The LLM code generator is working with ~20% of the available context.** It's generating test code from incomplete information and filling the gaps with assumptions.

---

## The Correct V2 Architecture

### Core Insight: The Parser Doesn't Need to "Match" — It Needs to Build a Rich Knowledge Artifact

The matching problem goes away when you realize:

1. **The parser's job is EXTRACTION, not mapping** — Parse the entire FRD into a complete knowledge artifact. Parse all test case files. Done.
2. **The code generator's job is CONTEXT SELECTION** — When generating code for TC-001, select the relevant slices of the knowledge artifact to include in the LLM prompt.
3. **The LLM naturally understands which FRD sections are relevant** — You don't need embeddings or fuzzy matching to tell an LLM that a registration test relates to FR-001. The LLM reads the test case steps and the requirement description and figures it out.

```
V1 ARCHITECTURE (Wrong)                V2 ARCHITECTURE (Correct)
────────────────────────                ─────────────────────────

Parser:                                 Parser:
  Read FRD (partial)                      Read ENTIRE FRD → DocumentAST
  Read TC doc (partial)                   Read ALL TC files → TestCases[]
  Match TC ↔ FR (fuzzy)                   Serialize everything → knowledge_artifact.json
  Attach feature_context                  NO matching, NO mapping
  Output: test_cases[] with context       Output: complete knowledge artifact

Code Generator:                         Code Generator:
  For each TC:                            For each TC:
    Send TC JSON to LLM                     Select relevant context slices
    (only feature_context)                  Send TC + context slices to LLM
    LLM generates with partial data         LLM generates with FULL context
```

### The V2 Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 1: FULL DOCUMENT PARSER (deterministic, zero LLM)         │
│                                                                   │
│  FRD.docx → Full AST extraction:                                 │
│    • metadata (author, version, date, status)                    │
│    • scope (in-scope items, out-of-scope, tech stack)            │
│    • references (linked documents, APIs, specs)                  │
│    • enhancement_overview (background, proposal, business KPIs)  │
│    • functional_requirements[] (FR-001..FR-010 with all fields)  │
│    • performance_requirements[] (8 NFR targets with metrics)     │
│    • system_interfaces[] (Stripe, SendGrid, FedEx, etc.)         │
│    • non_functional_requirements{} (security, usability, etc.)   │
│    • glossary{} (domain term definitions)                        │
│    • attachments[] (referenced artifacts)                        │
│                                                                   │
│  TC_folder/ → Multi-file test case extraction:                   │
│    • test_cases[] from all .docx/.xlsx files, all tables          │
│                                                                   │
│  Output: knowledge_artifact.json (complete, no matching)          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 2: CONTEXT-AWARE CODE GENERATOR                           │
│                                                                   │
│  For each test case:                                             │
│                                                                   │
│  1. BUILD CONTEXT WINDOW:                                        │
│     Start with the test case itself (steps, expected result)     │
│     + Always include: scope.in_scope, glossary                   │
│     + Include relevant FRs based on test subject/type/steps      │
│     + Include relevant NFRs based on test type:                  │
│       - Type contains "Security" → include nfr.security          │
│       - Type contains "Performance" → include perf_requirements  │
│       - Type contains "Accessibility" → include nfr.usability    │
│     + Include relevant interfaces if test mentions integrations  │
│                                                                   │
│  2. SEND TO LLM:                                                 │
│     Prompt: test_case + selected_context → generate 3 artifacts  │
│                                                                   │
│  3. OUTPUT:                                                       │
│     CSV rows + Cucumber .feature + Selenium pytest               │
└──────────────────────────────────────────────────────────────────┘
```

### Why This Eliminates the Matching Problem

**V1**: Parser must figure out `TC-001 → FR-001` via fuzzy matching, then attach FR-001's context to TC-001.

**V2**: Parser doesn't match anything. The code generator builds a context window by including:
- The test case itself
- The scope section (always — tells the LLM what tech stack to target)
- All FRs whose names contain words from the TC subject (simple keyword filter, not fuzzy matching)
- NFR sections matching the TC type
- The glossary (always — helps LLM understand domain terms)

The LLM then reads the test steps alongside the requirement content and **naturally generates code that aligns with the requirement** — because it has the actual context, not a fuzzy-matched label.

```python
# V2: Context selection is SIMPLE — no embeddings, no fuzzy matching needed

def build_context_for_tc(tc: dict, knowledge: dict) -> dict:
    """
    Select relevant slices of the knowledge artifact for this test case.
    This is NOT matching — it's context windowing for the LLM prompt.
    """
    context = {
        "project": knowledge["project"],
        "scope": knowledge["scope"],          # Always include — tech stack context
        "glossary": knowledge["glossary"],    # Always include — domain terms
    }

    # Include FRs whose name overlaps with TC subject or title
    tc_words = set(
        (tc.get("subject", "") + " " + tc.get("title", "")).lower().split()
    )
    # Remove stop words
    tc_words -= {"the", "a", "an", "and", "or", "for", "in", "on", "with", "—", "-"}

    relevant_frs = []
    for fr in knowledge["functional_requirements"]:
        fr_words = set(fr["name"].lower().split())
        if tc_words & fr_words:  # Any word overlap
            relevant_frs.append(fr)

    # If no overlap found, include ALL FRs (let the LLM sort it out)
    # This is safe because FRs are typically 10-20 items, small enough
    context["functional_requirements"] = relevant_frs or knowledge["functional_requirements"]

    # Include NFRs based on test type
    tc_type = " ".join(tc.get("type", [])).lower() if isinstance(tc.get("type"), list) else tc.get("type", "").lower()
    tc_text = f"{tc_type} {tc.get('title', '')} {tc.get('subject', '')}".lower()

    nfr = knowledge.get("non_functional_requirements", {})
    if any(kw in tc_text for kw in ["security", "injection", "xss", "auth", "csrf"]):
        context["nfr_security"] = nfr.get("security", [])
    if any(kw in tc_text for kw in ["performance", "load", "latency", "speed"]):
        context["performance_requirements"] = knowledge.get("performance_requirements", [])
    if any(kw in tc_text for kw in ["accessibility", "wcag", "screen reader", "keyboard"]):
        context["nfr_usability"] = nfr.get("usability", [])
    if any(kw in tc_text for kw in ["compliance", "gdpr", "ccpa", "pci"]):
        context["nfr_compliance"] = nfr.get("compliance", [])

    # Include interfaces if TC mentions integration points
    if any(kw in tc_text for kw in ["stripe", "payment", "sendgrid", "email", "sms", "shipping"]):
        context["system_interfaces"] = knowledge.get("system_interfaces", [])

    return context
```

---

## Is the Embedding/LLM Matching Approach Optimal?

**No. Here's why:**

| Aspect | Embedding/LLM Matching | Simple Context Windowing |
|--------|----------------------|--------------------------|
| **Complexity** | High — needs sentence-transformers, embedding index, threshold tuning | Low — keyword filter + include-all fallback |
| **Accuracy** | Over-engineered — 95% of matches are obvious (Registration → FR-001) | Same effective accuracy — the LLM in Stage 2 does the real understanding |
| **Dependencies** | `sentence-transformers` (80MB model), `numpy`, `scipy` | Zero additional dependencies |
| **What it solves** | "Which FR does this TC belong to?" | "What context does the LLM need to generate good code?" |
| **The actual need** | We don't need a mapping table | We need the LLM to have enough context to write correct Selenium |
| **For 10 FRs** | Massive overkill — embeddings for 10 items? | Just include all 10 FRs — they total ~2K tokens |
| **For 500 FRs** | Makes more sense at scale (context window limits) | Still works with keyword filtering to select top 10-20 |
| **Maintenance** | Model versioning, threshold tuning, index rebuilds | Zero maintenance — just keyword lists |

### When Would Embeddings Actually Be Needed?

Only when:
- **500+ functional requirements** in a single FRD (rare — most enterprise FRDs have 20-100)
- **The combined text of all relevant context exceeds the LLM context window** (~100K tokens for Gemini)
- **Requirements use completely different vocabulary than test cases** across the entire document

For Baxter's current scale (10 FRs, 23 TCs, 15 tables), embeddings add complexity with zero benefit.

---

## The Optimal V2 Parser Architecture (Revised)

```
Parser responsibilities (Stage 1):
  ✅ Extract EVERYTHING from the FRD deterministically
  ✅ Extract ALL test cases from the TC folder
  ✅ Produce a single knowledge_artifact.json
  ❌ Do NOT match test cases to requirements
  ❌ Do NOT use LLMs for parsing
  ❌ Do NOT use embeddings

Code Generator responsibilities (Stage 2):
  ✅ For each TC, build a context window from knowledge_artifact.json
  ✅ Context selection via simple keyword filtering
  ✅ Include scope + glossary always (small, universally useful)
  ✅ Include matching FRs + type-relevant NFRs
  ✅ Send TC + context to LLM → generate Cucumber + Selenium + CSV
```

### Revised Knowledge Artifact Output (What Parser Produces)

```json
{
  "_schema": "baxter_knowledge_artifact_v2",

  "project": { "name": "ShopSphere", "version": "2.0", "release": "..." },

  "document_metadata": { "author": "...", "date": "...", "status": "..." },

  "scope": {
    "in_scope": ["React 18 + Redux Toolkit", "Node.js / Express API", "..."],
    "out_of_scope": ["Native mobile apps", "..."],
    "tech_stack": ["React 18", "Redux Toolkit", "Node.js", "Express",
                   "PostgreSQL", "Redis", "Stripe", "SendGrid", "Twilio",
                   "Elasticsearch", "AWS S3", "Kubernetes (EKS)"]
  },

  "functional_requirements": [
    {
      "id": "FR-001",
      "name": "User Registration & Authentication",
      "description": "...",
      "actors": ["Guest User", "Registered Customer"],
      "pre_conditions": ["..."],
      "trigger": "...",
      "main_flow": ["Step 1...", "Step 2..."],
      "exception_flow": ["If email exists..."],
      "post_conditions": ["..."],
      "business_rules": ["Passwords must meet complexity rules", "..."],
      "priority": "High"
    }
  ],

  "performance_requirements": [
    { "parameter": "Page Load Time (p95)", "target": "≤ 1.5s on 4G" },
    { "parameter": "API Response — Cart", "target": "≤ 500ms at p95" }
  ],

  "system_interfaces": [
    {
      "system": "Stripe",
      "type": "REST API / Webhooks",
      "direction": "Bidirectional",
      "data": "Payment intents, tokens, charge & refund status"
    }
  ],

  "non_functional_requirements": {
    "security": ["TLS 1.3", "PCI-DSS SAQ-A via Stripe.js", "OWASP Top 10", "..."],
    "usability": ["WCAG 2.1 AA", "Mobile-first", "Max 2 screens / 3 clicks checkout"],
    "reliability": ["Circuit breakers on all integrations", "PostgreSQL failover RTO 5 min"],
    "compliance": ["GDPR right-to-erasure within 30 days", "CCPA opt-out", "PCI-DSS v4.0"]
  },

  "glossary": {
    "SKU": "Stock Keeping Unit",
    "JWT": "JSON Web Token — signed token for API auth",
    "Idempotency Key": "Unique key ensuring payment processed exactly once"
  },

  "test_cases": [
    {
      "tc_id": "TC-001",
      "title": "User Registration — Valid Details",
      "type": ["UI Form Validation"],
      "subject": "Registration",
      "steps": ["Navigate to Sign Up", "Enter email/password", "Click Create Account"],
      "expected_result": "Account created, welcome email sent, user auto-logged-in",
      "execution_status": "Pass",
      "source_file": "ShopSphere_Manual_Testcases.docx"
    }
  ],

  "parsing_stats": {
    "frd_coverage": "100%",
    "frd_paragraphs": 89,
    "frd_tables": 15,
    "tc_files_parsed": 1,
    "tc_total": 23
  }
}
```

### What the Code Generator Prompt Looks Like in V2

```python
# V2: The LLM gets RICH context, not just a feature_context blob

V2_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a senior QA Automation Engineer expert in BDD, Cucumber, and Selenium.\n\n"

        "You have access to the following PROJECT CONTEXT:\n"
        "─────────────────────────────────────\n"
        "TECH STACK: {tech_stack}\n"
        "GLOSSARY: {glossary}\n\n"

        "RELEVANT REQUIREMENTS:\n{requirements_context}\n\n"

        "RELEVANT NON-FUNCTIONAL REQUIREMENTS:\n{nfr_context}\n\n"

        "RELEVANT SYSTEM INTERFACES:\n{interfaces_context}\n\n"

        "Using this context, generate all THREE artifacts for the test case below.\n"
        "Your Selenium selectors should target {tech_stack} components.\n"
        "Use the glossary definitions when interpreting domain terms.\n"
        "Apply business rules from the requirements as assertions.\n"
        "For payment tests, use Stripe test card numbers.\n"
        "Base URL: {base_url}\n\n"

        "━━ ARTIFACT 1 — csv_rows ━━\n"
        "...(same rules as V1)...\n\n"

        "━━ ARTIFACT 2 — cucumber_feature ━━\n"
        "...(same rules as V1)...\n\n"

        "━━ ARTIFACT 3 — selenium_script ━━\n"
        "...(same rules as V1, but now the LLM knows the tech stack)...\n"
    ),
    (
        "human",
        "Test Case:\n{tc_json}\n\n"
        "Generate all three artifacts now."
    ),
])
```

### Concrete Example: What Changes for TC-001

**V1 LLM Input** (~500 tokens of context):
```json
{
  "tc_id": "TC-001",
  "title": "User Registration — Valid Details",
  "steps": ["Navigate to Sign Up", "Enter email/password", "Click Create Account"],
  "expected_result": "Account created, welcome email sent",
  "feature_context": {
    "feature_name": "User Registration & Authentication",
    "description": "Allow new customers to create an account...",
    "business_rules": ["Passwords must meet complexity rules"]
  }
}
```
→ LLM guesses URLs, guesses selectors, guesses password rules, no tech stack awareness.

**V2 LLM Input** (~1500 tokens of context):
```
TECH STACK: React 18, Redux Toolkit, Node.js/Express API
GLOSSARY: JWT = JSON Web Token for API auth, OAuth 2.0 = delegated authorization...

REQUIREMENTS:
FR-001 - User Registration & Authentication
  Description: Allow new customers to create an account using email/password
               or OAuth 2.0 (Google, Facebook)
  Actors: Guest User, Registered Customer
  Pre-conditions: Valid unused email or OAuth account
  Trigger: User selects "Sign Up" from storefront header
  Main Flow: 1. Navigate to Sign Up → enter name/email/password → submit...
  Exception: If email exists → "An account with this email already exists" + login link
  Business Rules: Passwords must meet complexity rules, OAuth accounts no password needed,
                  duplicate emails rejected at DB unique constraint AND API validation
  Post-conditions: New user record in users table, session established

NFR-SECURITY:
  JWT access tokens expire after 15 minutes
  CSRF tokens enforced
  Rate limiting: 100 req/min per IP on auth endpoints

TEST CASE:
  TC-001: User Registration — Valid Details
  Steps: Navigate to Sign Up, Enter email/password, Click Create Account
  Expected: Account created, welcome email sent via SendGrid, auto-logged-in
```
→ LLM knows exact URLs, knows React selectors, knows JWT expiry, knows rate limiting, knows exact error messages, knows SendGrid is the email provider.

---

## Summary: What Changed and Why

| Previous Approach | Revised Approach |
|---|---|
| Parser does fuzzy matching (TC → FR) | Parser does zero matching |
| Parser attaches `feature_context` per TC | Parser outputs everything in knowledge artifact |
| Code generator gets partial context | Code generator selects relevant context slices |
| Embedding/LLM matching adds complexity | Simple keyword filtering selects context |
| Parser is smart, code generator is dumb | Parser is a dumb extractor, code generator is smart |

**The embedding/LLM matching approach is NOT optimal for Baxter.** It solves a mapping problem that doesn't need to exist. The real problem is context richness for the code generator, and that's solved by:
1. Parsing everything (deterministic, full AST)
2. Simple context windowing (keyword filter)
3. Letting the LLM do what LLMs are good at — understanding context and generating code
