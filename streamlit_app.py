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
st.markdown("Excel dosyanızı yükleyin ve Gemini AI ile ürün kataloğunuzu temizleyin.")

# --- SESSION STATE BAŞLATMA ---
# Sayfa yenilendiğinde verilerin kaybolmaması için sonuçları burada tutuyoruz
if 'islem_tamamlandi' not in st.session_state:
    st.session_state.islem_tamamlandi = False
if 'islenen_veriler' not in st.session_state:
    st.session_state.islenen_veriler = None

# API Key yönetimi
api_key = None
if hasattr(st, 'secrets') and "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]

if not api_key:
    api_key = st.text_input("Google Gemini API Key", type="password", 
                           help="API key'inizi girin veya Streamlit Cloud secrets'a ekleyin")

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

def gemini_eksik_sutun_sor_streamlit(urun_adi, eksik_sutun_basligi, marka=None, model_adi=None):
    """main.py'deki gemini_eksik_sutun_sor fonksiyonunun Streamlit versiyonu"""
    try:
        soru_parts = [f"Ürün adı: {urun_adi}"]
        if marka:
            soru_parts.append(f"Marka: {marka}")
        if model_adi:
            soru_parts.append(f"Model: {model_adi}")
        
        if not model_adi:
            model_match = re.search(r'[A-Z0-9]{4,}[-]?[A-Z0-9]{0,}', urun_adi)
            if model_match:
                model_kodu = model_match.group(0)
                if len(model_kodu) >= 4:
                    soru_parts.append(f"Model Kodu: {model_kodu}")
        
        soru_parts.append(f"\nEksik olan özellik: {eksik_sutun_basligi}")
        
        ek_talimat = ""
        if "program" in eksik_sutun_basligi.lower():
            ek_talimat = "- Eğer farklı sitelerde farklı program sayıları varsa (örn: 14, 15, 15+1), en güncel ve en sık geçen resmi değeri seç.\n- Sadece rakam ver (örn: 15)."
        
        soru = "\n".join(soru_parts) + f"""

Bu ürün için "{eksik_sutun_basligi}" özelliği nedir?

ÖNEMLİ KURALLAR:
- WEB ARAMASI YAP: Google, Trendyol, MediaMarkt, Hepsiburada, Teknosa, Vatan Bilgisayar gibi güvenilir e-ticaret sitelerinde bu ürünü ara ve güncel bilgileri kontrol et.
- İç bilgilerini değil, WEB'DEKİ GÜNCEL BİLGİLERİ kullan.
- Eğer farklı sitelerde farklı değerler görürsen, en yaygın ve en güncel resmi değeri seç.
{ek_talimat}
- Sadece değeri verin (açıklama, cümle, noktalama işareti YOK)
- Sadece sayı + birim veya değer (örn: "2 l", "16 GB", "2200 w", "Siyah", "15 kg", "15")
- Eğer kesin olarak bilmiyorsanız sadece "bilinmiyor" yazın
- Başka hiçbir şey yazmayın

Örnek cevaplar: "2 l", "16 GB", "2200 W", "Siyah", "15 kg", "15"
Yanlış örnekler: "Bu ürün 2 litre", "2 l kapasiteli", "2l.", "Yaklaşık 2 litre"

Cevap:"""
        
        response = chat_model.generate_content(soru)
        cevap = response.text.strip()
        
        if "bilinmiyor" in cevap.lower() or "bilmiyorum" in cevap.lower() or not cevap or len(cevap) < 1:
            return None
        
        return cevap
        
    except Exception as e:
        return None

