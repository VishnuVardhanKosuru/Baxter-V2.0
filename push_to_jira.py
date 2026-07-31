import os
import sys
import glob
from pathlib import Path
from dotenv import load_dotenv

# Ensure we can import from core
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from core.jira_client import JiraClient

def main():
    load_dotenv()
    
    jira = JiraClient()
    if not jira.is_configured():
        print("Error: Jira is not fully configured in .env")
        print(f"URL: {jira.url}")
        print(f"Email: {jira.email}")
        print(f"Token: {'Set' if jira.token else 'Missing'}")
        print(f"Project Key: {jira.project_key}")
        sys.exit(1)
        
    print(f"Pushing to Jira Project: {jira.project_key} at {jira.url}")
    print("NOTE: If you get a 'target project doesn't exist' error, your JIRA_PROJECT_KEY in .env is incorrect.")
    
    # Find all generated manual test CSVs
    csv_files = glob.glob("output/*/tests/manual/*_tests_master.csv")
    
    if not csv_files:
        print("No generated CSV test cases found in output/*/tests/manual/")
        sys.exit(0)
        
    count = 0
    for csv_file in csv_files:
        print(f"\nProcessing {csv_file}...")
        with open(csv_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
            # Skip header
            if lines and lines[0].startswith("Test ID"):
                lines = lines[1:]
                
            for row in lines:
                row = row.strip()
                if not row:
                    continue
                    
                parts = row.split(",")
                if len(parts) >= 9:
                    test_id, module, func_name, test_type, scenario, pre_cond, steps, data, expected = parts[:9]
                    summary = f"[{test_id}] {func_name} - {scenario}"
                    desc = f"Module: {module}\nPre-conditions: {pre_cond}\nSteps:\n{steps}\nTest Data: {data}\nExpected Result: {expected}"
                    
                    # Push to Jira as Bug
                    issue_key = jira.create_issue(summary=summary, description=desc, issue_type="Bug")
                    if issue_key:
                        count += 1
                        
    print(f"\nSuccessfully pushed {count} issues to Jira!")

if __name__ == "__main__":
    main()
