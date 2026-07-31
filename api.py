import sys
import os
import asyncio
import subprocess
import json
import shutil
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RunRequest(BaseModel):
    repo: str

# Global state for SSE streaming
listeners = []
pipeline_state = {
    "currentStep": 0,
    "isRunning": False,
    "metrics": {
        "files_scanned": 0,
        "functions_found": 0,
        "graph_nodes": 0,
        "graph_edges": 0,
        "security_vulns": 0,
        "unit_tests": 0,
        "integration_tests": 0,
        "bva_tests": 0,
        "security_tests": 0,
        "jira_tests_created": 0,
        "jira_project_url": ""
    },
    "logs": []
}

async def notify_listeners(event_type: str, data: dict):
    message = {"type": event_type, "data": data}
    for q in listeners:
        await q.put(message)

def parse_log_line(line: str):
    # This function analyzes the line and updates pipeline_state if needed
    line = line.strip()
    updated = False
    
    # New 6-step pipeline flow:
    # 1 = Sync Repository
    # 2 = Build Knowledge Graph
    # 3 = Delta Calculation
    # 4 = Strategy Injection
    # 5 = Generating Tests
    # 6 = Jira Integration
    # 7 = Complete
    
    if "=== Starting Delta Pipeline" in line or "Fetching latest commit SHA" in line:
        pipeline_state["currentStep"] = 1  # Sync Repository
        updated = True
    elif "=== Phase 1: Running Scanner Agent" in line:
        pipeline_state["currentStep"] = 2  # Build Knowledge Graph
        updated = True
    elif "Delta Mode: Comparing commits" in line:
        pipeline_state["currentStep"] = 3  # Delta Calculation
        updated = True
    elif "=== Phase 2: Running Tester Agent" in line:
        pipeline_state["currentStep"] = 4  # Strategy Injection
        
        # Scanner just finished, load kb.json for realtime scanner metrics
        try:
            repo_name = pipeline_state.get("repo_name")
            if repo_name:
                kb_path = f"output/{repo_name}/kb.json"
                if os.path.exists(kb_path):
                    with open(kb_path, "r") as f:
                        kb_data = json.load(f)
                        nodes = kb_data.get("nodes", [])
                        edges = kb_data.get("edges", [])
                        files = [n for n in nodes if n.get("type") == "FILE"]
                        functions = [n for n in nodes if n.get("type") == "FUNCTION"]
                        pipeline_state["metrics"]["files_scanned"] = len(files)
                        pipeline_state["metrics"]["functions_found"] = len(functions)
                        pipeline_state["metrics"]["graph_nodes"] = len(nodes)
                        pipeline_state["metrics"]["graph_edges"] = len(edges)
                        pipeline_state["metrics"]["security_vulns"] = kb_data.get("summary", {}).get("total_vulnerabilities", 0)
        except Exception as e:
            print(f"Error reading kb.json in realtime: {e}")
            
        updated = True
    elif "Generating tests with Gemini" in line:
        pipeline_state["currentStep"] = 5  # Generating Tests
        updated = True
    elif "[Jira] Created Test:" in line or "[Jira] Created Bug:" in line or "[Jira] Created Task:" in line:
        # Step 6: Jira Integration
        if pipeline_state["currentStep"] < 6:
            pipeline_state["currentStep"] = 6
        pipeline_state["metrics"]["jira_tests_created"] += 1
        
        # Extract the base URL to construct project URL if not already set
        if not pipeline_state["metrics"]["jira_project_url"]:
            import re
            match = re.search(r'(https?://[^/]+)/browse', line)
            if match:
                base_url = match.group(1)
                project_key = os.getenv("JIRA_PROJECT_KEY", "TCG")
                pipeline_state["metrics"]["jira_project_url"] = f"{base_url}/projects/{project_key}/issues"
        
        updated = True
    elif "[Jira Error]" in line or "[Jira Warning]" in line:
        if pipeline_state["currentStep"] < 6:
            pipeline_state["currentStep"] = 6
        updated = True
    elif "[SUCCESS] Pipeline Complete" in line:
        pipeline_state["currentStep"] = 7  # Complete (all 6 steps done)
        updated = True
    elif "-> Saved" in line:
        lower_line = line.lower()
        if "unit" in lower_line and "positive" in lower_line:
            pipeline_state["metrics"]["unit_tests"] += 1
            updated = True
        if "integration" in lower_line:
            pipeline_state["metrics"]["integration_tests"] += 1
            updated = True
        if "bva" in lower_line:
            pipeline_state["metrics"]["bva_tests"] += 1
            updated = True
        if "security" in lower_line:
            pipeline_state["metrics"]["security_tests"] += 1
            updated = True
        if "tests_master.csv" in lower_line:
             pass # ignore csv
    
    # We could also parse metrics here if the script outputted them, but the pipeline writes output to json/md which we could read at the end.
    
    return updated

