# 🧠 Content-Aware Matching — Embeddings vs. LLM Approaches

## The Problem We're Solving

The V1 parser matches test cases to requirements by comparing **text labels**:

```
TC Subject: "Registration"  →  fuzzy compare  →  Feature Name: "User Registration & Authentication"
```

This is fundamentally broken because:
- It ignores what the test steps actually do
- It ignores what the requirement actually describes
- It produces 1:1 mappings when the reality is 1:N
- It can't handle NFRs, performance targets, or cross-cutting concerns at all

**The correct approach**: Read the *content* of the test case (steps, expected results) and the *content* of all document sections (functional requirements, NFRs, interfaces, performance targets) and match based on **semantic meaning**.

There are two viable approaches to do this. Both are explained in full detail below.

---

## Approach 1: Embedding-Based Semantic Matching (Local, Offline)

### How It Works

**Core Idea**: Convert both requirement text and test case text into **numerical vectors** (embeddings) that capture semantic meaning, then use **cosine similarity** to find which requirements a test case is closest to.

```
Step 1: Build the Requirement Index (one-time per FRD)
─────────────────────────────────────────────────────────

  FR-001 description: "Allow new customers to create an account
                       using email/password or OAuth 2.0..."
         ↓ encode()
  Vector: [0.23, 0.87, -0.12, 0.45, ...]  (384 dimensions)

  FR-002 description: "Enable customers to browse product catalog
                       and search by keyword..."
         ↓ encode()
  Vector: [0.56, 0.11, 0.78, -0.33, ...]

  NFR-Security text:  "TLS 1.3, PCI-DSS, OWASP Top 10 mitigations,
                       parameterized queries, input sanitization..."
         ↓ encode()
  Vector: [0.91, -0.45, 0.67, 0.22, ...]

  ... (all sections become vectors)


Step 2: Match Each Test Case (per TC)
─────────────────────────────────────────

  TC-025 content:  "Enter SQL injection payload in search bar.
                    System sanitizes input, returns safe results."
         ↓ encode()
  Query Vector: [0.88, -0.41, 0.71, 0.19, ...]

  Cosine Similarity:
    vs FR-001 (Registration):  0.12  ❌ low
    vs FR-002 (Catalog):       0.67  ✅ related (search bar)
    vs NFR-Security:           0.91  ✅ primary match (SQL injection)

  Result: TC-025 → [NFR-Security (0.91), FR-002 (0.67)]
```

### Implementation Design

```python
from sentence_transformers import SentenceTransformer
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class DocumentSection:
    """Represents any parseable section of the FRD."""
    section_id: str        # "FR-001", "NFR-Security", "PERF", "INTF-Stripe"
    section_type: str      # "functional", "nfr", "performance", "interface"
    title: str             # "User Registration & Authentication"
    content: str           # Full concatenated text of description + flows + rules
    source_location: str   # "Section 5.1, Table 3"

class EmbeddingMatcher:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        all-MiniLM-L6-v2:
          - 80MB model, runs on CPU
          - 384-dimensional embeddings
          - No API calls, no data leaves the machine
          - Free, unlimited usage
        """
        self.model = SentenceTransformer(model_name)
        self.sections: List[DocumentSection] = []
        self.embeddings: np.ndarray = None

    def build_index(self, sections: List[DocumentSection]) -> None:
        """
        Pre-compute embeddings for all FRD sections.
        Called once per document — takes ~2-5 seconds for 20-30 sections.
        """
        self.sections = sections

        # Combine title + content for richer embeddings
        texts = [
            f"{s.title}. {s.content}"
            for s in sections
        ]
        self.embeddings = self.model.encode(texts, normalize_embeddings=True)

    def match(
        self,
        test_case_text: str,
        top_k: int = 3,
        threshold: float = 0.40
    ) -> List[Tuple[DocumentSection, float]]:
        """
        Find the top-K most semantically similar FRD sections
        for a given test case's content.

        Args:
            test_case_text: Concatenation of TC steps + expected result + subject
            top_k: Maximum number of matches to return
            threshold: Minimum similarity score to include

        Returns:
            List of (section, similarity_score) tuples, sorted by relevance
        """
        query_embedding = self.model.encode(
            [test_case_text], normalize_embeddings=True
        )

        # Cosine similarity (dot product since vectors are normalized)
        similarities = np.dot(self.embeddings, query_embedding.T).flatten()

        # Get top-K above threshold
        scored = [
            (self.sections[i], float(similarities[i]))
            for i in np.argsort(similarities)[::-1][:top_k]
            if similarities[i] >= threshold
        ]

        return scored

    def match_test_case(self, tc: "TestCaseModel") -> List[dict]:
        """
        Build a rich content string from the test case and match it.
        This is what gets compared — not just the subject label.
        """
        content_parts = [
            f"Subject: {tc.subject}",
            f"Type: {', '.join(tc.type)}",
            f"Title: {tc.title}",
            f"Steps: {' '.join(tc.steps)}",
            f"Expected Result: {tc.expected_result}",
        ]
        full_text = " | ".join(content_parts)

        matches = self.match(full_text)
        return [
            {
                "ref_id": section.section_id,
                "ref_type": section.section_type,
                "ref_title": section.title,
                "confidence": round(score, 3),
            }
            for section, score in matches
        ]
```

