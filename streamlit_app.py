import streamlit as st
import pandas as pd
import os
import io
import time
import requests

# Page Configuration
st.set_page_config(
    page_title="Product Catalog Cleaning",
    page_icon="📦",
    layout="wide"
)

st.title("📦 Product Catalog Cleaning Tool")
st.markdown("""
This tool is designed to handle long-running processes (e.g., 1000+ products). 
Even if the page refreshes, you can continue where you left off. 
Your data is saved instantly as each product is processed.
""")

# --- SESSION STATE ---
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "job_status" not in st.session_state:
    st.session_state.job_status = None
if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None

# Streamlit Cloud'da st.secrets, local'de .env / BACKEND_URL
_backend = "http://localhost:8000"
if hasattr(st, "secrets") and st.secrets.get("BACKEND_URL"):
    _backend = st.secrets["BACKEND_URL"]
else:
    _backend = os.getenv("BACKEND_URL", _backend)
backend_url = _backend.rstrip("/")

# --- BACKEND CHECK ---
def backend_reachable():
    try:
        r = requests.get(f"{backend_url}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

with st.sidebar:
    st.subheader("⚙️ Backend")
    st.caption(f"URL: `{backend_url}`")
    if backend_reachable():
        st.success("✅ API bağlı")
    else:
        st.error("❌ API’ye ulaşılamıyor. Önce şunları çalıştır:\n1. Redis\n2. `uvicorn api:app --reload`\n3. `celery -A celery_app.celery_app worker --loglevel=info`")

# --- FILE UPLOAD & START JOB ---
uploaded_file = st.file_uploader("Excel dosyası yükle", type=["xlsx", "xls"])

if uploaded_file is not None:
    st.info("📁 Dosya seçildi. İşlemi başlatmak için butona bas.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 İşlemi Başlat / Devam", type="primary", use_container_width=True):
            try:
                existing_id = (st.session_state.job_id or "").strip()
                if existing_id and existing_id != "None":
                    # Sadece geçerli job_id ile GET; yoksa yeni job oluştur
                    resp = requests.get(f"{backend_url}/jobs/{existing_id}", timeout=30)
                    resp.raise_for_status()
                    st.session_state.job_status = resp.json()
                else:
                    file_bytes = uploaded_file.getvalue()
                    files = {
                        "file": (
                            uploaded_file.name,
                            file_bytes,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    }
                    resp = requests.post(f"{backend_url}/jobs", files=files, timeout=60)
                    resp.raise_for_status()
                    data = resp.json()
                    new_id = (data.get("job_id") or "").strip()
                    if new_id:
                        st.session_state.job_id = new_id
                        st.session_state.job_status = data
                        st.session_state.uploaded_file_name = uploaded_file.name
                    else:
                        st.error("❌ Backend job_id döndürmedi.")
                st.success("✅ İş backend’e gönderildi. Aşağıda durumu görebilirsin.")
                st.rerun()
            except requests.exceptions.ConnectionError:
                st.error(f"❌ Backend’e bağlanılamadı. {backend_url} çalışıyor mu? (uvicorn api:app --reload)")
            except Exception as e:
                st.error(f"❌ Hata: {e}")

    with col2:
        if st.button("🗑️ Job’u Sıfırla", use_container_width=True):
            st.session_state.job_id = None
            st.session_state.job_status = None
            st.session_state.uploaded_file_name = None
            st.rerun()

# --- JOB STATUS (show even when no file selected) ---
job_id = (st.session_state.job_id or "").strip()
if job_id:
    st.divider()
    st.subheader("📊 İş durumu")

    # Refresh status (only with valid job_id so we never GET /jobs)
    try:
        resp = requests.get(f"{backend_url}/jobs/{job_id}", timeout=30)
        resp.raise_for_status()
        st.session_state.job_status = resp.json()
    except Exception:
        pass

    status = st.session_state.job_status or {}
    if status:
        total = status.get("total", 0)
        processed = status.get("processed", 0)
        percentage = status.get("percentage", 0.0)
        if st.session_state.get("uploaded_file_name"):
            st.caption(f"📄 Dosya: {st.session_state.uploaded_file_name}")
        st.write(f"**Job ID:** `{job_id}`")
        st.write(f"**Toplam:** {total} ürün | **İşlenen:** {processed} (%{percentage})")

        # Streamlit progress 0.0 - 1.0
        st.progress(min(percentage / 100.0, 1.0))

        if status.get("is_complete"):
            st.success("✅ İşlem tamamlandı.")
        else:
            st.caption("İşlem arka planda (Celery worker) yapılıyor. İlerleme için **Durumu yenile** butonuna bas.")
            if processed == 0 and total > 0:
                st.warning("İlerleme hâlâ 0 mı? Celery worker terminalinde şunu çalıştır: `celery -A celery_app.celery_app worker --loglevel=info` — 'Task process_catalog_job received' görünmeli.")

    if st.button("🔄 Durumu yenile"):
        try:
            resp = requests.get(f"{backend_url}/jobs/{job_id}", timeout=30)
            resp.raise_for_status()
            st.session_state.job_status = resp.json()
            st.rerun()
        except Exception as e:
            st.error(f"❌ Yenileme hatası: {e}")

    # Download when ready
    if status.get("output_ready"):
        try:
            result_resp = requests.get(
                f"{backend_url}/jobs/{job_id}/download",
                timeout=120,
            )
            result_resp.raise_for_status()
            buffer = io.BytesIO(result_resp.content)
            res_df = pd.read_excel(buffer)

            st.subheader(f"📊 İşlenen veri ({len(res_df)} ürün)")
            st.dataframe(res_df, use_container_width=True)

            buffer.seek(0)
            st.download_button(
                label="📥 Temiz katalogu indir",
                data=buffer,
                file_name=f"cleaned_catalog_{job_id}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        except Exception as e:
            st.error(f"❌ İndirme hatası: {e}")
