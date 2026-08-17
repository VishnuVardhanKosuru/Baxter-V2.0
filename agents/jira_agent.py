"""
agents/jira_agent.py
--------------------
Jira FRD & Manual Test Cases fetcher agent.

Handles Jira Cloud REST API communication, attachment extraction, and AI
classification of requirements and manual test suites.

Every outbound HTTP call carries an explicit timeout and is issued through a
pooled Session with automatic retry/backoff on transient failures, so a hung or
flaky Jira instance cannot stall the pipeline indefinitely.
"""

import argparse
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core import constants as const
from core.logger import logger

try:
    from agents.jira_prompts import SYSTEM_PROMPT
except ImportError:  # pragma: no cover - direct script execution fallback
    from jira_prompts import SYSTEM_PROMPT


def sanitize_filename(name: str) -> str:
    """
    Reduce an arbitrary string to a safe, portable filename component.

    Strips directory separators, path traversal sequences, and non-ASCII symbols,
    so a value taken from a Jira attachment name can never escape the intended
    output directory.

    Returns:
        A cleaned filename, or "Feature" if nothing usable remains.
    """
    if not name:
        return "Feature"
    name = name.replace("—", "_").replace("–", "_")
    name = os.path.basename(name.replace("\\", "/"))
    clean = re.sub(r"[^\w\s.-]", "", name)
    clean = re.sub(r"\s+", "_", clean.strip())
    clean = re.sub(r"_+", "_", clean.strip("_"))
    clean = clean.lstrip(".")
    return clean or "Feature"


