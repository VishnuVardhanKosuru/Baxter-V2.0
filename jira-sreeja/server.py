import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

from jira_agent import JiraClient, LLMAnalyzer, sanitize_filename

load_dotenv()

app = FastAPI(title="Jira Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class JiraEpicRequest(BaseModel):
    issue_key: str

from fastapi import FastAPI, HTTPException, Request

@app.get("/api/jira/epic/{issue_key}")
async def get_epic_details(issue_key: str, request: Request):
    try:
        jira_url = request.headers.get("x-jira-url") or os.getenv("JIRA_URL")
        jira_email = request.headers.get("x-jira-email") or os.getenv("JIRA_EMAIL")
        jira_token = request.headers.get("x-jira-token") or os.getenv("JIRA_API_TOKEN")
        gemini_key = request.headers.get("x-gemini-key") or os.getenv("GEMINI_API_KEY")

        client = JiraClient(jira_url=jira_url, email=jira_email, api_token=jira_token)
        
        analyzer = LLMAnalyzer()
        if gemini_key:
            analyzer.gemini_key = gemini_key
        
        # Get raw issue data from Jira
        raw_issue = client.get_issue(issue_key)
        context = client.extract_context(raw_issue)
        
        # We classify the attachments
        analysis = analyzer.classify(context)
        
        # We want to format the response to match what the frontend expects
        # The frontend expects a list of FRDs and Manual Test Cases with id, name
        
        frds = []
        test_cases = []
        
        for file in analysis.get("classified_files", []):
            item = {
                "id": file["id"],
                "name": file["original_filename"],
                "suggested_name": file["suggested_filename"],
                "reason": file["reason"]
            }
            if file["category"] == "FRD":
                frds.append(item)
            elif file["category"] == "MANUAL_TEST_CASES":
                test_cases.append(item)
                
        # To match the frontend, we could return a structure that looks like a "release"
        return {
            "success": True,
            "epic": {
                "id": issue_key,
                "name": context.get("summary", issue_key),
                "frds": frds,
                "manualTestCases": test_cases
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/jira/evaluate")
async def evaluate_jira_epic(payload: JiraEpicRequest, request: Request):
    try:
        issue_key = payload.issue_key
        jira_url = request.headers.get("x-jira-url") or os.getenv("JIRA_URL")
        jira_email = request.headers.get("x-jira-email") or os.getenv("JIRA_EMAIL")
        jira_token = request.headers.get("x-jira-token") or os.getenv("JIRA_API_TOKEN")
        gemini_key = request.headers.get("x-gemini-key") or os.getenv("GEMINI_API_KEY")

        client = JiraClient(jira_url=jira_url, email=jira_email, api_token=jira_token)
        
        analyzer = LLMAnalyzer()
        if gemini_key:
            analyzer.gemini_key = gemini_key
        
        raw_issue = client.get_issue(issue_key)
        context = client.extract_context(raw_issue)
        analysis = analyzer.classify(context)
        
        # Download files to input_modules
        output_dir = os.path.join(os.getcwd(), "input_modules")
        os.makedirs(output_dir, exist_ok=True)
        
        downloaded_files = []
        classified_map = {str(item.get("id")): item for item in analysis.get("classified_files", [])}
        
        feature_name = sanitize_filename(analysis.get("feature_name", "Feature"))
        for att in context.get("attachments", []):
            att_id = str(att["id"])
            fname = att["filename"]
            item = classified_map.get(att_id)
            
            if not item:
                rule_meta = analyzer.classify_single_file(fname, issue_key, feature_name)
                cat = rule_meta.get("category", "OTHER")
                sug_name = rule_meta.get("suggested_filename", fname)
            else:
                cat = item.get("category", "OTHER")
                sug_name = item.get("suggested_filename", fname)
                
            sug_name = sanitize_filename(sug_name)
            save_path = os.path.join(output_dir, sug_name)
            
            try:
                client.download_attachment(att["content_url"], save_path)
                downloaded_files.append({
                    "original_name": fname,
                    "saved_name": sug_name,
                    "category": cat,
                    "path": save_path
                })
            except Exception as e:
                print(f"Failed to download {fname}: {e}")
                    
        return {
            "success": True,
            "message": f"Downloaded {len(downloaded_files)} files to input_modules",
            "files": downloaded_files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
