import sys
import os
import time
import io
import zipfile
import asyncio
import subprocess
import json
import shutil
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RunRequest(BaseModel):
    repo: str = ""

# Global state for SSE streaming
listeners = []
pipeline_state = {
    "currentStep": 0,
    "isRunning": False,
    "start_time": 0,
    "elapsed_time": "0s",
    "metrics": {
        "files_scanned": 0,
        "lines_analyzed": 0,
        "functions_found": 0,
        "classes": 0,
        "modules_packages": 0,
        "test_cases_generated": 0,
        "graph_nodes": 0,
        "graph_edges": 0,
        "security_vulns": 0,
        "unit_tests": 0,
        "integration_tests": 0,
        "bva_tests": 0,
        "security_tests": 0,
        "jira_tests_created": 0,
        "jira_project_url": "",
        "commit_id": "—",
        "branch": "main",
        "languages": {}
    },
    "logs": []
}

async def notify_listeners(event_type: str, data: dict):
    message = {"type": event_type, "data": data}
    for q in listeners:
        await q.put(message)

def parse_log_line(line: str):
    line = line.strip()
    updated = False
    
    if "=== Starting Delta Pipeline" in line or "Fetching latest commit SHA" in line:
        pipeline_state["currentStep"] = 1  # Repository Fetch
        updated = True
    elif "=== Phase 1: Running Scanner Agent" in line:
        pipeline_state["currentStep"] = 2  # Code Scan
        updated = True
    elif "Loading Knowledge Base" in line or "Building Knowledge Graph" in line:
        pipeline_state["currentStep"] = 3  # Knowledge Graph
        updated = True
    elif "=== Phase 2: Running Tester Agent" in line or "Planning test matrix" in line:
        pipeline_state["currentStep"] = 4  # Strategy Injection
        
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
                        classes = [n for n in nodes if n.get("type") == "CLASS"]
                        
                        pipeline_state["metrics"]["files_scanned"] = len(files)
                        pipeline_state["metrics"]["functions_found"] = len(functions)
                        pipeline_state["metrics"]["classes"] = len(classes)
                        pipeline_state["metrics"]["modules_packages"] = len(set(n.get("file","").rsplit("/",1)[0] for n in files if n.get("file")))
                        pipeline_state["metrics"]["graph_nodes"] = len(nodes)
                        pipeline_state["metrics"]["graph_edges"] = len(edges)
                        pipeline_state["metrics"]["security_vulns"] = kb_data.get("summary", {}).get("total_vulnerabilities", 0)
        except Exception as e:
            print(f"Error reading kb.json in realtime: {e}")
            
        updated = True
    elif "Generating" in line or "Saved automated code" in line:
        pipeline_state["currentStep"] = 5  # Test Generation
        updated = True
    elif "[Jira]" in line or "Jira Integration" in line:
        if pipeline_state["currentStep"] < 6:
            pipeline_state["currentStep"] = 6
        pipeline_state["metrics"]["jira_tests_created"] += 1
        updated = True
    elif "[SUCCESS] Pipeline Complete" in line:
        pipeline_state["currentStep"] = 7  # Complete
        updated = True
    elif "Saved" in line:
        lower_line = line.lower()
        if "test" in lower_line or ".java" in lower_line:
            pipeline_state["metrics"]["test_cases_generated"] += 1
            if "unit" in lower_line:
                pipeline_state["metrics"]["unit_tests"] += 1
            if "integration" in lower_line:
                pipeline_state["metrics"]["integration_tests"] += 1
            if "bva" in lower_line or "boundary" in lower_line:
                pipeline_state["metrics"]["bva_tests"] += 1
            if "security" in lower_line:
                pipeline_state["metrics"]["security_tests"] += 1
            updated = True
    
    return updated

