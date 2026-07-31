#!/usr/bin/env python3
"""
GitHub API client with rate limit handling and retry logic.
"""
import time
import requests
from typing import Dict, Optional


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, pat: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.BASE_URL}{path}"
        response = self.session.request(method, url, **kwargs)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"  Rate limited — waiting {retry_after}s...")
            time.sleep(retry_after)
            return self._request(method, path, **kwargs)

        return response

    def get(self, path: str, params: Dict = None) -> Dict:
        r = self._request("GET", path, params=params)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, json: Dict = None) -> requests.Response:
        return self._request("POST", path, json=json)

    def put(self, path: str, json: Dict = None) -> Dict:
        r = self._request("PUT", path, json=json)
        r.raise_for_status()
        return r.json()

    def download_zip(self, path: str) -> bytes:
        """Download a ZIP artifact, following redirects."""
        url = f"{self.BASE_URL}{path}"
        r = self.session.get(url, allow_redirects=True)
        r.raise_for_status()
        return r.content

    # ── Repo ──────────────────────────────────────────────

    def get_repo(self, owner: str, repo: str) -> Dict:
        return self.get(f"/repos/{owner}/{repo}")

    def get_languages(self, owner: str, repo: str) -> Dict:
        return self.get(f"/repos/{owner}/{repo}/languages")

    def get_latest_commit(self, owner: str, repo: str, branch: str = "main") -> str:
        """Fetches the latest commit SHA for a given branch."""
        data = self.get(f"/repos/{owner}/{repo}/commits/{branch}")
        return data["sha"]

    def compare_commits(self, owner: str, repo: str, base_sha: str, head_sha: str) -> list:
        """Returns a list of file paths that were added or modified between two commits."""
        data = self.get(f"/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}")
        changed_files = []
        for file in data.get("files", []):
            if file.get("status") in ["added", "modified", "renamed"]:
                changed_files.append(file["filename"])
        return changed_files

    def get_file(self, owner: str, repo: str, path: str) -> Optional[Dict]:
        try:
            return self.get(f"/repos/{owner}/{repo}/contents/{path}")
        except Exception:
            return None

    def commit_file(self, owner: str, repo: str, path: str,
                    content_b64: str, message: str,
                    sha: Optional[str] = None) -> Dict:
        body = {"message": message, "content": content_b64}
        if sha:
            body["sha"] = sha
        return self.put(f"/repos/{owner}/{repo}/contents/{path}", json=body)

    # ── Actions ───────────────────────────────────────────

    def trigger_workflow(self, owner: str, repo: str,
                         workflow_file: str, ref: str,
                         inputs: Dict = None) -> bool:
        body = {"ref": ref}
        if inputs:
            body["inputs"] = inputs
        r = self.post(
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_file}/dispatches",
            json=body,
        )
        return r.status_code == 204

    def get_workflow_runs(self, owner: str, repo: str,
                          event: str = None) -> Dict:
        params = {}
        if event:
            params["event"] = event
        return self.get(f"/repos/{owner}/{repo}/actions/runs", params=params)

    def get_run(self, owner: str, repo: str, run_id: int) -> Dict:
        return self.get(f"/repos/{owner}/{repo}/actions/runs/{run_id}")

    def get_run_artifacts(self, owner: str, repo: str, run_id: int) -> Dict:
        return self.get(f"/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts")

    def download_artifact(self, owner: str, repo: str,
                          artifact_id: int) -> bytes:
        return self.download_zip(
            f"/repos/{owner}/{repo}/actions/artifacts/{artifact_id}/zip"
        )
