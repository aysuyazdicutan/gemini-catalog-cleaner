from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Tuple

import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # Worker'ın .env okuması için (proje klasöründen çalıştır)

from celery_app import celery_app


# Job dosyaları: varsayılan proje içi; Railway'de Volume kullanmak için JOBS_BASE_DIR ile kalıcı yol ver
BASE_DIR = Path(__file__).resolve().parent
JOBS_DIR = Path(os.getenv("JOBS_BASE_DIR", str(BASE_DIR / "jobs")))
JOBS_DIR.mkdir(parents=True, exist_ok=True)


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


# Excel sütun eşlemesi (process_single_product için)
GEMINI_TO_EXCEL = {
    "RAM": "RAM Bellek Boyutu",
    "RAM_Boyutu": "RAM Bellek Boyutu",
    "Disk": "Sabit disk kapasitesi",
    "Disk_Kapasitesi": "Sabit disk kapasitesi",
    "Disk_Tipi": "Sabit disk tipi",
    "RAM_Tipi": "RAM Tipi",
    "Renk_Temel": "Renk (temel)",
    "Renk": "Renk (temel)",
    "Renk_Uretici": "Renk (Üreticiye Göre) (tr_TR)",
    "Isletim_Sistemi": "İşletim Sistemi",
    "Grafik_Karti": "Grafik Kartı",
    "Islemci_Modeli": "İşlemci (tr_TR)",
    "Ekran_Boyutu_Inc": "Ekran Boyutu (inç)",
    "Ekran_Boyutu_cm": "Ekran boyutu(cm)",
    "Kutu_Icerigi": "Kutu İçeriği (tr_TR)",
    "Kapasite": "Kapasite",
    "Guc": "Güç",
    "Frekans": "Frekans",
    "Voltaj": "Voltaj",
    "Urun_Tipi": "Ürün Tipi",
}
TERS_HARITA = {
    "Isletim_Sistemi": "İşletim Sistemi",
    "Renk_Temel": "Renk (temel)",
    "Renk_Uretici": "Renk (Üreticiye Göre) (tr_TR)",
    "RAM_Boyutu": "RAM Bellek Boyutu",
    "Disk_Kapasitesi": "Sabit disk kapasitesi",
    "Ekran_Boyutu_Inc": "Ekran Boyutu (inç)",
    "Grafik_Karti": "Grafik Kartı",
    "Islemci_Modeli": "İşlemci (tr_TR)",
    "Urun_Tipi": "Ürün Tipi (tr_TR)",
}


def _process_single_product(idx: int, row_dict: Dict[str, Any], eksik_sutunlar: List[str]) -> Tuple[int, Dict[str, Any]]:
    """
    Tek ürünü işler, (idx, flat_result) döner. ThreadPoolExecutor ile paralel çağrılabilir.
    """
    from main import urun_isle

    gemini_output = urun_isle(row_dict, eksik_sutunlar=eksik_sutunlar if eksik_sutunlar else None)
    features = gemini_output.get("duzenlenmis_ozellikler") or {}

    flat_result = row_dict.copy()
    flat_result["Başlık"] = gemini_output.get("temiz_baslik", row_dict.get("Başlık", ""))

    for key, val in features.items():
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        col = GEMINI_TO_EXCEL.get(key)
        if col and col in flat_result:
            flat_result[col] = val
        elif key in flat_result:
            flat_result[key] = val

    yeni_uyari = gemini_output.get("uyari", "")

    celiski_cozum = gemini_output.get("celiski_cozum")
    if celiski_cozum and isinstance(celiski_cozum, dict):
        ozellik_adi = celiski_cozum.get("ozellik_adi", "")
        dogru_deger = celiski_cozum.get("dogru_deger", "")
        excel_sutun = TERS_HARITA.get(ozellik_adi)
        if excel_sutun and excel_sutun in flat_result and dogru_deger:
            flat_result[excel_sutun] = dogru_deger
            yeni_uyari = f"Çözüldü: {ozellik_adi} = {dogru_deger}"

    flat_result["Warning"] = yeni_uyari if yeni_uyari and yeni_uyari != "null" else ""

    eksik_degerler = gemini_output.get("eksik_sutun_degerleri") or {}
    if isinstance(eksik_degerler, dict):
        for sutun, deger in eksik_degerler.items():
            if sutun in flat_result and deger and (
                not isinstance(deger, str) or "bilinmiyor" not in str(deger).lower()
            ):
                flat_result[sutun] = str(deger).strip() if isinstance(deger, str) else deger

    return (idx, flat_result)