def gemini_celiskic_coz_streamlit(urun_adi, uyari_metni, baslik_degeri, ozellik_dict, marka=None):
    """main.py'deki gemini_celiskic_coz fonksiyonunun Streamlit versiyonu"""
    try:
        ozellik_bilgileri = []
        for key, value in ozellik_dict.items():
            if value:
                ozellik_bilgileri.append(f"  - {key}: {value}")
        
        soru = f"""Ürün bilgisi:
- Ürün adı: {urun_adi}
{f"- Marka: {marka}" if marka else ""}
- Mevcut başlık: {baslik_degeri}

Mevcut özellikler:
{chr(10).join(ozellik_bilgileri) if ozellik_bilgileri else "  (Henüz özellik yok)"}

ÇELİŞKİ TESPİT EDİLDİ:
{uyari_metni}

Yukarıdaki uyarıya göre, çelişkili olan özellik hangisi ve doğru değer nedir?

Lütfen şu formatta JSON cevap ver:
{{
  "ozellik_adi": "çelişkili özellik adı (örn: Isletim_Sistemi, Renk_Temel, RAM_Boyutu)",
  "dogru_deger": "doğru olan değer",
  "kaynak": "baslik" veya "ozellik"
}}

Örnek: {{"ozellik_adi": "Isletim_Sistemi", "dogru_deger": "Windows 11", "kaynak": "baslik"}}

Eğer çelişki çözülemiyorsa: {{"ozellik_adi": "", "dogru_deger": "", "kaynak": "cozulemedi"}}
"""
        
        response = chat_model.generate_content(soru)
        cevap_text = response.text.strip()
        
        try:
            if "```json" in cevap_text:
                json_start = cevap_text.find("```json") + 7
                json_end = cevap_text.find("```", json_start)
                cevap_text = cevap_text[json_start:json_end].strip()
            elif "```" in cevap_text:
                json_start = cevap_text.find("```") + 3
                json_end = cevap_text.find("```", json_start)
                if json_end > json_start:
                    cevap_text = cevap_text[json_start:json_end].strip()
            
            sonuc = json.loads(cevap_text)
            ozellik_adi = sonuc.get("ozellik_adi", "").strip()
            dogru_deger = sonuc.get("dogru_deger", "").strip()
            kaynak = sonuc.get("kaynak", "").strip().lower()
            
            if ozellik_adi and dogru_deger and kaynak and kaynak != "cozulemedi":
                return {
                    "ozellik_adi": ozellik_adi,
                    "dogru_deger": dogru_deger,
                    "kaynak": kaynak
                }
        except (json.JSONDecodeError, KeyError):
            pass
        
        return None
        
    except Exception as e:
        return None

def urun_isle_streamlit(row_dict, model, max_retries=3):
    """main.py'deki urun_isle fonksiyonunun Streamlit versiyonu"""
    teknik_veri = {}
    for excel_key, deger in row_dict.items():
        if pd.notna(deger):
            teknik_key = EXCEL_TO_TECHNICAL.get(excel_key, excel_key)
            teknik_veri[teknik_key] = deger
    
    anlasilir_veri = {}
    for teknik_key, deger in teknik_veri.items():
        yeni_key = SUTUN_HARITASI.get(teknik_key, teknik_key)
        if pd.notna(deger):
            anlasilir_veri[yeni_key] = deger
    
    if 'Kategori' in row_dict:
        kategori = str(row_dict.get('Kategori', '')).strip()
        if pd.notna(kategori) and kategori and kategori != 'CATEGORY':
            anlasilir_veri['_Kategori_Bilgisi'] = kategori
            anlasilir_veri['_Kategori_Notu'] = f"Bu ürün '{kategori}' kategorisinde. Bu kategorinin tipik özelliklerine göre başlıktan bilgi çıkar ve uygun formatları uygula."
            
            template_ozellikler = template_bul(kategori)
            if template_ozellikler:
                anlasilir_veri['_Template_Basliktan_Silinecek_Ozellikler'] = template_ozellikler
                anlasilir_veri['_Template_Notu'] = f"Bu kategoride başlıktan şu özellikler SİLİNECEK (template'de var): {', '.join(template_ozellikler)}. Template'de OLMAYAN özellikler başlıkta KALACAK."
    
    prompt = f"GİRDİ VERİSİ:\n{json.dumps(anlasilir_veri, ensure_ascii=False)}"
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(system_instruction + prompt)
            return json.loads(response.text)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                if attempt < max_retries - 1:
                    wait_match = re.search(r'retry in (\d+\.?\d*)s', error_str, re.IGNORECASE)
                    wait_time = float(wait_match.group(1)) + 2 if wait_match else 40 + (attempt * 10)
                    time.sleep(wait_time)
                    continue
                else:
                    return {"uyari": f"Rate Limit Hatası: API kotası aşıldı", "temiz_baslik": row_dict.get('Başlık', row_dict.get('TITLE__TR_TR', 'HATA'))}
            else:
                return {"uyari": f"API Hatası: {error_str[:200]}", "temiz_baslik": row_dict.get('Başlık', row_dict.get('TITLE__TR_TR', 'HATA'))}
    
    return {"uyari": "Tüm denemeler başarısız oldu", "temiz_baslik": row_dict.get('Başlık', row_dict.get('TITLE__TR_TR', 'HATA'))}

