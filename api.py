from __future__ import annotations

from io import BytesIO
from typing import Dict, Any
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from tasks import create_job_from_dataframe, read_job_status
from tasks import _output_path  # type: ignore[attr-defined]
from tasks import process_catalog_job


app = FastAPI(title="Catalog Processing API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Backend is running."""
    return {"status": "ok"}


@app.get("/jobs")
async def jobs_list_disallowed():
    """GET /jobs is not supported; use POST /jobs to create, GET /jobs/{job_id} for status."""
    raise HTTPException(status_code=405, detail="Method Not Allowed. Use POST /jobs to create a job, GET /jobs/{job_id} for status.")


@app.post("/jobs", response_model=Dict[str, Any])
async def create_job(
    file: UploadFile = File(...),
    language: str = Form("tr"),
) -> Dict[str, Any]:
    """
    Create a new processing job from an uploaded Excel file.
    language: output language for Gemini (tr, en, de, it). Default: tr
    """
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx / .xls files are supported")

    lang = (language or "tr").strip().lower()
    if lang not in ("tr", "en", "de", "it"):
        lang = "tr"

    try:
        content = await file.read()
        df = pd.read_excel(BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read Excel: {exc}") from exc

    job_id = create_job_from_dataframe(df, language=lang)

    # Fire-and-forget Celery task
    process_catalog_job.delay(job_id)

    status = read_job_status(job_id)
    return status


@app.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Return status for a given job_id (progress, percentages, etc.).
    """
    if not (job_id or "").strip():
        raise HTTPException(status_code=400, detail="job_id required")
    try:
        status = read_job_status(job_id.strip())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


@app.get("/jobs/{job_id}/download")
async def download_result(job_id: str):
    """
    Download the processed Excel file for the given job.
    """
    if not (job_id or "").strip():
        raise HTTPException(status_code=400, detail="job_id required")
    output_path: Path = _output_path(job_id.strip())  # type: ignore[assignment]
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Result file not ready yet")

    return FileResponse(
        path=str(output_path),
        filename=f"cleaned_catalog_{job_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

