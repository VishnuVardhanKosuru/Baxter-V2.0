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
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from dotenv import load_dotenv

load_dotenv()

# ─── PATHS ────────────────────────────────────────────────────────────────────

BASE_DIR    = Path(__file__).parent.resolve()
AGENTS_DIR  = BASE_DIR / "agents"
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUT_DIR  = BASE_DIR / "output"
TESTS_DIR   = OUTPUT_DIR / "tests"
JOBS_DIR    = OUTPUT_DIR / "jobs"

# ─── SERVER CONFIG ────────────────────────────────────────────────────────────

SERVER_HOST:         str = os.environ.get("SERVER_HOST", "127.0.0.1")
SERVER_PORT:         int = int(os.environ.get("SERVER_PORT", "5000"))
SAMPLE_FRD_FILENAME: str = os.environ.get("SAMPLE_FRD", "ShopSphere_Functional_Requirements_Document.docx")
SAMPLE_TC_FILENAME:  str = os.environ.get("SAMPLE_TC",  "ShopSphere_Manual_Testcases.docx")

for _d in (UPLOADS_DIR, OUTPUT_DIR, TESTS_DIR, JOBS_DIR):
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

try:
    from sse_starlette.sse import EventSourceResponse
    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False
    print("[WARN] sse-starlette not installed. /stream endpoint will be unavailable.")

# ─── APP ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Baxter Parser & Code Generator API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

@app.post("/api/stage1-parse")
async def stage1_parse(
    frd_file:   Optional[UploadFile] = File(None),
    tc_file:    Optional[UploadFile] = File(None),
    use_sample: bool = Form(False),
):
    """
    Stage 1: Parse FRD + TC .docx files into structured JSON.
    Returns standard JSON response.
    """
    if use_sample or (not frd_file and not tc_file):
        sample_frd = BASE_DIR / "samples" / SAMPLE_FRD_FILENAME
        sample_tc  = BASE_DIR / "samples" / SAMPLE_TC_FILENAME
        if not sample_frd.exists() or not sample_tc.exists():
            raise HTTPException(400, "Sample documents not found in workspace.")
        frd_path, tc_path = str(sample_frd), str(sample_tc)
    else:
        if not frd_file or not tc_file:
            raise HTTPException(400, "Both FRD (.docx) and Test Cases (.docx) files are required.")
        frd_path = str(UPLOADS_DIR / frd_file.filename)
        tc_path  = str(UPLOADS_DIR / tc_file.filename)
        with open(frd_path, "wb") as f:
            f.write(await frd_file.read())
        with open(tc_path, "wb") as f:
            f.write(await tc_file.read())

    try:
        output_json_path = await asyncio.to_thread(
            parse_documents, frd_path, tc_path, str(OUTPUT_DIR)
        )

        try:
            with open(output_json_path, "r", encoding="utf-8") as jf:
                parsed_data = json.load(jf)
        except Exception:
            parsed_data = {}

        return JSONResponse({
            "success": True,
            "result": {
                "success":     True,
                "output_file": str(Path(output_json_path).relative_to(BASE_DIR)),
                "data":        parsed_data,
            }
        })
    except Exception as exc:
        return JSONResponse({"success": False, "detail": str(exc)}, status_code=500)


@app.post("/api/stage2-generate")
async def stage2_generate():
    """
    Stage 2: Generate Cucumber + Selenium test code from the parsed JSON.
    Returns standard JSON response.
    """
    json_files = sorted(OUTPUT_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
    if not json_files:
        raise HTTPException(400, "No parsed JSON found. Run Stage 1 first.")

    latest_json = json_files[0]

    try:
        await asyncio.to_thread(
            run_agent,
            stage1_json_path=str(latest_json),
            out_dir_path=str(TESTS_DIR)
        )

        try:
            with open(latest_json, "r", encoding="utf-8") as jf:
                parsed_data = json.load(jf)
        except Exception:
            parsed_data = {}

        test_cases  = parsed_data.get("test_cases", [])
        total_tc    = len(test_cases)
        feature_ids = {tc.get("feature_ref") for tc in test_cases if tc.get("feature_ref")}
        sel_dir     = TESTS_DIR / "selenium"
        cuc_dir     = TESTS_DIR / "cucumber"
        selenium_count = len(list(sel_dir.glob("*.py")))      if sel_dir.exists() else total_tc
        cucumber_count = len(list(cuc_dir.glob("*.feature"))) if cuc_dir.exists() else total_tc

        return JSONResponse({
            "success": True,
            "result": {
                "success":    True,
                "output_file": str(latest_json.relative_to(BASE_DIR)),
                "tests_dir":  str(TESTS_DIR.relative_to(BASE_DIR)),
                "summary": {
                    "total_test_cases": total_tc,
                    "total_features":   len(feature_ids),
                    "selenium_count":   selenium_count,
                    "cucumber_count":   cucumber_count,
                    "project":          parsed_data.get("project", ""),
                    "version":          parsed_data.get("version", "1.0"),
                },
                "data": parsed_data,
            }
        })
    except Exception as exc:
        return JSONResponse({"success": False, "detail": str(exc)}, status_code=500)


@app.get("/api/download-zip")
def download_zip():
    """Stream all generated test files as a ZIP archive (legacy single-FRD)."""
    if not TESTS_DIR.exists() or not any(TESTS_DIR.rglob("*")):
        raise HTTPException(404, "No generated test files available.")

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in TESTS_DIR.rglob("*"):
            if fp.is_file():
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
            json_path = await asyncio.to_thread(
                parse_documents, frd_p, tc_p, parse_out_dir
            )
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
    if not SSE_AVAILABLE:
        raise HTTPException(503, "SSE not available. Install sse-starlette.")

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