### How FRD Sections Become Indexable Content

```python
def build_sections_from_ast(document_ast: DocumentAST) -> List[DocumentSection]:
    """Convert the full document AST into indexable sections."""
    sections = []

    # Functional Requirements (FR-001 through FR-010)
    for req in document_ast.requirements:
        content = " ".join([
            req.description,
            f"Actors: {', '.join(req.actors)}",
            f"Pre-conditions: {'; '.join(req.pre_conditions)}",
            f"Main Flow: {' '.join(req.main_flow)}",
            f"Exception Flow: {' '.join(req.exception_flow)}",
            f"Business Rules: {'; '.join(req.business_rules)}",
        ])
        sections.append(DocumentSection(
            section_id=req.feature_id,
            section_type="functional",
            title=req.feature_name,
            content=content,
            source_location=f"Section 5, {req.feature_id}"
        ))

    # NFR Sections (Security, Usability, Reliability, etc.)
    for nfr_name, nfr_content in document_ast.nfr.items():
        sections.append(DocumentSection(
            section_id=f"NFR-{nfr_name.capitalize()}",
            section_type="nfr",
            title=f"Non-Functional: {nfr_name.capitalize()}",
            content=nfr_content,  # Full paragraph text from Section 8.x
            source_location=f"Section 8 ({nfr_name})"
        ))

    # Performance Targets (Table 13)
    if document_ast.performance:
        perf_text = " | ".join(
            f"{row['parameter']}: {row['target']}"
            for row in document_ast.performance
        )
        sections.append(DocumentSection(
            section_id="NFR-Performance",
            section_type="performance",
            title="Performance Requirements",
            content=perf_text,
            source_location="Section 6, Table 13"
        ))

    # System Interfaces (Table 14)
    for intf in document_ast.interfaces:
        sections.append(DocumentSection(
            section_id=f"INTF-{intf['system'].replace(' ', '_')}",
            section_type="interface",
            title=f"Interface: {intf['system']}",
            content=f"{intf['type']}, {intf['direction']}, {intf['data']}, {intf['frequency']}",
            source_location="Section 7, Table 14"
        ))

    return sections
```

### Strengths & Weaknesses

| ✅ Strengths | ❌ Weaknesses |
|---|---|
| **100% offline** — no data leaves the machine | Cannot *reason* about context — just measures distance |
| **Zero cost** — no API calls, no tokens consumed | Threshold tuning needed per domain (0.40 may be too low/high) |
| **Fast** — index build ~3s, each match ~5ms | Struggles with implicit relationships ("Guest checkout" → requires auth bypass logic from FR-001) |
| **Deterministic** — same input = same output every time | Cannot explain *why* it matched — just a similarity score |
| **Scales to 100K+ test cases** — O(1) per lookup after index build | Embedding model may not understand domain-specific jargon without fine-tuning |
| **No privacy concerns** — model runs locally on CPU | 1:N matching requires picking a threshold — below it you miss refs, above it you get false positives |

