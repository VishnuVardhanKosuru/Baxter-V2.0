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

    def create_issue(self, summary: str, description: str, issue_type: str = "Test", labels: Optional[List[str]] = None) -> Optional[str]:
        """Creates a Jira Issue and returns its key (e.g. TCG-101)."""
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
                print(f"[Jira] Created Test: {self.url}/browse/{issue_key}")
                return issue_key
            else:
                # If "Test" issue type fails, try falling back to "Task"
                if issue_type == "Test" and "issue type" in response.text.lower():
                    print(f"[Jira Warning] 'Test' issue type not found. Falling back to 'Task' for {summary[:30]}...")
                    return self.create_issue(summary, description, "Task", labels)
                
                print(f"[Jira Error] Failed to create issue ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            print(f"[Jira Exception] {e}")
            return None
