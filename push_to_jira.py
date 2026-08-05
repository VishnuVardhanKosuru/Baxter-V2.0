import os
import sys
import glob
import json
from pathlib import Path
from dotenv import load_dotenv

# Ensure we can import from core
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from core.jira_client import JiraClient

import argparse

def main():
    """
    Connects to Jira API using credentials from .env, reads output test plan files,
    and publishes test issue tickets to the target Jira project.
    """
    parser = argparse.ArgumentParser(description="Jira Integration Publisher")
    parser.add_argument("--repo", default="", help="Target repository (owner/repo or repo_name)")
    parser.add_argument("--max-issues", type=int, default=int(os.getenv("JIRA_MAX_ISSUES", "20")), help="Maximum issues to create per run (default: 20)")
    args = parser.parse_args()

    load_dotenv()

    jira = JiraClient()
    if not jira.is_configured():
        print("[Jira Sync Note] Jira is not fully configured in .env. Skipping Jira synchronization.")
        print(f"  URL: {jira.url or 'Missing'}")
        print(f"  Email: {jira.email or 'Missing'}")
        print(f"  Token: {'Set' if jira.token else 'Missing'}")
        print(f"  Project Key: {jira.project_key or 'Missing'}")
        return

    # 1. Verify Connection and Fetch Allowed Issue Types
    print(f"[Jira Sync] Verifying connection to Project '{jira.project_key}' at {jira.url}...")
    connected, msg = jira.verify_connection()
    if not connected:
        print(f"[Jira Sync Error] {msg}")
        print("[Jira Sync Aborted] Halting Jira sync to prevent infinite retries.")
        return

    target_status = os.getenv("JIRA_FEATURE_STATUS", "In Progress")
    max_issues = args.max_issues

    # 2. Determine target plan files
    repo_input = args.repo.strip() or os.getenv("GITHUB_REPO", "").strip()
    repo_name = repo_input.split("/")[-1] if "/" in repo_input else repo_input

    if repo_name:
        plan_files = glob.glob(f"output/{repo_name}/test_plan.json")
        sync_state_path = Path("output") / repo_name / ".jira_synced.json"
    else:
        plan_files = glob.glob("output/*/test_plan.json")
        sync_state_path = Path("output") / ".jira_synced.json"

    # Load synced summary cache to prevent duplicate ticket creation
    synced_summaries = set()
    if sync_state_path.exists():
        try:
            with open(sync_state_path, "r", encoding="utf-8") as f:
                synced_summaries = set(json.load(f))
        except Exception:
            synced_summaries = set()

    # Pre-flight count analysis
    total_features = 0
    pending_tasks = []
    already_synced_count = 0

    if plan_files:
        for plan_file in plan_files:
            try:
                with open(plan_file, "r", encoding="utf-8") as f:
                    tasks = json.load(f)
                    for t in tasks:
                        total_features += 1
                        cls = t.get("class", "TestClass")
                        func = t.get("func", "testMethod")
                        axis = t.get("axis", "unit")
                        summary = f"[{cls}] {func}() - {axis.upper()} Test Suite"
                        if summary in synced_summaries:
                            already_synced_count += 1
                        else:
                            pending_tasks.append((plan_file, t, summary))
            except Exception as e:
                print(f"Error inspecting {plan_file}: {e}")
    else:
        csv_files = glob.glob(f"output/{repo_name}/test_matrix_summary.csv") if repo_name else glob.glob("output/*/test_matrix_summary.csv")
        for csv_file in csv_files:
            try:
                with open(csv_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in lines[1:]:
                        parts = line.strip().split(",")
                        if len(parts) >= 4:
                            total_features += 1
                            cls, func, axis, tech = parts[:4]
                            summary = f"[{cls}] {func} - {tech}"
                            if summary in synced_summaries:
                                already_synced_count += 1
                            else:
                                pending_tasks.append((csv_file, {"class": cls, "func": func, "axis": axis, "techniques": [tech]}, summary))
            except Exception as e:
                print(f"Error inspecting {csv_file}: {e}")

    will_upload = min(len(pending_tasks), max_issues)

    print("\n" + "=" * 55)
    print(f"[Jira Pre-flight Analysis]")
    print(f"  Target Repository    : {repo_name or 'All Output Repos'}")
    print(f"  Jira Project Board   : {jira.url}/browse/{jira.project_key}")
    print(f"  Total Features Found : {total_features}")
    print(f"  Already Synced       : {already_synced_count}")
    print(f"  New Unsynced Pending : {len(pending_tasks)}")
    print(f"  Max Upload Cap/Run   : {max_issues}")
    print(f"  => WILL UPLOAD       : {will_upload} new feature issue(s)")
    print("=" * 55 + "\n")

    if will_upload == 0:
        print("[Jira Sync Complete] All features are already synced to Jira. 0 uploads needed.")
        return

    count = 0
    skips = already_synced_count
    for plan_file, t, summary in pending_tasks:
        if count >= max_issues or jira.circuit_broken:
            print(f"[Jira Sync Cap] Reached max limit of {max_issues} created issues. Stopping sync.")
            break

        cls = t.get("class", "TestClass")
        func = t.get("func", "testMethod")
        axis = t.get("axis", "unit")
        techniques = t.get("techniques", [])
        desc = f"Class: {cls}\nFunction: {func}\nAxis: {axis}\nTechniques: {', '.join(techniques)}"

        issue_key = jira.create_issue(summary=summary, description=desc, issue_type="Feature", status=target_status)
        if issue_key:
            count += 1
            synced_summaries.add(summary)


    # Save synced cache
    try:
        sync_state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sync_state_path, "w", encoding="utf-8") as f:
            json.dump(list(synced_summaries), f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save .jira_synced.json cache: {e}")

    print(f"\n[Jira Sync Summary]")
    print(f"  New Issues Created : {count} (Max Limit: {max_issues})")
    print(f"  Duplicates Skipped : {skips}")
    print(f"  Jira Project Board : {jira.url}/browse/{jira.project_key}")

if __name__ == "__main__":
    main()


