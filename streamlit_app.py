import streamlit as st
import pandas as pd
import os
import io
import requests

# --- ÇOK DİLLİ DESTEK ---
TRANSLATIONS = {
    "tr": {
        "title": "📦 Ürün Katalog Temizleme Aracı",
        "subtitle": "Bu araç uzun süren işlemleri (örn. 1000+ ürün) destekler. Sayfa yenilense bile kaldığınız yerden devam edebilirsiniz. Verileriniz her ürün işlendiğinde anında kaydedilir.",
        "backend": "⚙️ Backend",
        "api_connected": "✅ API bağlı",
        "api_error": "❌ API'ye ulaşılamıyor. Önce şunları çalıştır:\n1. Redis\n2. `uvicorn api:app --reload`\n3. `celery -A celery_app.celery_app worker --loglevel=info`",
        "language": "🌐 Dil",
        "lang_desc": "Arayüz ve Gemini çıktı dili",
        "upload": "Excel dosyası yükle",
        "file_selected": "📁 Dosya seçildi. İşlemi başlatmak için butona bas.",
        "start": "🚀 İşlemi Başlat / Devam",
        "reset": "🗑️ Job'u Sıfırla",
        "job_sent": "✅ İş backend'e gönderildi. Aşağıda durumu görebilirsin.",
        "backend_error": "❌ Backend'e bağlanılamadı.",
        "error": "❌ Hata",
        "status": "📊 İş durumu",
        "file": "📄 Dosya",
        "total": "Toplam",
        "processed": "İşlenen",
        "products": "ürün",
        "complete": "✅ İşlem tamamlandı.",
        "in_progress": "İşlem arka planda (Celery worker) yapılıyor. İlerleme için **Durumu yenile** butonuna bas.",
        "progress_warning": "İlerleme hâlâ 0 mı? Celery worker terminalinde şunu çalıştır: `celery -A celery_app.celery_app worker --loglevel=info` — 'Task process_catalog_job received' görünmeli.",
        "refresh": "🔄 Durumu yenile",
        "refresh_error": "❌ Yenileme hatası",
        "processed_data": "📊 İşlenen veri",
        "download": "📥 Temiz katalogu indir",
        "download_error": "❌ İndirme hatası",
    },
    "en": {
        "title": "📦 Product Catalog Cleaning Tool",
        "subtitle": "This tool handles long-running processes (e.g. 1000+ products). Even if the page refreshes, you can continue where you left off. Your data is saved instantly as each product is processed.",
        "backend": "⚙️ Backend",
        "api_connected": "✅ API connected",
        "api_error": "❌ Cannot reach API. Run these first:\n1. Redis\n2. `uvicorn api:app --reload`\n3. `celery -A celery_app.celery_app worker --loglevel=info`",
        "language": "🌐 Language",
        "lang_desc": "UI and Gemini output language",
        "upload": "Upload Excel file",
        "file_selected": "📁 File selected. Click the button to start processing.",
        "start": "🚀 Start / Continue",
        "reset": "🗑️ Reset Job",
        "job_sent": "✅ Job sent to backend. You can see the status below.",
        "backend_error": "❌ Could not connect to backend.",
        "error": "❌ Error",
        "status": "📊 Job status",
        "file": "📄 File",
        "total": "Total",
        "processed": "Processed",
        "products": "products",
        "complete": "✅ Processing complete.",
        "in_progress": "Processing in background (Celery worker). Click **Refresh status** for progress.",
        "progress_warning": "Still 0 progress? Run in Celery worker terminal: `celery -A celery_app.celery_app worker --loglevel=info` — you should see 'Task process_catalog_job received'.",
        "refresh": "🔄 Refresh status",
        "refresh_error": "❌ Refresh error",
        "processed_data": "📊 Processed data",
        "download": "📥 Download cleaned catalog",
        "download_error": "❌ Download error",
    },
    "de": {
        "title": "📦 Produktkatalog-Bereinigungs-Tool",
        "subtitle": "Dieses Tool verarbeitet lang laufende Prozesse (z. B. 1000+ Produkte). Selbst bei Seitenaktualisierung können Sie dort weitermachen. Ihre Daten werden bei jeder Produktverarbeitung sofort gespeichert.",
        "backend": "⚙️ Backend",
        "api_connected": "✅ API verbunden",
        "api_error": "❌ API nicht erreichbar. Zuerst starten:\n1. Redis\n2. `uvicorn api:app --reload`\n3. `celery -A celery_app.celery_app worker --loglevel=info`",
        "language": "🌐 Sprache",
        "lang_desc": "Oberfläche und Gemini-Ausgabesprache",
        "upload": "Excel-Datei hochladen",
        "file_selected": "📁 Datei ausgewählt. Klicken Sie zum Starten auf die Schaltfläche.",
        "start": "🚀 Starten / Fortsetzen",
        "reset": "🗑️ Job zurücksetzen",
        "job_sent": "✅ Job an Backend gesendet. Status unten sichtbar.",
        "backend_error": "❌ Verbindung zum Backend fehlgeschlagen.",
        "error": "❌ Fehler",
        "status": "📊 Job-Status",
        "file": "📄 Datei",
        "total": "Gesamt",
        "processed": "Verarbeitet",
        "products": "Produkte",
        "complete": "✅ Verarbeitung abgeschlossen.",
        "in_progress": "Verarbeitung läuft im Hintergrund (Celery worker). Klicken Sie auf **Status aktualisieren**.",
        "progress_warning": "Immer noch 0 Fortschritt? Im Celery-Terminal ausführen: `celery -A celery_app.celery_app worker --loglevel=info`",
        "refresh": "🔄 Status aktualisieren",
        "refresh_error": "❌ Aktualisierungsfehler",
        "processed_data": "📊 Verarbeitete Daten",
        "download": "📥 Bereinigten Katalog herunterladen",
        "download_error": "❌ Download-Fehler",
    },
    "it": {
        "title": "📦 Strumento per la pulizia del catalogo prodotti",
        "subtitle": "Questo strumento gestisce processi lunghi (es. 1000+ prodotti). Anche se la pagina si ricarica, puoi continuare da dove eri rimasto. I dati vengono salvati istantaneamente ad ogni prodotto elaborato.",
        "backend": "⚙️ Backend",
        "api_connected": "✅ API connessa",
        "api_error": "❌ Impossibile raggiungere l'API. Eseguire prima:\n1. Redis\n2. `uvicorn api:app --reload`\n3. `celery -A celery_app.celery_app worker --loglevel=info`",
        "language": "🌐 Lingua",
        "lang_desc": "Lingua dell'interfaccia e output Gemini",
        "upload": "Carica file Excel",
        "file_selected": "📁 File selezionato. Clicca il pulsante per avviare.",
        "start": "🚀 Avvia / Continua",
        "reset": "🗑️ Reset Job",
        "job_sent": "✅ Job inviato al backend. Lo stato è visibile sotto.",
        "backend_error": "❌ Connessione al backend fallita.",
        "error": "❌ Errore",
        "status": "📊 Stato del job",
        "file": "📄 File",
        "total": "Totale",
        "processed": "Elaborati",
        "products": "prodotti",
        "complete": "✅ Elaborazione completata.",
        "in_progress": "Elaborazione in background (Celery worker). Clicca **Aggiorna stato** per il progresso.",
        "progress_warning": "Ancora 0 progresso? Eseguire: `celery -A celery_app.celery_app worker --loglevel=info`",
        "refresh": "🔄 Aggiorna stato",
        "refresh_error": "❌ Errore di aggiornamento",
        "processed_data": "📊 Dati elaborati",
        "download": "📥 Scarica catalogo pulito",
        "download_error": "❌ Errore download",
    },
}

