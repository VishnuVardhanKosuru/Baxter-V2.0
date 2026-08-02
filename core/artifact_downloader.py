import io
import zipfile
import json
from typing import Dict, Any, List
from core.github_client import GitHubClient

class ArtifactDownloader:
    def __init__(self, client: GitHubClient):
        self.client = client

    def fetch_artifacts(self, owner: str, repo: str, run_id: int) -> Dict[str, Any]:
        """Download and extract AST and CodeQL structural JSONs from artifacts in memory."""
        print(f"Fetching artifacts for run {run_id}...")
        artifacts_info = self.client.get_run_artifacts(owner, repo, run_id)
        
        ast_data = {}
        structural_data = {}
        sarif_data = []

        for artifact in artifacts_info.get("artifacts", []):
            name = artifact["name"]
            if name == "ast-results":
                print("  Downloading AST artifact...")
                zip_bytes = self.client.download_artifact(owner, repo, artifact["id"])
                ast_data = self._extract_json_from_zip(zip_bytes, "ast.json")
            elif name == "codeql-structural":
                print("  Downloading CodeQL structural artifact...")
                zip_bytes = self.client.download_artifact(owner, repo, artifact["id"])
                structural_data = self._extract_json_from_zip(zip_bytes, "codeql_structural.json")
            # PAUSED: Vulnerability SARIF downloading (commented out)
            # elif name == "codeql-results":
            #     print("  Downloading CodeQL SARIF artifact...")
            #     zip_bytes = self.client.download_artifact(owner, repo, artifact["id"])
            #     sarif_data.extend(self._extract_all_sarifs_from_zip(zip_bytes))
                
        return {
            "ast": ast_data,
            "structural": structural_data,
            "sarif": sarif_data
        }

    def _extract_json_from_zip(self, zip_bytes: bytes, filename: str) -> Dict:
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                if filename in z.namelist():
                    with z.open(filename) as f:
                        return json.load(f)
        except Exception as e:
            print(f"  Error extracting {filename}: {e}")
        return {}

    def _extract_all_sarifs_from_zip(self, zip_bytes: bytes) -> List[Dict]:
        sarifs = []
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                for name in z.namelist():
                    if name.endswith(".sarif"):
                        with z.open(name) as f:
                            sarifs.append(json.load(f))
        except Exception as e:
            print(f"  Error extracting SARIFs: {e}")
        return sarifs