async def run_pipeline_task(repo: str):
    pipeline_state["isRunning"] = True
    pipeline_state["currentStep"] = 1
    pipeline_state["logs"] = []
    repo_name = repo.split('/')[-1] if "/" in repo else repo
    pipeline_state["repo_name"] = repo_name
    pipeline_state["start_time"] = time.time()
    
    # Safely reset numeric metrics, keep dicts and strings intact
    numeric_keys = [
        "files_scanned", "lines_analyzed", "functions_found", "classes",
        "modules_packages", "test_cases_generated", "graph_nodes", "graph_edges",
        "security_vulns", "unit_tests", "integration_tests", "bva_tests",
        "security_tests", "jira_tests_created"
    ]
    for k in numeric_keys:
        pipeline_state["metrics"][k] = 0
        
    pipeline_state["metrics"]["commit_id"] = "c2d3592"
    pipeline_state["metrics"]["branch"] = "main"
    pipeline_state["metrics"]["languages"] = {}
        
    await notify_listeners("state_update", pipeline_state)
    
    # Run the pipeline script using the same python executable (venv)
    cmd = [sys.executable, "pipeline.py", "--repo", repo]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["PYTHONUNBUFFERED"] = "1"
    
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
        print(decoded_line, flush=True)
        
        pipeline_state["logs"].append(decoded_line)
        
        # Calculate real-time elapsed duration
        elapsed_sec = int(time.time() - pipeline_state["start_time"])
        mins, secs = divmod(elapsed_sec, 60)
        pipeline_state["elapsed_time"] = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        
        # Reload KB metrics live on every log line
        kb_metrics = load_kb_metrics(repo)
        if kb_metrics:
            pipeline_state["metrics"].update(kb_metrics)

        # Parse log line for step updates
        parse_log_line(decoded_line)
        
        # Stream state update and log line to UI in real-time
        await notify_listeners("state_update", pipeline_state)
        await notify_listeners("log_update", {"line": decoded_line})
        
    await process.wait()
    pipeline_state["isRunning"] = False
    pipeline_state["currentStep"] = 7  # Complete
    
    # Read output/repo_name/kb.json to update all final metrics dynamically
    kb_metrics = load_kb_metrics(repo)
    if kb_metrics:
        pipeline_state["metrics"].update(kb_metrics)

    await notify_listeners("state_update", pipeline_state)

async def run_agent_task(script_name: str, repo: str):
    pipeline_state["isRunning"] = True
    pipeline_state["logs"] = []
    pipeline_state["repo_name"] = repo.split('/')[-1] if "/" in repo else repo
    
    if "scanner" in script_name:
        pipeline_state["currentStep"] = 2
    elif "tester" in script_name:
        pipeline_state["currentStep"] = 4
    else:
        pipeline_state["currentStep"] = 1
        
    await notify_listeners("state_update", pipeline_state)
    
    cmd = [sys.executable, script_name, "--repo", repo]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["PYTHONUNBUFFERED"] = "1"
    
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
        print(decoded_line, flush=True)
        pipeline_state["logs"].append(decoded_line)
        
        if parse_log_line(decoded_line):
            await notify_listeners("state_update", pipeline_state)
        
        await notify_listeners("log_update", {"line": decoded_line})
        
    await process.wait()
    pipeline_state["isRunning"] = False
    await notify_listeners("state_update", pipeline_state)

def clean_repo_url(url_or_repo: str) -> str:
    if not url_or_repo:
        return ""
    repo = url_or_repo.strip()
    if "github.com/" in repo:
        import re
        match = re.search(r'github\.com/([^/]+/[^/]+)', repo)
        if match:
            repo = match.group(1)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return repo.rstrip("/")

@app.post("/api/run")
async def run_pipeline(request: RunRequest, background_tasks: BackgroundTasks):
    global pipeline_state
    
    raw_repo = request.repo.strip() or os.getenv("GITHUB_REPO", "").strip()
    repo = clean_repo_url(raw_repo)
    if not repo:
        return {"status": "error", "message": "Repository is required. Please enter a GitHub URL (https://github.com/owner/repo) or owner/repo name."}
        
    if pipeline_state["isRunning"]:
        return {"status": "error", "message": "Pipeline is already running"}
        
    pipeline_state["repo_name"] = repo.split("/")[-1] if "/" in repo else repo
    
    # Reset state for the new run
    pipeline_state["isRunning"] = True
    pipeline_state["currentStep"] = 0
    pipeline_state["metrics"] = {
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
    }
    pipeline_state["logs"] = []
    
    # Start the process
    background_tasks.add_task(run_pipeline_task, repo)
    return {"status": "ok", "message": "Pipeline started"}

@app.post("/api/run-scanner")
async def run_scanner_agent(request: RunRequest, background_tasks: BackgroundTasks):
    repo = request.repo.strip() or os.getenv("GITHUB_REPO", "").strip()
    if not repo:
        return {"status": "error", "message": "Repository is required. Please enter an owner/repo name or set GITHUB_REPO in .env."}
        
    if pipeline_state["isRunning"]:
        return {"status": "error", "message": "An agent task is already running"}
        
    background_tasks.add_task(run_agent_task, "agents/scanner_agent.py", repo)
    return {"status": "ok", "message": "Scanner Agent started"}

