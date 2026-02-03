import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import time
import os
import io
import re
from main import (
    EXCEL_TO_TECHNICAL, SUTUN_HARITASI, BASLIKTAN_SILINECEK_OZELLIKLER,
    template_bul, system_instruction
)

# Sayfa yapılandırması
st.set_page_config(
    page_title="Ürün Katalog Temizleme",
    page_icon="📦",
    layout="wide"
)

st.title("📦 Ürün Katalog Temizleme Aracı")
st.markdown("Excel dosyanızı yükleyin. İşlem uzun sürse veya sayfa yenilense bile verileriniz hafızada tutulur.")

# --- SESSION STATE (GELİŞTİRİLMİŞ HAFIZA) ---
if 'islenen_listesi' not in st.session_state:
    st.session_state.islenen_listesi = [] # İşlenen satırları anlık tutar
if 'islem_aktif' not in st.session_state:
    st.session_state.islem_aktif = False

# API Key yönetimi
api_key = None
if hasattr(st, 'secrets') and "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
if not api_key:
    api_key = st.text_input("Google Gemini API Key", type="password")
if not api_key:
    st.warning("⚠️ Lütfen API key'inizi girin.")
    st.stop()

# Gemini modellerini initialize et
@st.cache_resource
def init_models(api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-flash-latest",
        generation_config={"response_mime_type": "application/json"}
    )
    chat_model = genai.GenerativeModel(
        'gemini-flash-latest',
        generation_config={"temperature": 0.1}
    )
    return model, chat_model

try:
    model, chat_model = init_models(api_key)
except Exception as e:
    st.error(f"❌ API key hatası: {str(e)}")
    st.stop()

# --- YARDIMCI FONKSİYONLAR ---
def gemini_eksik_sutun_sor_streamlit(urun_adi, eksik_sutun_basligi, marka=None):
    try:
        soru = f"Ürün: {urun_adi}\nMarka: {marka if marka else ''}\nSoru: Bu ürün için '{eksik_sutun_basligi}' nedir? Sadece değeri (örn: 2 l, 16 GB) ver. Bilmiyorsan 'bilinmiyor' yaz."
        response = chat_model.generate_content(soru)
        cevap = response.text.strip()
        return None if "bilinmiyor" in cevap.lower() or not cevap else cevap
    except: return None

def urun_isle_streamlit(row_dict, model):
    teknik_veri = {EXCEL_TO_TECHNICAL.get(k, k): v for k, v in row_dict.items() if pd.notna(v)}
    anlasilir_veri = {SUTUN_HARITASI.get(k, k): v for k, v in teknik_veri.items()}
    if 'Kategori' in row_dict:
        kategori = str(row_dict.get('Kategori', '')).strip()
        template = template_bul(kategori)
        if template: anlasilir_veri['_Template_Basliktan_Silinecek_Ozellikler'] = template
    
    prompt = f"GİRDİ VERİSİ:\n{json.dumps(anlasilir_veri, ensure_ascii=False)}"
    try:
        response = model.generate_content(system_instruction + prompt)
        return json.loads(response.text)
    except Exception as e:
        return {"uyari": f"API Hatası: {str(e)[:100]}", "temiz_baslik": row_dict.get('Başlık', 'HATA')}

# --- DOSYA YÜKLEME VE KONTROLLER ---
uploaded_file = st.file_uploader("Excel dosyasını yükleyin", type=['xlsx'])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    if len(df) > 0 and 'Başlık' in df.columns and str(df.iloc[0].get('Başlık', '')).startswith('TITLE'):
        df = df.iloc[1:].reset_index(drop=True)

    st.info(f"Dosyada {len(df)} ürün var. Şu ana kadar {len(st.session_state.islenen_listesi)} ürün işlendi.")

    col1, col2 = st.columns(2)
    with col1:
        start_btn = st.button("🚀 İşlemi Başlat / Devam Et", type="primary", use_container_width=True)
    with col2:
        if st.button("🗑️ Hafızayı Sıfırla", use_container_width=True):
            st.session_state.islenen_listesi = []
            st.rerun()

    if start_btn:
        st.session_state.islem_aktif = True
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Kaldığı yerden devam etmek için mevcut SKU'ları kontrol et
        islenen_skular = [str(x.get('SHOP_SKU', '')) for x in st.session_state.islenen_listesi]

        for index, row in df.iterrows():
            row_dict = row.to_dict()
            sku = str(row_dict.get('SHOP_SKU', ''))

            # Ürün zaten işlendiyse atla
            if sku in islenen_skular:
                continue

            # İlerleme güncelle
            progress = (index + 1) / len(df)
            progress_bar.progress(progress)
            status_text.text(f"İşleniyor ({index+1}/{len(df)}): {row_dict.get('Başlık', '')[:50]}...")

            try:
                # Ana işleme
                gemini_cikti = urun_isle_streamlit(row_dict, model)
                flat_result = row_dict.copy()
                flat_result['Başlık'] = gemini_cikti.get("temiz_baslik", row_dict.get('Başlık', ''))
                
                # Özellikleri güncelle
                ozellikler = gemini_cikti.get("duzenlenmis_ozellikler", {})
                if "Islemci" in ozellikler: flat_result['İşlemci (tr_TR)'] = ozellikler.get("Islemci")
                if "RAM" in ozellikler: flat_result['RAM Bellek Boyutu'] = ozellikler.get("RAM")
                if "Disk" in ozellikler: flat_result['Sabit disk kapasitesi'] = ozellikler.get("Disk")
                
                # Boş sütunları doldur
                for sutun in row_dict.keys():
                    if sutun not in {'Başlık', 'SHOP_SKU', 'Kategori'} and (pd.isna(row_dict[sutun]) or str(row_dict[sutun]).strip() == ''):
                        bulunan = gemini_eksik_sutun_sor_streamlit(row_dict.get('Başlık', ''), sutun, row_dict.get('Marka'))
                        if bulunan: flat_result[sutun] = bulunan

                flat_result['Uyari'] = gemini_cikti.get("uyari", "")

                # --- KRİTİK: ANLIK KAYIT ---
                st.session_state.islenen_listesi.append(flat_result)
                
            except Exception as e:
                st.error(f"Satır {index} hatası: {e}")
            
            time.sleep(0.5) # API stabilitesi için kısa bekleme

        st.session_state.islem_aktif = False
        st.success("✅ İşlem tamamlandı!")

# --- SONUÇLARI GÖSTER VE İNDİR (Butonun Dışında) ---
if st.session_state.islenen_listesi:
    st.divider()
    st.subheader(f"📊 İşlenen Veriler ({len(st.session_state.islenen_listesi)} Ürün)")
    
    res_df = pd.DataFrame(st.session_state.islenen_listesi)
    st.dataframe(res_df, use_container_width=True)
    
    # Excel indirme hazırlığı
    output = io.BytesIO()
    res_df.to_excel(output, index=False)
    output.seek(0)
    
    st.download_button(
        label="📥 Temizlenmiş Kataloğu İndir",
        data=output,
        file_name="temizlenmis_katalog.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