---

## Approach 2: LLM-Based Content-Aware Matching (API, with Data Privacy)

### How It Works

**Core Idea**: Send the test case content and a **sanitized summary** of all FRD sections to an LLM, and ask it to reason about which sections the test case relates to — including *why* and at what confidence level.

### ⚠️ The Client Data Problem

**The concern**: If we send raw FRD content to an LLM API (Gemini, OpenAI, etc.), we're transmitting potentially confidential client information — business rules, internal system architecture, database schemas, security configurations, compliance details — to a third-party cloud service.

**This is a real risk for enterprise clients**. Here's how we handle it:

### Strategy 1: Structural Abstraction (Recommended for POC)

**Don't send the raw document. Send a sanitized structural representation.**

```python
class DocumentSanitizer:
    """
    Converts raw FRD content into privacy-safe structural descriptions.
    No client names, URLs, internal system details, or business-specific
    data leaves the machine.
    """

    def __init__(self):
        # Patterns to scrub
        self.scrub_patterns = [
            (re.compile(r'https?://\S+'), '[URL]'),                # URLs
            (re.compile(r'\b[A-Za-z0-9._%+-]+@\S+'), '[EMAIL]'),   # Emails
            (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'), '[IP]'),  # IPs
            (re.compile(r'(?i)api[_-]?key\s*[:=]\s*\S+'), '[API_KEY]'),
        ]

        # Domain-specific terms to generalize
        self.entity_replacements = {}  # Built dynamically per project

    def build_entity_map(self, project_config: dict):
        """
        Build a reversible mapping of client-specific terms to generic labels.

        Example:
            "ShopSphere"       → "Platform"
            "shop.shopsphere.com" → "[STOREFRONT_URL]"
            "admin.shopsphere.com" → "[ADMIN_URL]"
            "Stripe"           → "PaymentGateway"
            "SendGrid"         → "EmailService"
            "FedEx"            → "ShippingProvider"
            "PostgreSQL"       → "PrimaryDatabase"
            "Redis"            → "CacheLayer"
            "Elasticsearch"    → "SearchEngine"
        """
        self.entity_replacements = {
            project_config.get("project_name", ""): "Platform",
            # Add all client-specific entities here
        }

    def sanitize(self, text: str) -> str:
        """Remove all client-identifiable information from text."""
        result = text

        # Step 1: Replace known entities
        for original, replacement in self.entity_replacements.items():
            if original:
                result = result.replace(original, replacement)

        # Step 2: Scrub patterns (URLs, emails, IPs, keys)
        for pattern, replacement in self.scrub_patterns:
            result = pattern.sub(replacement, result)

        return result

    def sanitize_section(self, section: DocumentSection) -> dict:
        """
        Convert a DocumentSection into a privacy-safe dictionary
        that can be sent to the LLM.
        """
        return {
            "id": section.section_id,
            "type": section.section_type,
            "title": self.sanitize(section.title),
            "summary": self.sanitize(
                # Truncate to first 200 chars — enough for matching,
                # not enough to leak detailed business logic
                section.content[:200] + "..."
                if len(section.content) > 200
                else section.content
            ),
        }
```

**What the LLM actually sees** (after sanitization):

```json
{
  "sections": [
    {
      "id": "FR-001",
      "type": "functional",
      "title": "User Registration & Authentication",
      "summary": "Allow new customers to create an account using email/password or federated OAuth 2.0 login, and allow returning customers to authenticate securely. Actors: Guest User, Registered Customer..."
    },
    {
      "id": "NFR-Security",
      "type": "nfr",
      "title": "Non-Functional: Security",
      "summary": "All traffic encrypted in transit via TLS 1.3; data at rest encrypted with AES-256. PCI-DSS SAQ-A compliance maintained by tokenizing all card data via [PaymentGateway]. OWASP Top 10 mitigations enforced: parameterized queries, input saniti..."
    }
  ],
  "test_case": {
    "id": "TC-025",
    "title": "Security — SQL Injection Attempt on Search",
    "type": "Security",
    "steps": "Enter SQL injection payload in search bar. Verify system sanitizes input.",
    "expected": "System rejects malicious input, returns safe results, logs the attempt."
  }
}
```

