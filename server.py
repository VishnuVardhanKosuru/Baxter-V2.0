"""
server.py
─────────
FastAPI Backend — Baxter Test Case Generator.

Exposes two groups of endpoints:

 ── LEGACY (single FRD, sequential) ───────────────────────────────────────────
   POST /api/stage1-parse       → parse one FRD + TC pair, return JSON
   POST /api/stage2-generate    → generate artifacts from latest parsed JSON
   GET  /api/download-zip       → download all generated tests as ZIP

 ── BATCH (multi-FRD, parallel, SSE) ──────────────────────────────────────────
   POST /api/batch/submit               → upload N FRD+TC pairs, returns job_id
   GET  /api/batch/{job_id}/stream      → SSE live progress stream
   GET  /api/batch/{job_id}/status      → snapshot of job state (JSON)
   GET  /api/batch/{job_id}/download    → ZIP entire job output (all FRDs)
   GET  /api/batch/{job_id}/download/{frd_id}  → ZIP single FRD output
"""

import asyncio
import json
import os
import re
import sys
import traceback
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from sse_starlette.sse import EventSourceResponse

load_dotenv()

from core.logger import logger

# ─── PATHS ────────────────────────────────────────────────────────────────────

BASE_DIR          = Path(__file__).parent.resolve()
UPLOADS_DIR       = BASE_DIR / "uploads"
INPUT_MODULES_DIR = BASE_DIR / "input_modules"
from core.constants import (
    DIR_OUTPUT  as OUTPUT_DIR,
    DIR_JOBS    as JOBS_DIR,
    DIR_KNOWLEDGE,
    ALLOWED_ORIGINS,
)
TESTS_DIR  = OUTPUT_DIR / "tests"
AGENTS_DIR = BASE_DIR / "agents"

# ─── SERVER CONFIG ────────────────────────────────────────────────────────────

from core.constants import SERVER_HOST, SERVER_PORT

SAMPLE_FRD_FILENAME: str = os.environ.get("SAMPLE_FRD", "ShopSphere_Functional_Requirements_Document.docx")
SAMPLE_TC_FILENAME:  str = os.environ.get("SAMPLE_TC",  "ShopSphere_Manual_Testcases.docx")

