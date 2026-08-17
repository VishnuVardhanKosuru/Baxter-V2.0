"""
server.py
─────────
FastAPI backend — Baxter Test Case Generator.

Endpoint groups
───────────────
 ── HEALTH ────────────────────────────────────────────────────────────────────
   GET  /api/health                    → liveness + configuration snapshot

 ── SEQUENTIAL PIPELINE (single FRD) ──────────────────────────────────────────
   POST /api/stage1-parse              → parse FRD + TC pair(s) into knowledge JSON
   POST /api/stage2-generate           → generate artifacts from parsed JSON
   GET  /api/download-zip              → download all generated tests as ZIP

 ── BATCH PIPELINE (multi-FRD, parallel, SSE) ─────────────────────────────────
   POST /api/batch/submit                     → upload N FRD+TC pairs, returns job_id
   GET  /api/batch/{job_id}/stream            → SSE live progress stream
   GET  /api/batch/{job_id}/status            → JSON snapshot of job state
   GET  /api/batch/{job_id}/download          → ZIP entire job output
   GET  /api/batch/{job_id}/download/{frd_id} → ZIP single FRD output

 ── JIRA INGESTION ────────────────────────────────────────────────────────────
   GET  /api/jira/epics                → list accessible Epics
   GET  /api/jira/epic/{issue_key}     → classify one Epic's attachments
   POST /api/jira/evaluate             → download attachments into input_modules/

 ── COST TRACKING ─────────────────────────────────────────────────────────────
   GET  /api/cost/metrics              → aggregated token/cost metrics
   GET  /api/cost/download-report      → cost audit report as .txt

Error handling contract
───────────────────────
Internal exception text is returned to clients only when DEBUG_ERRORS=true.
In the default configuration clients receive a stable, generic message while the
full traceback goes to the server log.
"""

import asyncio
import datetime
import json
import os
import time
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

# Entry-point responsibility: load .env exactly once, before any module reads
# configuration from the environment at import time.
load_dotenv()

from agents.cs_agent import run_agent
from agents.doc_parser import parse_documents, reset_mapper_chain
from agents.jira_agent import JiraClient, LLMAnalyzer, sanitize_filename
from core import constants as const
from core.batch_manager import batch_manager, JobStatus
from core.cost_report import parse_cost_log
from core.logger import logger

# ─── DIRECTORIES ──────────────────────────────────────────────────────────────

BASE_DIR          = const.WORKSPACE_ROOT
UPLOADS_DIR       = const.DIR_UPLOADS
INPUT_MODULES_DIR = const.DIR_MODULES_INPUT
OUTPUT_DIR        = const.DIR_OUTPUT
JOBS_DIR          = const.DIR_JOBS
KNOWLEDGE_DIR     = const.DIR_KNOWLEDGE
TESTS_DIR         = const.DIR_TESTS
SAMPLES_DIR       = const.DIR_SAMPLES

