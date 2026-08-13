# 🔬 What the Parser is Actually Missing — Deep Dive

## Problem 1: We're Not Parsing the Whole Document

The FRD has **15 tables** and **89 paragraphs** of content. Here's exactly what gets parsed vs. dropped:

### ✅ What IS Captured (Tables 3–12 only)

The parser **only** extracts the 10 requirement specification tables (FR-001 through FR-010) by looking for the `"Requirement ID:"` heading signal and grabbing the next 2-column key-value table.

### ❌ What IS Silently Dropped

| Section | Content | Why It Matters |
|---------|---------|---------------|
| **Sections 1–2**: Purpose & Scope | Platform context, in-scope/out-of-scope boundaries, tech stack (React 18, Redux, Node/Express, Redis, PostgreSQL, Stripe) | Test cases reference these technologies — a TC about "Redis session" has no context without this |
| **Section 4**: Enhancement Overview & Business Benefits | "25% reduction in cart abandonment", "5,000-user pilot", checkout flow redesign rationale | Explains *why* requirements exist — critical for generating meaningful test scenarios |
| **Table 1**: Document metadata | Version, author, reviewer, approval date, confidentiality | Needed for traceability and audit |
| **Table 2**: References | 7 external systems (BRD, Figma wireframes, Stripe API, PCI-DSS, Architecture Diagram, WCAG, FedEx) | Test cases should reference these for validation criteria |
| **Table 13**: Performance NFRs | Page load ≤1.5s, API ≤500ms, checkout ≤3s, search ≤300ms, 5K concurrent checkouts, 50K concurrent sessions | **Entire class of performance test cases** can't be generated without this |
| **Table 14**: System Interfaces | 8 integrations (Stripe, FedEx/UPS, SendGrid, Twilio, Google/Facebook OAuth, S3, Elasticsearch, Segment/GA) — with direction, data exchanged, frequency | Integration test cases have no context |
| **Section 8**: Non-Functional Attributes | Security (TLS 1.3, PCI-DSS, OWASP, WAF, JWT), Usability (WCAG 2.1 AA), Reliability (circuit breakers, failover), Scalability (K8s, HPA), Compliance (GDPR, CCPA) | **6 entire NFR categories** — Security, Usability, Reliability, Scalability, Maintainability, Compliance — all dropped |
| **Table 15**: Glossary | 10 domain terms (SKU, JWT, OAuth, PCI-DSS, SLA, WAF, Idempotency Key, Webhook, RTO/RPO, p95) | Tests reference these terms — LLM needs definitions for correct code generation |

### The Numbers

```
FRD Document Content:
  Total paragraphs:     89
  Parsed:               ~20  (only "Requirement ID:" headings + FR names)
  Dropped:              ~69  (77% silently lost)

  Total tables:         15
  Parsed:               10   (FR requirement tables only)
  Dropped:              5    (metadata, references, performance, interfaces, glossary)

  Total sections:       10   (Purpose, Scope, References, Overview, Specs, Perf, Interfaces, NFRs, Glossary, Attachments)
  Parsed:               1    (Section 5 — Functional Specs only)
  Dropped:              9    (90% of document structure)
```

> [!CAUTION]
> **The parser treats 10 requirement tables as the entire FRD**, but those tables are only ~40% of the document's meaningful content. The other 60% — including all NFRs, performance targets, system interfaces, security requirements, and compliance rules — is silently discarded.

---

## Problem 2: Subject-to-Feature Matching is Fundamentally Wrong

### What's Happening Now

The test case table has a **"Subject"** column with high-level labels like `"Registration"`, `"Cart"`, `"Coupons & Discounts"`. The parser tries to fuzzy-match these labels against FRD feature names like `"User Registration & Authentication"`, `"Shopping Cart Management"`, `"Coupon & Discount Engine"`.

```
TC-001 Subject: "Registration"  →  fuzzy match → "User Registration & Authentication"  →  FR-001  ✅ Lucky hit
TC-012 Subject: "Coupons & Discounts"  →  fuzzy match → "Coupon & Discount Engine"  →  FR-010  ✅ Lucky hit
TC-025 Subject: "Search Security"  →  fuzzy match → "Product Catalog & Search"  →  FR-002  ⚠️ Wrong!
```

### Why This is Wrong

**1. Subject is a label, not a mapping key**

The "Subject" field is just a human-written category tag. It was never designed to be a foreign key to requirements. Different authors will write:
- `"Cart"` vs. `"Shopping Cart"` vs. `"Add to Cart"` vs. `"Basket"`
- All mean the same thing, but fuzzy matching handles them inconsistently

**2. One test case can relate to multiple requirements**

`TC-014: "Guest Checkout — Full Flow"` touches:
- FR-001 (Authentication — guest checkout bypasses registration)
- FR-003 (Cart Management — cart must exist to checkout)
- FR-004 (Checkout & Payment — the primary requirement)
- FR-009 (Notifications — order confirmation email)
- FR-010 (Coupons — coupon applied at checkout)

