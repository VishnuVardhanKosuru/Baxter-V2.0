"""
agents/jira_agent.py
--------------------
Production Jira FRD & Manual Test Cases Fetcher Agent.
Handles Jira Cloud REST API communication, attachment extraction,
and AI classification of requirements and manual test suites.
"""

import os
import re
import json
import time
import argparse
from typing import Dict, List, Any, Optional
import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Load environment variables
load_dotenv()
console = Console()

try:
    from agents.jira_prompts import SYSTEM_PROMPT
except ImportError:
    from jira_prompts import SYSTEM_PROMPT


def sanitize_filename(name: str) -> str:
    """Removes illegal filesystem characters, non-ASCII symbols, and cleans up whitespace."""
    name = name.replace("—", "_").replace("–", "_")
    clean = re.sub(r'[^\w\s.-]', '', name)
    clean = re.sub(r'\s+', '_', clean.strip())
    clean = re.sub(r'_+', '_', clean.strip('_'))
    return clean or "Feature"


# ==========================================
# Jira API Client
# ==========================================
class JiraClient:
    """Handles authentication and REST API calls to Jira Cloud efficiently."""

    def __init__(self, jira_url: Optional[str] = None, email: Optional[str] = None, api_token: Optional[str] = None):
        self.jira_url = (jira_url or os.getenv("JIRA_URL", "")).rstrip("/")
        self.email = email or os.getenv("JIRA_EMAIL", "")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN", "")

        self.session = requests.Session()
        if self.email and self.api_token:
            self.session.auth = (self.email, self.api_token)
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    def _parse_adf_text(self, node: Any) -> str:
        """Parses text recursively from Atlassian Document Format (ADF) nodes."""
        if not node:
            return ""
        if isinstance(node, str):
            return node
        if isinstance(node, dict):
            text = node.get("text", "")
            content = node.get("content", [])
            child_text = " ".join(self._parse_adf_text(c) for c in content)
            return (text + " " + child_text).strip()
        if isinstance(node, list):
            return " ".join(self._parse_adf_text(i) for i in node).strip()
        return ""

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """Fetches detailed metadata for a single Jira issue by key. 
        If the issue is an Epic, it also fetches and merges attachments from its child issues."""
        url = f"{self.jira_url}/rest/api/3/issue/{issue_key}?expand=renderedFields"
        response = self.session.get(url)
        if response.status_code == 404:
            raise ValueError(f"Jira issue '{issue_key}' not found (404). Check JIRA_URL and Issue Key.")
        elif response.status_code in (401, 403):
            raise PermissionError("Jira authentication failed. Check JIRA_EMAIL and JIRA_API_TOKEN in .env.")
        response.raise_for_status()
        issue_data = response.json()

        # If it is an Epic, fetch its children and merge their attachments
        issuetype = issue_data.get("fields", {}).get("issuetype", {}).get("name", "")
        if issuetype == "Epic":
            try:
                payload = {
                    "jql": f"parent = {issue_key} OR \"Epic Link\" = {issue_key}",
                    "maxResults": 100,
                    "fields": ["attachment"]
                }
                search_url = f"{self.jira_url}/rest/api/3/search/jql"
                search_resp = self.session.post(search_url, json=payload)
                if search_resp.status_code == 200:
                    children = search_resp.json().get("issues", [])
                    if "attachment" not in issue_data["fields"] or issue_data["fields"]["attachment"] is None:
                        issue_data["fields"]["attachment"] = []
                    
                    for child in children:
                        child_atts = child.get("fields", {}).get("attachment", [])
                        issue_data["fields"]["attachment"].extend(child_atts)
            except Exception:
                pass # Fail silently if child fetch fails, just return the Epic data

        return issue_data

    def get_all_projects(self) -> List[str]:
        """Fetches project keys from Jira Cloud."""
        url = f"{self.jira_url}/rest/api/3/project"
        response = self.session.get(url)
        if response.status_code == 200:
            return [p.get("key") for p in response.json() if p.get("key")]
        return []

    def search_issues(self, jql: str = "", max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Searches issues using JQL in a single request by requesting required fields directly.
        Avoids N+1 HTTP request overhead.
        """
        url = f"{self.jira_url}/rest/api/3/search/jql"

        if not jql or not jql.strip():
            projects = self.get_all_projects()
            jql = f"project IN ({','.join(projects)})" if projects else "order by created DESC"

        payload = {
            "jql": jql,
            "maxResults": max_results,
            "fields": ["summary", "description", "attachment"]
        }

        response = self.session.post(url, json=payload)
        response.raise_for_status()

        issues = response.json().get("issues", [])
        return [iss for iss in issues if iss.get("fields", {}).get("attachment")]

    def extract_context(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts issue key, summary, parsed description, and attachments metadata."""
        fields = issue_data.get("fields", {})
        raw_desc = fields.get("description")
        description = self._parse_adf_text(raw_desc) if raw_desc else ""

        attachments = [
            {
                "id": str(att.get("id")),
                "filename": att.get("filename"),
                "size": att.get("size"),
                "mimeType": att.get("mimeType"),
                "content_url": att.get("content")
            }
            for att in fields.get("attachment", [])
        ]

        return {
            "issue_key": issue_data.get("key", "ISSUE"),
            "summary": fields.get("summary", ""),
            "description": description,
            "attachments": attachments
        }

    def download_attachment(self, content_url: str, save_path: str) -> str:
        """Streams binary attachment content to local storage."""
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        response = self.session.get(content_url, stream=True)
        response.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return save_path


# ==========================================
# LLM Document Classifier
# ==========================================
class LLMAnalyzer:
    """Classifies attachments using Gemini/OpenAI with rule-based fallback."""

    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")

    def classify(self, context: Dict[str, Any]) -> Dict[str, Any]:
        attachments = context.get("attachments", [])
        if not attachments:
            return {"feature_name": "Feature", "classified_files": []}

        # 1. Try Gemini API if key is present
        if self.gemini_key and self.gemini_key != "your_gemini_api_key_here":
            try:
                return self._call_gemini(context)
            except Exception:
                pass

        # 2. Try OpenAI API if key is present
        if self.openai_key:
            try:
                return self._call_openai(context)
            except Exception:
                pass

        # 3. Fallback to rule-based classification
        return self._rule_based_classifier(context)

    def _call_gemini(self, context: Dict[str, Any]) -> Dict[str, Any]:
        from google import genai
        client = genai.Client(api_key=self.gemini_key)
        prompt = f"{SYSTEM_PROMPT}\n\nJIRA ISSUE DATA:\n{json.dumps(context, indent=2)}"
        response = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
        return self._parse_json(response.text)

    def _call_openai(self, context: Dict[str, Any]) -> Dict[str, Any]:
        import openai
        client = openai.OpenAI(api_key=self.openai_key)
        prompt = f"JIRA ISSUE DATA:\n{json.dumps(context, indent=2)}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(resp.choices[0].message.content)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        json_str = match.group(1) if match else text.strip()
        start, end = json_str.find("{"), json_str.rfind("}")
        return json.loads(json_str[start:end + 1])

    def classify_single_file(self, filename: str, issue_key: str = "", feature_name: str = "") -> Dict[str, str]:
        """Unified rule-based classifier for a single file attachment."""
        lower_fname = filename.lower()

        if any(k in lower_fname for k in ["frd", "req", "prd", "spec", "functional"]):
            cat = "FRD"
            reason = "Matched FRD keyword"
        elif any(k in lower_fname for k in ["test", "tc", "scenario", "manual"]):
            cat = "MANUAL_TEST_CASES"
            reason = "Matched Test Case keyword"
        elif lower_fname.endswith((".doc", ".docx", ".pdf")):
            cat = "FRD"
            reason = "Document extension defaulted to FRD"
        elif lower_fname.endswith((".xlsx", ".xls", ".csv")):
            cat = "MANUAL_TEST_CASES"
            reason = "Spreadsheet extension defaulted to Manual Test Cases"
        else:
            cat = "OTHER"
            reason = "Generic attachment"

        return {
            "category": cat,
            "suggested_filename": filename,
            "reason": reason
        }

    def _rule_based_classifier(self, context: Dict[str, Any]) -> Dict[str, Any]:
        issue_key = context.get("issue_key", "TASK")
        summary_raw = context.get("summary", "")
        feature_name = sanitize_filename("_".join(summary_raw.split()[:4])) or "Feature"

        classified = []
        for file in context.get("attachments", []):
            fname = file.get("filename", "")
            meta = self.classify_single_file(fname, issue_key, feature_name)
            classified.append({
                "id": str(file.get("id")),
                "original_filename": fname,
                "category": meta["category"],
                "suggested_filename": fname,
                "reason": meta["reason"]
            })

        return {"feature_name": feature_name, "classified_files": classified}


# ==========================================
# Core Processing Engine
# ==========================================
def process_issue(client: JiraClient, analyzer: LLMAnalyzer, issue_key: str, output_dir: str, preloaded_issue: Optional[Dict[str, Any]] = None):
    """Processes a Jira issue, classifies attachments, and downloads them cleanly."""
    console.print(f"\n[bold blue]==> Processing Jira Issue:[/bold blue] [bold yellow]{issue_key}[/bold yellow]")
    try:
        raw_issue = preloaded_issue or client.get_issue(issue_key)
    except Exception as e:
        console.print(f"[bold red]Error fetching issue {issue_key}:[/bold red] {e}")
        return

    context = client.extract_context(raw_issue)
    attachments = context.get("attachments", [])

    if not attachments:
        console.print(f"[yellow]No attachments found on issue {issue_key}.[/yellow]")
        return

    console.print(f"Found [bold yellow]{len(attachments)}[/bold yellow] attachment(s). Running AI classification...")
    analysis = analyzer.classify(context)

    table = Table(title=f"Jira Issue {issue_key} - Downloaded Artifacts", show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Original Filename", style="dim", ratio=2)
    table.add_column("Category", style="bold cyan", ratio=1)
    table.add_column("Saved File Path", style="bold green", ratio=3)

    classified_map = {str(item.get("id")): item for item in analysis.get("classified_files", [])}

    used_paths = set()

    for att in attachments:
        att_id = str(att["id"])
        fname = att["filename"]

        item = classified_map.get(att_id)
        if not item:
            rule_meta = analyzer.classify_single_file(fname, issue_key, "")
            cat = rule_meta["category"]
        else:
            cat = item.get("category", "OTHER")

        sug_name = fname
        folder = "frd" if cat == "FRD" else ("testcases" if cat == "MANUAL_TEST_CASES" else "other")

        stem, ext = os.path.splitext(sug_name)
        counter = 1
        curr_sug = sug_name
        save_path = os.path.join(output_dir, folder, curr_sug)

        while save_path.lower() in used_paths:
            counter += 1
            curr_sug = f"{stem}_{counter}{ext}"
            save_path = os.path.join(output_dir, folder, curr_sug)

        used_paths.add(save_path.lower())

        try:
            downloaded = client.download_attachment(att["content_url"], save_path)
            table.add_row(fname, cat, os.path.abspath(downloaded))
            console.print(f"  [bold green][+] Downloaded [{cat}]:[/bold green] {downloaded}")
        except Exception as e:
            console.print(f"  [bold red][-] Failed to download {fname}:[/bold red] {e}")

    console.print(table)


def run_mock_demo(output_dir: str):
    """Runs a dry-run mock mode without requiring live Jira access."""
    console.print("[bold yellow]Running Mock Dry-Run Mode...[/bold yellow]")
    mock_issue = {
        "key": "BANK-101",
        "fields": {
            "summary": "Implement User Authentication and OAuth Login Flow",
            "description": "FRD and manual test suite for authentication.",
            "attachment": [
                {"id": "att-1", "filename": "FRD_Auth_v1.docx", "content": "https://mock/att-1"},
                {"id": "att-2", "filename": "Manual_Test_Suite_Auth.xlsx", "content": "https://mock/att-2"}
            ]
        }
    }
    client = JiraClient()
    analyzer = LLMAnalyzer()
    context = client.extract_context(mock_issue)
    analysis = analyzer.classify(context)

    table = Table(title="Jira Agent Classification & Naming Summary (Mock)", expand=True)
    table.add_column("Original Filename", style="dim", ratio=2)
    table.add_column("Category", style="bold green", ratio=1)
    table.add_column("Standardized Filename", style="bold yellow", ratio=3)
    table.add_column("Reason", style="white", ratio=2)

    for file in analysis.get("classified_files", []):
        table.add_row(file["original_filename"], file["category"], file["suggested_filename"], file["reason"])

    console.print(table)


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Production Jira FRD & Manual Test Cases Fetcher Agent")
    parser.add_argument("--issue", "-i", type=str, help="Specific Jira Issue Key (optional)")
    parser.add_argument("--jql", "-q", type=str, help="JQL search query (optional)")
    parser.add_argument("--output", "-o", type=str, default="./output", help="Output directory to save files")
    parser.add_argument("--mock", action="store_true", help="Run in mock dry-run mode")

    args = parser.parse_args()

    console.print(Panel.fit("[bold green]Jira FRD & Manual Test Cases Fetcher Agent[/bold green]"))

    if args.mock:
        run_mock_demo(args.output)
        return

    client = JiraClient()
    analyzer = LLMAnalyzer()

    # Mode 1: Process single issue
    if args.issue:
        process_issue(client, analyzer, args.issue, args.output)
        return

    # Mode 2: Search and process all matching issues
    jql_query = args.jql if args.jql else ""
    if jql_query:
        console.print(f"[bold cyan]Searching Jira with custom JQL:[/bold cyan] {jql_query}")
    else:
        console.print("[bold cyan]Auto-scanning Jira workspace for ALL tickets with attachments...[/bold cyan]")

    try:
        issues = client.search_issues(jql_query)
        if not issues:
            console.print("[bold yellow]No issues with attachments found in Jira.[/bold yellow]")
            return

        console.print(f"[bold green]Found {len(issues)} Jira issue(s) with attachments![/bold green]")
        for idx, issue in enumerate(issues):
            key = issue.get("key")
            if key:
                if idx > 0:
                    time.sleep(1)
                process_issue(client, analyzer, key, args.output, preloaded_issue=issue)

    except Exception as e:
        console.print(f"[bold red]Jira Search Error:[/bold red] {e}")


if __name__ == "__main__":
    main()
