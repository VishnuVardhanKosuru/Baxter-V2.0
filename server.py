"""
server.py
─────────
FastAPI Backend Server for Baxter Test Case Generator & Document Parser.
Integrates doc_parser agent with the React UI.
"""

import os
import sys
import json
import shutil
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse

BASE_DIR = Path(__file__).parent.resolve()
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Baxter Parser API", version="1.0.0")

# Enable CORS for local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Baxter Parser API"}


@app.post("/api/parse")
async def parse_documents(
    frd_file: Optional[UploadFile] = File(None),
    tc_file: Optional[UploadFile] = File(None),
    use_sample: bool = Form(False)
):
    """
    Parses FRD (.docx) and Test Cases (.docx) files.
    Generates output JSON files inside output/ folder.
    """
    try:
        frd_path = None
        tc_path = None

        if use_sample or (not frd_file and not tc_file):
            # Fallback to local sample documents in Baxter root
            sample_frd = BASE_DIR / "ShopSphere_Functional_Requirements_Document.docx"
            sample_tc = BASE_DIR / "ShopSphere_Manual_Testcases.docx"
            
            if not sample_frd.exists() or not sample_tc.exists():
                raise HTTPException(
                    status_code=400,
                    detail="Sample documents not found in workspace."
                )
            frd_path = str(sample_frd)
            tc_path = str(sample_tc)
        else:
            if not frd_file or not tc_file:
                raise HTTPException(
                    status_code=400,
                    detail="Both FRD (.docx) and Test Cases (.docx) files are required."
                )

            # Save uploaded files
            frd_path = str(UPLOADS_DIR / frd_file.filename)
            tc_path = str(UPLOADS_DIR / tc_file.filename)

            with open(frd_path, "wb") as f:
                content = await frd_file.read()
                f.write(content)

            with open(tc_path, "wb") as f:
                content = await tc_file.read()
                f.write(content)

        # Run agents/doc_parser.py script
        parser_script = BASE_DIR / "agents" / "doc_parser.py"
        cmd = [
            sys.executable,
            str(parser_script),
            "--frd", frd_path,
            "--tc", tc_path,
            "--out", str(OUTPUT_DIR)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR)
        )

        if result.returncode != 0:
            print("Parser error output:", result.stderr)
            raise HTTPException(
                status_code=500,
                detail=f"Parser execution failed: {result.stderr or result.stdout}"
            )

        # Find generated JSON file in output directory
        json_files = list(OUTPUT_DIR.glob("*.json"))
        if not json_files:
            raise HTTPException(
                status_code=500,
                detail="Parser completed but no JSON output was generated in output folder."
            )

        # Get latest generated JSON
        latest_json = max(json_files, key=os.path.getmtime)

        with open(latest_json, "r", encoding="utf-8") as f:
            parsed_data = json.load(f)

        # Calculate metrics summary
        test_cases = parsed_data.get("test_cases", [])
        total_tc = len(test_cases)
        
        # Extract unique feature IDs
        feature_ids = set()
        for tc in test_cases:
            f_ref = tc.get("feature_ref")
            if f_ref:
                feature_ids.add(f_ref)

        return JSONResponse(content={
            "success": True,
            "message": "Documents parsed and output generated successfully.",
            "output_file": str(latest_json.relative_to(BASE_DIR)),
            "summary": {
                "total_test_cases": total_tc,
                "total_features": len(feature_ids),
                "project": parsed_data.get("project", "Baxter Test Suite"),
                "version": parsed_data.get("version", "1.0")
            },
            "data": parsed_data
        })

    except HTTPException as he:
        raise he
    except Exception as e:
        print("Error during document evaluation:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download-zip")
def download_zip():
    """Compresses all files in output/ folder into a zip and serves for download."""
    json_files = list(OUTPUT_DIR.glob("*"))
    if not json_files:
        raise HTTPException(status_code=404, detail="No output files available to download.")

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in OUTPUT_DIR.glob("*"):
            if file_path.is_file():
                zip_file.write(file_path, arcname=file_path.name)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=baxter_output.zip"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=5000, reload=True)