But the current parser maps it to **only FR-004** because "Checkout" substring-matches.

**3. The matching ignores the actual test content**

The parser matches based on subject **labels** but completely ignores:
- The **test steps** (what the test actually does)
- The **expected results** (what system behavior is verified)
- The **FRD requirement content** (description, main flows, business rules)

A correct matcher should look at `TC-025`'s steps — *"Enter SQL injection payload in search bar"* — and realize it tests the **Security NFR** (OWASP Top 10 mitigations, Section 8.1), not the Product Catalog feature.

**4. Non-functional test cases have no feature to match**

Test cases of type "Security", "Performance", "Accessibility" map to **NFR sections** (Section 8), not to FR-001 through FR-010. Since the parser doesn't even parse NFRs, these test cases are either:
- Incorrectly matched to a functional requirement via fuzzy guess
- Marked as `UNKNOWN` and lose all context

---

## What the Correct V2 Approach Should Look Like

### Full Document AST + Content-Aware Matching

```
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 1: Full Document AST Extraction                                │
│                                                                      │
│  Parse EVERY section of the document into a structured tree:         │
│                                                                      │
│  DocumentAST                                                         │
│  ├── metadata        (Table 1: version, author, date)                │
│  ├── purpose         (Section 1: what this document is for)          │
│  ├── scope                                                           │
│  │   ├── in_scope    (Section 2.1: what's covered)                   │
│  │   └── out_scope   (Section 2.2: what's explicitly excluded)       │
│  ├── references      (Table 2: external system docs)                 │
│  ├── overview                                                        │
│  │   ├── background  (Section 4.1: current state)                    │
│  │   ├── proposal    (Section 4.2: what's changing)                  │
│  │   └── benefits    (Section 4.3: business metrics)                 │
│  ├── requirements[]  (Section 5: FR-001 through FR-010)  ← V1 ONLY  │
│  ├── performance     (Table 13: NFR targets)                         │
│  ├── interfaces[]    (Table 14: external system integrations)        │
│  ├── nfr                                                             │
│  │   ├── security    (Section 8.1: TLS, PCI, OWASP, WAF, JWT)       │
│  │   ├── usability   (Section 8.2: WCAG, responsive, click targets) │
│  │   ├── reliability (Section 8.3: circuit breakers, failover)       │
│  │   ├── scalability (Section 8.4: K8s, HPA, read replicas)         │
│  │   ├── maintain.   (Section 8.5: CI/CD, feature flags)            │
│  │   ├── compliance  (Section 8.6: GDPR, CCPA, PCI-DSS)            │
│  │   └── audit       (Section 8.7: ELK, audit trails)               │
│  └── glossary        (Table 15: domain term definitions)             │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  STEP 2: Content-Aware Matching (not label matching)                 │
│                                                                      │
│  For each test case, analyze the CONTENT:                            │
│    - Test steps ("Enter SQL injection in search bar")                │
│    - Expected result ("System sanitizes input, returns safe results")│
│    - Test type ("Security")                                          │
│    - Subject ("Search Security")                                     │
│                                                                      │
│  Match against ALL document sections:                                │
│    - FR-001..FR-010 (functional requirements)                        │
│    - NFR sections (security, performance, usability, etc.)           │
│    - System interfaces (Stripe, SendGrid, etc.)                      │
│                                                                      │
│  Result: MULTIPLE refs per test case                                 │
│    TC-025 → [NFR-Security, FR-002]  (not just FR-002)                │
│    TC-014 → [FR-004, FR-001, FR-003, FR-009, FR-010]                 │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Architecture Changes

| V1 (Current) | V2 (Correct) |
|---|---|
| Parse only `"Requirement ID:"` headings + following tables | Parse every section via heading-level detection (Section 1–10) |
| 10 requirement tables → `FeatureModel` | 15 tables + 89 paragraphs → `DocumentAST` with typed sections |
| Match: `subject label` ↔ `feature name` | Match: `test content (steps + expected + type)` ↔ `all document sections` |
| 1:1 mapping (test → single feature) | 1:N mapping (test → multiple requirements + NFRs) |
| `feature_ref: "FR-001"` | `refs: [{type: "functional", id: "FR-004"}, {type: "nfr", id: "security"}, ...]` |
| No NFR context in output | Full NFR context enrichment for security/performance/compliance tests |

> [!IMPORTANT]
> The core question for V2 is: **Should we build the content-aware matching ourselves (embedding-based), or use an LLM to do the mapping?** An LLM can read the test steps + FRD content and produce accurate multi-ref mappings in a single call, while embeddings require building and tuning an index. Both are valid — LLM is more accurate but costs API calls, embeddings are free but need tuning.
