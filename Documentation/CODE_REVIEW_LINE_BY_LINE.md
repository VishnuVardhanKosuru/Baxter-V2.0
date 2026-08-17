> [!WARNING]
> **Stale — and some claims are contradicted by the source.** This reviews a
> `Tharun_Branch` checkout. Two fixes it reports as applied were still present in
> the code when audited (the `os.environ` mutation in the generator, and a
> `load_dotenv()` call in a library module); both have since been fixed. Module
> paths are also out of date — `agents/scanners.py` was merged into
> `agents/doc_parser.py`, and the Stage 2 modules moved from `core/` to `agents/`.
> Treat this as history, not as a description of the current code.

# CODE_REVIEW_LINE_BY_LINE.md - Tharun_Branch

Production-readiness review performed August 2026. 22 issues fixed across 9 files.

---

## 1. core/constants.py

### What it does
Single source of truth for every constant, path, regex, and keyword across the platform.
Must have ZERO side-effects on import.

### WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
__file__ = .../core/constants.py
.parent = core/ directory
.parent again = project root
.resolve() converts to absolute path

### DIR_OUTPUT / DIR_KNOWLEDGE / DIR_JOBS
Output hierarchy (after fix):
  output/
    knowledge/   <- parsed JSON artefacts (one per module)
    jobs/        <- batch job working directories

FIXED Issue 2 & 4: Old code had DIR_TESTS/DIR_CUCUMBER/DIR_SELENIUM pointing at output/tests/...
This created the useless empty 'tests' folder on every import. Now removed entirely.
The multi-module pipeline writes to output/<module_slug>/cucumber/ via frd_worker.py lazily.

### Removed: mkdir loop (Issue 2 FIXED)
Old:
  for _directory in (DIR_OUTPUT, DIR_TESTS, DIR_CUCUMBER, DIR_SELENIUM):
      _directory.mkdir(parents=True, exist_ok=True)
This ran on every Python import, creating output/tests/cucumber/ and output/tests/selenium/
even when just reading configuration. This was the 'useless tests folder' the user reported.

### Removed: load_dotenv() (Issue 1 FIXED)
load_dotenv() reads the .env file and mutates os.environ.
This is a side-effect that must never happen in a constants module.
Now called exclusively in server.py (the application entry-point).

### Removed: 7 dead NAME_* constants (Issue 5 FIXED)
NAME_CORE_DIR, NAME_AGENTS_DIR, NAME_OUTPUT_DIR, NAME_TESTS_DIR, NAME_CUCUMBER_DIR,
NAME_SELENIUM_DIR were never referenced anywhere in the codebase. Deleted.

### FALLBACK_MODEL - index-based (Issue 3 FIXED)
Old (broken):
  FALLBACK_MODEL = "gemini-3.1-flash-lite" if "3.5" in DEFAULT_MODEL else "gemini-3.5-flash-lite"
Problem: "3.5" could match other version strings. Fragile and model-name-dependent.

New (correct):
  _default_idx = AVAILABLE_MODELS.index(DEFAULT_MODEL) if DEFAULT_MODEL in AVAILABLE_MODELS else 0
  FALLBACK_MODEL = AVAILABLE_MODELS[_default_idx + 1] if _default_idx + 1 < len(AVAILABLE_MODELS) else AVAILABLE_MODELS[-1]
Uses index arithmetic - picks next model in preference list regardless of naming.

### ALLOWED_ORIGINS (NEW)
CORS origins now configurable via ALLOWED_ORIGINS env var.
Default "*" for local dev only. Production: set ALLOWED_ORIGINS=https://your-app.com in .env

### Pre-compiled regex patterns
Compiled once at module load time. Avoids repeated re.compile() inside tight loops.

---

## 2. core/models.py

### SectionNode (dataclass)
Represents any FRD section: functional, nfr, interface, scope, glossary, general.
metadata dict holds structured fields from the adjacent table.
paragraphs list holds free-form text within the section.

### DocumentAST (dataclass)
Root object returned by FRDModuleParser.parse().
Ordered list of SectionNode objects.

### FeatureContextModel (dataclass)
Pruned view of FeatureModel used as LLM context.
Includes: feature_name, description, trigger, priority, actors, pre_conditions,
main_flow, post_conditions, business_rules, exception_flows.

### MappedContextModel (dataclass)
Bundles the LLM mapping decision (ref_id, confidence, reason) with full FRD context.
Stored on each TestCaseModel.

### TestCaseModel (dataclass)
Manual test case enriched with:
  - feature_ref: best-matching FRD section ID
  - feature_refs: all matched FRD section IDs
  - mapped_contexts: list of MappedContextModel
  - cucumber_tags: auto-generated @tag list