for _d in (UPLOADS_DIR, OUTPUT_DIR, DIR_KNOWLEDGE, INPUT_MODULES_DIR, TESTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# agents/ needs to be on sys.path so its internal imports work
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from doc_parser import parse_documents    # importable API function
from core.cs_agent import run_agent            # importable API function

# ─── BATCH MANAGER ────────────────────────────────────────────────────────────
# Imported here once — batch_manager is a singleton that survives all requests.

from core.batch_manager import batch_manager, JobStatus

# ─── SSE helper ───────────────────────────────────────────────────────────────
# sse-starlette is used for the live progress stream endpoint.
# Imported at the top of the file (hard dependency in requirements.txt).

# ─── APP ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Baxter Parser & Code Generator API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── HEALTH ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Baxter Parser & Code Generator API", "version": "3.0.0"}


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY ENDPOINTS (unchanged — single FRD sequential pipeline)
# ══════════════════════════════════════════════════════════════════════════════


def _inject_ui_gemini_key(ui_keys: str | None) -> None:
    """
    Merge multiple UI-provided Gemini API keys (comma-separated) with the keys already in .env.
    - If a key already exists in .env → skip it (no duplicate).
    - If a key is new → add it as the next available GEMINI_API_KEY_N slot
      so the LiteLLM Router can use it as an additional deployment.
    Also resets the cached LLM mapper chain so it picks up fresh keys.
    """
    if not ui_keys or ui_keys == "your_gemini_api_key_here":
        return

    from core.llm_factory import _collect_keys
    existing_keys = _collect_keys("GEMINI_API_KEY")

    for k in ui_keys.split(","):
        k = k.strip()
        if len(k) < 10 or k in existing_keys:
            continue

        # Find the next free slot
        for i in range(1, 20):
            suffix = "" if i == 1 else f"_{i}"
            env_var = f"GEMINI_API_KEY{suffix}"
            if not os.getenv(env_var):
                os.environ[env_var] = k
                existing_keys.append(k)
                logger.info("UI Gemini API key added as %s (new deployment)", env_var)
                break

    # Reset cached LLM chains so they pick up the new key set
    import agents.doc_parser as _dp
    _dp._mapper_chain = None


@app.post("/api/stage1-parse")
async def stage1_parse(
    request:            Request,
    frd_file:           Optional[UploadFile] = File(None),
    tc_file:            Optional[UploadFile] = File(None),
    use_sample:         bool = Form(False),
    use_input_modules:  bool = Form(False),
):
    """
    Stage 1: Parse FRD + TC .docx files into structured JSON.
    Supports file uploads, sample files, or input_modules directory.
    parse_documents() returns a List[str] of knowledge JSON paths (one per module).
    """
    _inject_ui_gemini_key(request.headers.get("x-gemini-key"))

    logger.info("=" * 60)
    logger.info("[STAGE 1] INGESTION & DOCUMENT PARSING AGENT STARTED")
    logger.info("=" * 60)
    import litellm as _litellm
    _litellm.current_phase = "Parser"
    try:
        if use_input_modules or (INPUT_MODULES_DIR.exists() and any(INPUT_MODULES_DIR.rglob("*.docx")) and not frd_file and not tc_file and not use_sample):
            logger.info("[STAGE 1] Parsing all modules from directory: %s", INPUT_MODULES_DIR)
            json_paths = await asyncio.to_thread(
                parse_documents, str(INPUT_MODULES_DIR), str(OUTPUT_DIR)
            )
        elif use_sample or (not frd_file and not tc_file):
            sample_frd = BASE_DIR / "samples" / SAMPLE_FRD_FILENAME
            sample_tc  = BASE_DIR / "samples" / SAMPLE_TC_FILENAME
            logger.info("[STAGE 1] Using sample documents: %s & %s", sample_frd.name, sample_tc.name)
            if not sample_frd.exists() or not sample_tc.exists():
                raise HTTPException(400, "Sample documents not found in workspace.")
            json_paths = await asyncio.to_thread(
                parse_documents, str(sample_frd), str(sample_tc), str(OUTPUT_DIR)
            )
        else:
            if not frd_file or not tc_file:
                raise HTTPException(400, "Both FRD (.docx) and Test Cases (.docx) files are required.")
            frd_path = str(UPLOADS_DIR / frd_file.filename)
            tc_path  = str(UPLOADS_DIR / tc_file.filename)
            logger.info("[STAGE 1] Parsing uploaded files: %s & %s", frd_file.filename, tc_file.filename)
            with open(frd_path, "wb") as f:
                f.write(await frd_file.read())
            with open(tc_path, "wb") as f:
                f.write(await tc_file.read())
            json_paths = await asyncio.to_thread(
                parse_documents, frd_path, tc_path, str(OUTPUT_DIR)
            )

        # json_paths is now a List[str] — one path per module
        if not json_paths:
            # Fallback: pick up any knowledge files already on disk
            k_files = sorted((OUTPUT_DIR / "knowledge").glob("*.json"), key=os.path.getmtime, reverse=True)
            if k_files:
                json_paths = [str(p) for p in k_files]
            else:
                raise ValueError("No output JSON was generated during parsing.")

        # Aggregate data across all parsed modules
        all_test_cases = []
        modules_data = []
        for jp in json_paths:
            try:
                with open(jp, "r", encoding="utf-8") as jf:
                    pd = json.load(jf)
                all_test_cases.extend(pd.get("test_cases", []))
                modules_data.append(pd)
            except Exception:
                pass

        # Use first module data as primary result; UI only needs one payload
        primary_data = modules_data[0] if modules_data else {}
        primary_data["test_cases"] = all_test_cases  # merged across all modules

        logger.info("[STAGE 1] SUCCESS -> %d module(s) parsed, %d total test cases", len(json_paths), len(all_test_cases))
        logger.info("=" * 60)

        return JSONResponse({
            "success": True,
            "result": {
                "success":      True,
                "output_file":  str(Path(json_paths[0]).relative_to(BASE_DIR)),
                "modules":      [str(Path(p).relative_to(BASE_DIR)) for p in json_paths],
                "module_count": len(json_paths),
                "data":         primary_data,
            }
        })
    except Exception as exc:
        logger.error("[STAGE 1 ERROR] %s", exc, exc_info=True)
        return JSONResponse({"success": False, "detail": str(exc)}, status_code=500)


@app.post("/api/stage2-generate")
async def stage2_generate(request: Request):
    """
    Stage 2: Generate Cucumber + Selenium test code from all parsed knowledge JSONs.
    Each module gets its own sub-directory under output/tests/<module_slug>/
    containing expected.csv, cucumber/, and selenium/.
    """
    _inject_ui_gemini_key(request.headers.get("x-gemini-key"))

    logger.info("=" * 60)
    logger.info("[STAGE 2] TEST CODE GENERATOR AGENT STARTED")
    logger.info("=" * 60)
    import litellm as _litellm
    _litellm.current_phase = "Generator"

    # Collect all knowledge JSONs (per-module files from Stage 1)
    knowledge_dir = OUTPUT_DIR / "knowledge"
    json_files = sorted(
        list(knowledge_dir.glob("*.json")),
        key=os.path.getmtime
    )
    if not json_files:
        # Fallback: check root output dir for any json
        json_files = sorted(
            list(OUTPUT_DIR.glob("*.json")),
            key=os.path.getmtime,
            reverse=True
        )
    if not json_files:
        raise HTTPException(400, "No parsed JSON found. Run Stage 1 first.")

    logger.info("[STAGE 2] Processing %d module knowledge file(s)...", len(json_files))

    total_tc = 0
    total_cucumber = 0
    total_selenium = 0
    all_feature_ids: set = set()
    modules_summary = []
    primary_data = {}

    try:
        for knowledge_json in json_files:
            # Derive per-module output directory: output/tests/<module_slug>/
            module_slug = knowledge_json.stem.replace("_knowledge", "")
            module_out_dir = TESTS_DIR / module_slug
            module_out_dir.mkdir(parents=True, exist_ok=True)

            logger.info("[STAGE 2] Module: %s -> %s", module_slug, module_out_dir)

            await asyncio.to_thread(
                run_agent,
                stage1_json_path=str(knowledge_json),
                out_dir_path=str(module_out_dir)
            )

            # Read module stats
            try:
                with open(knowledge_json, "r", encoding="utf-8") as jf:
                    parsed_data = json.load(jf)
                if not primary_data:
                    primary_data = parsed_data
            except Exception:
                parsed_data = {}

            module_tcs = parsed_data.get("test_cases", [])
            module_tc_count = len(module_tcs)
            module_feature_ids = {tc.get("feature_ref") for tc in module_tcs if tc.get("feature_ref")}

            cuc_dir = module_out_dir / "cucumber"
            sel_dir = module_out_dir / "selenium"
            cuc_count = len(list(cuc_dir.glob("*.feature"))) if cuc_dir.exists() else module_tc_count
            sel_count = len(list(sel_dir.glob("*.py")))      if sel_dir.exists() else module_tc_count

            total_tc      += module_tc_count
            total_cucumber += cuc_count
            total_selenium += sel_count
            all_feature_ids.update(module_feature_ids)

            modules_summary.append({
                "module":          module_slug,
                "test_cases":      module_tc_count,
                "cucumber_files":  cuc_count,
                "selenium_files":  sel_count,
                "output_dir":      str(module_out_dir.relative_to(BASE_DIR)),
            })

        logger.info(
            "[STAGE 2] SUCCESS -> %d module(s), %d total TCs (%d Cucumber, %d Selenium)",
            len(json_files), total_tc, total_cucumber, total_selenium
        )
        logger.info("=" * 60)

        return JSONResponse({
            "success": True,
            "result": {
                "success":    True,
                "tests_dir":  str(TESTS_DIR.relative_to(BASE_DIR)),
                "modules":    modules_summary,
                "summary": {
                    "total_modules":    len(json_files),
                    "total_test_cases": total_tc,
                    "total_features":   len(all_feature_ids),
                    "selenium_count":   total_selenium,
                    "cucumber_count":   total_cucumber,
                    "project":          primary_data.get("project", ""),
                    "version":          primary_data.get("version", "1.0"),
                },
                "data": primary_data,
            }
        })
    except Exception as exc:
        logger.error("[STAGE 2 ERROR] %s", exc, exc_info=True)
        return JSONResponse({"success": False, "detail": str(exc)}, status_code=500)


@app.get("/api/download-zip")
def download_zip():
    """
    Stream all generated test files as a ZIP archive.
    Archive structure mirrors per-module output:
      <module_slug>/expected.csv
      <module_slug>/cucumber/TC-001.feature
      <module_slug>/selenium/test_TC-001.py
    """
    if not TESTS_DIR.exists() or not any(TESTS_DIR.rglob("*")):
        raise HTTPException(404, "No generated test files available.")

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in TESTS_DIR.rglob("*"):
            if fp.is_file():
                # Preserve full relative path so per-module structure is in the ZIP
                zf.write(fp, arcname=str(fp.relative_to(TESTS_DIR)))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=baxter_generated_tests.zip"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# BATCH ENDPOINTS — Multi-FRD parallel pipeline with SSE progress streaming
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/batch/submit")
async def batch_submit(
    frd_files: List[UploadFile] = File(...),
    tc_files:  List[UploadFile] = File(...),
):
    """
    Upload N FRD + TC .docx pairs for batch processing.

    Request (multipart/form-data):
      frd_files: [FRD-1.docx, FRD-2.docx, ...]   (N files)
      tc_files:  [TC-1.docx, TC-2.docx, ...]      (N files, matched by index)

    Response:
      {"job_id": "a1b2c3d4"}   — returned immediately
      Processing runs in background; poll /stream for live progress.

    Validation:
      - Number of FRD files must match number of TC files.
      - Each pair is parsed (Stage 1) synchronously before the job starts.
        This is fast (seconds per FRD), so it happens in the request lifecycle.
    """
    if len(frd_files) != len(tc_files):
        raise HTTPException(
            400,
            f"Mismatch: {len(frd_files)} FRD file(s) vs {len(tc_files)} TC file(s). "
            "Each FRD must have a corresponding TC file."
        )
    if not frd_files:
        raise HTTPException(400, "At least one FRD + TC file pair is required.")

    # ── Save uploaded files ───────────────────────────────────────────────────
    frd_paths, tc_paths = [], []
    for frd_file, tc_file in zip(frd_files, tc_files):
        frd_save = UPLOADS_DIR / frd_file.filename
        tc_save  = UPLOADS_DIR / tc_file.filename
        with open(frd_save, "wb") as f:
            f.write(await frd_file.read())
        with open(tc_save, "wb") as f:
            f.write(await tc_file.read())
        frd_paths.append(str(frd_save))
        tc_paths.append(str(tc_save))

    # ── Create job & allocate output directory ────────────────────────────────
    job_id  = batch_manager.create_job()
    job     = batch_manager.get_job(job_id)
    job_dir = job.output_root

    # ── Parse each FRD+TC pair (Stage 1) ─────────────────────────────────────
    # parse_documents() is CPU-bound; run each in a thread to avoid blocking.
    import litellm as _litellm
    _litellm.current_phase = "Parser"
    frd_inputs = []
    for idx, (frd_p, tc_p) in enumerate(zip(frd_paths, tc_paths), start=1):
        frd_id   = f"FRD-{idx:03d}"
        frd_stem = Path(frd_p).stem
        frd_name = (
            frd_stem.replace("_", " ")
                    .split("Functional")[0]
                    .strip()
                    .replace(" ", "_")
            or frd_stem
        )[:40]   # cap directory name length

        # Per-FRD parse output directory (Stage 1 JSON stored inside job dir)
        parse_out_dir = str(job_dir / f"{frd_id}_parse")
        Path(parse_out_dir).mkdir(parents=True, exist_ok=True)

        try:
            # parse_documents() returns List[str]; single-pair mode -> one element
            json_paths_list = await asyncio.to_thread(
                parse_documents, frd_p, tc_p, parse_out_dir
            )
            if not json_paths_list:
                raise ValueError("parse_documents returned no output paths")
            json_path = json_paths_list[0]
            with open(json_path, "r", encoding="utf-8") as jf:
                parsed = json.load(jf)
        except Exception as exc:
            # Clean up job and return error
            return JSONResponse(
                {"success": False, "detail": f"Failed to parse FRD-{idx} ({frd_p}): {exc}"},
                status_code=500,
            )

        frd_inputs.append({
            "frd_id":     frd_id,
            "frd_name":   frd_name,
            "test_cases": parsed.get("test_cases", []),
        })

    # ── Fire background task — returns job_id immediately ────────────────────
    asyncio.create_task(batch_manager.run_batch(job_id, frd_inputs))

    return JSONResponse({
        "success": True,
        "job_id":  job_id,
        "frd_count": len(frd_inputs),
        "total_test_cases": sum(len(f["test_cases"]) for f in frd_inputs),
        "stream_url": f"/api/batch/{job_id}/stream",
    })


@app.get("/api/batch/{job_id}/stream")
async def batch_stream(job_id: str):
    """
    SSE endpoint — browser connects once and receives live progress events.

    Event format (sent every ~1 second while job is running):
    data: {
      "job_id":  "a1b2c3d4",
      "status":  "running",
      "frds": [
        {"frd_id": "FRD-001", "frd_name": "UserAuth",
         "status": "running", "completed": 1500, "total": 3000, "percent": 50.0},
        {"frd_id": "FRD-002", "frd_name": "Payment",
         "status": "queued",  "completed": 0,    "total": 500,  "percent": 0.0}
      ]
    }

    Final event when all done:
    data: {"event": "batch_complete", "job_id": "a1b2c3d4", "status": "done"}

    The connection is closed automatically after the final event.
    """

    job = batch_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found.")

    async def event_generator():
        try:
            while True:
                job = batch_manager.get_job(job_id)
                if not job:
                    break

                payload = {
                    "job_id": job_id,
                    "status": job.status.value,
                    "frds": [p.to_dict() for p in job.frds.values()],
                }
                yield {"data": json.dumps(payload)}

                # Job is finished — send final event and stop streaming
                if job.status in (JobStatus.DONE, JobStatus.FAILED):
                    yield {
                        "event": "batch_complete",
                        "data":  json.dumps({
                            "event":  "batch_complete",
                            "job_id": job_id,
                            "status": job.status.value,
                        }),
                    }
                    break

                await asyncio.sleep(1)   # poll interval

        except asyncio.CancelledError:
            pass   # client disconnected — clean exit

    return EventSourceResponse(event_generator())


@app.get("/api/batch/{job_id}/status")
def batch_status(job_id: str):
    """
    Returns a JSON snapshot of the current job state.
    Useful for polling or initial page load (before SSE connects).
    """
    job = batch_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found.")

    return JSONResponse({
        "job_id": job_id,
        "status": job.status.value,
        "frds":   [p.to_dict() for p in job.frds.values()],
    })


@app.get("/api/batch/{job_id}/download")
def batch_download_all(job_id: str):
    """
    Download a ZIP archive containing all FRD outputs for the given job.

    Archive structure:
      FRD-001_UserAuth/
        expected.csv
        cucumber/TC-001.feature
        selenium/test_TC-001.py
      FRD-002_Payment/
        ...
    """
    job = batch_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found.")

    job_dir = job.output_root or (JOBS_DIR / job_id)
    if not job_dir.exists() or not any(job_dir.rglob("*")):
        raise HTTPException(404, "No output files found for this job yet.")

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in job_dir.rglob("*"):
            # Skip intermediate parse dirs and checkpoint files in archive
            if fp.is_file() and "_parse" not in str(fp.relative_to(job_dir)):
                zf.write(fp, arcname=str(fp.relative_to(job_dir)))
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=job_{job_id}_all_frds.zip"
        },
    )


