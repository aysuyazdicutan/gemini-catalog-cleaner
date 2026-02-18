from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List

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
    from main import urun_isle, gemini_eksik_sutun_sor, gemini_celiskic_coz

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
        features = gemini_output.get("duzenlenmis_ozellikler") or {}

        flat_result = row_dict.copy()
        flat_result["Başlık"] = gemini_output.get(
            "temiz_baslik", row_dict.get("Başlık", "")
        )

        # Gemini'den gelen tüm özellikleri Excel sütun adlarına yaz (boş çıktı önlenir)
        gemini_to_excel = {
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
        for key, val in features.items():
            if val is None or (isinstance(val, str) and not val.strip()):
                continue
            col = gemini_to_excel.get(key)
            if col and col in flat_result:
                flat_result[col] = val
            elif key in flat_result:
                flat_result[key] = val

        yeni_uyari = gemini_output.get("uyari", "")

        # Çelişki varsa gemini_celiskic_coz ile çöz
        if pd.notna(yeni_uyari) and yeni_uyari and yeni_uyari != "null":
            if "çelişki" in str(yeni_uyari).lower() or "uyuşmazlık" in str(yeni_uyari).lower() or "çeliş" in str(yeni_uyari).lower():
                try:
                    celiski_sonuc = gemini_celiskic_coz(
                        urun_adi=row_dict.get("Başlık", ""),
                        uyari_metni=yeni_uyari,
                        baslik_degeri=flat_result.get("Başlık", ""),
                        ozellik_dict=features,
                        marka=row_dict.get("Marka"),
                    )
                    if celiski_sonuc:
                        ozellik_adi = celiski_sonuc.get("ozellik_adi", "")
                        dogru_deger = celiski_sonuc.get("dogru_deger", "")
                        ters_harita = {
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
                        excel_sutun = ters_harita.get(ozellik_adi)
                        if excel_sutun and excel_sutun in flat_result:
                            flat_result[excel_sutun] = dogru_deger
                            yeni_uyari = f"Çözüldü: {ozellik_adi} = {dogru_deger}"
                except Exception as e:
                    print(f"  ⚠️ Çelişki çözme hatası: {str(e)[:100]}", flush=True)

        flat_result["Warning"] = yeni_uyari if yeni_uyari and yeni_uyari != "null" else ""

        # Eksik (boş) sütunlar için gemini_eksik_sutun_sor
        atlanacak_sutunlar = {"Başlık", "SHOP_SKU", "Warning", "Uyari", "Kategori"}
        urun_adi = row_dict.get("Başlık", "")
        marka = row_dict.get("Marka", "")

        for sutun_adi in flat_result.keys():
            if sutun_adi in atlanacak_sutunlar:
                continue
            mevcut = flat_result.get(sutun_adi, None)
            if pd.notna(mevcut) and (not isinstance(mevcut, str) or mevcut.strip() != ""):
                continue
            try:
                bulunan = gemini_eksik_sutun_sor(
                    urun_adi=urun_adi,
                    eksik_sutun_basligi=sutun_adi,
                    marka=marka,
                )
                if bulunan:
                    flat_result[sutun_adi] = bulunan
                time.sleep(1)
            except Exception as e:
                print(f"  ⚠️ Gemini eksik sütun hatası ({sutun_adi}): {str(e)[:80]}", flush=True)

        results.append(flat_result)

        # Mark this row as processed and persist status (her satırda)
        status_df.loc[status_df["index"] == idx, "processed"] = True
        status_df.to_csv(status_file, index=False)

        # Excel: her 20 satırda bir batch yaz (her satırda yazma - performans)
        if len(results) % 20 == 0:
            pd.DataFrame(results).to_excel(_output_path(job_id), index=False)

    # İşlem bittiğinde son Excel yazımı (kalan satırlar için)
    if results:
        pd.DataFrame(results).to_excel(_output_path(job_id), index=False)

    return read_job_status(job_id)