LANG_OPTIONS = {"tr": "🇹🇷 Türkçe", "en": "🇬🇧 English", "de": "🇩🇪 Deutsch", "it": "🇮🇹 Italiano"}


def t(key: str, lang: str = "tr") -> str:
    return TRANSLATIONS.get(lang, TRANSLATIONS["tr"]).get(key, key)


# Page Configuration
st.set_page_config(
    page_title="Product Catalog Cleaning",
    page_icon="📦",
    layout="wide"
)

# --- SESSION STATE ---
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "job_status" not in st.session_state:
    st.session_state.job_status = None
if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None
if "lang" not in st.session_state:
    st.session_state.lang = "tr"

# Streamlit Cloud'da st.secrets, local'de .env / BACKEND_URL
_backend = os.getenv("BACKEND_URL", "http://localhost:8000")
try:
    if hasattr(st, "secrets") and st.secrets.get("BACKEND_URL"):
        _backend = st.secrets["BACKEND_URL"]
except Exception:
    pass
backend_url = (_backend or "http://localhost:8000").rstrip("/")

# --- BACKEND CHECK ---
def backend_reachable():
    try:
        r = requests.get(f"{backend_url}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

# --- SIDEBAR: Dil + Backend ---
with st.sidebar:
    st.subheader(t("backend", st.session_state.lang))
    selected = st.selectbox(
        t("language", st.session_state.lang),
        options=list(LANG_OPTIONS.keys()),
        format_func=lambda x: LANG_OPTIONS[x],
        index=list(LANG_OPTIONS.keys()).index(st.session_state.lang) if st.session_state.lang in LANG_OPTIONS else 0,
    )
    st.session_state.lang = selected
    st.caption(t("lang_desc", st.session_state.lang))
    st.caption(f"URL: `{backend_url}`")
    if backend_reachable():
        st.success(t("api_connected", st.session_state.lang))
    else:
        st.error(t("api_error", st.session_state.lang))

lang = st.session_state.lang

# --- MAIN ---
st.title(t("title", lang))
st.markdown(t("subtitle", lang))

# --- FILE UPLOAD & START JOB ---
uploaded_file = st.file_uploader(t("upload", lang), type=["xlsx", "xls"])

if uploaded_file is not None:
    st.info(t("file_selected", lang))

    col1, col2 = st.columns(2)
    with col1:
        if st.button(t("start", lang), type="primary", use_container_width=True):
            try:
                existing_id = (st.session_state.job_id or "").strip()
                if existing_id and existing_id != "None":
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
                    resp = requests.post(
                        f"{backend_url}/jobs",
                        files=files,
                        data={"language": lang},
                        timeout=60,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    new_id = (data.get("job_id") or "").strip()
                    if new_id:
                        st.session_state.job_id = new_id
                        st.session_state.job_status = data
                        st.session_state.uploaded_file_name = uploaded_file.name
                    else:
                        st.error(f"❌ {t('error', lang)}: Backend job_id döndürmedi.")
                st.success(t("job_sent", lang))
                st.rerun()
            except requests.exceptions.ConnectionError:
                st.error(f"❌ {t('backend_error', lang)} {backend_url}")
            except Exception as e:
                st.error(f"❌ {t('error', lang)}: {e}")

    with col2:
        if st.button(t("reset", lang), use_container_width=True):
            st.session_state.job_id = None
            st.session_state.job_status = None
            st.session_state.uploaded_file_name = None
            st.rerun()

# --- JOB STATUS ---
job_id = (st.session_state.job_id or "").strip()
if job_id:
    st.divider()
    st.subheader(t("status", lang))

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
            st.caption(f"📄 {t('file', lang)}: {st.session_state.uploaded_file_name}")
        st.write(f"**Job ID:** `{job_id}`")
        st.write(f"**{t('total', lang)}:** {total} {t('products', lang)} | **{t('processed', lang)}:** {processed} (%{percentage})")

        st.progress(min(percentage / 100.0, 1.0))

        if status.get("is_complete"):
            st.success(t("complete", lang))
        else:
            st.caption(t("in_progress", lang))
            if processed == 0 and total > 0:
                st.warning(t("progress_warning", lang))

    if st.button(t("refresh", lang)):
        try:
            resp = requests.get(f"{backend_url}/jobs/{job_id}", timeout=30)
            resp.raise_for_status()
            st.session_state.job_status = resp.json()
            st.rerun()
        except Exception as e:
            st.error(f"❌ {t('refresh_error', lang)}: {e}")

    if status.get("output_ready"):
        try:
            result_resp = requests.get(
                f"{backend_url}/jobs/{job_id}/download",
                timeout=120,
            )
            result_resp.raise_for_status()
            buffer = io.BytesIO(result_resp.content)
            res_df = pd.read_excel(buffer)

            st.subheader(f"📊 {t('processed_data', lang)} ({len(res_df)} {t('products', lang)})")
            st.dataframe(res_df, use_container_width=True)

            buffer.seek(0)
            st.download_button(
                label=t("download", lang),
                data=buffer,
                file_name=f"cleaned_catalog_{job_id}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        except Exception as e:
            st.error(f"❌ {t('download_error', lang)}: {e}")