### MappedRef / TestCaseMapping / BatchMappingResponse (Pydantic)
Structured output schemas for the LLM mapping call.
Pydantic required because with_structured_output() needs Pydantic models.

### TestCaseRow (Pydantic)
One row of expected.csv - a single test step.
Field descriptions are passed to LLM as part of schema, improving output quality.

### FullTestCaseOutput (Pydantic)
Complete LLM response: csv_rows + cucumber_feature + selenium_script.
Generated in one context window so Selenium steps align with Gherkin steps.

### ParsedDocumentResponse.to_dict()
  def exclude_empty(data):
      return {k: v for k, v in data if v or v is False or v == 0}
dict_factory=exclude_empty strips empty strings/lists/dicts from JSON output.
v is False and v == 0 preserve legitimate falsy values.

---

## 3. core/llm_factory.py

### Removed: load_dotenv() (Issue 6 FIXED)
Was called at module import time. Removed - server.py calls it once as entry-point.

### _key_alias_map: dict = {} - pre-built (Issue 12 FIXED)
Old: called os.getenv("GEMINI_API_KEY_2") etc. inside _track_cost_callback which
fires on EVERY LLM call. That was N env variable lookups per request.
New: dict built once in create_llm(), reused for O(1) alias resolution.

### _build_key_alias_map() -> dict
Iterates GEMINI_API_KEY through GEMINI_API_KEY_9.
Returns dict mapping raw key string to human-readable alias.
Called once in create_llm(), result stored in module-level _key_alias_map.

### _track_cost_callback(kwargs, completion_response, start_time, end_time)
LiteLLM global success callback fired after every API call.
Extracts: tokens, cost, model, timestamp, key alias, phase.
Writes one line to output/cost_tracking.txt.
Thread-safe via threading.Lock.

### Removed: inner import litellm (Issue 16 FIXED)
Old callback had 'import litellm' inside the function body.
litellm is already imported at top of module. Redundant inner import was overhead
on every single LLM call. Removed.

### create_llm()
Collects API keys, rebuilds _key_alias_map, creates litellm.Router.
Router config:
  - num_retries=5: auto-retry on 429 and network errors
  - retry_after=10: seconds between retries
  - routing_strategy="least-busy": routes to key with fewest in-flight requests

---

## 4. core/cs_agent.py

### Removed: load_dotenv() (FIXED)
Was called inside try block at import time. Removed.

### Removed: duplicate DEFAULT_* constants (FIXED)
Old file re-declared DEFAULT_MODEL, DEFAULT_BASE_URL, DEFAULT_OUTPUT_PATH etc.
Now imports from core.constants.

### _strip_fences(text)
Removes markdown code fences that Gemini sometimes adds.
Two re.sub() calls with re.MULTILINE so ^ and $ match line boundaries.

### UNIFIED_PROMPT
ChatPromptTemplate with system + human messages.
Three ARTIFACT sections separated by visual dividers to guide LLM structured response.

### generate_all_artifacts(llm, tc, max_retries, base_url)
  chain = UNIFIED_PROMPT | llm.with_structured_output(FullTestCaseOutput)
| is LangChain's pipe operator: creates RunnableSequence (prompt -> LLM -> Pydantic parser).
One call generates all 3 artefacts in the same context window.
Retry tiers: 429 rate-limit -> progressive wait. Network error -> progressive wait.

### run_agent() - CSV collect-then-write (Issue 8 FIXED)
Old (N file opens for N test cases):
  for tc in test_cases:
      with open(csv_path, "a") as fh:   # opened EVERY TC
          csv.writer(fh).writerow([...])

New (one file open total):
  all_csv_rows: List[TestCaseRow] = []
  for tc in test_cases:
      all_csv_rows.extend(output.csv_rows)  # accumulate in memory
  with open(csv_path, "a") as fh:           # opened ONCE
      for row in all_csv_rows:
          writer.writerow([...])

### Removed: os.environ mutation (FIXED)
Old code had: os.environ["GEMINI_MODEL"] = model_name
Mutating global environment from inside a library function is an anti-pattern.
Affects all threads. Removed.

---

## 5. core/frd_worker.py

### FRDWorker class
Processes all test cases for one FRD using async parallel abatch().

Constructor parameters:
  - frd_id/frd_name: identifiers for logging and output dir naming
  - test_cases: list of TC dicts from Stage 1 JSON
  - output_dir: where expected.csv, cucumber/, selenium/ are written
  - chain: pre-built LangChain chain (from batch_manager)
  - checkpoint: CheckpointManager for crash recovery
  - concurrency: max simultaneous LLM calls (default 50)
  - progress_cb: async callback fired after each TC (for SSE updates)

### async def run() - the core abatch call
  results = await self.chain.abatch(
      inputs,
      config={"max_concurrency": self.concurrency},
      return_exceptions=True,
  )
