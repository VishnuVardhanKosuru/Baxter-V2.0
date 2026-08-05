"""
Jira Cloud REST API Integration Client.

Provides authentication and payload builder methods for creating Jira issues (Feature / Story / Task)
and performing status transitions via the Jira REST API v3.
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from typing import Dict, Any, List, Optional

class JiraClient:
    """
    Client for interacting with Jira Cloud REST API endpoints.
    Includes connection validation, timeouts, issue type caching, and circuit breaker.
    """

    def __init__(self, url: Optional[str] = None, email: Optional[str] = None, token: Optional[str] = None, project_key: Optional[str] = None, timeout: int = 10):
        """Initializes Jira credentials from explicit arguments or environment variables."""
        from dotenv import load_dotenv
        load_dotenv()

        self.url = (url or os.getenv("JIRA_URL", "")).rstrip("/")
        self.email = email or os.getenv("JIRA_EMAIL", "")
        self.token = token or os.getenv("JIRA_API_TOKEN", "")
        self.project_key = project_key or os.getenv("JIRA_PROJECT_KEY", "")
        self.timeout = timeout

        
        self.auth = HTTPBasicAuth(self.email, self.token) if self.email and self.token else None
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        
        # State & Caching
        self.valid_issue_types: List[str] = []
        self.circuit_broken: bool = False
        self.consecutive_failures: int = 0
        self.MAX_CONSECUTIVE_FAILURES: int = 3

    def is_configured(self) -> bool:
        return bool(self.url and self.email and self.token and self.project_key)

    def verify_connection(self) -> tuple[bool, str]:
        """
        Validates Jira credentials and project key upfront via a single fast HTTP GET call.
        Caches allowed issue types for the project.

        Returns:
            (success: bool, message: str)
        """
        if not self.is_configured():
            return False, "Jira parameters missing in .env (JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY)"

        endpoint = f"{self.url}/rest/api/3/project/{self.project_key}"
        try:
            res = requests.get(endpoint, headers=self.headers, auth=self.auth, timeout=self.timeout)
            if res.status_code == 200:
                proj_data = res.json()
                issue_types_data = proj_data.get("issueTypes", [])
                self.valid_issue_types = [it.get("name") for it in issue_types_data if it.get("name")]
                print(f"[Jira Sync] Successfully connected to Project '{self.project_key}' ({proj_data.get('name', '')}).")
                if self.valid_issue_types:
                    print(f"[Jira Sync] Available issue types: {', '.join(self.valid_issue_types)}")
                return True, "Connected successfully"
            elif res.status_code in (401, 403):
                return False, f"Authentication failed (HTTP {res.status_code}). Check JIRA_EMAIL and JIRA_API_TOKEN."
            elif res.status_code == 404:
                return False, f"Project '{self.project_key}' not found (HTTP 404). Check JIRA_PROJECT_KEY."
            else:
                return False, f"HTTP {res.status_code}: {res.text[:100]}"
        except requests.exceptions.Timeout:
            return False, f"Connection timeout after {self.timeout}s connecting to {self.url}"
        except Exception as e:
            return False, f"Connection error: {e}"

    def get_best_issue_type(self, preferred_type: str = "Feature") -> str:
        """Determines the best matching issue type supported by the target Jira project."""
        if not self.valid_issue_types:
            return preferred_type

        # Case-insensitive match check
        for it in self.valid_issue_types:
            if it.lower() == preferred_type.lower():
                return it

        # Fallbacks order: Task -> Story -> Bug -> First available
        for fallback in ["Task", "Story", "Bug", "Standard Issue"]:
            for it in self.valid_issue_types:
                if it.lower() == fallback.lower():
                    return it

        return self.valid_issue_types[0]

    def transition_issue(self, issue_key: str, target_status: str) -> bool:
        """Transitions a Jira issue to a specified target status (e.g., 'In Progress', 'Done', 'To Do')."""
        if not self.is_configured() or not issue_key or self.circuit_broken:
            return False

        trans_url = f"{self.url}/rest/api/3/issue/{issue_key}/transitions"
        try:
            res = requests.get(trans_url, headers=self.headers, auth=self.auth, timeout=self.timeout)
            if res.status_code != 200:
                print(f"[Jira Status] Could not fetch transitions for {issue_key}: HTTP {res.status_code}")
                return False

            transitions = res.json().get("transitions", [])
            target_trans_id = None
            target_lower = target_status.lower().strip()

            for t in transitions:
                name = t.get("name", "").lower()
                to_status = t.get("to", {}).get("name", "").lower()
                if name == target_lower or to_status == target_lower or target_lower in name or target_lower in to_status:
                    target_trans_id = t.get("id")
                    break

            if not target_trans_id:
                available = [f"{t.get('name')} -> {t.get('to',{}).get('name')}" for t in transitions]
                print(f"[Jira Status Note] Status '{target_status}' not available for {issue_key}. Available: {available}")
                return False

            payload = {"transition": {"id": target_trans_id}}
            post_res = requests.post(trans_url, json=payload, headers=self.headers, auth=self.auth, timeout=self.timeout)
            if post_res.status_code in (200, 204):
                print(f"[Jira Status] {issue_key} status updated to -> '{target_status}'")
                return True
            else:
                print(f"[Jira Status Error] Failed status update for {issue_key} ({post_res.status_code}): {post_res.text[:100]}")
                return False
        except Exception as e:
            print(f"[Jira Status Exception] {e}")
            return False

    def create_issue(self, summary: str, description: str, issue_type: str = "Feature", labels: Optional[List[str]] = None, status: Optional[str] = None) -> Optional[str]:
        """Creates a Jira Issue and returns its key (e.g. TCG-101), setting optional status."""
        if not self.is_configured() or self.circuit_broken:
            return None

        # Resolve issue type against project schema if known
        target_issue_type = self.get_best_issue_type(issue_type)

        endpoint = f"{self.url}/rest/api/3/issue"
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}]
                        }
                    ]
                },
                "issuetype": {"name": target_issue_type},
                "labels": labels or ["TestCaseGeneratorAgent", "Automated"]
            }
        }
        
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers, auth=self.auth, timeout=self.timeout)
            if response.status_code == 201:
                self.consecutive_failures = 0  # Reset circuit breaker counter
                issue_key = response.json().get("key")
                print(f"[Jira] Created {target_issue_type} ({issue_key}): {self.url}/browse/{issue_key}")
                
                if status:
                    self.transition_issue(issue_key, status)

                return issue_key
            else:
                self.consecutive_failures += 1
                print(f"[Jira Error] Failed to create issue ({response.status_code}): {response.text[:150]}")
                
                if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                    self.circuit_broken = True
                    print(f"[Jira Circuit Breaker] {self.MAX_CONSECUTIVE_FAILURES} consecutive API failures. Halting Jira sync to prevent infinite retries.")
                
                return None
        except requests.exceptions.Timeout:
            self.consecutive_failures += 1
            print(f"[Jira Timeout] HTTP request timed out after {self.timeout}s.")
            if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                self.circuit_broken = True
                print(f"[Jira Circuit Breaker] Halting Jira sync due to consecutive timeouts.")
            return None
        except Exception as e:
            self.consecutive_failures += 1
            print(f"[Jira Exception] {e}")
            if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                self.circuit_broken = True
            return None

