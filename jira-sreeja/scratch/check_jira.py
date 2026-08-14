import os
import requests
from dotenv import load_dotenv

load_dotenv()

jira_url = os.getenv("JIRA_URL")
email = os.getenv("JIRA_EMAIL")
token = os.getenv("JIRA_API_TOKEN")

auth = (email, token)

for key in ["SCRUM-2183", "SCRUM-2184", "SCRUM-2182", "SCRUM-2181"]:
    r = requests.get(f"{jira_url}/rest/api/3/issue/{key}", auth=auth)
    if r.status_code == 200:
        data = r.json()
        summary = data.get("fields", {}).get("summary", "")
        atts = data.get("fields", {}).get("attachment", [])
        print(f"=== {key}: {summary} ===")
        print(f"Attachments count: {len(atts)}")
        for a in atts:
            print(f"  - {a.get('filename')} (ID: {a.get('id')})")
    else:
        print(f"=== {key}: Status {r.status_code} ===")
