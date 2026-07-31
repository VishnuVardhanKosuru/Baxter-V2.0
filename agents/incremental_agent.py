import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
import time
import argparse
import re
import networkx as nx
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

from core.github_client import GitHubClient
from agents.tester_agent import build_prompt, append_to_csv, fetch_code_jit

load_dotenv()

def get_affected_ranges(patch_str):
    """Parses a unified diff patch and returns a list of (start_line, end_line) ranges in the new file."""
    ranges = []
    if not patch_str:
        return ranges
    for line in patch_str.splitlines():
        m = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
        if m:
            new_start = int(m.group(1))
            new_lines = int(m.group(2)) if m.group(2) else 1
            if new_lines > 0:
                ranges.append((new_start, new_start + new_lines - 1))
    return ranges

def main():
    parser = argparse.ArgumentParser(description="Incremental AST-Based Tester Agent")
    parser.add_argument('--repo', default='supriya-daita/LibraryManagementSystem', help="GitHub repo owner/name")
    parser.add_argument('--kb', default=r'output\LibraryManagementSystem\kb.json', help="Path to the fresh kb.json (after push)")
    parser.add_argument('--commit', required=True, help="The SHA of the new commit to analyze")
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

    # Reconstruct the Graph for context (Dependency mocking)
    java_files = {n["id"] for n in data.get("nodes", []) if n["type"] == "FILE" and n.get("properties", {}).get("language") == "java"}
    java_node_ids = {edge["target"] for edge in data.get("edges", []) if edge["type"] == "DEFINES" and edge["source"] in java_files}

    G = nx.DiGraph()
    functions_map = {}
    for n in data.get("nodes", []):
        if n["type"] == "FUNCTION" and n["id"] in java_node_ids:
            G.add_node(n["id"], **n)
            functions_map[n["id"]] = n

    for edge in data.get("edges", []):
        if edge["type"] == "CALLS" and edge["source"] in G and edge["target"] in G:
            if edge["source"] != edge["target"]: # Ignore self-loops
                G.add_edge(edge["source"], edge["target"])

    # 1. Fetch Commit Diff
    print(f"Fetching diff for commit {args.commit} from GitHub...")
    try:
        commit_data = gh_client.get(f"/repos/{owner}/{repo_name}/commits/{args.commit}")
    except Exception as e:
        print(f"Failed to fetch commit: {e}")
        return
        
    changed_files = commit_data.get("files", [])
    if not changed_files:
        print("No files changed in this commit.")
        return

    # 2. Deterministic Delta Detection
    modified_functions = []
    
    for file_info in changed_files:
        filename = file_info.get("filename")
        if not filename.endswith(".java"):
            continue
            
        patch = file_info.get("patch", "")
        affected_ranges = get_affected_ranges(patch)
        
        # Find all functions in this file that overlap with the affected ranges
        for func_id, func_node in functions_map.items():
            if func_node.get("file") == filename:
                f_start = func_node.get("line_start", 0)
                f_end = func_node.get("line_end", float('inf'))
                
                # Check overlap
                for r_start, r_end in affected_ranges:
                    if r_start <= f_end and r_end >= f_start:
                        modified_functions.append(func_node)
                        break # Node is modified, check next node

    if not modified_functions:
        print("No Java functions were mathematically affected by this commit.")
        return
        
    print(f"Detected {len(modified_functions)} modified/added Java functions!")

    # 3. Targeted Test Generation
    count = 1
    total = len(modified_functions)
    
    for node in modified_functions:
        print(f"\nProcessing [{count}/{total}]: {node.get('name')} (Incremental)...")
        
        out_edges = list(G.out_edges(node['id']))
        is_leaf = len(out_edges) == 0
        decorators = [d.lower() for d in node.get("decorators", [])]
        is_web = any(x in d for d in decorators for x in ["route", "mapping", "restcontroller"])

        code_block = None
        if is_leaf and not is_web:
            code_block = fetch_code_jit(gh_client, owner, repo_name, node.get('file'), node.get('line_start'), node.get('line_end'))

        prompt, base_type = build_prompt(node, G, code_block)
        
        try:
             print("  -> Generating tests with Gemini...")
             response = model.generate_content(prompt)
             text = response.text
             
             # Segregated File Saving
             import re
             java_blocks = {}
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
             
             for tag, code in java_blocks.items():
                 folder_path = Path(f"tests/automated/{base_type}/{tag}")
                 folder_path.mkdir(parents=True, exist_ok=True)
                 java_path = folder_path / f"{safe_name}Test.java"
                 with open(java_path, "w") as f:
                     f.write(code)
                 print(f"  -> Saved {java_path}")
                 
             if csv_rows:
                 csv_path = f"tests/manual/{base_type}_tests_master.csv"
                 append_to_csv(csv_path, csv_rows.strip())
                 print(f"  -> Appended rows to {csv_path}")
                 
             count += 1
             
             print("  -> Sleeping 4.5 seconds to respect API rate limits...")
             time.sleep(4.5)
             
        except Exception as e:
             print(f"  -> Error: {e}")
             
    print("\nIncremental testing complete.")

if __name__ == "__main__":
    main()
