# 📁 Direct Module Folder `.docx` Parser Architecture (Detailed Specifications)

## Executive Summary

Version 2 Parser processes root intake directories containing **direct module subfolders** (e.g. `01_Auth/`, `02_Checkout/`, `03_Inventory/`), where each module subfolder contains its FRD `.docx` document(s) and Manual Test Case `.docx` document(s) directly alongside each other in the same folder.

The architecture uses an **Automated Document Classifier** + **Modular 5-Part Pipeline** combining **deterministic Python code** for extraction/enrichment with **batched Gemini API calls** for semantic mapping per module.

---

## Folder Intake Directory Hierarchy

```
input_modules/
├── 01_User_Authentication/
│   ├── 01_Auth_FRD.docx             (FRD document)
│   └── 01_Auth_TCs.docx             (Manual Test Case suite)
├── 02_Checkout_and_Payment/
│   ├── 02_Checkout_FRD.docx         (FRD document)
│   └── 02_Checkout_TCs.docx         (Manual Test Case suite)
└── 03_Inventory_Management/
    ├── 03_Inventory_FRD.docx        (FRD document)
    └── 03_Inventory_TCs.docx        (Manual Test Case suite)
```

---

## Modular Pipeline Architecture

```
  [Input Modules Directory]
  ├── 01_User_Authentication/  ──▶ [Module 1 Loop] ──▶ Gemini Mapping 1
  ├── 02_Checkout_and_Payment/ ──▶ [Module 2 Loop] ──▶ Gemini Mapping 2
  └── 03_Inventory_Management/ ──▶ [Module 3 Loop] ──▶ Gemini Mapping 3
                                         │
                                         ▼
                 ┌──────────────────────────────────────────┐
                 │ Python Master Context & Artifact Merger  │
                 │ Combines all modules, synthesizes @tags │
                 └───────────────────┬──────────────────────┘
                                     │
                                     ▼
                 ┌──────────────────────────────────────────┐
                 │ Master Knowledge Artifact                │
                 │ (knowledge_artifact.json / parsed.json)  │
                 └──────────────────────────────────────────┘
```

---