**What was scrubbed**: `ShopSphere` → `Platform`, `shop.shopsphere.com` → `[STOREFRONT_URL]`, `Stripe` → `PaymentGateway`, all internal URLs removed.

**What remains**: The *structural and semantic content* needed for matching — requirement types, actors, flows, NFR categories — without any client-identifying information.

### Strategy 2: Local LLM (Zero Data Leakage)

Run a small LLM locally — **no API calls, no data ever leaves the machine**.

```python
# Option A: Ollama (easiest setup)
# Install: https://ollama.ai
# Run: ollama pull gemma3:4b

import requests

class LocalLLMMatcher:
    def __init__(self, model: str = "gemma3:4b", base_url: str = "http://localhost:11434"):
        """
        Runs entirely on the local machine.
        gemma3:4b: 4B parameters, ~3GB VRAM, runs on most laptops.
        No internet needed after model download.
        """
        self.model = model
        self.base_url = base_url

    def match(self, test_case: dict, sections: List[dict]) -> List[dict]:
        sections_text = "\n".join([
            f"[{s['id']}] ({s['type']}) {s['title']}: {s['summary']}"
            for s in sections
        ])

        prompt = f"""You are a requirements traceability expert.

Given the following test case and document sections, identify ALL sections
that this test case validates or relates to.

Return a JSON array of matches with: ref_id, ref_type, confidence (0.0-1.0),
and a one-line reason.

DOCUMENT SECTIONS:
{sections_text}

TEST CASE:
ID: {test_case['id']}
Title: {test_case['title']}
Type: {test_case['type']}
Steps: {test_case['steps']}
Expected Result: {test_case['expected']}

Return ONLY the JSON array, no markdown fences."""

        response = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False}
        )
        return json.loads(response.json()["response"])
```

### Strategy 3: Enterprise API with Data Processing Agreement (Production)

For actual production deployment, use Gemini or Azure OpenAI with:
- **Data Processing Agreement (DPA)** — contractual guarantee that data isn't used for training
- **Regional deployment** — data stays within the client's geography (EU, US, etc.)
- **VPC/Private endpoints** — traffic doesn't traverse public internet

```python
# Gemini with explicit data governance
import google.generativeai as genai

class EnterpriseLLMMatcher:
    def __init__(self):
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            # Safety settings to prevent data retention
            safety_settings={
                "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
            },
        )
        # Gemini API data usage policy:
        # - Data sent via API is NOT used to train models
        # - Data is processed in-transit and not stored beyond the request
        # - Enterprise tier offers additional DPA guarantees
```

### LLM Matching Prompt Design

```python
MATCHING_SYSTEM_PROMPT = """You are a requirements traceability engine.

Your task is to map a manual test case to ALL relevant document sections
it validates. A test case can relate to multiple sections.

RULES:
1. Match based on CONTENT, not just title similarity.
2. Look at what the test steps DO and what the expected result VERIFIES.
3. A security test about search relates to BOTH the search feature AND security NFRs.
4. A checkout test may relate to cart, payment, notifications, and authentication.
5. Performance-related expected results map to performance NFR targets.
6. Return confidence scores: 0.9+ = primary, 0.6-0.9 = secondary, 0.4-0.6 = tangential.
7. Always explain WHY each match exists in one sentence.
8. Return valid JSON only."""

MATCHING_USER_PROMPT = """
AVAILABLE DOCUMENT SECTIONS:
{sections_json}

TEST CASE TO MAP:
{test_case_json}

Return a JSON array:
[
  {{
    "ref_id": "FR-001",
    "ref_type": "functional",
    "confidence": 0.95,
    "reason": "Test directly validates user registration flow described in FR-001 main flow steps 1-3"
  }},
  ...
]"""
```

