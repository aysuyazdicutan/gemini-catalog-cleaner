from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # Worker'ın .env okuması için (proje klasöründen çalıştır)

from celery_app import celery_app


# Her zaman tasks.py'nin olduğu klasör (API ve Celery aynı jobs/ kullanır)
BASE_DIR = Path(__file__).resolve().parent
JOBS_DIR = BASE_DIR / "jobs"
JOBS_DIR.mkdir(exist_ok=True)


def _job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def _status_path(job_id: str) -> Path:
    return _job_dir(job_id) / "status.csv"


def _output_path(job_id: str) -> Path:
    return _job_dir(job_id) / "output.xlsx"


def _input_path(job_id: str) -> Path:
    return _job_dir(job_id) / "input.xlsx"


def create_job_from_dataframe(df: pd.DataFrame) -> str:
    """
    Persist uploaded DataFrame as a new job and return job_id.
    """
    job_id = uuid.uuid4().hex
    job_path = _job_dir(job_id)
    job_path.mkdir(parents=True, exist_ok=True)

    # Save raw input
    df.to_excel(_input_path(job_id), index=False)

    # Initialize empty status file – one row = one product
    status_df = pd.DataFrame(
        {
            "index": range(len(df)),
            "processed": False,
            "sku": df.get("SHOP_SKU", pd.Series([None] * len(df))).astype(str),
        }
    )
    status_df.to_csv(_status_path(job_id), index=False)

    return job_id


def read_job_status(job_id: str) -> Dict[str, Any]:
    """
    Return simple status information for the given job_id.
    """
    status_file = _status_path(job_id)
    if not status_file.exists():
        raise FileNotFoundError(f"Status file not found for job {job_id}")

    status_df = pd.read_csv(status_file)
    total = len(status_df)
    # CSV may store "True"/"False" as strings
    proc = status_df["processed"]
    is_done = (proc == True) | (proc.astype(str).str.lower() == "true")
    processed = int(is_done.sum())

    result: Dict[str, Any] = {
        "job_id": job_id,
        "total": total,
        "processed": processed,
        "remaining": total - processed,
        "percentage": round((processed / total * 100) if total > 0 else 0.0, 1),
        "is_complete": processed >= total,
    }

    if _output_path(job_id).exists():
        result["output_ready"] = True
    else:
        result["output_ready"] = False

    return result


@celery_app.task(name="process_catalog_job")
def process_catalog_job(job_id: str) -> Dict[str, Any]:
    """
    Celery task that processes a single Excel upload job.
    Progress is tracked via a per-row CSV; Streamlit/FastAPI poll for status.
    """
    import sys
    _project_root = Path(__file__).resolve().parent
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from main import urun_isle

    input_file = _input_path(job_id)
    status_file = _status_path(job_id)

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found for job {job_id}")

    df = pd.read_excel(input_file)
    print(f"[Job {job_id}] Başladı: toplam {len(df)} ürün", flush=True)

    # Skip technical header row if present
    if len(df) > 0 and "Başlık" in df.columns:
        first_title = str(df.iloc[0].get("Başlık", ""))
        if first_title.startswith("TITLE"):
            df = df.iloc[1:].reset_index(drop=True)

    status_df = pd.read_csv(status_file)
    proc = status_df["processed"]
    is_done = (proc == True) | (proc.astype(str).str.lower() == "true")
    processed_indices = set(status_df.loc[is_done, "index"].tolist())

    results: List[Dict[str, Any]] = []

    if _output_path(job_id).exists():
        existing = pd.read_excel(_output_path(job_id))
        results = existing.to_dict("records")

    total_rows = len(df)
    for idx, row in df.iterrows():
        if idx in processed_indices:
            continue

        # Railway/logda ilerleme görünsün
        done_so_far = len(results)
        print(f"[Job {job_id}] İşleniyor: satır {done_so_far + 1}/{total_rows} (index={idx})", flush=True)

        row_dict = row.to_dict()
        gemini_output = urun_isle(row_dict)

        flat_result = row_dict.copy()
        flat_result["Başlık"] = gemini_output.get(
            "temiz_baslik", row_dict.get("Başlık", "")
        )

        # Optional: extract structured features from 'duzenlenmis_ozellikler'
        features = gemini_output.get("duzenlenmis_ozellikler", {})
        for key, val in features.items():
            if key == "RAM":
                flat_result["RAM Bellek Boyutu"] = val
            if key == "Disk":
                flat_result["Sabit disk kapasitesi"] = val

        flat_result["Warning"] = gemini_output.get("uyari", "")
        results.append(flat_result)

        # Mark this row as processed and persist incremental progress
        status_df.loc[status_df["index"] == idx, "processed"] = True
        status_df.to_csv(status_file, index=False)
        pd.DataFrame(results).to_excel(_output_path(job_id), index=False)

    return read_job_status(job_id)