## Detailed Processing Flow per Module Folder (e.g., `01_User_Authentication/`)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 0: Automated Document Classification (Python Code — 0 LLM Calls)        │
│                                                                             │
│ • Python scans 01_User_Authentication/*.docx files.                         │
│ • Inspects filenames & XML heading/table signals:                           │
│   - Files with "FRD", "Requirement" or "Requirement ID:" → FRD Document     │
│   - Files with "TC", "Test", "Manual" or Test Data Grids → Test Case Suite  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1A: Extract Module FRD .docx (Python Code — 0 LLM Calls)                │
│                                                                             │
│ • Reads classified FRD .docx via FullDocumentParser.                        │
│ • Builds DocumentAST_01 (Metadata, Scope, FRs, NFRs, Interfaces, Glossary). │
│ • Namespaces section IDs with module prefix (e.g. MOD01:FR-001).             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1B: Extract Module Test Case .docx (Python Code — 0 LLM Calls)         │
│                                                                             │
│ • Reads classified Test Case .docx files, scanning ALL tables per file.     │
│ • Auto-detects header columns and extracts `Module_Test_Cases[]`.           │
│ • Attaches provenance: `module_folder`, `source_file`, `source_table`.      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Module Compact Index Construction (Python Code — 0 LLM Calls)       │
│                                                                             │
│ • Builds CompactIndex_01 (~800 tokens) summarizing Module 01 sections.      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Batched Gemini Mapping API Call (1 Call per Module Folder)          │
│                                                                             │
│ • Input: CompactIndex_01 + Module_Test_Cases[] (~3,000 tokens input).       │
│ • Output: Structured Pydantic response mapping Module 01 TCs -> section IDs.│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Post-Processing & Master Artifact Merge (Python Code)               │
│                                                                             │
│ • Resolves section IDs against DocumentAST_01 and embeds full FR/NFR text.  │
│ • Auto-synthesizes Cucumber tags (@mod01_auth, @fr_001, @nfr_sec).          │
│ • Appends enriched module test cases into master `knowledge_artifact.json`. │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Component Specifications & Trade-Off Analysis

---

### STEP 0: Automated Document Classification

#### What We Will Be Doing
When inspecting a module folder like `01_User_Authentication/`, `DocumentClassifier` scans all `.docx` files. It evaluates both filename keywords and internal XML element signals:
- **FRD Document Signals**: Filename contains `"FRD"`, `"Requirement"`, `"Spec"`, or document contains paragraph headings with `"Requirement ID:"`.
- **Test Case Suite Signals**: Filename contains `"TC"`, `"Test"`, `"Manual"`, or document contains tables with header text (`"Test Name"`, `"Steps"`, `"Expected Result"`).

#### Why This Specific Approach?
1. **Zero Configuration**: User just drops `.docx` files directly into module folders without needing subdirectories.
2. **Robust**: Dual-check (filename + internal XML structure) guarantees accurate classification even if files are renamed.

---

### PART 1: Module FRD AST Extraction (Step 1A)

#### What We Will Be Doing
`FRDModuleParser` parses the classified FRD `.docx` file using `FullDocumentParser`. It walks body XML elements (`p` paragraphs and `tbl` tables) in document order, building `DocumentAST_mod`. Section IDs are namespace-prefixed with the module folder name (`MOD01:FR-001`).

#### Tools & Libraries
- **Language/Runtime**: Python 3.10+
- **Library**: `python-docx` (`doc.element.body`, `w:pStyle` XML inspection), `pathlib.Path`

---

### PART 2: Module Test Case Extraction (Step 1B)

#### What We Will Be Doing
`TestCaseModuleParser` parses the classified Test Case `.docx` file(s). It iterates over **every table in every file**, auto-detecting column headers (`test_name`, `type`, `subject`, `description`, `expected_result`). It extracts all rows into `Module_Test_Cases[]`, tagging each row with `module_folder`, `source_file`, `source_table`, and `source_row`.

#### Tools & Libraries
- **Library**: `python-docx` (`DocxTable`, `table.rows`, `cell.text`)

---

### PART 3: Module Compact Section Index Construction

#### What We Will Be Doing
Builds a compact ~800-token summary index for the current module's FRD by extracting key information-bearing fields (`description` first sentence, `business_rules`, `system_interfaces` rows, NFR text) from `DocumentAST_mod`.

---

### PART 4: Per-Module Gemini Mapping API Loop (Step 3)

#### What We Will Be Doing
Executes **1 batched API call per module folder** to Gemini (`gemini-3.5-flash-lite` / `gemini-3.1-flash-lite`). Passes `CompactIndex_mod` + `Module_Test_Cases[]` in a single prompt using Pydantic structured output (`BatchMappingResponse`).

#### Tools & Libraries
- **Framework**: `langchain-google-genai` / `google-generativeai` SDK
- **Structured Output**: Pydantic v2 (`BaseModel`, `Field`, `with_structured_output`)

---

### PART 5: Master Context & Artifact Merging (Step 4)

#### What We Will Be Doing
Python receives Gemini's mapping array per module loop. For each test case, Python looks up mapped section IDs in `DocumentAST_mod`, attaches full requirement text, auto-synthesizes Cucumber tags (e.g. `@mod01_auth`, `@fr_001`, `@nfr_sec`, `@sendgrid`), and appends the enriched test cases into the master `knowledge_artifact.json`.

---

## Comprehensive Trade-Off Matrix

| Pipeline Part | Chosen Approach | Why Chosen | Alternative Rejected | Why Rejected |
|---|---|---|---|---|
| **Intake Layout** | Direct Module Subfolders (`01_Auth/01_Auth_FRD.docx`, `01_Auth_TCs.docx`) | Simple, zero subfolders needed; direct folder layout | Nested Subfolders (`01/FRD/`, `01/TestCases/`) | Extra nested directories required by user |
| **Doc Classifier** | Filename + XML Heading/Table Inspection | Auto-classifies FRDs vs TCs reliably | Manual File Flagging | Forces users to pass explicit CLI arguments per file |
| **Part 1: FRD Extraction** | `python-docx` XML Heading Traversal | 100% deterministic, sub-second, zero cost, zero hallucination | LLM FRD Extraction | Hallucinates, loses middle sections, expensive |
| **Part 2: TC Extraction** | Multi-Table `python-docx` Reader | Auto-detects headers, scans all tables per file | LLM Table Extraction | Redundant on Word data grids, risk of step loss |
| **Part 3: Indexing** | High-Density Compact Section Index | ~800 tokens/module, preserves technical signals | Full Text Index | 50K+ tokens, triggers rate limits & lost in middle |
| **Part 4: Mapping** | Batched Gemini API per Module Loop | 1 call per module folder (low RPD), structured JSON | Vector DB / Embeddings | Surface distance match only; cannot reason context |
| **Part 5: Enrichment** | Python Local Lookup & Tag Synthesis | Lossless full text attachment, strict `@tag` formatting | LLM Tag Generation | Inconsistent casing, missing `@`, non-deterministic |
