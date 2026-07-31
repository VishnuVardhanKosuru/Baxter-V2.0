import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import os
import time
import json
import base64
import argparse
import networkx as nx
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from core.github_client import GitHubClient


load_dotenv()

CSV_HEADERS = "Test ID,Module Name,Function Name,Test Type,Test Scenario,Pre Conditions,Test Steps,Test Data,Expected Result,Priority,Executed By,Execution Date,Status,Remarks\n"

def fetch_code_jit(gh_client, owner, repo, file_path, line_start, line_end):
    """Fetch specific lines of code via GitHub API JIT"""
    file_data = gh_client.get_file(owner, repo, file_path)
    if not file_data or "content" not in file_data:
        return ""
    
    content = base64.b64decode(file_data["content"]).decode('utf-8')
    lines = content.splitlines()
    start_idx = max(0, line_start - 1)
    end_idx = min(len(lines), line_end)
    return "\n".join(lines[start_idx:end_idx])

def build_prompt(node, G, code_block):
    strategies = []
    base_type = "unit" # Default
    
    out_edges = list(G.out_edges(node['id']))
    is_leaf = len(out_edges) == 0
    
    decorators = [d.lower() for d in node.get("decorators", [])]
    is_backend_api = any(x in d for d in decorators for x in ["route", "mapping", "restcontroller"])
    
    file_path = node.get("file", "")
    is_frontend = file_path.endswith(".js") or file_path.endswith(".jsx") or file_path.endswith(".ts") or file_path.endswith(".tsx")
    
    if is_frontend:
        base_type = "ui"
        strategies.append("UI / End-to-End Testing (Use Java Selenium WebDriver to interact with DOM elements found in the body)")
    elif is_backend_api:
        base_type = "api"
        strategies.append("API Testing (Use RestAssured or MockMvc for endpoint validation)")
    elif not is_leaf:
        base_type = "integration"
        strategies.append("Integration Testing (Mock dependencies)")
    else:
        strategies.append("Unit Testing (Positive Happy Path)")
        
    if len(node.get("parameters", [])) > 0:
        strategies.append("Boundary Value Analysis (BVA) (Test edge cases, nulls, limits)")
        
    if any("throws" in d.lower() for d in decorators) or "exception" in node.get("docstring", "").lower():
        strategies.append("Negative Testing (Ensure exceptions are thrown gracefully)")
        
    if node.get("properties", {}).get("vulnerabilities"):
        strategies.append("Security / Regression Testing (Test specifically against identified CodeQL vulnerabilities)")

    strategy_text = "\n".join(f"- {s}" for s in strategies)

    prompt = f"""You are an Expert Enterprise QA Automation Engineer.
Task: Generate a production-grade test suite for the function `{node['name']}`.

### Required Testing Strategies:
{strategy_text}

### Output 1: Automated Script
Generate a complete test file. For Java backend, you MUST use JUnit. For API testing, use RestAssured/MockMvc. For frontend UI testing, write a Java Selenium WebDriver test. Do not include package declarations.

### Output 2: Manual Test Cases (Strict CSV Rows)
Generate manual test cases for a human QA. Output ONLY valid CSV rows matching the exact headers below. 
Do not output the headers themselves, just the data rows (comma separated).
For the last 4 columns (Executed By, Execution Date, Status, Remarks), leave the values completely empty.
The Test ID must be unique and descriptive (e.g., TC_LOGIN_001).

Headers Expected:
Test ID, Module Name, Function Name, Test Type, Test Scenario, Pre Conditions, Test Steps, Test Data, Expected Result, Priority, Executed By, Execution Date, Status, Remarks

"""
    if code_block:
        prompt += f"\nSource Code:\n```java\n{code_block}\n```\n"
    else:
        prompt += "\nNote: Source code is intentionally omitted. Base your Black-Box tests entirely on the provided metadata.\n"
        
    prompt += f"\nContext (Parameters, Docs, Decorators, Vulnerabilities):\n{json.dumps(node, indent=2)}\n"
    
    if len(out_edges) > 0:
        prompt += "\nMock or integrate the following dependencies:\n"
        for _, target in out_edges:
            dep_node = G.nodes.get(target)
            if dep_node:
                prompt += f"- {dep_node.get('name')}: {json.dumps(dep_node, indent=2)}\n"

    prompt += "\nFormat your response exactly as follows:\n"
    prompt += "For each test strategy, output a separate Java file block using specific tags: [JAVA:POSITIVE], [JAVA:BVA], [JAVA:NEGATIVE], [JAVA:SECURITY].\n"
    prompt += "Example:\n[JAVA:POSITIVE]\n<junit code>\n[/JAVA:POSITIVE]\n[JAVA:BVA]\n<junit code>\n[/JAVA:BVA]\n"
    prompt += "[CSV]\n<csv rows here>\n[/CSV]\n"
    return prompt, base_type