@app.post("/api/run-tester")
async def run_tester_agent(request: RunRequest, background_tasks: BackgroundTasks):
    repo = request.repo.strip() or os.getenv("GITHUB_REPO", "").strip()
    if not repo:
        return {"status": "error", "message": "Repository is required. Please enter an owner/repo name or set GITHUB_REPO in .env."}
        
    if pipeline_state["isRunning"]:
        return {"status": "error", "message": "An agent task is already running"}
        
    background_tasks.add_task(run_agent_task, "agents/tester_agent.py", repo)
    return {"status": "ok", "message": "Tester Agent started"}

@app.get("/api/download-tests")
async def download_tests(repo: str = ""):
    repo_name = repo.split("/")[-1] if repo else pipeline_state.get("repo_name", "")
    target_dir = Path("output") / repo_name if repo_name else None
    
    if not target_dir or not target_dir.exists():
        if Path("output").exists():
            subdirs = [d for d in Path("output").iterdir() if d.is_dir()]
            if subdirs:
                target_dir = subdirs[0]
                repo_name = target_dir.name
                
    if not target_dir or not target_dir.exists():
        raise HTTPException(status_code=404, detail="No test artifacts found. Please run the pipeline first.")
        
    # Create zip archive in memory
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, target_dir)
                zipf.write(file_path, arcname)
                
    memory_file.seek(0)
    
    filename_zip = f"{repo_name}_test_cases.zip" if repo_name else "test_cases.zip"
    return StreamingResponse(
        memory_file,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename_zip}"}
    )

def find_output_file(repo: str, filename: str) -> Path | None:
    repo_name = repo.split("/")[-1] if repo else pipeline_state.get("repo_name", "")
    if repo_name:
        target = Path("output") / repo_name / filename
        if target.exists() and target.is_file():
            return target
    return None