@celery_app.task(name="process_catalog_job")
def process_catalog_job(job_id: str) -> Dict[str, Any]:
    """
    Celery task that processes a single Excel upload job.
    Progress is tracked via a per-row CSV; Streamlit/FastAPI poll for status.
    Uses ThreadPoolExecutor for parallel product processing (GEMINI_PARALLEL_WORKERS, default 5).
    """
    import sys
    _project_root = Path(__file__).resolve().parent
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))

    input_file = _input_path(job_id)
    status_file = _status_path(job_id)

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found for job {job_id}")

    df = pd.read_excel(input_file)
    total_rows = len(df)
    print(f"[Job {job_id}] Başladı: toplam {total_rows} ürün (paralel workers: {os.getenv('GEMINI_PARALLEL_WORKERS', '5')})", flush=True)

    # Skip technical header row if present
    if total_rows > 0 and "Başlık" in df.columns:
        first_title = str(df.iloc[0].get("Başlık", ""))
        if first_title.startswith("TITLE"):
            df = df.iloc[1:].reset_index(drop=True)
            total_rows = len(df)

    status_df = pd.read_csv(status_file)
    proc = status_df["processed"]
    is_done = (proc == True) | (proc.astype(str).str.lower() == "true")
    processed_indices = set(int(x) for x in status_df.loc[is_done, "index"].tolist())

    # results_by_idx: index -> flat_result (orijinal sırayı korumak için)
    results_by_idx: Dict[int, Dict[str, Any]] = {}
    if _output_path(job_id).exists():
        existing = pd.read_excel(_output_path(job_id))
        existing_records = existing.to_dict("records")
        sorted_done = sorted(processed_indices)
        for i, idx in enumerate(sorted_done):
            if i < len(existing_records):
                results_by_idx[idx] = existing_records[i]

    # İşlenecek ürünleri topla: (idx, row_dict, eksik_sutunlar)
    atlanacak_sutunlar = {"Başlık", "SHOP_SKU", "Warning", "Uyari", "Kategori"}
    to_process: List[Tuple[int, Dict[str, Any], List[str]]] = []
    for idx, row in df.iterrows():
        idx = int(idx)
        if idx in processed_indices:
            continue
        row_dict = row.to_dict()
        eksik_sutunlar = []
        if os.getenv("GEMINI_EKSIK_SUTUN", "1") == "1":
            for sutun_adi in row_dict.keys():
                if sutun_adi in atlanacak_sutunlar:
                    continue
                mevcut = row_dict.get(sutun_adi, None)
                if pd.notna(mevcut) and (not isinstance(mevcut, str) or str(mevcut).strip() != ""):
                    continue
                eksik_sutunlar.append(sutun_adi)
        to_process.append((idx, row_dict, eksik_sutunlar))

    parallel_workers = int(os.getenv("GEMINI_PARALLEL_WORKERS", "5"))
    parallel_workers = max(1, min(parallel_workers, 15))

    with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        futures = {
            executor.submit(_process_single_product, idx, row_dict, eksik_sutunlar): idx
            for idx, row_dict, eksik_sutunlar in to_process
        }
        batch_count = 0
        for future in as_completed(futures):
            try:
                idx, flat_result = future.result()
                results_by_idx[idx] = flat_result
                processed_indices.add(idx)
                batch_count += 1
                if batch_count % 10 == 0 or batch_count == len(to_process):
                    print(f"[Job {job_id}] İşlendi: {len(results_by_idx)}/{total_rows}", flush=True)
            except Exception as e:
                orig_idx = futures[future]
                print(f"[Job {job_id}] Hata (index={orig_idx}): {str(e)[:100]}", flush=True)
                # Hata olan ürün için orijinal veri + uyarı ile placeholder ekle
                for tidx, trow, _ in to_process:
                    if tidx == orig_idx:
                        fallback = trow.copy()
                        fallback["Warning"] = f"İşleme hatası: {str(e)[:150]}"
                        results_by_idx[orig_idx] = fallback
                        break

            # Her batch sonrası status ve Excel güncelle (her 10 üründe veya tamamlandığında)
            if batch_count % 10 == 0 or batch_count == len(to_process):
                status_df.loc[status_df["index"].isin(results_by_idx.keys()), "processed"] = True
                status_df.to_csv(status_file, index=False)
                ordered = [results_by_idx[i] for i in sorted(results_by_idx.keys())]
                if ordered:
                    pd.DataFrame(ordered).to_excel(_output_path(job_id), index=False)

    # Son Excel yazımı
    if results_by_idx:
        ordered = [results_by_idx[i] for i in sorted(results_by_idx.keys())]
        pd.DataFrame(ordered).to_excel(_output_path(job_id), index=False)

    return read_job_status(job_id)