def append_to_csv(filepath, rows_str):
    """Appends rows to a master CSV file, creating headers if it doesn't exist."""
    path = Path(filepath)
    needs_headers = not path.exists()
    
    with open(path, "a", encoding="utf-8") as f:
        if needs_headers:
            f.write(CSV_HEADERS)
        f.write(rows_str)
        if not rows_str.endswith("\n"):
            f.write("\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default='supriya-daita/LibraryManagementSystem', help="GitHub repo owner/name")
    parser.add_argument('--kb', default=r'output\LibraryManagementSystem\kb.json', help="Path to kb.json")
    parser.add_argument('--limit', type=int, default=999999, help="Max nodes to process")
    parser.add_argument('--changed-files', type=str, default="", help="Comma separated list of modified files to test")
    args = parser.parse_args()

    gh_pat = os.getenv("GITHUB_PAT")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gh_pat or not gemini_key:
         print("Ensure GITHUB_PAT and GEMINI_API_KEY are set in .env")
         return

    owner, repo_name = args.repo.split('/')
    gh_client = GitHubClient(gh_pat)
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-3.5-flash-lite')

    print(f"Loading Knowledge Graph from {args.kb}...")
    with open(args.kb, 'r') as f:
         data = json.load(f)

    # 1. Frontend and Backend Filtering
    changed_files_list = []
    if args.changed_files:
        changed_files_list = [f.strip() for f in args.changed_files.split(",") if f.strip()]
        print(f"Delta Mode Active: Restricting tests to {len(changed_files_list)} changed file(s).")

    target_files = set()
    for n in data.get("nodes", []):
        if n["type"] == "FILE" and n.get("properties", {}).get("language") in ("java", "javascript", "typescript", "tsx"):
            file_path = n["id"].replace("file://", "")
            if changed_files_list and file_path not in changed_files_list:
                continue
            target_files.add(file_path)

    G = nx.DiGraph()
    for n in data.get("nodes", []):
         if n["type"] == "FUNCTION" and n.get("file") in target_files:
             G.add_node(n["id"], **n)

    for edge in data.get("edges", []):
         if edge["type"] == "CALLS" and edge["source"] in G and edge["target"] in G:
             if edge["source"] != edge["target"]:
                 G.add_edge(edge["source"], edge["target"])

    # 2. Topological Sort
    try:
         order = list(nx.topological_sort(G))
         order.reverse()
    except nx.NetworkXUnfeasible:
         order = sorted(G.nodes(), key=lambda x: G.out_degree(x))

    print(f"Filtered to {len(order)} functions. Starting testing loop...")
    
    out_dir = Path("output") / repo_name / "tests"
    (out_dir / "automated/unit").mkdir(parents=True, exist_ok=True)
    (out_dir / "automated/integration").mkdir(parents=True, exist_ok=True)
    (out_dir / "automated/ui").mkdir(parents=True, exist_ok=True)
    (out_dir / "manual").mkdir(parents=True, exist_ok=True)

    count = 0
    metric_counts = {"tests_unit": 0, "tests_integration": 0, "tests_bva": 0, "tests_security": 0}
    report_lines = ["# Test Strategy Segregation Report\n\n| Function | Test Type | Reason |", "|---|---|---|"]
    
    for node_id in order:
        if count >= args.limit:
            break
            
        node = G.nodes[node_id]
        print(f"\nProcessing [{count+1}/{args.limit}]: {node.get('name')}...")

        
        # JIT conditional fetching (only for Leaf nodes / Unit tests)
        code_block = ""
        is_leaf = G.out_degree(node_id) == 0
        if is_leaf:
            code_block = fetch_code_jit(gh_client, owner, repo_name, node["file"], node.get("line_start", 0), node.get("line_end", 0))

        prompt, base_type = build_prompt(node, G, code_block)
        
        # Log to report
        applied_strats = []
        if base_type == "ui": applied_strats.append("UI")
        elif not is_leaf: applied_strats.append("Integration")
        else: applied_strats.append("Unit")
        
        if len(node.get("parameters", [])) > 0: applied_strats.append("BVA")
        if any("throws" in d.lower() for d in [d.lower() for d in node.get("decorators", [])]) or "exception" in node.get("docstring", "").lower(): applied_strats.append("Negative")
        if node.get("properties", {}).get("vulnerabilities"): applied_strats.append("Security")
            
        reason = " + ".join(applied_strats)
        report_lines.append(f"| `{node.get('name')}` | {base_type.upper()} | Built with strategies: {reason} |")
        
        try:
             print("  -> Generating tests with Gemini...")

             response = model.generate_content(prompt)
             text = response.text
             import re
             java_blocks = {}
             # Find all blocks like [JAVA:BVA]...[/JAVA:BVA]
             for match in re.finditer(r'\[JAVA:([^\]]+)\](.*?)\[/JAVA:\1\]', text, re.DOTALL):
                 tag = match.group(1).lower().strip()
                 code = match.group(2).strip()
                 if code.startswith("```java"): code = code[7:]
                 if code.startswith("```"): code = code[3:]
                 if code.endswith("```"): code = code[:-3]
                 java_blocks[tag] = code.strip()

             csv_rows = ""
             if "[CSV]" in text and "[/CSV]" in text:
                 csv_rows = text.split("[CSV]")[1].split("[/CSV]")[0].strip()
                 if csv_rows.startswith("```csv"): csv_rows = csv_rows[6:]
                 if csv_rows.startswith("```"): csv_rows = csv_rows[3:]
                 if csv_rows.endswith("```"): csv_rows = csv_rows[:-3]
                     
             safe_name = node.get('name', 'unnamed').replace("<", "").replace(">", "").replace("/", "_")
             
             # Segregated Sub-Folder File Saving
             for tag, code in java_blocks.items():
                 folder_path = out_dir / "automated" / base_type / tag
                 folder_path.mkdir(parents=True, exist_ok=True)
                 java_path = folder_path / f"{safe_name}Test.java"
                 with open(java_path, "w") as f:
                     f.write(code)
                 print(f"  -> Saved {java_path}")
                 
             # Consolidated CSV Appending
             if csv_rows:
                 csv_path = out_dir / "manual" / f"{base_type}_tests_master.csv"
                 append_to_csv(csv_path, csv_rows.strip())
                 print(f"  -> Appended rows to {csv_path}")
                 
             count += 1
             
             # Update live UI metrics
             if "Unit" in applied_strats: metric_counts["tests_unit"] += 1
             if "Integration" in applied_strats: metric_counts["tests_integration"] += 1
             if "BVA" in applied_strats: metric_counts["tests_bva"] += 1
             if "Security" in applied_strats: metric_counts["tests_security"] += 1

             
             # Rate Limit Protection (15 RPM = 1 request every 4 seconds)
             print("  -> Sleeping 4.5 seconds to respect API rate limits...")
             time.sleep(4.5)
             
        except Exception as e:
             print(f"  -> Error: {e}")
             print("  -> Sleeping 10 seconds before retry...")
             time.sleep(10)

    # Save the report
    with open(out_dir / "test_strategy_report.md", "w") as f:
        f.write("\n".join(report_lines))
    print(f"\nSaved {out_dir}/test_strategy_report.md")
    print("\nTesting complete.")

if __name__ == "__main__":
    main()