# ==========================================
# Jira API Client
# ==========================================
class JiraClient:
    """Handles authentication and REST API calls to Jira Cloud."""

    def __init__(
        self,
        jira_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
        timeout: int = const.JIRA_TIMEOUT_S,
    ):
        self.jira_url = (jira_url or os.getenv("JIRA_URL", "")).rstrip("/")
        self.email = email or os.getenv("JIRA_EMAIL", "")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN", "")
        self.timeout = timeout

        self.session = requests.Session()
        if self.email and self.api_token:
            self.session.auth = (self.email, self.api_token)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        # Retry transient failures (rate limits, 5xx, dropped connections) with
        # exponential backoff. Mounted on both schemes so the pool is reused.
        retry = Retry(
            total=const.JIRA_MAX_RETRIES,
            backoff_factor=const.JIRA_BACKOFF_S,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _require_config(self) -> None:
        """
        Raises:
            ValueError: if the client has no base URL or no credentials.
        """
        if not self.jira_url:
            raise ValueError("Jira URL is not configured. Set JIRA_URL or pass jira_url.")
        if not (self.email and self.api_token):
            raise ValueError(
                "Jira credentials are not configured. Set JIRA_EMAIL and JIRA_API_TOKEN."
            )

    def _post(self, path: str, payload: dict) -> requests.Response:
        """Issues a POST to a Jira REST path with the configured timeout."""
        self._require_config()
        return self.session.post(f"{self.jira_url}{path}", json=payload, timeout=self.timeout)

    def _get(self, path: str, **kwargs) -> requests.Response:
        """Issues a GET to a Jira REST path with the configured timeout."""
        self._require_config()
        return self.session.get(f"{self.jira_url}{path}", timeout=self.timeout, **kwargs)

    def _parse_adf_text(self, node: Any) -> str:
        """Recursively extracts plain text from Atlassian Document Format nodes."""
        if not node:
            return ""
        if isinstance(node, str):
            return node
        if isinstance(node, dict):
            text = node.get("text", "")
            child_text = " ".join(self._parse_adf_text(c) for c in node.get("content", []))
            return (text + " " + child_text).strip()
        if isinstance(node, list):
            return " ".join(self._parse_adf_text(i) for i in node).strip()
        return ""

    def search(self, jql: str, fields: List[str], max_results: int) -> List[Dict[str, Any]]:
        """
        Runs a JQL search and returns the raw issue list.

        Raises:
            ValueError:               if the client is not configured.
            requests.HTTPError:       on a non-2xx response.
            requests.RequestException: on a network/timeout failure.
        """
        response = self._post("/rest/api/3/search/jql", {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields,
        })
        response.raise_for_status()
        return response.json().get("issues", [])

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """
        Fetches a single Jira issue. If it is an Epic, attachments from its child
        issues are merged into the returned payload.

        Raises:
            ValueError:         if the issue is not found or the key is empty.
            PermissionError:    if authentication or authorisation fails.
            requests.HTTPError: on any other non-2xx response.
        """
        if not issue_key or not issue_key.strip():
            raise ValueError("Issue key is required.")
        issue_key = issue_key.strip()

        response = self._get(
            f"/rest/api/3/issue/{issue_key}", params={"expand": "renderedFields"}
        )
        if response.status_code == 404:
            raise ValueError(
                f"Jira issue '{issue_key}' not found (404). Check the Jira URL and issue key."
            )
        if response.status_code in (401, 403):
            raise PermissionError(
                "Jira authentication failed. Check JIRA_EMAIL and JIRA_API_TOKEN."
            )
        response.raise_for_status()
        issue_data = response.json()

        issuetype = issue_data.get("fields", {}).get("issuetype", {}).get("name", "")
        if issuetype == "Epic":
            self._merge_child_attachments(issue_key, issue_data)

        return issue_data

    def _merge_child_attachments(self, issue_key: str, issue_data: Dict[str, Any]) -> None:
        """
        Appends attachments from an Epic's child issues onto the Epic payload.

        A failure here is logged and swallowed: the Epic's own attachments are
        still usable, so a permissions gap on children must not fail the request.
        """
        try:
            children = self.search(
                jql=f'parent = {issue_key} OR "Epic Link" = {issue_key}',
                fields=["attachment"],
                max_results=const.JIRA_MAX_RESULTS,
            )
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[JIRA] Could not fetch child issues of %s: %s", issue_key, exc)
            return

        fields = issue_data.setdefault("fields", {})
        if not fields.get("attachment"):
            fields["attachment"] = []

        for child in children:
            fields["attachment"].extend(child.get("fields", {}).get("attachment", []) or [])

    def get_all_projects(self) -> List[str]:
        """Returns all accessible project keys, or an empty list on failure."""
        try:
            response = self._get("/rest/api/3/project")
            response.raise_for_status()
            return [p.get("key") for p in response.json() if p.get("key")]
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[JIRA] Could not list projects: %s", exc)
            return []

    def search_issues(self, jql: str = "", max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Searches issues with JQL and returns only those that have attachments.

        Requests all required fields in one call to avoid N+1 HTTP overhead.
        """
        if not jql or not jql.strip():
            projects = self.get_all_projects()
            jql = f"project IN ({','.join(projects)})" if projects else "order by created DESC"

        issues = self.search(
            jql=jql,
            fields=["summary", "description", "attachment"],
            max_results=max_results,
        )
        return [iss for iss in issues if iss.get("fields", {}).get("attachment")]

    def extract_context(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts issue key, summary, parsed description, and attachment metadata."""
        fields = issue_data.get("fields", {}) or {}
        raw_desc = fields.get("description")

        attachments = [
            {
                "id": str(att.get("id")),
                "filename": att.get("filename"),
                "size": att.get("size"),
                "mimeType": att.get("mimeType"),
                "content_url": att.get("content"),
            }
            for att in (fields.get("attachment") or [])
        ]

        return {
            "issue_key": issue_data.get("key", "ISSUE"),
            "summary": fields.get("summary", ""),
            "description": self._parse_adf_text(raw_desc) if raw_desc else "",
            "attachments": attachments,
        }

    def download_attachment(self, content_url: str, save_path: str) -> str:
        """
        Streams a binary attachment to local storage.

        Raises:
            ValueError:                if content_url is empty.
            requests.RequestException: on a network, timeout, or HTTP failure.
        """
        if not content_url:
            raise ValueError("Attachment content URL is missing.")

        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        with self.session.get(content_url, stream=True, timeout=self.timeout) as response:
            response.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=const.JIRA_DOWNLOAD_CHUNK_BYTES):
                    if chunk:
                        f.write(chunk)
        return save_path


# ==========================================
# LLM Document Classifier
# ==========================================
class LLMAnalyzer:
    """Classifies Jira attachments using Gemini/OpenAI with a rule-based fallback."""

    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")

    def classify(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classifies every attachment on an issue.

        Tries Gemini, then OpenAI, then a deterministic filename-keyword
        classifier. Each LLM failure is logged and falls through to the next tier
        so classification always returns a usable result.
        """
        if not context.get("attachments"):
            return {"feature_name": "Feature", "classified_files": []}

        if self.gemini_key:
            try:
                return self._call_gemini(context)
            except Exception as exc:
                logger.warning("[JIRA] Gemini classification failed (%s) — trying next tier.", exc)

        if self.openai_key:
            try:
                return self._call_openai(context)
            except Exception as exc:
                logger.warning("[JIRA] OpenAI classification failed (%s) — using rule-based.", exc)

        logger.info("[JIRA] Using rule-based attachment classification.")
        return self._rule_based_classifier(context)

    def _call_gemini(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Classifies attachments via the Gemini API."""
        from google import genai

        client = genai.Client(api_key=self.gemini_key)
        prompt = f"{SYSTEM_PROMPT}\n\nJIRA ISSUE DATA:\n{json.dumps(context, indent=2)}"
        response = client.models.generate_content(
            model=const.JIRA_GEMINI_MODEL, contents=prompt
        )
        return self._parse_json(response.text)

    def _call_openai(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Classifies attachments via the OpenAI API."""
        import openai

        client = openai.OpenAI(api_key=self.openai_key, timeout=const.JIRA_TIMEOUT_S)
        resp = client.chat.completions.create(
            model=const.JIRA_OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"JIRA ISSUE DATA:\n{json.dumps(context, indent=2)}"},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """
        Extracts a JSON object from an LLM response, tolerating markdown fences.

        Raises:
            ValueError: if no JSON object can be recovered.
        """
        if not text:
            raise ValueError("LLM returned an empty response.")

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        json_str = match.group(1) if match else text.strip()

        start, end = json_str.find("{"), json_str.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("No JSON object found in the LLM response.")

        return json.loads(json_str[start:end + 1])

    def classify_single_file(self, filename: str) -> Dict[str, str]:
        """
        Deterministic filename-keyword classifier for one attachment.

        Returns:
            {"category", "suggested_filename", "reason"} where category is one of
            FRD, MANUAL_TEST_CASES, or OTHER.
        """
        lower_fname = (filename or "").lower()

        if any(k in lower_fname for k in const.JIRA_FRD_KEYWORDS):
            cat, reason = "FRD", "Matched FRD keyword"
        elif any(k in lower_fname for k in const.JIRA_TC_KEYWORDS):
            cat, reason = "MANUAL_TEST_CASES", "Matched test case keyword"
        elif lower_fname.endswith(const.JIRA_DOC_EXTENSIONS):
            cat, reason = "FRD", "Document extension defaulted to FRD"
        elif lower_fname.endswith(const.JIRA_SHEET_EXTENSIONS):
            cat, reason = "MANUAL_TEST_CASES", "Spreadsheet extension defaulted to test cases"
        else:
            cat, reason = "OTHER", "Generic attachment"

        return {"category": cat, "suggested_filename": filename, "reason": reason}

    def _rule_based_classifier(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Applies classify_single_file() across every attachment on the issue."""
        summary_raw = context.get("summary", "")
        feature_name = sanitize_filename("_".join(summary_raw.split()[:4])) or "Feature"

        classified = []
        for file in context.get("attachments", []):
            fname = file.get("filename", "")
            meta = self.classify_single_file(fname)
            classified.append({
                "id": str(file.get("id")),
                "original_filename": fname,
                "category": meta["category"],
                "suggested_filename": fname,
                "reason": meta["reason"],
            })

        return {"feature_name": feature_name, "classified_files": classified}


# ==========================================
# CLI processing engine
# ==========================================
def process_issue(
    client: JiraClient,
    analyzer: LLMAnalyzer,
    issue_key: str,
    output_dir: str,
    preloaded_issue: Optional[Dict[str, Any]] = None,
) -> None:
    """Processes one Jira issue: classifies its attachments and downloads them."""
    logger.info("Processing Jira issue: %s", issue_key)

    try:
        raw_issue = preloaded_issue or client.get_issue(issue_key)
    except (ValueError, PermissionError, requests.RequestException) as exc:
        logger.error("Error fetching issue %s: %s", issue_key, exc)
        return

    context = client.extract_context(raw_issue)
    attachments = context.get("attachments", [])
    if not attachments:
        logger.info("No attachments found on issue %s.", issue_key)
        return

    logger.info("Found %d attachment(s). Running classification...", len(attachments))
    analysis = analyzer.classify(context)
    classified_map = {str(item.get("id")): item for item in analysis.get("classified_files", [])}

    used_paths = set()
    for att in attachments:
        fname = att["filename"]
        item = classified_map.get(str(att["id"]))
        cat = item.get("category", "OTHER") if item else analyzer.classify_single_file(fname)["category"]

        folder = {"FRD": "frd", "MANUAL_TEST_CASES": "testcases"}.get(cat, "other")
        safe_name = sanitize_filename(fname)
        stem, ext = os.path.splitext(safe_name)

        save_path = os.path.join(output_dir, folder, safe_name)
        counter = 1
        while save_path.lower() in used_paths:
            counter += 1
            save_path = os.path.join(output_dir, folder, f"{stem}_{counter}{ext}")
        used_paths.add(save_path.lower())

        try:
            downloaded = client.download_attachment(att["content_url"], save_path)
            logger.info("Downloaded [%s]: %s", cat, downloaded)
        except (ValueError, OSError, requests.RequestException) as exc:
            logger.error("Failed to download %s: %s", fname, exc)


def main() -> None:
    """CLI entry-point for the Jira fetcher agent."""
    parser = argparse.ArgumentParser(
        description="Jira FRD & Manual Test Cases fetcher agent"
    )
    parser.add_argument("--issue", "-i", type=str, help="Specific Jira issue key")
    parser.add_argument("--jql", "-q", type=str, help="JQL search query")
    parser.add_argument(
        "--output", "-o", type=str, default="./output", help="Output directory"
    )
    args = parser.parse_args()

    client = JiraClient()
    analyzer = LLMAnalyzer()

    if args.issue:
        process_issue(client, analyzer, args.issue, args.output)
        return

    jql_query = args.jql or ""
    logger.info(
        "Searching Jira with JQL: %s", jql_query or "(all projects with attachments)"
    )

    try:
        issues = client.search_issues(jql_query)
    except (ValueError, requests.RequestException) as exc:
        logger.error("Jira search error: %s", exc)
        return

    if not issues:
        logger.info("No issues with attachments found in Jira.")
        return

    logger.info("Found %d Jira issue(s) with attachments.", len(issues))
    for idx, issue in enumerate(issues):
        key = issue.get("key")
        if not key:
            continue
        if idx > 0:
            time.sleep(1)   # be gentle with the Jira API between issues
        process_issue(client, analyzer, key, args.output, preloaded_issue=issue)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    main()
