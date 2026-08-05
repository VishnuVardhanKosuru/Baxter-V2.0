import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv

from core.github_client import GitHubClient

def main():
    parser = argparse.ArgumentParser(description="End-to-end Automated Delta Testing Pipeline")
    parser.add_argument('--repo', required=True, help="GitHub repo owner/name (e.g., supriya-daita/LibraryManagementSystem)")
    args = parser.parse_args()

    load_dotenv()
    gh_pat = os.getenv("GITHUB_PAT")
    if not gh_pat:
        print("Error: GITHUB_PAT not set in .env")
        return

    owner, repo_name = args.repo.split('/')
    gh_client = GitHubClient(gh_pat)

    print(f"=== Starting Delta Pipeline for {args.repo} ===")

    # 1. State Management
    state_dir = Path("output") / repo_name
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / ".pipeline_state.json"
    
    previous_sha = None
    if state_file.exists():
        with open(state_file, "r") as f:
            state = json.load(f)
            previous_sha = state.get("last_commit_sha")

    # 2. Get Latest Commit
    print("Fetching latest commit SHA...")
    latest_sha = gh_client.get_latest_commit(owner, repo_name)
    print(f"Latest SHA:   {latest_sha}")
    if previous_sha:
        print(f"Previous SHA: {previous_sha}")

    if previous_sha == latest_sha:
        print("\nNo commit delta detected. Running full pipeline scan and test generation...")

    # 3. Determine Changed Files (if delta mode)
    changed_files = []
    is_delta = False
    if previous_sha:
        print("\nDelta Mode: Comparing commits...")
        changed_files = gh_client.compare_commits(owner, repo_name, previous_sha, latest_sha)
        print(f"Found {len(changed_files)} changed files.")
        is_delta = True

    # 4. Run Scanner Agent
    print("\n=== Phase 1: Running Scanner Agent ===")
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    scan_result = subprocess.run([sys.executable, "agents/scanner_agent.py", "--repo", args.repo], env=env)
    if scan_result.returncode != 0:
        print("Scanner agent failed. Aborting pipeline.")
        return

    # 5. Run Tester Agent
    print("\n=== Phase 2: Running Tester Agent ===")
    tester_cmd = [sys.executable, "agents/tester_agent.py", "--repo", args.repo]
    if is_delta and changed_files:
        print(f"Delta Mode: Testing {len(changed_files)} changed files...")
        tester_cmd.extend(["--changed-files", ",".join(changed_files)])
    else:
        print("Full Scan Mode: Generating test suite across all target functions...")
        
    tester_result = subprocess.run(tester_cmd, env=env)

    # 6. Run Jira Integration Agent
    print("\n=== Phase 3: Running Jira Integration Agent ===")
    jira_result = subprocess.run([sys.executable, "push_to_jira.py"], env=env)

    # 7. Update State
    with open(state_file, "w") as f:
        json.dump({"last_commit_sha": latest_sha}, f)
    
    print(f"\n[SUCCESS] Pipeline Complete. State updated to {latest_sha}.")

if __name__ == "__main__":
    main()
