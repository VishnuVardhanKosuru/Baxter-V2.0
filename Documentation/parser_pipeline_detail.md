> [!WARNING]
> **Stale — describes a previous branch layout.** File paths point at a
> `Tharun_Branch` checkout, line numbers have drifted, and `agents/scanners.py` no
> longer exists: its contents were merged into `agents/doc_parser.py`
> (sections 1–3). The described *behaviour* is still broadly accurate; the
> references are not. See `readme.md` for the current structure.

# Parser Pipeline — Detailed Code Walkthrough
> From raw `.docx` files → `output/knowledge/<module>_knowledge.json`

**Files involved:**
- [`agents/doc_parser.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/doc_parser.py)
- [`agents/scanners.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/scanners.py)
- [`core/models.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/models.py)
- [`core/constants.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/constants.py)
- [`core/llm_factory.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/llm_factory.py)

---

## Entry Point — `parse_documents()` [`doc_parser.py:150`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/doc_parser.py#L150)

Called by `server.py`. Signature:
```python
parse_documents(
    modules_dir,   # path to input_modules/
    out_dir,       # path to output/
    project,       # "ShopSphere"
    version,       # "2.0"
    skip_types     # TC types to skip (optional)
)
```

---

## PHASE 1 — Discover Module Folders

### Step 1.1 — `ModuleFolderScanner.scan()` [`scanners.py:103`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/scanners.py#L103)

```python
scanner = ModuleFolderScanner(Path(modules_dir))
packages = scanner.scan()
```

Iterates every **subfolder** inside `input_modules/` in sorted (deterministic) order.
For each subfolder, calls `DocumentClassifier.classify_files()`.

### Step 1.2 — `DocumentClassifier.classify_files()` [`scanners.py:56`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/scanners.py#L56)

```python
for file in folder_path.glob("*.docx"):
    if file.name.startswith("~$"):   # skip Word temp/lock files
        continue
    if any(kw in name_lower for kw in ["frd","requirement","spec","functional"]):
        frd_files.append(file)
    elif any(kw in name_lower for kw in ["tc","test","manual","case","mtc"]):
        tc_files.append(file)
```

Constants from [`constants.py:151-152`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/constants.py#L151):
```python
FRD_FILENAME_KEYWORDS = ["frd", "requirement", "spec", "functional"]
TC_FILENAME_KEYWORDS  = ["tc", "test", "manual", "case", "mtc"]
```

Returns a `ModulePackage` dataclass [`scanners.py:42`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/scanners.py#L42):
```python
@dataclass
class ModulePackage:
    module_folder: str        # e.g. "01_User_Auth"
    frd_files:     List[Path] # e.g. [Path("FRD_UserAuth.docx")]
    tc_files:      List[Path] # e.g. [Path("TC_UserAuth.docx")]
```

> If a module folder has no `.docx` files at all, it is skipped silently.

---

## PHASE 2 — Parse the FRD `.docx` → `DocumentAST`

### Step 2.1 — `FRDModuleParser.parse()` [`scanners.py:175`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/scanners.py#L175)

```python
frd_file = package.frd_files[0]      # only first FRD used per module
ast = FRDModuleParser.parse(frd_file, package.module_folder)
```

**Opens the `.docx`:**
```python
doc = docx.Document(str(file_path))
```
If the file cannot be opened → prints `[ERROR]` and returns an empty `DocumentAST` (no crash).

**Seeds a starter section** to catch any paragraphs before the first heading:
```python
current_section = SectionNode(
    section_id = "01_User_Auth:GEN-001",
    title      = "Document Header & Overview",
    type       = "general",
)
ast.sections.append(current_section)
```

**Walks every XML element** in the Word document body [`scanners.py:250`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/scanners.py#L250):

#### If element is a Paragraph (`<w:p>`)

```python
p_text = "".join(node.text for node in child.iter() if node.tag.endswith("}t")).strip()
```
Collects all `<w:t>` (text run) nodes inside the paragraph XML element.

**Is it a heading?** Two signals are checked:

1. Paragraph Word style is `Heading1`, `Heading2`, etc.:
```python
style_node = child.find("{...}pPr/{...}pStyle")
if "Heading" in style_node.attrib["val"]:
    is_heading = True
```

2. Text contains `"Requirement ID:"` keyword ([`constants.py:120`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/constants.py#L120)).

**If heading → create new `SectionNode`** via `derive_section_id()` [`scanners.py:211`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/scanners.py#L211):

| Heading text contains | section_id suffix | type |
|---|---|---|
| `"Requirement ID: FR-001 – Login"` | `FR-001` (regex match) | `functional` |
| Has "Requirement ID:" but no FR number | `FR-001`, `FR-002`... (zero-padded index) | `functional` |
| `"scope"` | `SCOPE` | `scope` |
| `"purpose"` | `PURPOSE` | `general` |
| `"interface"` | `INTF` | `interface` |
| `"performance"` | `PERF` | `nfr` |
| `"non-functional"` / `"nfr"` / `"security"` | `NFR` | `nfr` |
| `"glossary"` | `GLOSSARY` | `general` |
| anything else | slug of first 15 chars e.g. `USER_MANAGEMEN` | `general` |

Full `section_id` = `module_folder + ":" + suffix`, e.g. `01_User_Auth:FR-001`.

Resulting `SectionNode` ([`models.py:16`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/models.py#L16)):
```python
SectionNode(
    section_id    = "01_User_Auth:FR-001",
    title         = "Requirement ID: FR-001 – Login Functionality",
    type          = "functional",
    module_folder = "01_User_Auth",
    source_file   = "FRD_UserAuth.docx",
    paragraphs    = [],   # filled as more paragraphs arrive
    tables        = [],   # filled when a table element follows
    metadata      = {}    # filled when a table element follows
)
```

**If NOT a heading → append text to current section's paragraphs:**
```python
current_section.paragraphs.append(p_text)
```

#### If element is a Table (`<w:tbl>`)

```python
for row in table.rows:
    cells = [c.text.strip() for c in row.cells]
    key = cells[0].lower().rstrip(":")
    val = cells[1]
```

Recognized keys are mapped to `current_section.metadata`:

| Table cell[0] contains | `metadata` key | processing |
|---|---|---|
| `"description"` | `metadata["description"]` | raw string |
| `"actor"` | `metadata["actors"]` | split by `/` or `,` → list |
| `"trigger"` | `metadata["trigger"]` | raw string |
| `"priority"` | `metadata["priority"]` | raw string |
| `"pre-condition"` / `"precondition"` | `metadata["pre_conditions"]` | split by `;` or newline → list |
| `"business rule"` | `metadata["business_rules"]` | split by `;` or newline → list |
| `"alternate"` / `"exception"` | `metadata["exception_flows"]` | split numbered steps → list |
| `"main flow"` | `metadata["main_flow"]` | split numbered steps → list |
| `"post-condition"` / `"postcondition"` | `metadata["post_conditions"]` | split by `;` or newline → list |

All table rows also stored raw in `section.tables[]` (used later for glossary extraction).

**Returns `DocumentAST`** ([`models.py:29`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/models.py#L29)):
```python
DocumentAST(
    module_folder = "01_User_Auth",
    source_file   = "FRD_UserAuth.docx",
    sections      = [
        SectionNode(section_id="01_User_Auth:GEN-001", ...),  # seeded header
        SectionNode(section_id="01_User_Auth:PURPOSE", ...),
        SectionNode(section_id="01_User_Auth:SCOPE",   ...),
        SectionNode(section_id="01_User_Auth:FR-001",  type="functional", metadata={...}),
        SectionNode(section_id="01_User_Auth:FR-002",  type="functional", metadata={...}),
        SectionNode(section_id="01_User_Auth:NFR",     type="nfr",        metadata={...}),
        SectionNode(section_id="01_User_Auth:GLOSSARY",type="general",    tables=[...]),
    ]
)
```

---

## PHASE 3 — Build Compact LLM Index from AST

### Step 3.1 — `build_compact_section_index(ast)` [`doc_parser.py:62`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/doc_parser.py#L62)

```python
compact_index = build_compact_section_index(ast)
```

For every `SectionNode`, produces one line:
```python
line = f"[{section.section_id}] {section.title} ({section.type})"
if section.paragraphs:
    summary = first_paragraph[:140] + "..."
    line += f" | {summary}"
```

**Example output string:**
```
Module: 01_User_Auth
[01_User_Auth:GEN-001] Document Header & Overview (general) | This document defines...
[01_User_Auth:PURPOSE] 1. Purpose (general) | The purpose of this document is...
[01_User_Auth:SCOPE] 2. Scope (scope) | This system covers user registration, login...
[01_User_Auth:FR-001] Requirement ID: FR-001 – Login (functional) | Users must be able to log in...
[01_User_Auth:FR-002] Requirement ID: FR-002 – Registration (functional) | New users can register...
[01_User_Auth:NFR] Non-Functional Requirements (nfr) | All APIs must respond within 2 seconds...
```

Replaces the full FRD document in the LLM prompt — saves ~25-30% tokens.

---

## PHASE 4 — Parse the Test Case `.docx` → `List[TestCaseModel]`

### Step 4.1 — `TestCaseModuleParser.parse()` [`scanners.py:326`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/scanners.py#L326)

```python
for tc_file in package.tc_files:
    tcs = TestCaseModuleParser.parse(tc_file, package.module_folder)
    module_tcs.extend(tcs)
```

Opens the `.docx`. If it fails → returns `[]` (no crash).

**Iterates every table** in the document. For each table:

**Header row detection** (row index 0):
```python
headers = [(cell.text or "").strip().lower() for cell in header_row.cells]
```

**Dynamic column discovery via `find_col()`** [`scanners.py:366`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/scanners.py#L366):
```python
def find_col(targets) -> Optional[int]:
    for idx, h in enumerate(headers):
        if any(t == h or (len(t) > 3 and t in h) for t in targets_tuple):
            return idx
    return None

col_map = {
    "test_name":        find_col(("test name", "name")),
    "type":             find_col(["type", "category"]),
    "subject":          find_col(["subject", "module"]),
    "description":      find_col(("description",)),
    "expected_result":  find_col(("expected result", "expected")),
    "execution_status": find_col(("execution status", "status")),
}
```

> If `col_map["test_name"]` is `None` — no valid TC table → **entire table skipped silently**.

**For each data row** (rows 1 onwards):

```python
tc_name_full = get_val("test_name")   # e.g. "TC-001 - Login with valid credentials"
```

**TC ID extraction:**
```python
# REGEX_TC_ID = re.compile(r"(TC-\d+)", re.IGNORECASE)
tc_id = tc_id_match.group(1).upper()        # "TC-001"
      if tc_id_match else f"TC-UNKN-{row_idx}"  # fallback if no TC-xxx pattern
```

**Title extraction:**
```python
# REGEX_TC_TITLE = re.compile(r"TC-\d+[:\s\-–—]+(.+)", re.IGNORECASE)
title = title_match.group(1).strip()    # "Login with valid credentials"
      if title_match else tc_name_full  # fallback: entire cell text
```

**Type extraction:**
```python
type_str = get_val("type")     # "Functional/Regression"
types = REGEX_TYPE_SPLIT.split(type_str)   # split by / or ,
# → ["Functional", "Regression"]
```

**Steps from description:**
```python
desc_text = get_val("description")
steps = split_numbered_steps(desc_text)
# Strips whitespace, splits on "1. " "2. " etc.
# "1. Navigate to login 2. Enter email" → ["Navigate to login", "Enter email"]
if not steps and desc_text:
    steps = [desc_text]    # fallback: whole text as one step
```

**Builds `TestCaseModel`** ([`models.py:80`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/models.py#L80)):
```python
TestCaseModel(
    tc_id              = "TC-001",
    title              = "Login with valid credentials",
    module_folder      = "01_User_Auth",
    source_file        = "TC_UserAuth.docx",
    source_table_index = 0,
    source_row_index   = 1,
    type               = ["Functional", "Regression"],
    subject            = "User Login",
    execution_status   = "Pass",
    steps              = ["Navigate to login page", "Enter valid email", "Click Submit"],
    expected_result    = "User is redirected to dashboard",
    # Not set yet — filled after LLM mapping in Phase 7:
    feature_ref        = "",
    feature_refs       = [],
    cucumber_tags      = [],
    mapped_contexts    = []
)
```

---

## PHASE 5 — Build Compact TC Summaries for LLM

### Step 5.1 [`doc_parser.py:203`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/doc_parser.py#L203)

```python
for tc in module_tcs:
    steps_preview = " ".join(tc.steps)[:120]
    types_str     = ",".join(tc.type) if tc.type else "General"
    tc_summaries.append(
        f"[{tc.tc_id}] {tc.title} | Subj: {tc.subject} | Type: {types_str} | Steps: {steps_preview}"
    )
tc_text = "\n".join(tc_summaries)
```

**Example `tc_text`:**
```
[TC-001] Login with valid credentials | Subj: User Login | Type: Functional | Steps: Navigate to login page Enter valid email...
[TC-002] Login with invalid password  | Subj: User Login | Type: Negative   | Steps: Navigate to login Enter wrong password...
[TC-003] Forgot password flow         | Subj: Password   | Type: Functional | Steps: Click Forgot Password Enter registered email...
```

Queued into `batch_inputs`:
```python
batch_inputs.append({
    "index":      compact_index,   # FRD compact string (Phase 3 output)
    "test_cases": tc_text          # TC compact summaries
})
```

---

## PHASE 6 — Async Batch LLM Mapping

### Step 6.1 — Concurrency calculation [`doc_parser.py:219`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/doc_parser.py#L219)

```python
rpm         = int(os.getenv("GEMINI_RPM", "50"))
num_keys    = len(_collect_keys("GEMINI_API_KEY"))  # counts KEY, KEY_2...KEY_9
concurrency = min(rpm * num_keys, 500)
# e.g. 3 API keys x 50 rpm = 150 max concurrent LLM requests
```

### Step 6.2 — Lazy LLM chain init [`doc_parser.py:52`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/doc_parser.py#L52)

```python
bundle = create_llm()          # from core/llm_factory.py → ChatLiteLLMRouter
llm    = bundle.llm
_mapper_chain = MAPPER_PROMPT | llm.with_structured_output(BatchMappingResponse)
```

Chain flow:
1. Fills `MAPPER_PROMPT` slots `{index}` and `{test_cases}`
2. Sends to LLM (via LiteLLM multi-key router)
3. Forces LLM output into `BatchMappingResponse` Pydantic schema (not freeform text)

### Step 6.3 — Fire async batch [`doc_parser.py:228`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/doc_parser.py#L228)

```python
async def _async_map_all():
    return await chain.abatch(
        batch_inputs,
        config={"max_concurrency": concurrency},
        return_exceptions=True  # individual failures stored, don't crash everything
    )
responses = asyncio.run(_async_map_all())
```

**LLM Prompt per module:**
```
SYSTEM: You are an expert Test Automation Architect.
        Map each Manual Test Case to ALL relevant FRD Section IDs from the provided Index.
        A test case may map to multiple sections (Functional Requirement, NFR, Scope).
        Return all mapped references per test case with confidence score (0.0-1.0) and a 1-sentence reason.

USER:   FRD Index:
        Module: 01_User_Auth
        [01_User_Auth:FR-001] Login Functionality (functional) | Users must be able to log in...
        [01_User_Auth:FR-002] Registration (functional) | New users can self-register...
        [01_User_Auth:NFR] Non-Functional Requirements (nfr) | All APIs must respond...

        Test Cases to Map:
        [TC-001] Login with valid credentials | Subj: Login | Type: Functional | Steps: ...
        [TC-002] Login with invalid password  | Subj: Login | Type: Negative   | Steps: ...
```

**LLM returns `BatchMappingResponse`** ([`models.py:110`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/models.py#L110)):
```python
BatchMappingResponse(
    mappings=[
        TestCaseMapping(
            tc_id="TC-001",
            mapped_refs=[
                MappedRef(ref_id="01_User_Auth:FR-001", confidence=0.95, reason="Directly tests login flow"),
                MappedRef(ref_id="01_User_Auth:NFR",    confidence=0.60, reason="Validates response time SLA"),
            ]
        ),
        TestCaseMapping(
            tc_id="TC-002",
            mapped_refs=[
                MappedRef(ref_id="01_User_Auth:FR-001", confidence=0.88, reason="Negative login scenario"),
            ]
        ),
    ]
)
```

**If entire batch call throws an exception:**
```python
except Exception as e:
    responses = [Exception(str(e))] * len(batch_inputs)
    # Every module gets an exception → falls back to empty mappings in Phase 7
```

---

## PHASE 7 — Enrich Test Cases with FRD Context

### Step 7.1 — `enrich_module_test_cases()` [`doc_parser.py:79`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/doc_parser.py#L79)

```python
if isinstance(response, Exception):
    mapping_response = BatchMappingResponse(mappings=[])  # empty fallback
else:
    mapping_response = response

enriched = enrich_module_test_cases(module_tcs, mapping_response, ast)
```

Two lookup dicts are built:
```python
section_map     = {sec.section_id: sec for sec in ast.sections}
tc_mapping_dict = {m.tc_id: m for m in mapping_response.mappings}
```

**For each `TestCaseModel`:**

#### Case A — No LLM mapping for this TC:
```python
mapping = tc_mapping_dict.get(tc.tc_id)
if not mapping or not mapping.mapped_refs:
    tc.feature_ref = "UNKNOWN"   # const.UNKNOWN_FEATURE_REF
    enriched_tcs.append(tc)
    continue
```

#### Case B — Mapping found:

For each `MappedRef` returned by the LLM:

```python
sec = section_map.get(ref.ref_id.strip("[]"))   # look up SectionNode in AST

meta = sec.metadata
# Fallback: no description in metadata → use first 2 paragraphs of section text
d = meta.get("description", "")
if not d and sec.paragraphs:
    d = "\n".join(sec.paragraphs[:2])

sec_context = FeatureContextModel(
    feature_name    = sec.title,
    description     = d,
    trigger         = meta.get("trigger", ""),
    priority        = meta.get("priority", ""),
    actors          = meta.get("actors", []),
    pre_conditions  = meta.get("pre_conditions", []),
    main_flow       = meta.get("main_flow", []),
    post_conditions = meta.get("post_conditions", []),
    business_rules  = meta.get("business_rules", []),
    exception_flows = meta.get("exception_flows", [])
)
```

Builds a `MappedContextModel` per ref ([`models.py:69`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/models.py#L69)):
```python
MappedContextModel(
    ref_id     = "01_User_Auth:FR-001",
    title      = "Login Functionality",
    type       = "functional",
    confidence = 0.95,
    reason     = "Directly tests login flow",
    context    = sec_context    # full FeatureContextModel
)
```

**Picks the single best FRD reference** (highest confidence):
```python
best_ref          = max(mapping.mapped_refs, key=lambda x: x.confidence)
tc.feature_ref    = best_ref.ref_id.strip("[]")    # "01_User_Auth:FR-001"
tc.feature_refs   = [all ref_ids]
tc.mapped_contexts= [all MappedContextModel objects]
```

**Auto-generates Cucumber tags:**
```python
# From tc.subject: "User Login" → "@user_login"
tag_subject = "".join([c if c.isalnum() else "_" for c in tc.subject.lower()]).strip("_")
# From best_ref: "01_User_Auth:FR-001" → "@01_user_auth_fr_001"
tag_feat    = best_ref.ref_id.lower().replace("-","_").replace(":","_")

tags = [f"@{t.lower()}" for t in tc.type]  # ["@functional", "@regression"]
if tag_subject: tags.append(f"@{tag_subject}")
tags.append(f"@{tag_feat}")
tc.cucumber_tags = list(dict.fromkeys(tags))  # deduplicated, order preserved
```

**Final enriched `TestCaseModel`:**
```python
TestCaseModel(
    tc_id            = "TC-001",
    title            = "Login with valid credentials",
    type             = ["Functional", "Regression"],
    subject          = "User Login",
    steps            = ["Navigate to login page", "Enter valid email", "Click Submit"],
    expected_result  = "User is redirected to dashboard",
    feature_ref      = "01_User_Auth:FR-001",
    feature_refs     = ["01_User_Auth:FR-001", "01_User_Auth:NFR"],
    cucumber_tags    = ["@functional", "@regression", "@user_login", "@01_user_auth_fr_001"],
    mapped_contexts  = [
        MappedContextModel(
            ref_id="01_User_Auth:FR-001", confidence=0.95,
            context=FeatureContextModel(
                feature_name   = "Login Functionality",
                description    = "Users must be able to log in using email and password",
                actors         = ["Registered User", "Guest"],
                pre_conditions = ["User has a registered account", "App is accessible"],
                main_flow      = ["Navigate to login", "Enter credentials", "Click Submit"],
                post_conditions= ["Session token issued", "Redirect to dashboard"],
                business_rules = ["Account locks after 5 failed attempts"],
                exception_flows= ["Show error toast on invalid credentials"]
            )
        ),
        MappedContextModel(ref_id="01_User_Auth:NFR", confidence=0.60, ...),
    ]
)
```

---

## PHASE 8 — Build Module Overview from FRD

### Step 8.1 [`doc_parser.py:249`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/doc_parser.py#L249)

Scans all parsed `SectionNode` titles:
```python
overview = ModuleOverviewModel()

for sec in ast.sections:
    title_lower = sec.title.lower()

    if "purpose" in title_lower and not overview.purpose:
        overview.purpose = "\n".join(sec.paragraphs)

    elif "scope" in title_lower:
        is_out = "out of scope" in title_lower
        for p in sec.paragraphs:
            if is_out or "out of scope" in p.lower():
                overview.out_of_scope.append(p)
            else:
                overview.in_scope.append(p)

    elif "glossary" in title_lower:
        for table in sec.tables:
            for row in table:
                if len(row) >= 2:
                    term, definition = row[0].strip(), row[1].strip()
                    if term and term.lower() not in ["term", "acronym"]:
                        overview.glossary[term] = definition
```

**Result `ModuleOverviewModel`** ([`models.py:122`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/models.py#L122)):
```python
ModuleOverviewModel(
    purpose      = "This document defines the login and registration flows...",
    in_scope     = ["User registration", "Login via email", "Password reset"],
    out_of_scope = ["OAuth/SSO login", "Admin user management"],
    glossary     = {"JWT": "JSON Web Token", "OTP": "One-Time Password"}
)
```

---

## PHASE 9 — Assemble and Write the JSON Knowledge File

### Step 9.1 [`doc_parser.py:271`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/agents/doc_parser.py#L271)

**Output path construction:**
```python
module_slug     = "01_user_auth"    # lowercased, non-alphanum → _
module_filename = "01_user_auth_knowledge.json"
knowledge_dir   = os.path.join(out_dir, "knowledge")
module_out_path = os.path.join(knowledge_dir, module_filename)
os.makedirs(knowledge_dir, exist_ok=True)
```

**Assemble root response** [`models.py:131`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/models.py#L131):
```python
module_payload = ParsedDocumentResponse(
    project         = "ShopSphere - 01_User_Auth",
    version         = "2.0",
    module_overview = overview,
    summary         = ParserSummaryModel(total_test_cases=12, skipped_types=[]),
    test_cases      = enriched   # List[TestCaseModel] fully enriched
)
```

**Serialize + strip empty fields via `to_dict()`** [`models.py:139`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/models.py#L139):
```python
def to_dict(self):
    def exclude_empty(data):
        return {k: v for k, v in data if v or v is False or v == 0}
    return asdict(self, dict_factory=exclude_empty)
    # asdict() recursively walks all nested dataclasses → dicts
    # exclude_empty removes all keys with None, "", [], {} values
```

**Write JSON to disk:**
```python
with open(module_out_path, "w", encoding="utf-8") as f:
    json.dump(module_payload.to_dict(), f, indent=2, ensure_ascii=False)
```

---

## Final JSON — `output/knowledge/01_user_auth_knowledge.json`

```json
{
  "project": "ShopSphere - 01_User_Auth",
  "version": "2.0",
  "module_overview": {
    "purpose": "This document defines login and registration flows...",
    "in_scope": ["User registration", "Login via email", "Password reset"],
    "out_of_scope": ["OAuth/SSO login", "Admin user management"],
    "glossary": { "JWT": "JSON Web Token", "OTP": "One-Time Password" }
  },
  "summary": {
    "total_test_cases": 12
  },
  "test_cases": [
    {
      "tc_id": "TC-001",
      "title": "Login with valid credentials",
      "module_folder": "01_User_Auth",
      "type": ["Functional", "Regression"],
      "subject": "User Login",
      "execution_status": "Pass",
      "steps": ["Navigate to login page", "Enter valid email", "Click Submit"],
      "expected_result": "User is redirected to dashboard",
      "feature_ref": "01_User_Auth:FR-001",
      "feature_refs": ["01_User_Auth:FR-001", "01_User_Auth:NFR"],
      "cucumber_tags": ["@functional", "@regression", "@user_login", "@01_user_auth_fr_001"],
      "mapped_contexts": [
        {
          "ref_id": "01_User_Auth:FR-001",
          "title": "Login Functionality",
          "type": "functional",
          "confidence": 0.95,
          "reason": "Directly tests login flow",
          "context": {
            "feature_name": "Login Functionality",
            "description": "Users must be able to log in using email and password",
            "actors": ["Registered User"],
            "pre_conditions": ["User has a registered account"],
            "main_flow": ["Navigate to login", "Enter credentials", "Click Submit"],
            "post_conditions": ["Redirect to dashboard"],
            "business_rules": ["Account locks after 5 failed attempts"],
            "exception_flows": ["Show error toast on invalid credentials"]
          }
        },
        {
          "ref_id": "01_User_Auth:NFR",
          "title": "Non-Functional Requirements",
          "type": "nfr",
          "confidence": 0.60,
          "reason": "Validates response time SLA",
          "context": { "feature_name": "...", "description": "All APIs must respond within 2 seconds" }
        }
      ]
    }
  ]
}
```

---

## Full Pipeline Summary

```
input_modules/01_User_Auth/
  FRD_UserAuth.docx ────────────────────────────────────────────┐
  TC_UserAuth.docx  ──────────────────────────────┐             │
                                                   │             │
                              [scanners.py]        │   [scanners.py]
                      TestCaseModuleParser         │   FRDModuleParser
                                                   │             │
                               List[TestCaseModel] │        DocumentAST
                         (tc_id, title, steps,     │  (SectionNodes: id, type,
                          subject, type, ...)       │   paragraphs, metadata)
                                                   │             │
                                                   └─────────────┤
                                                                 │
                                            [doc_parser.py]      │
                                       build_compact_index ──────┘
                                       build TC summaries
                                                                 │
                                                                 ▼
                                                    LLM: MAPPER_PROMPT
                                               (async batch, all modules
                                                concurrently via LiteLLM)
                                                                 │
                                                  BatchMappingResponse
                                             (TC-001 → FR-001 @ 0.95, NFR @ 0.60)
                                                                 │
                                                                 ▼
                                           enrich_module_test_cases()
                                         Merges: feature_ref, feature_refs,
                                                 mapped_contexts (with full
                                                 FRD context), cucumber_tags
                                                                 │
                                           build ModuleOverviewModel
                                           (purpose, scope, glossary)
                                                                 │
                                                                 ▼
                                output/knowledge/01_user_auth_knowledge.json
                                (ParsedDocumentResponse.to_dict() → JSON)
                                      → picked up by cs_agent.py (Stage 2)
```