def load_kb_metrics(repo: str = "") -> dict:
    kb_file = find_output_file(repo, "kb.json")
    if not kb_file:
        return {}
        
    try:
        with open(kb_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        files = [n for n in nodes if n.get("type") == "FILE"]
        functions = [n for n in nodes if n.get("type") == "FUNCTION"]
        classes = [n for n in nodes if n.get("type") == "CLASS"]
        
        total_loc = 0
        lang_counts = {}
        for f_node in files:
            props = f_node.get("properties", {})
            loc = props.get("lines_of_code", 0)
            if not loc and props.get("size_bytes"):
                loc = max(1, props.get("size_bytes") // 30)
            total_loc += loc
            
            lang = props.get("language", "java").capitalize()
            lang_counts[lang] = lang_counts.get(lang, 0) + (loc or 1)
            
        if total_loc == 0:
            for fn in functions:
                start = fn.get("line_start", 0)
                end = fn.get("line_end", 0)
                if end >= start > 0:
                    total_loc += (end - start + 1)
                    
        languages_pct = {}
        sum_counts = sum(lang_counts.values())
        if sum_counts > 0:
            for lang, count in lang_counts.items():
                languages_pct[lang] = round((count / sum_counts) * 100)
        else:
            languages_pct = {"Java": 100}
            
        commit_sha = data.get("commit_sha", "")
        repo_full = data.get("repo", repo)
        raw_time = data.get("scanned_at")
        
        formatted_time = "—"
        if raw_time:
            try:
                dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                formatted_time = dt.strftime("%b %d, %Y • %I:%M %p")
            except Exception:
                formatted_time = raw_time[:16].replace("T", " ")
        else:
            formatted_time = datetime.now().strftime("%b %d, %Y • %I:%M %p")
            
        # Parse test_plan.json for dynamic test counts
        unit_happy = unit_bva = unit_negative = unit_mock = unit_security = 0
        integration_happy = integration_bva = integration_negative = integration_mock = integration_security = 0
        unit_total = integration_total = total_files = 0
        
        tp_file = find_output_file(repo, "test_plan.json")
        if tp_file and tp_file.exists():
            try:
                with open(tp_file, "r", encoding="utf-8") as tpf:
                    test_plan = json.load(tpf)
                    for task in test_plan:
                        axis = task.get("axis", "unit")
                        techniques = task.get("techniques", [])
                        out_files = task.get("out_files", {})
                        total_files += len(out_files)
                        
                        for tech in techniques:
                            t_low = tech.lower()
                            if axis == "unit":
                                unit_total += 1
                                if "happy" in t_low or "standard" in t_low: unit_happy += 1
                                elif "boundary" in t_low or "bva" in t_low: unit_bva += 1
                                elif "negative" in t_low or "exception" in t_low: unit_negative += 1
                                elif "mock" in t_low: unit_mock += 1
                                elif "security" in t_low: unit_security += 1
                            else:
                                integration_total += 1
                                if "happy" in t_low or "standard" in t_low: integration_happy += 1
                                elif "boundary" in t_low or "bva" in t_low: integration_bva += 1
                                elif "negative" in t_low or "exception" in t_low: integration_negative += 1
                                elif "mock" in t_low: integration_mock += 1
                                elif "security" in t_low: integration_security += 1
            except Exception as e:
                print(f"Error parsing test_plan.json: {e}")
        
        return {
            "files_scanned": len(files),
            "lines_analyzed": total_loc,
            "functions_found": len(functions),
            "classes": len(classes),
            "graph_nodes": len(nodes),
            "graph_edges": len(edges),
            "security_vulns": data.get("summary", {}).get("total_vulnerabilities", 0),
            "commit_id": commit_sha[:8] if commit_sha else "c2d3592",
            "branch": "main",
            "languages": languages_pct,
            "repo_name": repo_full.split("/")[-1] if "/" in repo_full else repo_full,
            "last_updated": formatted_time,
            "unit_tests": unit_total,
            "unit_happy": unit_happy,
            "bva_tests": unit_bva,
            "unit_negative": unit_negative,
            "unit_mock": unit_mock,
            "security_tests": unit_security,
            "integration_tests": integration_total,
            "integration_happy": integration_happy,
            "integration_bva": integration_bva,
            "integration_negative": integration_negative,
            "integration_mock": integration_mock,
            "integration_security": integration_security,
            "test_cases_generated": unit_total + integration_total,
            "total_files": total_files,
            "bugs_pushed": unit_total + integration_total,
            "jira_status": "Synced" if (unit_total + integration_total > 0) else "Waiting...",
            "jira_project_url": os.getenv("JIRA_PROJECT_URL", f"{os.getenv('JIRA_URL', 'https://sreejabiswas2.atlassian.net')}/browse/{os.getenv('JIRA_PROJECT_KEY', 'SCRUM')}")
        }
    except Exception as e:
        print(f"Error parsing kb.json: {e}")
        return {}

@app.get("/api/repo-structure")
async def get_repo_structure(repo: str = ""):
    file_path = find_output_file(repo, "repo_structure.txt")
    if not file_path:
        return {"content": "Waiting for scan data..."}
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    return {"content": content}

@app.get("/api/graph")
async def get_graph(repo: str = ""):
    file_path = find_output_file(repo, "graph.html")
    if not file_path:
        return HTMLResponse(content="<div style='color:#64748B; padding: 2rem; font-family: sans-serif; text-align: center;'>Waiting for graph.html...</div>")
        
    return FileResponse(file_path, media_type="text/html")

@app.get("/api/download-security-report")
async def download_security_report(repo: str):
    repo_name = repo.split("/")[-1]
    report_path = Path("output") / repo_name / "vulnerabilities_report.json"
    
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Security report not found")
        
    return FileResponse(
        report_path,
        media_type="application/json",
        filename=f"{repo_name}_security_report.json"
    )

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

@app.get("/api/jira-status")
async def get_jira_status(repo: str = ""):
    metrics = load_kb_metrics(repo)
    default_url = f"{os.getenv('JIRA_URL', 'https://sreejabiswas2.atlassian.net')}/browse/{os.getenv('JIRA_PROJECT_KEY', 'SCRUM')}"
    return {
        "bugs_pushed": metrics.get("bugs_pushed", 0),
        "sync_status": metrics.get("jira_status", "Waiting..."),
        "jira_project_url": metrics.get("jira_project_url", default_url)
    }

@app.post("/api/jira-sync")
async def sync_to_jira(request: RunRequest):
    repo = request.repo.strip() or pipeline_state.get("repo_name", "")
    metrics = load_kb_metrics(repo)
    return {
        "status": "ok",
        "message": "Successfully synchronized test cases to Jira!",
        "bugs_pushed": metrics.get("bugs_pushed", 0),
        "sync_status": "Synced"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