@app.get("/api/batch/{job_id}/download/{frd_id}")
def batch_download_frd(job_id: str, frd_id: str):
    """
    Download a ZIP archive containing the output for a single FRD.

    Archive structure:
      expected.csv
      cucumber/TC-001.feature
      selenium/test_TC-001.py
      checkpoint.json   (excluded from archive)
    """
    job = batch_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found.")

    # Locate the FRD output directory (name format: FRD-001_FrdName)
    job_dir = job.output_root or (JOBS_DIR / job_id)
    frd_dir = next(
        (d for d in job_dir.iterdir() if d.is_dir() and d.name.startswith(frd_id)),
        None,
    )

    if not frd_dir or not any(frd_dir.rglob("*")):
        raise HTTPException(
            404,
            f"No output files found for FRD '{frd_id}' in job '{job_id}'."
        )

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in frd_dir.rglob("*"):
            if fp.is_file() and fp.name != "checkpoint.json":
                zf.write(fp, arcname=str(fp.relative_to(frd_dir)))
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={frd_id}_tests.zip"
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# JIRA INGESTION & ATTACHMENT EVALUATION ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

from agents.jira_agent import JiraClient, LLMAnalyzer, sanitize_filename

class JiraEpicRequest(BaseModel):
    issue_key: str
    selected_frd_ids: Optional[List[str]] = []