async def run_pipeline_task(repo: str):
    pipeline_state["isRunning"] = True
    pipeline_state["currentStep"] = 1
    pipeline_state["logs"] = []
    pipeline_state["repo_name"] = repo.split('/')[-1]
    
    # Reset metrics
    for k in pipeline_state["metrics"]:
        pipeline_state["metrics"][k] = 0
        
    await notify_listeners("state_update", pipeline_state)
    
    # Run the pipeline script using the same python executable (venv)
    cmd = [sys.executable, "pipeline.py", "--repo", repo]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["PYTHONUNBUFFERED"] = "1"
    
    # Use asyncio.create_subprocess_exec to stream output asynchronously
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env
    )
    
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        
        decoded_line = line.decode('utf-8', errors='replace').rstrip()
        # Print to terminal
        print(decoded_line, flush=True)
        
        pipeline_state["logs"].append(decoded_line)
        
        # Parse for state changes
        if parse_log_line(decoded_line):
             await notify_listeners("state_update", pipeline_state)
        
        # Notify about the new log line
        await notify_listeners("log_update", {"line": decoded_line})
        
    await process.wait()
    pipeline_state["isRunning"] = False
    pipeline_state["currentStep"] = 6
    
    # Read output/repo_name/kb.json to update metrics here
    try:
        repo_name = repo.split('/')[-1]
        kb_path = f"output/{repo_name}/kb.json"
        if os.path.exists(kb_path):
            with open(kb_path, "r") as f:
                kb_data = json.load(f)
                nodes = kb_data.get("nodes", [])
                edges = kb_data.get("edges", [])
                files = [n for n in nodes if n.get("type") == "FILE"]
                functions = [n for n in nodes if n.get("type") == "FUNCTION"]
                pipeline_state["metrics"]["files_scanned"] = len(files)
                pipeline_state["metrics"]["functions_found"] = len(functions)
                pipeline_state["metrics"]["graph_nodes"] = len(nodes)
                pipeline_state["metrics"]["graph_edges"] = len(edges)
    except Exception as e:
        print(f"Error reading metrics: {e}")

    await notify_listeners("state_update", pipeline_state)

@app.post("/api/run")
async def run_pipeline(req: RunRequest, background_tasks: BackgroundTasks):
    if pipeline_state["isRunning"]:
        return {"status": "error", "message": "Pipeline is already running"}
    
    background_tasks.add_task(run_pipeline_task, req.repo)
    return {"status": "ok", "message": "Pipeline started"}

@app.get("/api/download-tests")
async def download_tests(repo: str):
    try:
        repo_name = repo.split('/')[-1]
        tests_dir = Path(f"output/{repo_name}/tests")
        
        if not tests_dir.exists():
            return {"status": "error", "message": "Tests folder not found."}
            
        # Create a zip archive of the tests directory
        archive_path = Path(f"output/{repo_name}_tests")
        shutil.make_archive(str(archive_path), 'zip', str(tests_dir))
        
        return FileResponse(
            path=f"{archive_path}.zip", 
            filename=f"{repo_name}_tests.zip",
            media_type="application/zip"
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/stream")
async def message_stream(request: Request):
    q = asyncio.Queue()
    listeners.append(q)
    
    # Send initial state immediately
    await q.put({"type": "state_update", "data": pipeline_state})
    
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                
                # Wait for next event
                message = await q.get()
                yield {
                    "event": message["type"],
                    "data": json.dumps(message["data"])
                }
        finally:
            listeners.remove(q)
            
    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
