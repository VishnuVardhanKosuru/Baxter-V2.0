import os
import requests
from requests.auth import HTTPBasicAuth
from typing import Dict, Any, List, Optional

class JiraClient:
    def __init__(self, url: Optional[str] = None, email: Optional[str] = None, token: Optional[str] = None, project_key: Optional[str] = None):
        self.url = (url or os.getenv("JIRA_URL", "")).rstrip("/")
        self.email = email or os.getenv("JIRA_EMAIL", "")
        self.token = token or os.getenv("JIRA_API_TOKEN", "")
        self.project_key = project_key or os.getenv("JIRA_PROJECT_KEY", "")
        
        self.auth = HTTPBasicAuth(self.email, self.token) if self.email and self.token else None
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}

    def is_configured(self) -> bool:
        return bool(self.url and self.email and self.token and self.project_key)

    def transition_issue(self, issue_key: str, target_status: str) -> bool:
        """Transitions a Jira issue to a specified target status (e.g., 'In Progress', 'Done', 'To Do')."""
        if not self.is_configured() or not issue_key:
            return False

        # 1. Fetch available transitions for this issue
        trans_url = f"{self.url}/rest/api/3/issue/{issue_key}/transitions"
        try:
            res = requests.get(trans_url, headers=self.headers, auth=self.auth)
            if res.status_code != 200:
                print(f"[Jira Status] Could not fetch transitions for {issue_key}: {res.status_code}")
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
                print(f"[Jira Status Note] Status '{target_status}' not available for {issue_key}. Available transitions: {available}")
                return False

            # 2. Perform transition POST
            payload = {"transition": {"id": target_trans_id}}
            post_res = requests.post(trans_url, json=payload, headers=self.headers, auth=self.auth)
            if post_res.status_code in (200, 204):
                print(f"[Jira Status] {issue_key} status updated to -> '{target_status}'")
                return True
            else:
                print(f"[Jira Status Error] Failed to update status for {issue_key} ({post_res.status_code}): {post_res.text}")
                return False
        except Exception as e:
            print(f"[Jira Status Exception] {e}")
            return False

    def create_issue(self, summary: str, description: str, issue_type: str = "Feature", labels: Optional[List[str]] = None, status: Optional[str] = None) -> Optional[str]:
        """Creates a Jira Issue and returns its key (e.g. TCG-101), setting optional status."""
        if not self.is_configured():
            return None

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
                "issuetype": {"name": issue_type},
                "labels": labels or ["TestCaseGeneratorAgent", "Automated"]
            }
        }
        
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers, auth=self.auth)
            if response.status_code == 201:
                issue_key = response.json().get("key")
                print(f"[Jira] Created {issue_type}: {self.url}/browse/{issue_key}")
                
                # If a custom status is requested, transition issue
                if status:
                    self.transition_issue(issue_key, status)

                return issue_key
            else:
                # If issue type fails, fallback gracefully
                if issue_type not in ("Task", "Bug") and "issue type" in response.text.lower():
                    print(f"[Jira Warning] '{issue_type}' type not found. Falling back to 'Task' for {summary[:30]}...")
                    return self.create_issue(summary, description, "Task", labels, status)
                
                print(f"[Jira Error] Failed to create issue ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            print(f"[Jira Exception] {e}")
            return None
