"""
server.py
─────────
FastAPI Backend — Baxter Test Case Generator.

Agents are imported directly as Python modules (no subprocess / CLI).
Each pipeline stage streams its console logs to the browser in real-time
via Server-Sent Events (SSE), so you see every print() line live.
"""

import asyncio
import importlib.util
import json
import os
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional

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

# ─── SERVER CONFIG ────────────────────────────────────────────────────────────
# Override via environment variables — no need to touch this file.

SERVER_HOST:          str = os.environ.get("SERVER_HOST", "127.0.0.1")
SERVER_PORT:          int = int(os.environ.get("SERVER_PORT", "5000"))
SAMPLE_FRD_FILENAME:  str = os.environ.get("SAMPLE_FRD",  "ShopSphere_Functional_Requirements_Document.docx")
SAMPLE_TC_FILENAME:   str = os.environ.get("SAMPLE_TC",   "ShopSphere_Manual_Testcases.docx")

for _d in (UPLOADS_DIR, OUTPUT_DIR, TESTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# agents/ needs to be on sys.path so its internal imports work
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from doc_parser import parse_documents    # importable API function
from cs_agent import run_agent            # importable API function

# ─── APP ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Baxter Parser & Code Generator API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── LOG STREAMING REMOVED ────────────────────────────────────────────────────
# The UI no longer intercepts logs via SSE. All print() statements now go
# directly and cleanly to the server terminal.

# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Baxter Parser & Code Generator API"}


@app.post("/api/stage1-parse")
async def stage1_parse(
    frd_file: Optional[UploadFile] = File(None),
    tc_file:  Optional[UploadFile] = File(None),
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
        # Run synchronous parse_documents in a thread to not block the event loop
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
                "success": True,
                "output_file": str(Path(output_json_path).relative_to(BASE_DIR)),
                "data": parsed_data,
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
        selenium_count = len(list(sel_dir.glob("*.py")))   if sel_dir.exists() else total_tc
        cucumber_count = len(list(cuc_dir.glob("*.feature"))) if cuc_dir.exists() else total_tc

        return JSONResponse({
            "success": True,
            "result": {
                "success": True,
                "output_file": str(latest_json.relative_to(BASE_DIR)),
                "tests_dir": str(TESTS_DIR.relative_to(BASE_DIR)),
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
    """Stream all generated test files as a ZIP archive."""
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
        reload_includes=["server.py", "agents/*.py"],
    )