@app.get("/api/jira/epics")
async def get_all_epics(request: Request, max_results: int = 100):
    """
    Fetches all Epics from the connected Jira instance across all accessible projects.
    Returns a list of {key, summary} objects for populating a dropdown in the UI.
    """
    try:
        jira_url   = request.headers.get("x-jira-url")   or os.getenv("JIRA_URL")
        jira_email = request.headers.get("x-jira-email") or os.getenv("JIRA_EMAIL")
        jira_token = request.headers.get("x-jira-token") or os.getenv("JIRA_API_TOKEN")

        if not jira_url or not jira_email or not jira_token:
            raise HTTPException(400, "Jira credentials (URL, email, token) are required.")

        client = JiraClient(jira_url=jira_url, email=jira_email, api_token=jira_token)

        # Directly search for all Epics the user can see, ordered by most recently updated
        # We bypass client.search_issues() because that method drops issues without attachments
        url = f"{client.jira_url}/rest/api/3/search/jql"
        payload = {
            "jql": "issuetype = Epic ORDER BY updated DESC",
            "maxResults": max_results,
            "fields": ["summary"]
        }
        resp = client.session.post(url, json=payload)
        resp.raise_for_status()
        
        issues = resp.json().get("issues", [])

        epics = [
            {
                "key":     issue.get("key", ""),
                "summary": (
                    issue.get("fields", {}).get("summary")
                    or issue.get("summary")
                    or issue.get("key", "")
                ),
            }
            for issue in issues
            if issue.get("key")
        ]

        logger.info("[JIRA] Fetched %d epics from %s", len(epics), jira_url)
        
        # Save epics to a local text file
        try:
            epics_file = OUTPUT_DIR / "available_epics.txt"
            with open(epics_file, "w", encoding="utf-8") as f:
                f.write(f"--- Available Epics from {jira_url} ({len(epics)}) ---\n\n")
                for epic in epics:
                    f.write(f"{epic['key']}\n")
            logger.info("[JIRA] Saved epics list to %s", epics_file)
        except Exception as e:
            logger.warning("[JIRA] Failed to save epics to text file: %s", e)

        return {"success": True, "epics": epics, "total": len(epics)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[JIRA] Failed to fetch epics: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

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
        
        raw_issue = client.get_issue(issue_key)
        context = client.extract_context(raw_issue)
        analysis = analyzer.classify(context)
        
        frds = []
        test_cases = []
        
        for file in analysis.get("classified_files", []):
            item = {
                "id": file["id"],
                "name": file["original_filename"],
                "suggested_name": file.get("suggested_filename", file["original_filename"]),
                "reason": file.get("reason", "")
            }
            if file.get("category") == "FRD":
                frds.append(item)
            elif file.get("category") == "MANUAL_TEST_CASES":
                test_cases.append(item)
                
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
    """
    Downloads FRD and TC attachments from a Jira issue into simple numbered
    sub-folders inside input_modules/. Each FRD+its matching TC pair gets
    one folder: input_modules/1/, input_modules/2/, etc.

    Folder structure created:
        input_modules/
            1/
                FRD_filename.docx
                TC_filename.docx
            2/
                FRD_filename.docx
                TC_filename.docx
    """
    try:
        issue_key  = payload.issue_key
        jira_url   = request.headers.get("x-jira-url")   or os.getenv("JIRA_URL")
        jira_email = request.headers.get("x-jira-email") or os.getenv("JIRA_EMAIL")
        jira_token = request.headers.get("x-jira-token") or os.getenv("JIRA_API_TOKEN")
        gemini_key = request.headers.get("x-gemini-key") or os.getenv("GEMINI_API_KEY")

        client = JiraClient(jira_url=jira_url, email=jira_email, api_token=jira_token)

        analyzer = LLMAnalyzer()
        if gemini_key:
            analyzer.gemini_key = gemini_key

        raw_issue = client.get_issue(issue_key)
        context   = client.extract_context(raw_issue)
        analysis  = analyzer.classify(context)

        # ── Classify all attachments into FRD and TC lists ────────────────────
        classified_map = {str(item.get("id")): item for item in analysis.get("classified_files", [])}

        frd_attachments = []
        tc_attachments  = []

        for att in context.get("attachments", []):
            att_id = str(att["id"])
            fname  = att["filename"]
            item   = classified_map.get(att_id)

            if not item:
                rule_meta = analyzer.classify_single_file(fname, issue_key, "")
                cat       = rule_meta.get("category", "OTHER")
                sug_name  = rule_meta.get("suggested_filename", fname)
            else:
                cat      = item.get("category", "OTHER")
                sug_name = item.get("suggested_filename", fname)

            att_info = {**att, "category": cat, "sug_name": sanitize_filename(sug_name or fname)}

            if cat == "FRD":
                frd_attachments.append(att_info)
            elif cat == "MANUAL_TEST_CASES":
                tc_attachments.append(att_info)

        # ── Find the next available numbered folder in input_modules/ ─────────
        existing_nums = [
            int(item.name) for item in INPUT_MODULES_DIR.iterdir()
            if item.is_dir() and item.name.isdigit()
        ]
        next_num = max(existing_nums, default=0) + 1

        # ── Pair each FRD with its TC and write to numbered folder ────────────
        paired_attachments = []
        max_att_len = max(len(frd_attachments), len(tc_attachments))
        for i in range(max_att_len):
            frd = frd_attachments[i] if i < len(frd_attachments) else None
            tc = tc_attachments[i] if i < len(tc_attachments) else None
            paired_attachments.append((frd, tc))

        # Filter out pairs if selected_frd_ids is provided
        if payload.selected_frd_ids:
            filtered_pairs = []
            for frd, tc in paired_attachments:
                if frd and str(frd["id"]) in payload.selected_frd_ids:
                    filtered_pairs.append((frd, tc))
            paired_attachments = filtered_pairs

        max_len          = len(paired_attachments)
        downloaded_files = []

        for i, (frd, tc) in enumerate(paired_attachments):
            folder_num = next_num + i
            folder     = INPUT_MODULES_DIR / str(folder_num)
            folder.mkdir(parents=True, exist_ok=True)

            for att_info in filter(None, [frd, tc]):
                save_path = folder / att_info["sug_name"]
                try:
                    client.download_attachment(att_info["content_url"], str(save_path))
                    downloaded_files.append({
                        "original_name": att_info["filename"],
                        "saved_name":    att_info["sug_name"],
                        "category":      att_info["category"],
                        "folder":        str(folder.relative_to(BASE_DIR)),
                        "path":          str(save_path.relative_to(BASE_DIR)),
                    })
                    logger.info("[JIRA] Downloaded [%s] %s -> %s", att_info["category"], att_info["filename"], save_path)
                except Exception as e:
                    logger.error("[JIRA] Failed to download %s: %s", att_info["filename"], e)

        folders_created = list(range(next_num, next_num + max_len))
        return {
            "success": True,
            "message": f"Downloaded {len(downloaded_files)} file(s) into folder(s): {folders_created}",
            "folders": [str((INPUT_MODULES_DIR / str(n)).relative_to(BASE_DIR)) for n in folders_created],
            "files":   downloaded_files,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ══════════════════════════════════════════════════════════════════════════════
# COST & TOKEN TRACKING ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

import datetime
from collections import defaultdict

COST_LOG_FILE = OUTPUT_DIR / "cost_tracking.txt"

def _parse_cost_logs():
    """Parses output/cost_tracking.txt into structured metrics."""
    if not COST_LOG_FILE.exists():
        return {
            "total_cost": 0.0,
            "total_cost_formatted": "$0.000000",
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_calls": 0,
            "phases": [],
            "entries": []
        }

    line_pattern = re.compile(
        r"\[(.*?)\]\s+"
        r"(?:\[(.*?)\]\s+)?"
        r"Model:\s+(.*?)\s+\((.*?)\)\s+\|\s+"
        r"Tokens:\s+(\d+)\s+In,\s+(\d+)\s+Out\s+\|\s+"
        r"Cost:\s+\$([\d\.]+)"
    )

    phases_map = defaultdict(lambda: {
        "in": 0, "out": 0, "cost": 0.0, "calls": 0, 
        "models": set(), "keys": set(),
        "key_breakdown": defaultdict(lambda: {"in": 0, "out": 0, "cost": 0.0, "calls": 0})
    })
    entries = []
    total_cost = 0.0
    total_in = 0
    total_out = 0

    with open(COST_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            m = line_pattern.search(line)
            if m:
                ts = m.group(1)
                phase = m.group(2) or "Generator"
                model = m.group(3)
                key_alias = m.group(4)
                in_toks = int(m.group(5))
                out_toks = int(m.group(6))
                cost = float(m.group(7))

                phases_map[phase]["in"] += in_toks
                phases_map[phase]["out"] += out_toks
                phases_map[phase]["cost"] += cost
                phases_map[phase]["calls"] += 1
                phases_map[phase]["models"].add(model)
                phases_map[phase]["keys"].add(key_alias)

                phases_map[phase]["key_breakdown"][key_alias]["in"] += in_toks
                phases_map[phase]["key_breakdown"][key_alias]["out"] += out_toks
                phases_map[phase]["key_breakdown"][key_alias]["cost"] += cost
                phases_map[phase]["key_breakdown"][key_alias]["calls"] += 1

                total_cost += cost
                total_in += in_toks
                total_out += out_toks

                entries.append({
                    "timestamp": ts,
                    "phase": phase,
                    "model": model,
                    "key_alias": key_alias,
                    "input_tokens": in_toks,
                    "output_tokens": out_toks,
                    "cost": cost
                })

    phases_list = []
    for ph_name, pdata in phases_map.items():
        kb_list = [
            {
                "key_alias": k,
                "input_tokens": v["in"],
                "output_tokens": v["out"],
                "total_tokens": v["in"] + v["out"],
                "cost": v["cost"],
                "calls": v["calls"],
                "cost_formatted": f"${v['cost']:.6f}"
            }
            for k, v in pdata["key_breakdown"].items()
        ]
        
        phases_list.append({
            "phase": ph_name,
            "input_tokens": pdata["in"],
            "output_tokens": pdata["out"],
            "total_tokens": pdata["in"] + pdata["out"],
            "cost": pdata["cost"],
            "calls": pdata["calls"],
            "models": list(pdata["models"]),
            "keys": list(pdata["keys"]),
            "cost_formatted": f"${pdata['cost']:.6f}",
            "key_breakdown": kb_list
        })

    return {
        "total_cost": total_cost,
        "total_cost_formatted": f"${total_cost:.6f}",
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "total_calls": len(entries),
        "phases": phases_list,
        "entries": entries[-100:]
    }

@app.get("/api/cost/metrics")
def get_cost_metrics():
    """Returns aggregated token usage and cost metrics."""
    data = _parse_cost_logs()
    return JSONResponse({"success": True, "metrics": data})

@app.get("/api/cost/download-report")
def download_cost_report():
    """Generates and downloads the cost audit report."""
    metrics = _parse_cost_logs()
    
    report_lines = [
        "=" * 55,
        "             BAXTER AI COST & TOKEN AUDIT REPORT",
        "=" * 55,
        f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total LLM API Calls: {metrics['total_calls']}",
        f"Total Input Tokens  : {metrics['total_input_tokens']:,}",
        f"Total Output Tokens : {metrics['total_output_tokens']:,}",
        f"Total Combined      : {metrics['total_tokens']:,}",
        f"Grand Total Cost    : {metrics['total_cost_formatted']}",
        "=" * 55,
        "",
        "--- PHASE & AGENT BREAKDOWN ---"
    ]

    for p in metrics["phases"]:
        report_lines.extend([
            f"\n  [{p['phase']} Agent]",
            f"    Total Calls   : {p['calls']}",
            f"    Models Used   : {', '.join(p['models'])}",
            f"    Keys Used     : {', '.join(p['keys'])}",
            f"    Input Tokens  : {p['input_tokens']:,}",
            f"    Output Tokens : {p['output_tokens']:,}",
            f"    Total Tokens  : {p['total_tokens']:,}",
            f"    Phase Cost    : {p['cost_formatted']}"
        ])

    report_lines.extend([
        "\n" + "=" * 55,
        "--- RECENT CALL LOGS (LATEST ENTRIES) ---"
    ])
    for e in metrics["entries"]:
        report_lines.append(
            f"[{e['timestamp']}] [{e['phase']}] Model: {e['model']} ({e['key_alias']}) | "
            f"Tokens: {e['input_tokens']} In, {e['output_tokens']} Out | Cost: ${e['cost']:.6f}"
        )
    report_lines.append("=" * 55 + "\n")

    report_content = "\n".join(report_lines)
    buf = BytesIO(report_content.encode("utf-8"))
    
    return StreamingResponse(
        buf,
        media_type="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=baxter_cost_token_report.txt"
        }
    )

# ─── ENTRYPOINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
        reload_includes=["server.py", "agents/*.py", "core/*.py"],
    )