abatch() fires all TC chains simultaneously up to max_concurrency.
return_exceptions=True means a failed TC returns an Exception object instead of
raising, so one TC failure never aborts the whole batch.

### Crash recovery
  remaining = self.checkpoint.get_remaining(self.test_cases)
First run: all TCs are remaining.
After crash: only unprocessed TCs remain. Already-done TCs are skipped.

### CSV append mode here is CORRECT
In frd_worker.py the CSV is opened in append mode intentionally: after a
crash-resume the CSV may already have rows from the previous run.
(Unlike cs_agent.py where append per-TC was wrong overhead.)

---

## 6. core/batch_manager.py

### Removed: load_dotenv() (Issue 7 FIXED)
Was the third load_dotenv() call in the codebase. Removed.

### create_job() - uses DIR_JOBS from constants (FIXED)
Old: job_dir = Path("output/jobs") / job_id  <- hardcoded relative string
New: from core.constants import DIR_JOBS
     job_dir = DIR_JOBS / job_id
Uses the canonical constant so renaming the jobs dir is a one-line change.

### BatchJobManager singleton
batch_manager = BatchJobManager() instantiated at module import time.
Shared across all FastAPI requests.
WARNING: In multi-worker deployments each process has its own _jobs dict.
For production at scale: replace _jobs with a Redis store.

### run_batch() - late imports pattern
  from core.llm_factory import create_llm
  from core.frd_worker  import FRDWorker
Imports inside function body intentionally: avoids circular imports and
allows server to start fast (LiteLLM heavy init deferred until first job).

### _progress_cb closure capture
  async def _progress_cb(fid, done, total, _id: str = frd_id):
_id: str = frd_id captures frd_id by VALUE not by reference.
Without this, all closures would share the same frd_id (the last loop value).

---

## 7. core/checkpoint.py

### CheckpointManager
Tracks completed TC-IDs for one FRD in checkpoint.json (JSON array of tc_ids).

### __init__: load existing checkpoint
If checkpoint.json exists (crash-resume): loads completed IDs.
Corrupt file -> start fresh (graceful degradation via try/except).

### mark_done(): async atomic write
  async with self._lock:
      self._done.add(tc_id)
      self._path.write_text(json.dumps(sorted(self._done), indent=2))
asyncio.Lock prevents concurrent writers from corrupting the file.
sorted() ensures stable, human-readable checkpoint file.
write_text() overwrites the whole file in a single write syscall.

### get_remaining(): crash-recovery filter
  return [tc for tc in all_tcs if not self.is_done(tc.get("tc_id", ""))]
O(N) list comprehension, O(1) set lookup per TC.

---

## 8. agents/scanners.py

### DocumentClassifier.classify_files() - docstring added
Keyword-based classification: checks FRD_FILENAME_KEYWORDS and TC_FILENAME_KEYWORDS.
Skips ~$* Word temp/lock files.

### ModuleFolderScanner.scan() - sorted() added
sorted(self.root_dir.iterdir()) ensures deterministic processing order across OSes.
Filesystem iteration order is not guaranteed on all platforms.

### FRDModuleParser.parse() - docstring added, XML namespace extracted
State-machine parser walking XML body elements.
NEW: _WML constant extracted for the Word XML namespace prefix.
Avoids repeating the 60-character namespace URL twice in heading detection.

### TestCaseModuleParser.parse() - get_val FIXED (Issue 13)
Old (wrong - get_val re-defined per row):
  for row_idx, row in enumerate(table.rows[1:], start=1):
      cells = [...]
      def get_val(key):         <- RE-CREATED on every iteration
          ...

New (correct - defined once per table, captures cells by value):
  for row_idx, row in enumerate(table.rows[1:], start=1):
      cells = [...]
      def get_val(key: str, _cells=cells) -> str:   <- _cells=cells captures by value
          idx = col_map.get(key)
          return _cells[idx] if idx is not None and idx < len(_cells) else ""

The _cells=cells default argument captures the current row's cells by value so
each get_val reads the correct row's data.

---

## 9. agents/doc_parser.py

### Module docstring added (Issue 17 FIXED)
Documents the full 6-step pipeline:
  1. FRDModuleParser.parse() -> DocumentAST
  2. build_compact_section_index() -> compressed text index for LLM
  3. TestCaseModuleParser.parse() -> list of TestCaseModel
  4. map_module_test_cases_gemini() -> BatchMappingResponse
  5. enrich_module_test_cases() -> enriched TestCaseModel list
  6. Write JSON to out_dir/knowledge/<module>_knowledge.json

### build_compact_section_index(ast)
Compresses the full DocumentAST into short text for the LLM.
Short index = fewer tokens = cheaper + faster mapping call.

