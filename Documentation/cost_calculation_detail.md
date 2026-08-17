> [!WARNING]
> **Stale — describes a previous branch layout.** File paths point at a
> `Tharun_Branch` checkout and line numbers have drifted. The log parsing and
> aggregation shown inline in `calculate_totals.py` now lives in
> `core/cost_report.py`, shared with the `/api/cost/*` endpoints.
> See `readme.md` for the current structure.

# Cost Tracking & Aggregation Pipeline — Detailed Code Walkthrough
> From real-time LLM token interception → `output/cost_tracking.txt` → `output/cost_totals.txt`

**Files involved:**
- [`calculate_totals.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/calculate_totals.py)
- [`core/llm_factory.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/llm_factory.py)
- [`run_pipeline.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/run_pipeline.py)
- [`output/cost_tracking.txt`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/output/cost_tracking.txt)
- [`output/cost_totals.txt`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/output/cost_totals.txt)

---

## Architecture & Data Flow Overview

```
[run_pipeline.py]
  litellm.current_phase = "Parser" ───┐
  litellm.current_phase = "Generator" ─┤
                                      │
                                      ▼
[Any LLM API Call] ──► LiteLLM Router (Key 1, 2, or 3)
                              │
                              ▼ (on completion)
[core/llm_factory.py]
  _track_cost_callback()
    ├── Extracts usage (prompt_tokens, completion_tokens)
    ├── Calculates cost via litellm.completion_cost()
    ├── Maps API Key -> Key Alias via pre-built _key_alias_map
    ├── Reads litellm.current_phase ("Parser" / "Generator")
    └── Thread-safe append (with _cost_log_lock)
                              │
                              ▼
           output/cost_tracking.txt (Raw Execution Log)
                              │
                              ▼
[calculate_totals.py]
  main()
    ├── Reads output/cost_tracking.txt line-by-line
    ├── Extracts fields via compiled regex (Line Pattern)
    ├── Aggregates into nested defaultdict: totals[key][phase]
    └── Formats & writes human-readable summary
                              │
                              ▼
           output/cost_totals.txt (Final Summary Report)
```

---

## PHASE 1 — Key Alias Mapping Initialization

### Step 1.1 — `_build_key_alias_map()` [`core/llm_factory.py:43`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/llm_factory.py#L43)

Before any LLM calls are made, `llm_factory.py` scans the environment for configured keys and builds an **in-memory lookup table** mapping secret keys to human-readable labels:

```python
def _build_key_alias_map() -> dict:
    mapping = {}
    for prefix in ["GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
        for i in range(1, 10):
            suffix = "" if i == 1 else f"_{i}"
            key = os.getenv(f"{prefix}{suffix}")
            if key:
                mapping[key] = f'{prefix.split("_")[0]} Key {i}'
    return mapping

_key_alias_map = _build_key_alias_map()  # pre-computed at module load time
```

**Example generated `_key_alias_map`:**
```python
{
    "AIzaSyD...key1...": "GEMINI Key 1",
    "AIzaSyB...key2...": "GEMINI Key 2",
    "AIzaSyC...key3...": "GEMINI Key 3",
    "sk-proj-...":       "OPENAI Key 1"
}
```

> **Why pre-built? (Issue 12 FIXED):** Instead of calling `os.getenv()` multiple times per API call inside the callback (which executes hundreds of times), this lookup is `O(1)` dictionary access.

---

## PHASE 2 — Dynamic Pipeline Phase Tagging

### Step 2.1 — Runtime Phase Injection [`run_pipeline.py:27, 35`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/run_pipeline.py#L27)

`run_pipeline.py` tags the global `litellm` module state dynamically before each stage:

```python
# Stage 1: Document Parsing & AST Enrichment
litellm.current_phase = "Parser"
json_paths = parse_documents(modules_dir, out_dir)

# Stage 2: Cucumber & Selenium Code Generation
litellm.current_phase = "Generator"
for json_path in json_paths:
    run_agent(stage1_json_path=json_path, out_dir_path=module_out_dir)
```

Because `litellm` is a shared module singleton across all threads, any LLM request completed during Stage 1 inherits `"Parser"`, and any completed during Stage 2 inherits `"Generator"`.

---

## PHASE 3 — Real-Time Cost Interception & Logging

### Step 3.1 — Callback Registration [`core/llm_factory.py:84-85`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/llm_factory.py#L84-L85)

LiteLLM hooks are registered globally for both synchronous and asynchronous invocations:

```python
litellm.success_callback = [_track_cost_callback]
litellm._async_success_callback = [_track_cost_callback]
```

### Step 3.2 — `_track_cost_callback()` [`core/llm_factory.py:53`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/llm_factory.py#L53)

After **every single model call**, LiteLLM triggers this handler:

```python
def _track_cost_callback(kwargs, completion_response, start_time, end_time):
    try:
        # 1. Extract token usage
        usage = completion_response.get("usage", {})
        input_tokens  = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # 2. Calculate exact dollar cost via LiteLLM pricing tables
        cost = litellm.completion_cost(completion_response=completion_response)
        cost = cost or 0.0

        # 3. Extract model name & timestamp
        model     = completion_response.get("model", "unknown")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 4. Resolve key alias in O(1)
        api_key   = kwargs.get("litellm_params", {}).get("api_key", "")
        key_alias = _key_alias_map.get(api_key, "Unknown Key")

        # 5. Read current execution phase
        phase    = getattr(litellm, "current_phase", "Unknown")

        # 6. Format raw log line
        log_line = (
            f"[{timestamp}] [{phase}] Model: {model} ({key_alias}) | "
            f"Tokens: {input_tokens} In, {output_tokens} Out | "
            f"Cost: ${cost:.6f}\n"
        )

        os.makedirs(os.path.dirname(_COST_LOG_FILE), exist_ok=True)

        # 7. Thread-safe atomic file append
        with _cost_log_lock:
            with open(_COST_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_line)
    except Exception as exc:
        print(f"[WARN] Failed to track cost: {exc}")
```

### Step 3.3 — Output Format of `output/cost_tracking.txt`

```text
[2026-08-17 14:47:52] [Parser] Model: gemini-3.1-flash-lite (GEMINI Key 1) | Tokens: 878 In, 429 Out | Cost: $0.000863
[2026-08-17 14:47:53] [Parser] Model: gemini-3.1-flash-lite (GEMINI Key 1) | Tokens: 853 In, 469 Out | Cost: $0.000917
[2026-08-17 14:47:59] [Generator] Model: gemini-3.1-flash-lite (GEMINI Key 1) | Tokens: 1395 In, 1047 Out | Cost: $0.001919
[2026-08-17 14:48:02] [Generator] Model: gemini-3.1-flash-lite (GEMINI Key 2) | Tokens: 1274 In, 1022 Out | Cost: $0.001852
[2026-08-17 14:48:07] [Generator] Model: gemini-3.1-flash-lite (GEMINI Key 3) | Tokens: 1277 In, 1266 Out | Cost: $0.002218
```

---

## PHASE 4 — Log Parsing & Regular Expression Extraction

### Step 4.1 — `main()` & Pre-compiled Regex [`calculate_totals.py:22-54`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/calculate_totals.py#L22)

```python
def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(base_dir, "output", "cost_tracking.txt")
    out_file = os.path.join(base_dir, "output", "cost_totals.txt")

    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return
```

### Step 4.2 — Regex Pattern Breakdown [`calculate_totals.py:48-54`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/calculate_totals.py#L48)

```python
line_pattern = re.compile(
    r"\[.*?\]\s+"                       # Match timestamp [2026-08-17 ...]
    r"(?:\[(.*?)\]\s+)?"                # Match optional phase [Parser] or [Generator] (Group 1)
    r"Model:\s+.*?\((.*?)\)\s+\|\s+"    # Match key alias inside parentheses (Group 2)
    r"Tokens:\s+(\d+)\s+In,\s+(\d+)\s+Out\s+\|\s+"  # Input & Output tokens (Groups 3, 4)
    r"Cost:\s+\$([\d\.]+)"              # Dollar cost (Group 5)
)
```

| Capture Group | Regex Component | Extracted Value Example | Fallback if Missing |
|---|---|---|---|
| Group 1 | `(?:\[(.*?)\]\s+)?` | `"Parser"` or `"Generator"` | Defaults to `"Generator"` (backward compatibility) |
| Group 2 | `\((.*?)\)` | `"GEMINI Key 1"` | N/A (must match) |
| Group 3 | `Tokens:\s+(\d+)\s+In` | `878` (parsed as `int`) | N/A |
| Group 4 | `(\d+)\s+Out` | `429` (parsed as `int`) | N/A |
| Group 5 | `Cost:\s+\$([\d\.]+)` | `0.000863` (parsed as `float`)| N/A |

---

## PHASE 5 — Multi-Dimensional Aggregation

### Step 5.1 — Nested `defaultdict` Structure [`calculate_totals.py:45-68`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/calculate_totals.py#L45)

To prevent `KeyError` checks and streamline grouping, a two-level nested `defaultdict` is used:

```python
totals = defaultdict(lambda: defaultdict(lambda: {"in": 0, "out": 0, "cost": 0.0}))
```

**Accumulation Loop:**
```python
with open(log_file, "r", encoding="utf-8") as f:
    for line in f:
        m = line_pattern.search(line)
        if m:
            phase   = m.group(1) or "Generator"
            key     = m.group(2)
            in_toks = int(m.group(3))
            out_toks= int(m.group(4))
            cost    = float(m.group(5))

            totals[key][phase]["in"]   += in_toks
            totals[key][phase]["out"]  += out_toks
            totals[key][phase]["cost"] += cost
```

**Internal State Representation after Loop:**
```python
{
    "GEMINI Key 1": {
        "Parser":    {"in": 4551,  "out": 2759,  "cost": 0.005277},
        "Generator": {"in": 12590, "out": 11200, "cost": 0.019948}
    },
    "GEMINI Key 2": {
        "Generator": {"in": 10539, "out": 8633,  "cost": 0.015587}
    },
    "GEMINI Key 3": {
        "Generator": {"in": 6525,  "out": 5602,  "cost": 0.010034}
    }
}
```

---

## PHASE 6 — Report Generation & Formatting

### Step 6.1 — Writing `output/cost_totals.txt` [`calculate_totals.py:74-97`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/calculate_totals.py#L74)

```python
with open(out_file, "w", encoding="utf-8") as f:
    f.write("="*50 + "\n")
    f.write("           COST & TOKEN TOTALS\n")
    f.write("="*50 + "\n\n")

    grand_cost = 0.0
    
    for key, phases in totals.items():
        f.write(f"--- {key} ---\n")
        key_cost = 0.0
        for phase, metrics in phases.items():
            f.write(f"  [{phase}]\n")
            f.write(f"    Input Tokens : {metrics['in']:,}\n")       # e.g. 4,551
            f.write(f"    Output Tokens: {metrics['out']:,}\n")      # e.g. 2,759
            f.write(f"    Phase Cost   : ${metrics['cost']:.6f}\n\n")# e.g. $0.005277
            key_cost += metrics["cost"]
            
        f.write(f"  > Total {key} Cost: ${key_cost:.6f}\n\n")
        grand_cost += key_cost
        
    f.write("="*50 + "\n")
    f.write(f"GRAND TOTAL COST: ${grand_cost:.6f}\n")
    f.write("="*50 + "\n")
```

### Step 6.2 — Final Output Report (`output/cost_totals.txt`)

```text
==================================================
           COST & TOKEN TOTALS
==================================================

--- GEMINI Key 1 ---
  [Parser]
    Input Tokens : 4,551
    Output Tokens: 2,759
    Phase Cost   : $0.005277

  [Generator]
    Input Tokens : 12,590
    Output Tokens: 11,200
    Phase Cost   : $0.019948

  > Total GEMINI Key 1 Cost: $0.025225

--- GEMINI Key 2 ---
  [Generator]
    Input Tokens : 10,539
    Output Tokens: 8,633
    Phase Cost   : $0.015587

  > Total GEMINI Key 2 Cost: $0.015587

--- GEMINI Key 3 ---
  [Generator]
    Input Tokens : 6,525
    Output Tokens: 5,602
    Phase Cost   : $0.010034

  > Total GEMINI Key 3 Cost: $0.010034

==================================================
GRAND TOTAL COST: $0.050846
==================================================
```

---

## PHASE 7 — Execution Triggers

### 1. Automatic Execution at End of Pipeline
In [`run_pipeline.py:50-57`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/run_pipeline.py#L50):
```python
print("\n" + "="*60)
print("  Stage 3: Calculating Cost Totals")
print("="*60)
try:
    import calculate_totals
    calculate_totals.main()
except Exception as e:
    print(f"Failed to calculate totals: {e}")
```
Wrapped in `try/except` so that any logging file-system glitch does not fail an otherwise successful test-generation run.

### 2. Standalone CLI Execution
Can be run independently at any time to re-aggregate existing logs:
```bash
python calculate_totals.py
```

---

## DEEP DETAIL — Key Implementation Specifics

### K1. Thread-Safe Logging (`_cost_log_lock`)
Because async batch mapping and parallel test-case generation invoke the callback concurrently across multiple threads, writing directly to `cost_tracking.txt` without synchronization would lead to corrupted, interleaved log lines. `_cost_log_lock = threading.Lock()` guarantees **atomic line-by-line appends**.

### K2. `litellm.completion_cost()` Precision
Instead of estimating costs with rough token math, LiteLLM calculates exact dynamic prices based on model provider pricing tables (e.g. `$0.075 / 1M input tokens` for Gemini Flash Lite).

### K3. Backward Compatibility for Legacy Logs
The regex group `(?:\[(.*?)\]\s+)?` with `phase = m.group(1) or "Generator"` ensures that if older log lines lack the `[Parser]` or `[Generator]` tag, `calculate_totals.py` still processes them seamlessly without throwing parsing errors.

---

## Complete Reference Table

| Component | File | Lines | Purpose |
|---|---|---|---|
| `_build_key_alias_map()` | [`core/llm_factory.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/llm_factory.py#L43-L51) | 43–51 | Builds `O(1)` mapping from secret API key strings to human aliases |
| `_track_cost_callback()` | [`core/llm_factory.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/llm_factory.py#L53-L82) | 53–82 | Intercepts tokens/cost on every LLM call and writes to log |
| `_cost_log_lock` | [`core/llm_factory.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/core/llm_factory.py#L37) | 37 | Thread lock preventing interleaved log writes |
| `litellm.current_phase` | [`run_pipeline.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/run_pipeline.py#L27) | 27, 35 | Runtime stage tag ("Parser" vs "Generator") |
| `line_pattern` regex | [`calculate_totals.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/calculate_totals.py#L48-L54) | 48–54 | Extracts timestamp, phase, key, tokens in/out, cost |
| Nested `defaultdict` | [`calculate_totals.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/calculate_totals.py#L46) | 46 | Multi-dimensional aggregation structure |
| `main()` | [`calculate_totals.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/calculate_totals.py#L22-L98) | 22–98 | Aggregates log and formats `output/cost_totals.txt` |
| Stage 3 Trigger | [`run_pipeline.py`](file:///c:/Users/2862390/Desktop/PoC/Baxter/Tharun_Branch/run_pipeline.py#L50-L58) | 50–58 | Automatic invocation after Stage 2 completion |
