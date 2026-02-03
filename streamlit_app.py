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

# --- SESSION STATE (MEMORY) MANAGEMENT ---
if 'islenen_listesi' not in st.session_state:
    st.session_state.islenen_listesi = []
if 'islem_aktif' not in st.session_state:
    st.session_state.islem_aktif = False

# API Key Management
api_key = None
if hasattr(st, 'secrets') and "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]

if not api_key:
    api_key = st.text_input("Google Gemini API Key", type="password", 
                           help="Enter your Gemini API key")

if not api_key:
    st.warning("⚠️ Please enter your API key to proceed.")
    st.stop()

# Initialize Gemini Models
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
    st.error(f"❌ API key error: {str(e)}")
    st.stop()

# --- HELPER FUNCTIONS ---
def gemini_eksik_sutun_sor_streamlit(urun_adi, eksik_sutun_basligi, marka=None):
    """Asks Gemini for missing columns with a focus on web search"""
    try:
        soru = f"""Product Name: {urun_adi}
Brand: {marka if marka else 'Unknown'}
Missing Feature: {eksik_sutun_basligi}

What is the value of this feature for this product? Provide only the value (e.g., 2 l, 16 GB, Black). 
If it is absolutely unknown, just write 'unknown'."""
        
        response = chat_model.generate_content(soru)
        cevap = response.text.strip()
        
        if "unknown" in cevap.lower() or not cevap:
            return None
        return cevap
    except:
        return None

def urun_isle_streamlit(row_dict, model):
    """Main cleaning and standardization process"""
    teknik_veri = {EXCEL_TO_TECHNICAL.get(k, k): v for k, v in row_dict.items() if pd.notna(v)}
    anlasilir_veri = {SUTUN_HARITASI.get(k, k): v for k, v in teknik_veri.items()}
    
    if 'Kategori' in row_dict:
        kategori = str(row_dict.get('Kategori', '')).strip()
        template = template_bul(kategori)
        if template:
            anlasilir_veri['_Template_Basliktan_Silinecek_Ozellikler'] = template
    
    prompt = f"INPUT DATA:\n{json.dumps(anlasilir_veri, ensure_ascii=False)}"
    
    try:
        response = model.generate_content(system_instruction + prompt)
        return json.loads(response.text)
    except:
        return {"uyari": "API error", "temiz_baslik": row_dict.get('Başlık', 'ERROR')}

# --- FILE UPLOAD ---
uploaded_file = st.file_uploader("Upload your Excel file", type=['xlsx'])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    
    # Skip technical header row if exists
    if len(df) > 0 and 'Başlık' in df.columns:
        if str(df.iloc[0].get('Başlık', '')).startswith('TITLE'):
            df = df.iloc[1:].reset_index(drop=True)
    
    st.info(f"📋 Total Products: {len(df)} | ✅ Processed: {len(st.session_state.islenen_listesi)}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Start / Continue Process", type="primary", use_container_width=True):
            st.session_state.islem_aktif = True
    with col2:
        if st.button("🗑️ Reset Memory", use_container_width=True):
            st.session_state.islenen_listesi = []
            st.session_state.islem_aktif = False
            st.rerun()

    if st.session_state.islem_aktif:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Determine already processed SKUs
        islenen_skular = [str(x.get('SHOP_SKU', '')) for x in st.session_state.islenen_listesi]
        
        for index, row in df.iterrows():
            row_dict = row.to_dict()
            sku = str(row_dict.get('SHOP_SKU', ''))
            
            # Skip if already processed
            if sku in islenen_skular:
                continue
                
            progress = (index + 1) / len(df)
            progress_bar.progress(progress)
            status_text.text(f"Processing ({index + 1}/{len(df)}): {row_dict.get('Başlık', '')[:50]}...")
            
            # Processing
            gemini_cikti = urun_isle_streamlit(row_dict, model)
            flat_result = row_dict.copy()
            flat_result['Başlık'] = gemini_cikti.get("temiz_baslik", row_dict.get('Başlık', ''))
            
            # Update features based on output
            ozellikler = gemini_cikti.get("duzenlenmis_ozellikler", {})
            for key, val in ozellikler.items():
                if key == "RAM": flat_result['RAM Bellek Boyutu'] = val
                if key == "Disk": flat_result['Sabit disk kapasitesi'] = val
            
            # Ask for missing columns
            for sutun in row_dict.keys():
                if sutun not in {'Başlık', 'SHOP_SKU', 'Kategori'} and pd.isna(row_dict[sutun]):
                    bulunan = gemini_eksik_sutun_sor_streamlit(row_dict.get('Başlık', ''), sutun, row_dict.get('Marka'))
                    if bulunan:
                        flat_result[sutun] = bulunan

            flat_result['Warning'] = gemini_cikti.get("uyari", "")
            
            # --- PERSISTENCE: SAVE INSTANTLY ---
            st.session_state.islenen_listesi.append(flat_result)
            
            # Rate limit protection
            time.sleep(0.5)
            
        st.session_state.islem_aktif = False
        st.success("✅ Process finished or no new products to process!")

# --- RESULTS AND DOWNLOAD ---
if st.session_state.islenen_listesi:
    st.divider()
    res_df = pd.DataFrame(st.session_state.islenen_listesi)
    st.subheader(f"📊 Processed Data ({len(res_df)} Products)")
    st.dataframe(res_df, use_container_width=True)
    
    output = io.BytesIO()
    res_df.to_excel(output, index=False)
    output.seek(0)
    
    st.download_button(
        label="📥 Download Cleaned Catalog",
        data=output,
        file_name="cleaned_catalog.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