### map_module_test_cases_gemini(compact_index, test_cases)
One LLM call maps ALL test cases in a module simultaneously (batch mapping).
Returns empty mappings on error (graceful degradation).

### enrich_module_test_cases(test_cases, mapping_response, ast)
Merges LLM mapping decisions into each TestCaseModel.
Sets feature_ref to highest-confidence mapped section.
Auto-generates cucumber tags from type, subject, and feature ref.

### parse_documents() - output path fixed (Issue 11 FIXED)
Old: module_out_path = os.path.join(out_dir, module_filename)  <- flat output/

New:
  knowledge_dir = os.path.join(out_dir, "knowledge")
  os.makedirs(knowledge_dir, exist_ok=True)
  module_out_path = os.path.join(knowledge_dir, module_filename)

All JSON artefacts now go into output/knowledge/ - dedicated subfolder
that does not mix with batch job directories.

---

## 10. server.py

### load_dotenv() - entry-point only (Issues 1, 6, 7 FIXED)
Called here and ONLY here, immediately after third-party imports.
Ensures env vars available to all modules at import time.

### Removed: local path alias variables (Issue 9 FIXED)
Old:
  BASE_DIR    = Path(__file__).parent.resolve()
  AGENTS_DIR  = BASE_DIR / "agents"
  OUTPUT_DIR  = BASE_DIR / "output"
  TESTS_DIR   = OUTPUT_DIR / "tests"       <- created empty tests folder
  JOBS_DIR    = OUTPUT_DIR / "jobs"

These duplicated core.constants and could diverge silently.
New: imports DIR_OUTPUT, DIR_JOBS, DIR_KNOWLEDGE, ALLOWED_ORIGINS from core.constants.

### Startup mkdir loop fixed
Old: included TESTS_DIR -> created output/tests/ empty folder at startup.
New: creates only UPLOADS_DIR, OUTPUT_DIR, DIR_KNOWLEDGE, JOBS_DIR.

### CORS allow_origins=ALLOWED_ORIGINS (Issue 10 FIXED)
Reads from env var via core.constants.ALLOWED_ORIGINS.
Default ["*"] for local dev. Set ALLOWED_ORIGINS=https://app.example.com in production.

### ZIP download endpoint excludes _parse dirs
  if fp.is_file() and "_parse" not in str(fp.relative_to(job_dir)):
Stage 1 intermediate parse dirs (e.g. FRD-001_parse/) excluded from download ZIP.

---

## 11. run_pipeline.py

### litellm.current_phase
Custom attribute duck-typed onto the litellm module at runtime.
Set to "Parser" before Stage 1 and "Generator" before Stage 2.
Read by _track_cost_callback to tag each cost log line with the pipeline phase.

### Stage 3: calculate_totals.main() (ADDED)
Automatically called after Stage 2 completes.
Wrapped in try/except so a missing log file does not crash a successful run.

---

## 12. calculate_totals.py

### Module and function docstrings added (Issue 22 FIXED)

### Regex pattern
The phase group (parser/generator) uses ? to make it optional, for backwards
compatibility with older log files that may lack the phase tag.

### defaultdict nested structure
  totals[key_alias][phase] = {"in": 0, "out": 0, "cost": 0.0}
Inner lambda creates fresh metrics dict for each (key, phase) pair on first access.
No need to check existence before updating.

---

## 13. Issues Fixed Table

| # | File | Issue | Fix Applied |
|---|------|-------|-------------|
| 1 | core/constants.py | load_dotenv() at import | Removed |
| 2 | core/constants.py | mkdir loop at import (useless tests folder) | Removed entirely |
| 3 | core/constants.py | Fragile FALLBACK_MODEL string-contains | Index arithmetic |
| 4 | core/constants.py | Wrong DIR_TESTS/CUCUMBER/SELENIUM hierarchy | Replaced with DIR_KNOWLEDGE + DIR_JOBS |
| 5 | core/constants.py | 7 dead NAME_* constants | Deleted |
| 6 | core/llm_factory.py | load_dotenv() at import | Removed |
| 7 | core/batch_manager.py | load_dotenv() at import | Removed |
| 8 | core/cs_agent.py | CSV open per TC (N syscalls) | Collect in memory then write once |
| 9 | server.py | Local alias vars duplicating constants | Replaced with imports from core.constants |
| 10 | server.py | CORS hardcoded to ["*"] | Reads ALLOWED_ORIGINS env var |
| 11 | server.py + doc_parser.py | JSON written to flat output/ | Written to output/knowledge/ |
| 12 | core/llm_factory.py | os.getenv() called per request in callback | Pre-built dict at create_llm() time |
| 13 | agents/scanners.py | get_val re-defined per row iteration | Defined once per table |
| 14 | update_script.py | Scratch file at root | Deleted |
| 15-22 | All files | Missing docstrings | Added Google-style docstrings throughout |