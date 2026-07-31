# Autonomous Tester Agent: Detailed Implementation Plan

This is the finalized specification for the `tester.py` architecture, updated to reflect the most recent enhancements (Subfolder Strategy Splitting, Self-Loop Cleaning, and the Gemini 3.5 Flash Lite upgrade).

## 1. Graph Parsing & Java Filtering (The Initialization)
Before any testing begins, the Python script must prepare the graph:
1. **Load:** Load the entire `kb.json` into a NetworkX directed graph.
2. **Filter:** Iterate through the nodes and **drop everything that is not Java**. 
3. **Clean (No Self-Loops):** Strip any edges where a function calls itself. This prevents standalone functions from accidentally being marked as Integration tests.
4. **Sort:** Perform a **Topological Sort** on the remaining Java nodes. This ensures we test functions from the "bottom-up" (testing standalone leaf nodes before testing the complex orchestrator functions that rely on them).

---

## 2. Production-Level Test Strategy Engine
For each Java node in the sorted list, the script evaluates its metadata to determine the **Base Execution Type** (`Unit`, `Integration`, `UI`) and injects additional testing strategies:

*   **Unit Tests:** Triggered for pure Leaf Nodes (out-degree = 0). 
*   **Integration Tests:** Triggered for intermediate nodes that call other internal functions.
*   **UI / Selenium Tests:** Triggered for web endpoints (e.g., `@RestController`).
*   **Boundary Value Analysis (BVA):** Injected if the function accepts parameters.
*   **Negative Testing:** Injected to handle exceptions/invalid states (e.g., `throws` keyword).
*   **Security Tests:** Injected if a CodeQL vulnerability exists on the node.

---

## 3. Programmatic Prompt Construction (Gemini 3.5 Flash Lite)
The script connects to the `gemini-3.5-flash-lite` model. It builds a prompt that commands Gemini to generate **multiple separate Java files** (one for each strategy) and one unified CSV block.

```python
prompt = f"""
You are an Expert Enterprise Java QA Automation Engineer.
Task: Generate a production-grade test suite for the Java function `{target_node['name']}`.

For each test strategy, output a separate Java file block using specific tags: [JAVA:POSITIVE], [JAVA:BVA], [JAVA:NEGATIVE], [JAVA:SECURITY].

[CSV]
Generate manual test cases for a human QA. Output ONLY valid CSV rows matching the exact 14 headers. 
[/CSV]
"""
```

---

## 4. Dual-Output Parsing & Sub-Folder Segregation

When Gemini responds, the Python script parses the text. It uses regex to extract the specific tagged Java blocks and the CSV rows.

### Automated Tests (`.java`) in Sub-Folders
Java files are saved into strictly segregated sub-folders based on their base type AND their specific test strategy:
*   `tests/automated/<base_type>/positive/{Function}Test.java` (Happy Path)
*   `tests/automated/<base_type>/bva/{Function}Test.java` (Edge cases / Nulls)
*   `tests/automated/<base_type>/negative/{Function}Test.java` (Exception Handling)
*   `tests/automated/<base_type>/security/{Function}Test.java` (Vulnerability exploits)

### Manual Test Cases (Consolidated CSVs)
The script **appends** the generated CSV rows into master files based on the test type, resulting in 3 clean, consolidated master files that cover all positive, BVA, and negative manual scenarios:
*   `tests/manual/unit_tests_master.csv`
*   `tests/manual/integration_tests_master.csv`
*   `tests/manual/ui_tests_master.csv`

---

## 5. Strategy Segregation Report
When the run is complete, the script writes `tests/test_strategy_report.md`. This report explicitly lists every function processed, its Base Execution Type, and the exact combination of strategies (e.g., `Integration + BVA + Negative`) that were injected into the LLM prompt.
