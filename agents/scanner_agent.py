import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

from core.github_client import GitHubClient
from core.workflow_manager import WorkflowManager
from core.artifact_downloader import ArtifactDownloader
from core.kb_merger import KBMerger

# Set your default repository here
TARGET_REPO = "supriya-daita/LibraryManagementSystem"

def load_env():
    """Load variables from .env file into os.environ"""
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

def main():
    parser = argparse.ArgumentParser(description="Code Knowledge Base Scanner")
    parser.add_argument("--repo", default=TARGET_REPO, help="Target repository (owner/repo)")
    parser.add_argument("--pat", help="GitHub Personal Access Token (defaults to GITHUB_PAT env var)")
    parser.add_argument("--language", help="CodeQL language to scan (comma separated). Leave empty for auto-detect.")
    parser.add_argument("--output", default="output", help="Output directory")
    
    args = parser.parse_args()
    
    # Load .env file if it exists
    load_env()
    
    pat = args.pat or os.environ.get("GITHUB_PAT")
    if not pat:
        print("Error: GitHub PAT is required. Pass via --pat or GITHUB_PAT env var.")
        sys.exit(1)
        
    try:
        owner, repo = args.repo.split("/")
    except ValueError:
        print("Error: Repository must be in the format 'owner/repo'")
        sys.exit(1)

    print(f"Starting KB scan for {owner}/{repo}")
    
    # Initialize components
    client = GitHubClient(pat)
    wf_manager = WorkflowManager(client)
    downloader = ArtifactDownloader(client)
    
    # Pre-flight check: verify repo access
    try:
        repo_info = client.get_repo(owner, repo)
        print(f"  Connected to {repo_info.get('full_name')} (default branch: {repo_info.get('default_branch')})")
    except Exception as e:
        print(f"Error accessing repository '{owner}/{repo}'.")
        print(f"Details: {e}")
        print("\nCommon reasons for a 404 here:")
        print("1. The repository name has a typo (it should be exactly owner/repo, no .git).")
        print("2. The repository is private, and your PAT is missing the 'repo' scope.")
        print("3. Your PAT is a Fine-Grained token and you didn't grant access to this specific repository.")
        sys.exit(1)
        
    # 1. Setup workflow files if missing
    try:

        wf_manager.setup_repo(owner, repo)
    except Exception as e:
        print(f"Error setting up repo: {e}")
        sys.exit(1)
        
    # 2. Trigger and poll
    try:
        run_id = wf_manager.trigger_and_wait(owner, repo, args.language)
        if not run_id:
            print("Scan failed or timed out.")
            sys.exit(1)
    except Exception as e:
        print(f"Error during workflow execution: {e}")
        sys.exit(1)
        
    # 3. Download artifacts
    try:
        artifacts = downloader.fetch_artifacts(owner, repo, run_id)
        if not artifacts["ast"] and not artifacts["sarif"]:
            print("Warning: No AST or SARIF artifacts found.")
    except Exception as e:
        print(f"Error downloading artifacts: {e}")
        sys.exit(1)
        
    # 4. Merge into KB

    kb = KBMerger.merge(args.repo, artifacts["ast"], artifacts["sarif"])
    

    
    files_count = sum(1 for n in kb.get('nodes', []) if n.get('type') == 'FILE')
    funcs_count = sum(1 for n in kb.get('nodes', []) if n.get('type') == 'FUNCTION')


    
    # 5. Save output
    out_dir = Path(args.output) / repo
    out_dir.mkdir(parents=True, exist_ok=True)
    
    out_file = out_dir / "kb.json"
    with open(out_file, "w") as f:
        json.dump(kb, f, indent=2)
        
    # 6. Generate Visualization
    graph_out = out_dir / "graph.html"
    print(f"\nGenerating interactive Knowledge Graph visualization...")
    subprocess.run(["python", "tools/visualize.py", "--input", str(out_file), "--output", str(graph_out)])
        
    print(f"\n[SUCCESS] KB Extraction and Visualization Complete!")
    print(f"Summary:")
    print(f"  Total Nodes: {kb['summary'].get('total_nodes', 0)}")
    print(f"  Total Edges: {kb['summary'].get('total_edges', 0)}")
    print(f"  Vulnerabilities: {kb['summary'].get('total_vulnerabilities', 0)}")
    
    print(f"\nGenerated Files:")
    print(f"- Knowledge Base Data : {out_file}")
    print(f"- Interactive Graph   : {graph_out}")
    print(f"\nOpen {graph_out.name} in your web browser to explore the architecture.")

if __name__ == "__main__":
    main()