for _d in (UPLOADS_DIR, OUTPUT_DIR, KNOWLEDGE_DIR, INPUT_MODULES_DIR, TESTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Sample filenames come from configuration, so they are sanitized before being
# joined to SAMPLES_DIR just like any other externally supplied name.
SAMPLE_FRD_FILENAME = sanitize_filename(const.SAMPLE_FRD_FILENAME)
SAMPLE_TC_FILENAME = sanitize_filename(const.SAMPLE_TC_FILENAME)

# ─── APP ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Baxter Parser & Code Generator API", version="3.0.0")

# Wildcard origins and credentialed CORS are mutually exclusive: browsers reject
# `Access-Control-Allow-Origin: *` on a credentialed request. constants derives
# CORS_ALLOW_CREDENTIALS from ALLOWED_ORIGINS so the pair is always coherent.
app.add_middleware(
    CORSMiddleware,
    allow_origins=const.ALLOWED_ORIGINS,
    allow_credentials=const.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

if "*" in const.ALLOWED_ORIGINS:
    logger.warning(
        "CORS is open to all origins (ALLOWED_ORIGINS=*). Set an explicit "
        "origin list before deploying to production."
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Structured request/response logging with a per-request correlation ID.

    The ID is echoed back in the X-Request-ID response header so a client-visible
    error can be traced to its server-side log lines and stack trace.
    """
    request_id = uuid.uuid4().hex[:8]
    request.state.request_id = request_id
    started = time.perf_counter()

    logger.info("[REQ %s] %s %s", request_id, request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.exception(
            "[REQ %s] %s %s -> unhandled exception after %.1fms",
            request_id, request.method, request.url.path, elapsed_ms,
        )
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "[REQ %s] %s %s -> %d (%.1fms)",
        request_id, request.method, request.url.path, response.status_code, elapsed_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


# ─── SHARED HELPERS ───────────────────────────────────────────────────────────

def _error_response(request: Request, exc: Exception, context: str, status_code: int = 500):
    """
    Logs an exception with its traceback and returns a safe JSON error response.

    Internal exception text is exposed only when DEBUG_ERRORS=true; otherwise the
    client receives a generic message plus the request ID for correlation.
    """
    request_id = getattr(request.state, "request_id", "-")
    logger.error("[%s] request=%s: %s", context, request_id, exc, exc_info=True)

    detail = str(exc) if const.DEBUG_ERRORS else (
        f"{context} failed. Contact support with request ID {request_id}."
    )
    return JSONResponse(
        {"success": False, "detail": detail, "request_id": request_id},
        status_code=status_code,
    )


async def _save_upload(upload: UploadFile, dest_dir: Path) -> Path:
    """
    Persists an uploaded document safely.

    The client-supplied filename is reduced to a bare, sanitized basename before
    being joined to dest_dir, so a name such as "../../etc/passwd" cannot escape
    the uploads directory. Extension and size are both validated.

    Raises:
        HTTPException: 400 for a missing name or wrong extension,
                       413 if the file exceeds MAX_UPLOAD_MB.
    """
    if not upload or not upload.filename:
        raise HTTPException(400, "Uploaded file is missing a filename.")

    safe_name = sanitize_filename(upload.filename)
    if not safe_name.lower().endswith(const.SUPPORTED_DOC_EXT):
        raise HTTPException(
            400,
            f"Unsupported file type '{upload.filename}'. "
            f"Only {const.SUPPORTED_DOC_EXT} documents are accepted.",
        )

    content = await upload.read()
    if len(content) > const.MAX_UPLOAD_BYTES:
        raise HTTPException(
            413,
            f"'{safe_name}' is {len(content) / 1_048_576:.1f} MB, which exceeds the "
            f"{const.MAX_UPLOAD_BYTES // 1_048_576} MB limit.",
        )
    if not content:
        raise HTTPException(400, f"'{safe_name}' is empty.")

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe_name
    try:
        dest.write_bytes(content)
    except OSError as exc:
        raise HTTPException(500, f"Could not save upload '{safe_name}': {exc}") from exc

    return dest


def _stream_zip(files_root: Path, filename: str, exclude=()) -> StreamingResponse:
    """
    Builds an in-memory ZIP of every file under files_root and streams it.

    Args:
        files_root: Directory whose tree is archived (paths kept relative to it).
        filename:   Download filename offered to the browser.
        exclude:    Substrings; a file whose relative path contains any of them
                    is omitted (used to drop intermediate parse dirs).
    """
    buf = BytesIO()
    written = 0

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in files_root.rglob("*"):
            if not fp.is_file():
                continue
            rel = str(fp.relative_to(files_root))
            if any(token in rel for token in exclude):
                continue
            zf.write(fp, arcname=rel)
            written += 1

    if not written:
        raise HTTPException(404, "No generated files available to download.")

    buf.seek(0)
    logger.info("Streaming ZIP '%s' with %d file(s) from %s", filename, written, files_root)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _jira_client_from_request(request: Request) -> JiraClient:
    """
    Builds a JiraClient from X-Jira-* request headers, falling back to .env.

    Raises:
        HTTPException: 400 if URL, email, or token is missing.
    """
    jira_url = request.headers.get("x-jira-url") or os.getenv("JIRA_URL")
    jira_email = request.headers.get("x-jira-email") or os.getenv("JIRA_EMAIL")
    jira_token = request.headers.get("x-jira-token") or os.getenv("JIRA_API_TOKEN")

    missing = [
        label for label, value in
        (("URL", jira_url), ("email", jira_email), ("API token", jira_token))
        if not value
    ]
    if missing:
        raise HTTPException(
            400, f"Jira {', '.join(missing)} required. Provide it in the Jira credentials dialog."
        )

    return JiraClient(jira_url=jira_url, email=jira_email, api_token=jira_token)


def _analyzer_from_request(request: Request) -> LLMAnalyzer:
    """Builds an LLMAnalyzer, preferring a UI-supplied Gemini key when present."""
    analyzer = LLMAnalyzer()
    ui_key = request.headers.get("x-gemini-key")
    if ui_key:
        # A comma-separated list may arrive from the multi-key UI; the classifier
        # is a single call, so use the first key only.
        analyzer.gemini_key = ui_key.split(",")[0].strip()
    return analyzer


def _validate_issue_key(issue_key: str) -> str:
    """
    Validates a Jira issue key before it is interpolated into a REST path.

    Raises:
        HTTPException: 400 if the key is not of the form PROJECT-123.
    """
    key = (issue_key or "").strip()
    if not const.REGEX_JIRA_KEY.match(key):
        raise HTTPException(
            400, f"Invalid Jira issue key '{issue_key}'. Expected a format like PROJ-123."
        )
    return key


def _inject_ui_gemini_key(ui_keys: Optional[str]) -> None:
    """
    Merges UI-supplied Gemini API keys into the process environment.

    Keys already configured are skipped; new ones fill the next free
    GEMINI_API_KEY_N slot so the LiteLLM router treats each as an additional
    deployment. Slots are bounded by MAX_API_KEY_SLOTS — the same limit
    collect_keys() reads — so a key can never land in a slot that is then ignored.

    The cached mapper chain and cost-tracking alias map are both refreshed so the
    new keys take effect immediately.
    """
    if not ui_keys:
        return

    from core.llm_factory import collect_keys, refresh_key_alias_map

    existing_keys = collect_keys("GEMINI_API_KEY")
    added = 0

    for raw in ui_keys.split(","):
        key = raw.strip()
        if len(key) < 10 or key in existing_keys:
            continue

        for i in range(1, const.MAX_API_KEY_SLOTS + 1):
            env_var = f"GEMINI_API_KEY{'' if i == 1 else f'_{i}'}"
            if not os.getenv(env_var):
                os.environ[env_var] = key
                existing_keys.append(key)
                added += 1
                logger.info("Registered UI-supplied Gemini key as %s.", env_var)
                break
        else:
            logger.warning(
                "All %d Gemini key slots are in use — ignoring additional UI key.",
                const.MAX_API_KEY_SLOTS,
            )
            break

    if added:
        # Rebuild cached state that captured the previous key set.
        reset_mapper_chain()
        refresh_key_alias_map()


def _set_phase(phase: str) -> None:
    """
    Tags the current pipeline phase for cost attribution.

    litellm.current_phase is read by the cost callback to label each logged call
    as Parser or Generator.
    """
    import litellm

    litellm.current_phase = phase


# ─── HEALTH ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    """
    Liveness probe plus a non-sensitive configuration snapshot.

    Reports whether an LLM key is configured — never the key itself or any part
    of it — so a deployment can be verified without exposing credentials.
    """
    from core.llm_factory import collect_keys

    gemini_keys = len(collect_keys("GEMINI_API_KEY"))
    openai_keys = len(collect_keys("OPENAI_API_KEY"))
    anthropic_keys = len(collect_keys("ANTHROPIC_API_KEY"))

    return {
        "status": "ok",
        "app": "Baxter Parser & Code Generator API",
        "version": "3.0.0",
        "model": const.DEFAULT_MODEL,
        "llm_configured": bool(gemini_keys or openai_keys or anthropic_keys),
        "api_key_counts": {
            "gemini": gemini_keys,
            "openai": openai_keys,
            "anthropic": anthropic_keys,
        },
        "samples_available": SAMPLES_DIR.is_dir(),
        "debug_errors": const.DEBUG_ERRORS,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SEQUENTIAL PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/stage1-parse")
async def stage1_parse(
    request:           Request,
    frd_file:          Optional[UploadFile] = File(None),
    tc_file:           Optional[UploadFile] = File(None),
    use_sample:        bool = Form(False),
    use_input_modules: bool = Form(False),
):
    """
    Stage 1 — parse FRD + Test Case .docx documents into structured knowledge JSON.

    Input source is resolved in this order:
      1. input_modules/ directory (explicit flag, or auto-detected when populated)
      2. bundled sample documents (explicit flag, or when no files were uploaded)
      3. the uploaded FRD + TC pair

    Returns the merged test cases across all parsed modules.
    """
    _inject_ui_gemini_key(request.headers.get("x-gemini-key"))

    logger.info("[STAGE 1] Ingestion & document parsing started.")
    _set_phase("Parser")

    try:
        has_input_modules = INPUT_MODULES_DIR.is_dir() and any(
            INPUT_MODULES_DIR.rglob(f"*{const.SUPPORTED_DOC_EXT}")
        )
        no_uploads = not frd_file and not tc_file

        if use_input_modules or (has_input_modules and no_uploads and not use_sample):
            if not has_input_modules:
                raise HTTPException(
                    400,
                    f"No {const.SUPPORTED_DOC_EXT} documents found in {INPUT_MODULES_DIR.name}/.",
                )
            logger.info("[STAGE 1] Parsing all modules in %s", INPUT_MODULES_DIR)
            json_paths = await asyncio.to_thread(
                parse_documents, str(INPUT_MODULES_DIR), str(OUTPUT_DIR)
            )

        elif use_sample or no_uploads:
            sample_frd = SAMPLES_DIR / SAMPLE_FRD_FILENAME
            sample_tc = SAMPLES_DIR / SAMPLE_TC_FILENAME

            if sample_frd.is_file() and sample_tc.is_file():
                logger.info("[STAGE 1] Using sample documents %s & %s", sample_frd.name, sample_tc.name)
                json_paths = await asyncio.to_thread(
                    parse_documents, str(sample_frd), str(sample_tc), str(OUTPUT_DIR)
                )
            elif has_input_modules:
                # The samples/ directory is optional. Rather than dead-ending the
                # default "Evaluate" click, fall back to whatever the user has
                # already placed in (or Jira has downloaded into) input_modules/.
                logger.warning(
                    "[STAGE 1] Sample documents missing from %s/ — falling back to %s/.",
                    SAMPLES_DIR.name, INPUT_MODULES_DIR.name,
                )
                json_paths = await asyncio.to_thread(
                    parse_documents, str(INPUT_MODULES_DIR), str(OUTPUT_DIR)
                )
            else:
                raise HTTPException(
                    400,
                    f"No documents available to parse. Sample documents were not found in "
                    f"{SAMPLES_DIR.name}/ (expected '{SAMPLE_FRD_FILENAME}' and "
                    f"'{SAMPLE_TC_FILENAME}') and {INPUT_MODULES_DIR.name}/ is empty. "
                    "Upload an FRD and a Test Cases document to continue.",
                )

        else:
            if not frd_file or not tc_file:
                raise HTTPException(
                    400,
                    f"Both an FRD and a Test Cases {const.SUPPORTED_DOC_EXT} file are required.",
                )
            frd_path = await _save_upload(frd_file, UPLOADS_DIR)
            tc_path = await _save_upload(tc_file, UPLOADS_DIR)
            logger.info("[STAGE 1] Parsing uploads %s & %s", frd_path.name, tc_path.name)
            json_paths = await asyncio.to_thread(
                parse_documents, str(frd_path), str(tc_path), str(OUTPUT_DIR)
            )

        if not json_paths:
            # Fall back to knowledge files already on disk from an earlier run.
            existing = sorted(
                KNOWLEDGE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            if not existing:
                raise HTTPException(
                    422,
                    "Parsing produced no output. Check that the documents contain a "
                    "requirements section and a test case table.",
                )
            logger.warning("[STAGE 1] No new output — reusing %d existing knowledge file(s).", len(existing))
            json_paths = [str(p) for p in existing]

        # Merge test cases across every parsed module for the UI payload.
        all_test_cases = []
        modules_data = []
        for jp in json_paths:
            try:
                with open(jp, "r", encoding="utf-8") as jf:
                    parsed = json.load(jf)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("[STAGE 1] Skipping unreadable knowledge file %s: %s", jp, exc)
                continue
            all_test_cases.extend(parsed.get("test_cases", []))
            modules_data.append(parsed)

        if not modules_data:
            raise HTTPException(500, "Parsed knowledge files could not be read back.")

        primary_data = modules_data[0]
        primary_data["test_cases"] = all_test_cases

        logger.info(
            "[STAGE 1] Success — %d module(s), %d test case(s).", len(json_paths), len(all_test_cases)
        )

        return JSONResponse({
            "success": True,
            "result": {
                "success":      True,
                "output_file":  _relative_to_base(json_paths[0]),
                "modules":      [_relative_to_base(p) for p in json_paths],
                "module_count": len(json_paths),
                "data":         primary_data,
            },
        })

    except HTTPException:
        raise
    except Exception as exc:
        return _error_response(request, exc, "Stage 1 parsing")


def _relative_to_base(path) -> str:
    """Renders a path relative to the project root, falling back to absolute."""
    try:
        return str(Path(path).relative_to(BASE_DIR))
    except ValueError:
        return str(path)


@app.post("/api/stage2-generate")
async def stage2_generate(request: Request):
    """
    Stage 2 — generate Cucumber features and Selenium scripts from parsed JSON.

    Each module writes into output/tests/<module_slug>/ containing expected.csv,
    cucumber/, and selenium/.
    """
    _inject_ui_gemini_key(request.headers.get("x-gemini-key"))

    logger.info("[STAGE 2] Test code generation started.")
    _set_phase("Generator")

    json_files = sorted(KNOWLEDGE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not json_files:
        raise HTTPException(400, "No parsed knowledge JSON found. Run Stage 1 first.")

    logger.info("[STAGE 2] Processing %d module knowledge file(s).", len(json_files))

    total_tc = total_cucumber = total_selenium = 0
    all_feature_ids: set = set()
    modules_summary = []
    primary_data: dict = {}
    failed_modules = []

    try:
        for knowledge_json in json_files:
            module_slug = knowledge_json.stem.replace("_knowledge", "")
            module_out_dir = TESTS_DIR / module_slug
            module_out_dir.mkdir(parents=True, exist_ok=True)

            logger.info("[STAGE 2] Module %s -> %s", module_slug, module_out_dir)

            try:
                result = await asyncio.to_thread(
                    run_agent,
                    stage1_json_path=str(knowledge_json),
                    out_dir_path=str(module_out_dir),
                )
            except Exception as exc:
                # One bad module must not sink the whole batch; record and continue.
                logger.error("[STAGE 2] Module %s failed: %s", module_slug, exc, exc_info=True)
                failed_modules.append(module_slug)
                continue

            # Every test case failing is a module failure, even though run_agent
            # itself returns normally — otherwise the UI shows a green success
            # alongside zero generated files.
            if not result.succeeded:
                logger.error(
                    "[STAGE 2] Module %s generated nothing (%d/%d test cases failed).",
                    module_slug, len(result.failed), result.total,
                )
                failed_modules.append(module_slug)
                continue

            if result.failed:
                logger.warning(
                    "[STAGE 2] Module %s partially generated — %d of %d test case(s) failed.",
                    module_slug, len(result.failed), result.total,
                )

            try:
                with open(knowledge_json, "r", encoding="utf-8") as jf:
                    parsed_data = json.load(jf)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("[STAGE 2] Cannot re-read %s: %s", knowledge_json.name, exc)
                parsed_data = {}

            if not primary_data and parsed_data:
                primary_data = parsed_data

            module_tcs = parsed_data.get("test_cases", [])
            module_tc_count = len(module_tcs)

            cuc_dir = module_out_dir / "cucumber"
            sel_dir = module_out_dir / "selenium"
            cuc_count = len(list(cuc_dir.glob("*.feature"))) if cuc_dir.is_dir() else 0
            sel_count = len(list(sel_dir.glob("*.py"))) if sel_dir.is_dir() else 0

            total_tc += module_tc_count
            total_cucumber += cuc_count
            total_selenium += sel_count
            all_feature_ids.update(
                tc.get("feature_ref") for tc in module_tcs if tc.get("feature_ref")
            )

            modules_summary.append({
                "module":         module_slug,
                "test_cases":     module_tc_count,
                "cucumber_files": cuc_count,
                "selenium_files": sel_count,
                "failed_test_cases": result.failed,
                "output_dir":     _relative_to_base(module_out_dir),
            })

        if failed_modules and not modules_summary:
            raise HTTPException(
                502,
                f"Generation failed for every module ({', '.join(failed_modules)}). "
                "Check the LLM API key and server logs.",
            )

        logger.info(
            "[STAGE 2] Success — %d module(s), %d TCs (%d Cucumber, %d Selenium), %d failed.",
            len(modules_summary), total_tc, total_cucumber, total_selenium, len(failed_modules),
        )

        return JSONResponse({
            "success": True,
            "result": {
                "success":   True,
                "tests_dir": _relative_to_base(TESTS_DIR),
                "modules":   modules_summary,
                "failed_modules": failed_modules,
                "summary": {
                    "total_modules":    len(modules_summary),
                    "total_test_cases": total_tc,
                    "total_features":   len(all_feature_ids),
                    "selenium_count":   total_selenium,
                    "cucumber_count":   total_cucumber,
                    "project":          primary_data.get("project", ""),
                    "version":          primary_data.get("version", const.DEFAULT_VERSION),
                },
                "data": primary_data,
            },
        })

    except HTTPException:
        raise
    except Exception as exc:
        return _error_response(request, exc, "Stage 2 generation")


@app.get("/api/download-zip")
def download_zip():
    """
    Stream all generated test files as a ZIP archive.

    Archive structure:
      <module_slug>/expected.csv
      <module_slug>/cucumber/TC-001.feature
      <module_slug>/selenium/test_TC-001.py
    """
    if not TESTS_DIR.is_dir():
        raise HTTPException(404, "No generated test files available.")
    return _stream_zip(TESTS_DIR, "baxter_generated_tests.zip")


# ══════════════════════════════════════════════════════════════════════════════
# BATCH PIPELINE — multi-FRD with SSE progress streaming
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/batch/submit")
async def batch_submit(
    request:   Request,
    frd_files: List[UploadFile] = File(...),
    tc_files:  List[UploadFile] = File(...),
):
    """
    Upload N FRD + TC .docx pairs for batch processing.

    Request (multipart/form-data):
      frd_files: [FRD-1.docx, ...]   (N files)
      tc_files:  [TC-1.docx, ...]     (N files, matched by index)

    Returns a job_id immediately; processing continues in the background and
    progress is available on /api/batch/{job_id}/stream.

    Stage 1 parsing runs inside the request (seconds per FRD) so a malformed
    document is reported synchronously rather than failing a background job.
    """
    if not frd_files or not tc_files:
        raise HTTPException(400, "At least one FRD + TC file pair is required.")
    if len(frd_files) != len(tc_files):
        raise HTTPException(
            400,
            f"Mismatch: {len(frd_files)} FRD file(s) vs {len(tc_files)} TC file(s). "
            "Each FRD must have a corresponding TC file.",
        )

    saved_pairs = []
    for frd_file, tc_file in zip(frd_files, tc_files):
        saved_pairs.append((
            await _save_upload(frd_file, UPLOADS_DIR),
            await _save_upload(tc_file, UPLOADS_DIR),
        ))

    job_id = batch_manager.create_job()
    job = batch_manager.get_job(job_id)
    job_dir = job.output_root

    _set_phase("Parser")
    frd_inputs = []

    for idx, (frd_p, tc_p) in enumerate(saved_pairs, start=1):
        frd_id = f"FRD-{idx:03d}"
        frd_stem = frd_p.stem
        frd_name = (
            frd_stem.replace("_", " ").split("Functional")[0].strip().replace(" ", "_")
            or frd_stem
        )[:40]   # cap directory name length

        parse_out_dir = job_dir / f"{frd_id}_parse"
        parse_out_dir.mkdir(parents=True, exist_ok=True)

        try:
            json_paths = await asyncio.to_thread(
                parse_documents, str(frd_p), str(tc_p), str(parse_out_dir)
            )
            if not json_paths:
                raise ValueError("parsing produced no output")
            with open(json_paths[0], "r", encoding="utf-8") as jf:
                parsed = json.load(jf)
        except Exception as exc:
            logger.error("[BATCH] Stage 1 failed for %s: %s", frd_p.name, exc, exc_info=True)
            detail = (
                f"Failed to parse {frd_p.name}: {exc}" if const.DEBUG_ERRORS
                else f"Failed to parse '{frd_p.name}'. Check that it is a valid FRD document."
            )
            return JSONResponse({"success": False, "detail": detail}, status_code=422)

        frd_inputs.append({
            "frd_id":     frd_id,
            "frd_name":   frd_name,
            "test_cases": parsed.get("test_cases", []),
        })

    asyncio.create_task(batch_manager.run_batch(job_id, frd_inputs))

    return JSONResponse({
        "success": True,
        "job_id": job_id,
        "frd_count": len(frd_inputs),
        "total_test_cases": sum(len(f["test_cases"]) for f in frd_inputs),
        "stream_url": f"/api/batch/{job_id}/stream",
    })


@app.get("/api/batch/{job_id}/stream")
async def batch_stream(job_id: str):
    """
    SSE endpoint — the browser connects once and receives live progress events.

    Emits a snapshot roughly every second, then a terminal `batch_complete`
    event, after which the connection closes.
    """
    if not batch_manager.get_job(job_id):
        raise HTTPException(404, f"Job '{job_id}' not found.")

    async def event_generator():
        try:
            while True:
                job = batch_manager.get_job(job_id)
                if not job:
                    break

                yield {"data": json.dumps({
                    "job_id": job_id,
                    "status": job.status.value,
                    "frds": [p.to_dict() for p in job.frds.values()],
                })}

                if job.status in (JobStatus.DONE, JobStatus.FAILED):
                    yield {
                        "event": "batch_complete",
                        "data": json.dumps({
                            "event":  "batch_complete",
                            "job_id": job_id,
                            "status": job.status.value,
                            "error":  job.error,
                        }),
                    }
                    break

                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("[SSE] Client disconnected from job %s stream.", job_id)
            raise

    return EventSourceResponse(event_generator())


@app.get("/api/batch/{job_id}/status")
def batch_status(job_id: str):
    """JSON snapshot of the current job state, for polling or initial page load."""
    job = batch_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found.")

    return JSONResponse({
        "job_id": job_id,
        "status": job.status.value,
        "error":  job.error,
        "frds":   [p.to_dict() for p in job.frds.values()],
    })


@app.get("/api/batch/{job_id}/download")
def batch_download_all(job_id: str):
    """
    Download a ZIP of all FRD outputs for a job.

    Intermediate Stage 1 parse directories are excluded from the archive.
    """
    job = batch_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found.")

    job_dir = job.output_root or (JOBS_DIR / job_id)
    if not job_dir.is_dir():
        raise HTTPException(404, "No output files found for this job yet.")

    return _stream_zip(job_dir, f"job_{job_id}_all_frds.zip", exclude=("_parse",))


@app.get("/api/batch/{job_id}/download/{frd_id}")
def batch_download_frd(job_id: str, frd_id: str):
    """Download a ZIP of the output for a single FRD within a job."""
    job = batch_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found.")

    job_dir = job.output_root or (JOBS_DIR / job_id)
    if not job_dir.is_dir():
        raise HTTPException(404, f"No output directory for job '{job_id}'.")

    frd_dir = next(
        (d for d in sorted(job_dir.iterdir())
         if d.is_dir() and d.name.startswith(frd_id) and not d.name.endswith("_parse")),
        None,
    )
    if not frd_dir:
        raise HTTPException(404, f"No output found for FRD '{frd_id}' in job '{job_id}'.")

    return _stream_zip(
        frd_dir, f"{frd_id}_tests.zip", exclude=(const.NAME_CHECKPOINT,)
    )


# ══════════════════════════════════════════════════════════════════════════════
# JIRA INGESTION & ATTACHMENT EVALUATION
# ══════════════════════════════════════════════════════════════════════════════

class JiraEpicRequest(BaseModel):
    """Request body for /api/jira/evaluate."""
    issue_key: str = Field(min_length=1, max_length=64)
    selected_frd_ids: Optional[List[str]] = Field(default_factory=list)


@app.get("/api/jira/epics")
async def get_all_epics(request: Request, max_results: int = const.JIRA_MAX_RESULTS):
    """
    List all Epics visible to the caller, most recently updated first.

    Bypasses JiraClient.search_issues() because that helper drops issues without
    attachments, whereas the UI dropdown needs every Epic.
    """
    max_results = max(1, min(max_results, 500))

    try:
        client = _jira_client_from_request(request)
        issues = await asyncio.to_thread(
            client.search,
            "issuetype = Epic ORDER BY updated DESC",
            ["summary"],
            max_results,
        )

        epics = [
            {
                "key": issue.get("key", ""),
                "summary": issue.get("fields", {}).get("summary") or issue.get("key", ""),
            }
            for issue in issues
            if issue.get("key")
        ]

        logger.info("[JIRA] Fetched %d epic(s).", len(epics))
        return {"success": True, "epics": epics, "total": len(epics)}

    except HTTPException:
        raise
    except Exception as exc:
        return _error_response(request, exc, "Jira epic listing", status_code=502)


@app.get("/api/jira/epic/{issue_key}")
async def get_epic_details(issue_key: str, request: Request):
    """Fetch one Epic and classify its attachments into FRDs and test case suites."""
    issue_key = _validate_issue_key(issue_key)

    try:
        client = _jira_client_from_request(request)
        analyzer = _analyzer_from_request(request)

        raw_issue = await asyncio.to_thread(client.get_issue, issue_key)
        context = client.extract_context(raw_issue)
        analysis = await asyncio.to_thread(analyzer.classify, context)

        frds, test_cases = [], []
        for file in analysis.get("classified_files", []):
            item = {
                "id": file.get("id", ""),
                "name": file.get("original_filename", ""),
                "suggested_name": file.get("suggested_filename") or file.get("original_filename", ""),
                "reason": file.get("reason", ""),
            }
            category = file.get("category")
            if category == "FRD":
                frds.append(item)
            elif category == "MANUAL_TEST_CASES":
                test_cases.append(item)

        return {
            "success": True,
            "epic": {
                "id": issue_key,
                "name": context.get("summary", issue_key),
                "frds": frds,
                "manualTestCases": test_cases,
            },
        }

    except HTTPException:
        raise
    except (ValueError, PermissionError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        return _error_response(request, exc, "Jira epic fetch", status_code=502)


@app.post("/api/jira/evaluate")
async def evaluate_jira_epic(payload: JiraEpicRequest, request: Request):
    """
    Download an Epic's FRD and TC attachments into numbered input_modules folders.

    Each FRD is paired with the TC at the same index, and every pair gets its own
    folder so the directory-mode parser treats it as one module:

        input_modules/
            1/  FRD_filename.docx, TC_filename.docx
            2/  FRD_filename.docx, TC_filename.docx
    """
    issue_key = _validate_issue_key(payload.issue_key)

    try:
        client = _jira_client_from_request(request)
        analyzer = _analyzer_from_request(request)

        raw_issue = await asyncio.to_thread(client.get_issue, issue_key)
        context = client.extract_context(raw_issue)
        analysis = await asyncio.to_thread(analyzer.classify, context)

        classified_map = {
            str(item.get("id")): item for item in analysis.get("classified_files", [])
        }

        frd_attachments, tc_attachments = [], []
        for att in context.get("attachments", []):
            fname = att.get("filename", "")
            item = classified_map.get(str(att.get("id")))

            if item:
                category = item.get("category", "OTHER")
                suggested = item.get("suggested_filename") or fname
            else:
                rule_meta = analyzer.classify_single_file(fname)
                category = rule_meta["category"]
                suggested = rule_meta["suggested_filename"]

            att_info = {**att, "category": category, "sug_name": sanitize_filename(suggested or fname)}
            if category == "FRD":
                frd_attachments.append(att_info)
            elif category == "MANUAL_TEST_CASES":
                tc_attachments.append(att_info)

        if not frd_attachments and not tc_attachments:
            raise HTTPException(
                404,
                f"No FRD or test case attachments found on {issue_key}. "
                "Attach the documents to the Epic or its child issues.",
            )

        # Pair FRD[i] with TC[i]; a missing counterpart yields a partial pair.
        paired = [
            (
                frd_attachments[i] if i < len(frd_attachments) else None,
                tc_attachments[i] if i < len(tc_attachments) else None,
            )
            for i in range(max(len(frd_attachments), len(tc_attachments)))
        ]

        if payload.selected_frd_ids:
            selected = set(payload.selected_frd_ids)
            paired = [(frd, tc) for frd, tc in paired if frd and str(frd["id"]) in selected]
            if not paired:
                raise HTTPException(400, "None of the selected FRD IDs match this Epic's attachments.")

        try:
            existing_nums = [
                int(item.name) for item in INPUT_MODULES_DIR.iterdir()
                if item.is_dir() and item.name.isdigit()
            ]
        except OSError as exc:
            raise HTTPException(500, f"Cannot read {INPUT_MODULES_DIR.name}/: {exc}") from exc

        next_num = max(existing_nums, default=0) + 1
        downloaded_files = []
        folders_created = []

        for i, (frd, tc) in enumerate(paired):
            folder = INPUT_MODULES_DIR / str(next_num + i)
            folder.mkdir(parents=True, exist_ok=True)
            folder_had_download = False

            for att_info in filter(None, [frd, tc]):
                save_path = folder / att_info["sug_name"]
                try:
                    await asyncio.to_thread(
                        client.download_attachment, att_info["content_url"], str(save_path)
                    )
                except Exception as exc:
                    logger.error(
                        "[JIRA] Failed to download %s: %s", att_info.get("filename"), exc
                    )
                    continue

                folder_had_download = True
                downloaded_files.append({
                    "original_name": att_info.get("filename", ""),
                    "saved_name":    att_info["sug_name"],
                    "category":      att_info["category"],
                    "folder":        _relative_to_base(folder),
                    "path":          _relative_to_base(save_path),
                })
                logger.info(
                    "[JIRA] Downloaded [%s] %s -> %s",
                    att_info["category"], att_info.get("filename"), save_path,
                )

            if folder_had_download:
                folders_created.append(folder)

        if not downloaded_files:
            raise HTTPException(
                502, f"Could not download any attachments from {issue_key}. See server logs."
            )

        return {
            "success": True,
            "message": (
                f"Downloaded {len(downloaded_files)} file(s) into "
                f"{len(folders_created)} folder(s)."
            ),
            "folders": [_relative_to_base(f) for f in folders_created],
            "files": downloaded_files,
        }

    except HTTPException:
        raise
    except (ValueError, PermissionError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        return _error_response(request, exc, "Jira evaluation", status_code=502)


# ══════════════════════════════════════════════════════════════════════════════
# COST & TOKEN TRACKING
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/cost/metrics")
def get_cost_metrics():
    """Aggregated token usage and cost metrics, grouped by phase and API key."""
    return JSONResponse({"success": True, "metrics": parse_cost_log()})


@app.get("/api/cost/download-report")
def download_cost_report():
    """Generate and stream the cost audit report as a plain text file."""
    metrics = parse_cost_log()

    divider = "=" * 55
    lines = [
        divider,
        "             BAXTER AI COST & TOKEN AUDIT REPORT",
        divider,
        f"Generated: {datetime.datetime.now().strftime(const.LOG_DATE_FORMAT)}",
        f"Total LLM API Calls : {metrics['total_calls']}",
        f"Total Input Tokens  : {metrics['total_input_tokens']:,}",
        f"Total Output Tokens : {metrics['total_output_tokens']:,}",
        f"Total Combined      : {metrics['total_tokens']:,}",
        f"Grand Total Cost    : {metrics['total_cost_formatted']}",
        divider,
        "",
        "--- PHASE & AGENT BREAKDOWN ---",
    ]

    for phase in metrics["phases"]:
        lines.extend([
            f"\n  [{phase['phase']} Agent]",
            f"    Total Calls   : {phase['calls']}",
            f"    Models Used   : {', '.join(phase['models'])}",
            f"    Keys Used     : {', '.join(phase['keys'])}",
            f"    Input Tokens  : {phase['input_tokens']:,}",
            f"    Output Tokens : {phase['output_tokens']:,}",
            f"    Total Tokens  : {phase['total_tokens']:,}",
            f"    Phase Cost    : {phase['cost_formatted']}",
        ])

    lines.extend(["\n" + divider, "--- RECENT CALL LOGS (LATEST ENTRIES) ---"])
    for e in metrics["entries"]:
        lines.append(
            f"[{e['timestamp']}] [{e['phase']}] Model: {e['model']} ({e['key_alias']}) | "
            f"Tokens: {e['input_tokens']} In, {e['output_tokens']} Out | Cost: ${e['cost']:.6f}"
        )
    lines.append(divider + "\n")

    buf = BytesIO("\n".join(lines).encode("utf-8"))
    return StreamingResponse(
        buf,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=baxter_cost_token_report.txt"},
    )


# ─── ENTRYPOINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    logger.info(
        "Starting Baxter API on %s:%d (reload=%s, log_level=%s)",
        const.SERVER_HOST, const.SERVER_PORT, const.SERVER_RELOAD, const.LOG_LEVEL,
    )

    uvicorn.run(
        "server:app",
        host=const.SERVER_HOST,
        port=const.SERVER_PORT,
        # Auto-reload is a development convenience and must stay off by default;
        # it spawns a file watcher and reloads workers mid-request.
        reload=const.SERVER_RELOAD,
        reload_includes=["server.py", "agents/*.py", "core/*.py"] if const.SERVER_RELOAD else None,
    )