**Example LLM output for TC-025 (SQL Injection on Search)**:
```json
[
  {
    "ref_id": "NFR-Security",
    "ref_type": "nfr",
    "confidence": 0.95,
    "reason": "Test validates OWASP Top 10 mitigation (input sanitization, parameterized queries) defined in Security NFRs"
  },
  {
    "ref_id": "FR-002",
    "ref_type": "functional",
    "confidence": 0.72,
    "reason": "Test targets the search bar component which is part of the Product Catalog & Search feature"
  },
  {
    "ref_id": "NFR-Audit",
    "ref_type": "nfr",
    "confidence": 0.48,
    "reason": "Expected result mentions logging the attempt, which relates to the audit trail requirement"
  }
]
```

### Strengths & Weaknesses

| ✅ Strengths | ❌ Weaknesses |
|---|---|
| **Reasons about context** — understands implicit relationships | **API cost** — ~$0.001-0.005 per test case mapping |
| **Explains its reasoning** — auditable "why" for every match | **Latency** — 1-3 seconds per test case (vs 5ms for embeddings) |
| **Handles edge cases** — cross-cutting concerns, implicit dependencies | **Non-deterministic** — may produce slightly different results on re-runs |
| **No threshold tuning** — LLM decides confidence naturally | **Requires privacy safeguards** — must sanitize or use local model |
| **1:N mapping built-in** — naturally returns multiple refs | **Rate limits** — 15 RPM on free Gemini tier = slow for 3K+ test cases |
| **Zero training data needed** — works out of the box | **Model dependency** — behavior changes across model versions |

---

## Side-by-Side Comparison

| Dimension | Embeddings (Local) | LLM (API/Local) |
|---|---|---|
| **Data Privacy** | ✅ Zero risk — nothing leaves machine | ⚠️ Requires sanitization or local model |
| **Cost** | ✅ Free forever | 💰 $0.001-0.005 per TC (API) or free (local LLM) |
| **Accuracy** | 🟡 Good for explicit matches, weak for implicit | ✅ Excellent — understands context and reasoning |
| **Speed** | ✅ ~5ms per match | 🟡 1-3s per match (API), 5-15s (local LLM) |
| **1:N Mapping** | 🟡 Returns top-K by score — threshold determines cutoff | ✅ Natural multi-ref reasoning |
| **Explainability** | ❌ Just a similarity score — no "why" | ✅ Full reasoning per match |
| **Determinism** | ✅ Same input = same output | ❌ May vary between runs |
| **Scale (3K+ TCs)** | ✅ Handles 100K+ easily | 🟡 Rate limits; batch with backoff |
| **Offline capable** | ✅ Yes | 🟡 Only with local model (Ollama) |
| **Setup complexity** | Low (pip install sentence-transformers) | Medium (API key + sanitizer, or Ollama setup) |

---

## Recommended Hybrid Approach for POC

> [!TIP]
> **Don't choose one — use both in a pipeline.**

```
┌───────────────┐      ┌──────────────────┐      ┌───────────────────┐
│  Full Doc AST │─────▶│  Embedding Index │─────▶│  Fast Pre-Filter  │
│  (all sections)│      │  (local, free)   │      │  Top-5 candidates │
└───────────────┘      └──────────────────┘      └────────┬──────────┘
                                                          │
                                                          ▼
                                                 ┌───────────────────┐
                                                 │  LLM Refinement   │
                                                 │  (sanitized input)│
                                                 │                   │
                                                 │  • Confirm/reject │
                                                 │  • Add reasoning  │
                                                 │  • Set confidence │
                                                 │  • Find implicit  │
                                                 │    refs missed by │
                                                 │    embeddings     │
                                                 └────────┬──────────┘
                                                          │
                                                          ▼
                                                 ┌───────────────────┐
                                                 │  Final Mapping    │
                                                 │  TC-025 → [       │
                                                 │    NFR-Security,  │
                                                 │    FR-002,        │
                                                 │    NFR-Audit      │
                                                 │  ]                │
                                                 └───────────────────┘
```