# Dosya yükleme
uploaded_file = st.file_uploader("Excel dosyasını yükleyin", type=['xlsx'])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        st.success(f"✅ Dosya okundu: {len(df)} satır bulundu")
        
        # İlk satır teknik kodlar içeriyorsa atla
        if len(df) > 0 and 'Başlık' in df.columns:
            if str(df.iloc[0].get('Başlık', '')).startswith('TITLE'):
                df = df.iloc[1:].reset_index(drop=True)
        
        st.dataframe(df.head(), use_container_width=True)
        
        # İşlemi başlat butonu
        if st.button("🚀 İşlemi Başlat", type="primary"):
            # Yeni işlem başladığında eski sonuçları temizle
            st.session_state.islem_tamamlandi = False
            st.session_state.islenen_veriler = None
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            
            total_rows = len(df)
            
            for index, row in df.iterrows():
                row_dict = row.to_dict()
                
                # İlerleme göster
                progress = (index + 1) / total_rows
                progress_bar.progress(progress)
                status_text.text(f"İşleniyor: {index + 1}/{total_rows}")
                
                try:
                    if 'Kategori' in row_dict:
                        kategori = row_dict.get('Kategori', '')
                        row_dict_with_category = row_dict.copy()
                        if pd.notna(kategori) and kategori:
                            row_dict_with_category['_Kategori_Bilgisi'] = str(kategori)
                        gemini_cikti = urun_isle_streamlit(row_dict_with_category, model)
                    else:
                        gemini_cikti = urun_isle_streamlit(row_dict, model)
                    
                    flat_result = row_dict.copy()
                    flat_result['Başlık'] = gemini_cikti.get("temiz_baslik", row_dict.get('Başlık', ''))
                    
                    ozellikler = gemini_cikti.get("duzenlenmis_ozellikler", {})
                    
                    # Özellik güncelleme mantığı
                    if "Islemci" in ozellikler:
                        flat_result['İşlemci (tr_TR)'] = ozellikler.get("Islemci", row_dict.get('İşlemci (tr_TR)', ''))
                    
                    if "Renk" in ozellikler and pd.isna(row_dict.get('Renk (temel)', None)):
                        flat_result['Renk (temel)'] = ozellikler.get("Renk", '')
                    
                    if "Isletim_Sistemi" in ozellikler and pd.isna(row_dict.get('İşletim Sistemi', None)):
                        isletim_sistemi = ozellikler.get("Isletim_Sistemi", '')
                        if isletim_sistemi:
                            isletim_sistemi = isletim_sistemi.replace("Full HD", "FHD").replace("FullHD", "FHD")
                        flat_result['İşletim Sistemi'] = isletim_sistemi
                    
                    if "RAM" in ozellikler and pd.isna(row_dict.get('RAM Bellek Boyutu', None)):
                        flat_result['RAM Bellek Boyutu'] = ozellikler.get("RAM", '')
                    
                    if "Disk" in ozellikler and pd.isna(row_dict.get('Sabit disk kapasitesi', None)):
                        flat_result['Sabit disk kapasitesi'] = ozellikler.get("Disk", '')
                    
                    if "Ekran" in ozellikler and pd.isna(row_dict.get('Ekran Boyutu (inç)', None)):
                        flat_result['Ekran Boyutu (inç)'] = ozellikler.get("Ekran", '')
                    
                    if "Grafik_Karti" in ozellikler and pd.isna(row_dict.get('Grafik Kartı', None)):
                        grafik_karti = ozellikler.get("Grafik_Karti", '')
                        if grafik_karti:
                            grafik_karti = grafik_karti.replace("Full HD", "FHD").replace("FullHD", "FHD")
                        flat_result['Grafik Kartı'] = grafik_karti

                    # KETTLE/SU ISITICISI için özel sütunlar
                    if "Kapasite" in ozellikler:
                        mevcut_kapasite = str(row_dict.get('Hacimsel kapasite', '')).strip()
                        if pd.isna(row_dict.get('Hacimsel kapasite', None)) or not mevcut_kapasite or '-' in mevcut_kapasite or '/' in mevcut_kapasite:
                            flat_result['Hacimsel kapasite'] = ozellikler.get("Kapasite", '')

                    if "Guc" in ozellikler or "Güç" in ozellikler:
                        guc = ozellikler.get("Guc", ozellikler.get("Güç", ''))
                        mevcut_guc = str(row_dict.get('Maksimum güç', '')).strip()
                        if pd.isna(row_dict.get('Maksimum güç', None)) or not mevcut_guc or 've altı' in mevcut_guc.lower() or '-' in mevcut_guc:
                            flat_result['Maksimum güç'] = guc

                    if "Urun_Tipi" in ozellikler:
                        flat_result['Ürün Tipi (tr_TR)'] = ozellikler.get("Urun_Tipi", '')
                    
                    # Çelişki kontrolü ve uyarılar
                    yeni_uyari = gemini_cikti.get("uyari", '')
                    if yeni_uyari and "çelişki" in yeni_uyari.lower():
                        celiski_sonuc = gemini_celiskic_coz_streamlit(
                            urun_adi=row_dict.get('Başlık', ''),
                            uyari_metni=yeni_uyari,
                            baslik_degeri=flat_result.get('Başlık', ''),
                            ozellik_dict=ozellikler,
                            marka=row_dict.get('Marka', '')
                        )
                        if celiski_sonuc:
                            yeni_uyari = f"Çözüldü: {celiski_sonuc.get('ozellik_adi')} (kaynak: {celiski_sonuc.get('kaynak')})"

                    flat_result['Uyari'] = yeni_uyari if yeni_uyari and yeni_uyari != 'null' else ''
                    
                    # Eksik sütunları Gemini ile doldur
                    atlanacak_sutunlar = {'Başlık', 'SHOP_SKU', 'Uyari', 'Kategori'}
                    for sutun_adi in row_dict.keys():
                        if sutun_adi in atlanacak_sutunlar: continue
                        if pd.isna(row_dict.get(sutun_adi)) or str(row_dict.get(sutun_adi)).strip() == '':
                            bulunan = gemini_eksik_sutun_sor_streamlit(row_dict.get('Başlık', ''), sutun_adi, row_dict.get('Marka'))
                            if bulunan: flat_result[sutun_adi] = bulunan
                    
                    results.append(flat_result)
                    time.sleep(1) # Rate limit koruması
                    
                except Exception as e:
                    flat_result = row_dict.copy()
                    flat_result['Uyari'] = f"İşleme hatası: {str(e)[:150]}"
                    results.append(flat_result)
            
            # --- SONUÇLARI KAYDET ---
            df_result = pd.DataFrame(results)
            orijinal_sutunlar = list(df.columns)
            if 'Uyari' not in orijinal_sutunlar: orijinal_sutunlar.append('Uyari')
            
            st.session_state.islenen_veriler = df_result.reindex(columns=orijinal_sutunlar)
            st.session_state.islem_tamamlandi = True
            status_text.text("✅ İşlem bitti!")

        # --- SONUÇ GÖSTERİMİ VE İNDİRME ---
        # Bu kısım butonun dışındadır, böylece sayfa yenilense de gitmez
        if st.session_state.islem_tamamlandi and st.session_state.islenen_veriler is not None:
            st.divider()
            st.success(f"✅ Toplam {len(st.session_state.islenen_veriler)} ürün başarıyla işlendi.")
            st.dataframe(st.session_state.islenen_veriler, use_container_width=True)
            
            output = io.BytesIO()
            st.session_state.islenen_veriler.to_excel(output, index=False)
            output.seek(0)
            
            st.download_button(
                label="📥 Temizlenmiş Kataloğu İndir",
                data=output,
                file_name="temizlenmis_katalog.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
    
    except Exception as e:
        st.error(f"❌ Beklenmedik bir hata oluştu: {str(e)}")
