import base64
import time
from pathlib import Path
from typing import Optional, Dict
from core.github_client import GitHubClient

class WorkflowManager:
    WORKFLOW_PATH = ".github/workflows/kb-scanner.yml"
    SCRIPT_PATH = ".github/scripts/extract_ast.py"

    def __init__(self, client: GitHubClient):
        self.client = client

    def setup_repo(self, owner: str, repo: str) -> bool:
        """Ensure workflow files exist in target repo."""
        print(f"Checking workflow setup in {owner}/{repo}...")
        
        changed = False
        
        # Check and commit workflow
        with open("templates/kb-scanner.yml", "rb") as f:
            workflow_b64 = base64.b64encode(f.read()).decode()
            
        file_info = self.client.get_file(owner, repo, self.WORKFLOW_PATH)
        sha = file_info.get("sha") if file_info else None
        
        # Simple overwrite: if it exists, we update it to match our template exactly
        # In a more advanced version, we'd check if the content actually changed.
        print("  Committing kb-scanner.yml...")
        self.client.commit_file(owner, repo, self.WORKFLOW_PATH, workflow_b64, "Add/Update KB scanner workflow", sha=sha)
        changed = True
        
        # Check and commit AST script
        with open("templates/extract_ast.py", "rb") as f:
            script_b64 = base64.b64encode(f.read()).decode()
            
        file_info = self.client.get_file(owner, repo, self.SCRIPT_PATH)
        sha = file_info.get("sha") if file_info else None
        
        print("  Committing extract_ast.py...")
        self.client.commit_file(owner, repo, self.SCRIPT_PATH, script_b64, "Add/Update AST extraction script", sha=sha)

        # Check and commit custom CodeQL query files
        queries_dir = Path("templates/queries")
        if queries_dir.exists():
            for ql_file in queries_dir.glob("*.ql"):
                target_ql_path = f".github/scripts/queries/{ql_file.name}"
                with open(ql_file, "rb") as f:
                    ql_b64 = base64.b64encode(f.read()).decode()
                q_info = self.client.get_file(owner, repo, target_ql_path)
                q_sha = q_info.get("sha") if q_info else None
                print(f"  Committing {target_ql_path}...")
                self.client.commit_file(owner, repo, target_ql_path, ql_b64, f"Add/Update query {ql_file.name}", sha=q_sha)

        if changed:
            print("  Setup complete. Waiting 5 seconds for GitHub to register workflow...")
            time.sleep(5)
            
        return changed

    def determine_languages(self, owner: str, repo: str) -> str:
        """Detect CodeQL supported languages in the repo."""
        langs = self.client.get_languages(owner, repo)
        supported = {"Python", "JavaScript", "TypeScript", "Java", "Go", "Ruby", "C", "C++", "C#"}
        
        detected = [l.lower() for l in langs.keys() if l in supported]
        # Map typescript to javascript for CodeQL
        if "typescript" in detected and "javascript" not in detected:
            detected.append("javascript")
            detected.remove("typescript")
            
        return ",".join(list(set(detected)))

    def trigger_and_wait(self, owner: str, repo: str, language: str = None) -> Optional[int]:
        """Trigger workflow and wait for completion."""
        # Detect languages if not provided
        if not language:
            language = self.determine_languages(owner, repo)
            print(f"  Detected CodeQL languages: {language}")
            
        if not language:
            print("  No CodeQL supported languages found. CodeQL job will likely be skipped.")
            
        inputs = {"languages": language}
        
        print("Triggering workflow...")
        success = self.client.trigger_workflow(owner, repo, "kb-scanner.yml", "main", inputs)
        if not success:
            print("  Failed to trigger workflow.")
            return None
            
        print("  Triggered. Waiting for run to start...")
        time.sleep(5)
        
        # Get run ID
        runs = self.client.get_workflow_runs(owner, repo, event="workflow_dispatch")
        if not runs.get("workflow_runs"):
            print("  Could not find workflow run.")
            return None
            
        run_id = runs["workflow_runs"][0]["id"]
        print(f"  Found Run ID: {run_id}")
        
        # Poll
        while True:
            run_info = self.client.get_run(owner, repo, run_id)
            status = run_info["status"]
            conclusion = run_info.get("conclusion")
            
            if status == "completed":
                print(f"\nRun {run_id} completed with conclusion: {conclusion}")
                if conclusion == "success":
                    return run_id
                else:
                    print("Workflow failed. Please check GitHub Actions logs.")
                    return run_id # return anyway to pull any partial artifacts
            
            print(".", end="", flush=True)
            time.sleep(15)