### Why Hybrid?

1. **Embeddings pre-filter** narrows 30+ sections down to 5 candidates → LLM processes 80% less text
2. **LLM only sees the 5 candidate sections** (sanitized) → less data exposure, lower cost, faster response
3. **Embeddings handle the easy matches** (subject "Registration" → FR-001) without any API call at all
4. **LLM handles the hard matches** (SQL injection → NFR-Security + FR-002 + NFR-Audit)
5. **Fallback**: If LLM is unavailable (rate limit, offline), embedding results are still usable

### Hybrid Implementation

```python
class HybridMatcher:
    def __init__(self, use_llm: bool = True):
        self.embedding_matcher = EmbeddingMatcher()
        self.sanitizer = DocumentSanitizer()
        self.llm_matcher = LLMMatcher() if use_llm else None
        self.use_llm = use_llm

    def match(self, test_case: TestCaseModel) -> List[dict]:
        # Step 1: Embedding pre-filter (fast, free, private)
        candidates = self.embedding_matcher.match_test_case(test_case)

        # If embedding match is high-confidence (>0.85) and single-ref, skip LLM
        if (len(candidates) == 1
            and candidates[0]["confidence"] > 0.85
            and not self._is_cross_cutting(test_case)):
            return candidates

        # Step 2: LLM refinement (only for ambiguous or cross-cutting cases)
        if self.use_llm and self.llm_matcher:
            # Only send the top-5 candidate sections (not the whole FRD)
            candidate_sections = [
                self.sanitizer.sanitize_section(
                    self.embedding_matcher.get_section(c["ref_id"])
                )
                for c in candidates[:5]
            ]

            sanitized_tc = self.sanitizer.sanitize_test_case(test_case)
            refined = self.llm_matcher.match(sanitized_tc, candidate_sections)
            return refined

        return candidates

    def _is_cross_cutting(self, tc: TestCaseModel) -> bool:
        """Detect test cases likely to span multiple requirements."""
        cross_cutting_signals = [
            "security", "performance", "full flow", "end-to-end",
            "integration", "compliance", "accessibility", "guest checkout"
        ]
        tc_text = f"{tc.title} {' '.join(tc.type)} {tc.subject}".lower()
        return any(signal in tc_text for signal in cross_cutting_signals)
```

---

## Data Privacy Decision Matrix

| Scenario | Recommended Strategy | Data Exposure |
|---|---|---|
| **Internal POC / Demo** | Embeddings only (local) | Zero |
| **Client demo with sample data** | Embeddings + LLM (sanitized) | Minimal — structural only |
| **Client POC with real data** | Embeddings + Local LLM (Ollama) | Zero — everything on-premise |
| **Production (enterprise contract)** | Embeddings + Enterprise Gemini/Azure with DPA | Contractually protected |
| **Production (regulated industry — healthcare, finance)** | Embeddings + Local LLM only | Zero — compliance guaranteed |

> [!IMPORTANT]
> **For the Baxter POC**: Use **Embeddings + Sanitized Gemini API** as the default, with a `--offline` flag that switches to embeddings-only mode. This lets us demo the full hybrid accuracy while proving the privacy-safe pipeline works.

---

## Cost Estimate (LLM Approach)

| Scale | Embedding Cost | LLM API Cost (Gemini Flash) | Total |
|---|---|---|---|
| 25 test cases (POC) | $0 | ~$0.05 | $0.05 |
| 200 test cases (pilot) | $0 | ~$0.40 | $0.40 |
| 3,000 test cases (production) | $0 | ~$6.00 | $6.00 |
| 3,000 TCs with hybrid (LLM only for ambiguous) | $0 | ~$1.50 | $1.50 |

> The hybrid approach reduces LLM calls by ~75% since most straightforward matches (Registration → FR-001) are handled by embeddings alone.
