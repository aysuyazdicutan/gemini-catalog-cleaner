import google.generativeai as genai
import pandas as pd
import json
import time
import os
from dotenv import load_dotenv

# .env dosyasından environment variable'ları yükle
load_dotenv()

# Web scraping kaldırıldı - Gemini web'de arama yapacak
# from web_scraper import web_arama_ve_cek

# ---------------- AYARLAR ----------------
# API Key'i environment variable'dan al (güvenlik için)
API_KEY = os.getenv("GEMINI_API_KEY")  # Environment variable'dan alınır (.env dosyasından)
if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY environment variable bulunamadı!\n"
        "Lütfen .env dosyası oluşturun ve şu satırı ekleyin:\n"
        "GEMINI_API_KEY=your_api_key_here"
    )

GIRIS_DOSYASI = "Copy of KLİMAAA.xlsx"      # Excel dosyanızın tam adı
CIKIS_DOSYASI = "temizlenmis_katalog.xlsx"

# Excel'deki Türkçe sütun isimlerini teknik kodlara çeviren harita
# (Excel'de Türkçe başlıklar var, kod teknik kodları bekliyor)
EXCEL_TO_TECHNICAL = {
    "Başlık": "TITLE__TR_TR",
    "Marka": "BRAND",
    "RAM Tipi": "PROD_FEAT_15969",
    "RAM Bellek Boyutu": "PROD_FEAT_11184",
    "Sabit disk tipi": "PROD_FEAT_16383",
    "Sabit disk kapasitesi": "PROD_FEAT_16384",
    "Ekran Boyutu (inç)": "PROD_FEAT_14112",
    "Ekran boyutu(cm)": "PROD_FEAT_14111",
    "Renk (temel)": "PROD_FEAT_00003",
    "İşletim Sistemi": "PROD_FEAT_16858",
    "Grafik Kartı": "PROD_FEAT_16863",
    "Kutu İçeriği (tr_TR)": "PROD_FEAT_11470__TR_TR",
    "İşlemci (tr_TR)": "PROD_FEAT_11793__TR_TR",
    "Renk (Üreticiye Göre) (tr_TR)": "PROD_FEAT_10812__TR_TR"
}

# Sütun İsim Eşleştirme (Teknik kodları LLM'in anlayacağı dile çeviriyoruz)
SUTUN_HARITASI = {
    "TITLE__TR_TR": "Urun_Basligi",
    "BRAND": "Marka",
    "PROD_FEAT_15969": "RAM_Tipi",      # DDR4 vb.
    "PROD_FEAT_11184": "RAM_Boyutu",    # 16 GB vb.
    "PROD_FEAT_16383": "Disk_Tipi",     # SSD vb.
    "PROD_FEAT_16384": "Disk_Kapasitesi", # 2 TB vb.
    "PROD_FEAT_14112": "Ekran_Boyutu_Inc",
    "PROD_FEAT_14111": "Ekran_Boyutu_cm",
    "PROD_FEAT_00003": "Renk_Temel",
    "PROD_FEAT_16858": "Isletim_Sistemi",
    "PROD_FEAT_16863": "Grafik_Karti",
    "PROD_FEAT_11470__TR_TR": "Kutu_Icerigi",
    "PROD_FEAT_11793__TR_TR": "Islemci_Modeli",
    "PROD_FEAT_10812__TR_TR": "Renk_Uretici"
}

# ---------------- TEMPLATE SİSTEMİ ----------------
# Her kategori için başlıktan silinecek özellikleri tanımla
# Template'de OLMAYAN özellikler başlıkta KALACAK
# Template'de OLAN özellikler başlıktan SİLİNECEK
# Özellik isimleri SUTUN_HARITASI'ndaki anlaşılır isimlerle eşleşmeli

BASLIKTAN_SILINECEK_OZELLIKLER = {
    # Örnek: Çanta kategorisi için Renk ve Ürün Tipi başlıktan silinecek
    # "Su Geçirmez Siyah Çanta" → "Su Geçirmez" (Renk ve Ürün Tipi silindi, Su Geçirmez kaldı)
    # Not: Renk_Temel veya Renk_Uretici kullanılabilir, hangisi varsa o kullanılır
    "Çanta": ["Renk_Temel", "Urun_Tipi"],
    
    # Laptop için örnek template
    "Laptop": ["Marka", "Renk_Temel", "RAM_Boyutu", "Disk_Kapasitesi", "Urun_Tipi"],
    "Dizüstü Bilgisayar": ["Marka", "Renk_Temel", "RAM_Boyutu", "Disk_Kapasitesi", "Urun_Tipi"],
    
    # Kettle/Su Isıtıcısı için örnek
    "Kettle": ["Kapasite", "Guc", "Frekans", "Voltaj", "Renk_Temel", "Urun_Tipi"],
    "Su Isıtıcısı": ["Kapasite", "Guc", "Frekans", "Voltaj", "Renk_Temel", "Urun_Tipi"],

    # Kurutma Makinesi için template - Program sayısı başlıktan silinecek
    "Kurutma Makinesi": ["Marka", "Kapasite", "Enerji_Sinifi", "Program_Sayisi", "Renk_Temel", "Urun_Tipi"],
    "Çamaşır Kurutma Makinesi": ["Marka", "Kapasite", "Enerji_Sinifi", "Program_Sayisi", "Renk_Temel", "Urun_Tipi"],

    # Buraya yeni kategoriler ekleyebilirsiniz
    # "Kategori Adı": ["Özellik1", "Özellik2", ...]
    # Özellik isimleri SUTUN_HARITASI'ndaki anlaşılır isimlerle eşleşmeli
    # Örnek: "Renk_Temel", "Urun_Tipi", "Marka", "RAM_Boyutu", "Disk_Kapasitesi", vb.
}

def template_bul(kategori_adi):
    """
    Kategori adına göre template'i bulur (büyük/küçük harf duyarsız)
    
    Args:
        kategori_adi: Ürün kategorisi
    
    Returns:
        Başlıktan silinecek özellikler listesi veya None
    """
    if not kategori_adi:
        return None
    
    kategori_lower = str(kategori_adi).strip().lower()
    
    # Tam eşleşme kontrolü
    for key, value in BASLIKTAN_SILINECEK_OZELLIKLER.items():
        if key.lower() == kategori_lower:
            return value
    
    # Kısmi eşleşme kontrolü (kategori ismi içinde geçiyorsa)
    for key, value in BASLIKTAN_SILINECEK_OZELLIKLER.items():
        if key.lower() in kategori_lower or kategori_lower in key.lower():
            return value
    
    return None

genai.configure(api_key=API_KEY)

# Gemini Flash - Hız ve Maliyet optimizasyonu için
model = genai.GenerativeModel(
    model_name="gemini-flash-latest",
    generation_config={"response_mime_type": "application/json"}
)

# Gemini Chat Model (aynı model)
chat_model = genai.GenerativeModel(
    "gemini-flash-latest",
    generation_config={"temperature": 0.1}
)

def gemini_eksik_sutun_sor(urun_adi, eksik_sutun_basligi, marka=None, model_adi=None):
    """
    Gemini'ye ürün hakkında soru sorar ve eksik sütun bilgisini alır
    
    Args:
        urun_adi: Ürün adı/başlığı
        eksik_sutun_basligi: Eksik olan sütun başlığı (örn: "Hazne Kapasitesi")
        marka: Marka bilgisi (opsiyonel)
        model_adi: Model adı (opsiyonel)
    
    Returns:
        Bulunan değer (str) veya None
    """
    try:
        # Soru oluştur
        soru_parts = [f"Ürün adı: {urun_adi}"]
        if marka:
            soru_parts.append(f"Marka: {marka}")
        if model_adi:
            soru_parts.append(f"Model: {model_adi}")
        
        # Ürün adından model numarasını çıkarmaya çalış (örn: HLEH10A2TCEX-17)
        import re
        if not model_adi:
            # Model kodu genelde büyük harf ve sayılardan oluşur, tire ile ayrılabilir
            model_match = re.search(r'[A-Z0-9]{4,}[-]?[A-Z0-9]{0,}', urun_adi)
            if model_match:
                model_kodu = model_match.group(0)
                # Çok kısa olanları filtrele (en az 4 karakter)
                if len(model_kodu) >= 4:
                    soru_parts.append(f"Model Kodu: {model_kodu}")
        
        soru_parts.append(f"\nEksik olan özellik: {eksik_sutun_basligi}")
        
        # Sütun özel kuralları
        ek_talimat = ""
        if "program" in eksik_sutun_basligi.lower():
            ek_talimat = "- Eğer farklı değerler varsa (örn: 14, 15, 15+1), en güncel ve en sık geçen resmi değeri seç.\n- Sadece rakam ver (örn: 15)."
        
        soru = "\n".join(soru_parts) + f"""

Bu ürün için "{eksik_sutun_basligi}" özelliği nedir?

ÖNEMLİ KURALLAR:
- Ürün adı ve model bilgisinden bilinen değerleri kullan.
- Eğer farklı değerler görürsen, en yaygın olanı seç.
{ek_talimat}
- Sadece değeri verin (açıklama, cümle, noktalama işareti YOK)
- Sadece sayı + birim veya değer (örn: "2 l", "16 GB", "2200 w", "Siyah", "15 kg", "15")
- Eğer kesin olarak bilmiyorsanız sadece "bilinmiyor" yazın
- Başka hiçbir şey yazmayın

Örnek cevaplar: "2 l", "16 GB", "2200 w", "Siyah", "15 kg", "15"
Yanlış örnekler: "Bu ürün 2 litre", "2 l kapasiteli", "2l.", "Yaklaşık 2 litre"

Cevap:"""
        
        print(f"  🤖 Gemini'ye soruluyor: '{urun_adi}' için '{eksik_sutun_basligi}'")
        
        # Hatalı araç tanımı (tools) kaldırıldı, doğrudan içerik üretiliyor
        response = chat_model.generate_content(soru)
        cevap = response.text.strip()
        
        # "Bilinmiyor" kontrolü
        if "bilinmiyor" in cevap.lower() or "bilmiyorum" in cevap.lower() or not cevap or len(cevap) < 1:
            print(f"  ❌ Gemini bilmiyor: {eksik_sutun_basligi}")
            return None
        
        print(f"  ✅ Gemini cevabı: {cevap}")
        return cevap
        
    except Exception as e:
        print(f"  ⚠️ Gemini soru hatası: {str(e)[:100]}")
        return None


def gemini_eksik_sutunlar_toplu_sor(urun_adi, eksik_sutunlar: list, marka=None, model_adi=None) -> dict:
    """
    Birden fazla eksik sütun için TEK API çağrısıyla tüm değerleri alır (performans).
    
    Args:
        urun_adi: Ürün adı/başlığı
        eksik_sutunlar: Eksik sütun başlıkları listesi (örn: ["RAM Bellek Boyutu", "Renk (temel)"])
        marka: Marka bilgisi (opsiyonel)
        model_adi: Model adı (opsiyonel)
    
    Returns:
        {"Sütun Adı": "değer", ...} - sadece bulunanlar
    """
    if not eksik_sutunlar:
        return {}
    try:
        import re
        soru_parts = [f"Ürün adı: {urun_adi}"]
        if marka:
            soru_parts.append(f"Marka: {marka}")
        if model_adi:
            soru_parts.append(f"Model: {model_adi}")
        if not model_adi:
            model_match = re.search(r'[A-Z0-9]{4,}[-]?[A-Z0-9]{0,}', str(urun_adi))
            if model_match and len(model_match.group(0)) >= 4:
                soru_parts.append(f"Model Kodu: {model_match.group(0)}")

        sutun_listesi = "\n".join(f"- {s}" for s in eksik_sutunlar)
        soru = "\n".join(soru_parts) + f"""

Aşağıdaki eksik özellikleri bu ürün için doldur. Her özellik için SADECE değeri ver (açıklama yok).

Eksik özellikler:
{sutun_listesi}

KURALLAR:
- Sadece JSON formatında cevap ver: {{"Özellik Adı": "değer", ...}}
- Bilinmeyenler için "bilinmiyor" yaz veya o sütunu dahil etme
- Birimler: W (güç), bar, kg, GB (depolama), inç (ekran) - bu formatlarda yaz
- Örnek: {{"RAM Bellek Boyutu": "16 GB", "Renk (temel)": "Siyah", "Maksimum güç": "2200 W"}}
- Mümkün olduğunca çok sütunu doldur; ürün adı/model/marka bilgisinden çıkarabildiğini yaz

Cevap:"""

        print(f"  🤖 Gemini toplu soru: {len(eksik_sutunlar)} eksik sütun", flush=True)
        response = chat_model.generate_content(soru)
        text = response.text.strip()

        # JSON parse (```json``` veya direkt JSON)
        if "```" in text:
            start = text.find("```") + 3
            if "json" in text[:20].lower():
                start = text.find("```json") + 7 if "```json" in text else start
            end = text.find("```", start)
            text = text[start:end] if end > start else text[start:].strip()
        try:
            sonuc = json.loads(text)
            # Sadece eksik_sutunlar listesindekileri al, "bilinmiyor" olanları çıkar
            cevap = {}
            for sutun in eksik_sutunlar:
                val = sonuc.get(sutun, "")
                if val and isinstance(val, str) and "bilinmiyor" not in val.lower() and val.strip():
                    cevap[sutun] = val.strip()
            return cevap
        except json.JSONDecodeError:
            return {}
    except Exception as e:
        print(f"  ⚠️ Toplu soru hatası: {str(e)[:80]}", flush=True)
        return {}


def gemini_celiskic_coz(urun_adi, uyari_metni, baslik_degeri, ozellik_dict, marka=None):
    """
    Çelişkili bilgiler için Gemini'ye sorar ve doğru olanı belirler
    
    Args:
        urun_adi: Ürün adı
        uyari_metni: Gemini'den gelen uyarı metni (çelişki açıklaması)
        baslik_degeri: Mevcut başlık değeri (temizlenmiş)
        ozellik_dict: Gemini'den gelen özellikler dictionary'si
        marka: Marka bilgisi (opsiyonel)
    
    Returns:
        {"ozellik_adi": "Isletim_Sistemi", "dogru_deger": "Windows 11", "kaynak": "baslik"} veya None
    """
    try:
        # Özellik bilgilerini metne çevir
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
        
        print(f"  🔍 Çelişki tespit edildi - Gemini'ye soruluyor...")
        
        response = chat_model.generate_content(soru)
        cevap_text = response.text.strip()
        
        # JSON parse et
        try:
            # JSON kısmını bul (```json``` veya direkt JSON)
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
                print(f"  ✅ Çelişki çözüldü: {ozellik_adi} = '{dogru_deger}' (kaynak: {kaynak})")
                return {
                    "ozellik_adi": ozellik_adi,
                    "dogru_deger": dogru_deger,
                    "kaynak": kaynak
                }
        except (json.JSONDecodeError, KeyError) as e:
            # JSON parse edilemedi veya eksik alan var
            print(f"  ⚠️ JSON parse hatası: {str(e)[:100]}")
        
        print(f"  ❌ Çelişki çözülemedi")
        return None
        
    except Exception as e:
        print(f"  ⚠️ Çelişki çözme hatası: {str(e)[:100]}")
        return None

# ---------------- PROMPT (SİSTEM TALİMATI) ----------------
system_instruction = """
Sen uzman bir Ürün Katalog Yöneticisisin. Görevin, verilen JSON verisindeki ürünü analiz etmek ve başlığı sadeleştirip özellikleri standardize etmektir.

ÖNEMLİ: Ürün kategorisine göre (_Kategori_Bilgisi alanına bak) otomatik olarak uygun kuralları belirle ve uygula.

GENEL ÇALIŞMA PRENSİBİ (TÜM KATEGORİLER İÇİN):

1. **KATEGORİ ANALİZİ VE ADAPTASYON:**
   - _Kategori_Bilgisi alanına bakarak ürün kategorisini belirle
   - O kategorinin tipik özelliklerini analiz et (ör: Laptop için RAM/Disk/İşlemci, KETTLE için Kapasite/Güç/Malzeme)
   - Kategorinin özelliklerine göre başlıktan hangi bilgilerin çıkarılacağını belirle
   - Yeni bir kategori görürsen, o kategorinin tipik özelliklerini analiz et ve benzer mantıkla işle

2. **ÖZELLİK ÇIKARMA VE DOLDURMA:**

   - Başlıktan TÜM özellikleri çıkar (kategorinin tipik özelliklerine göre)
   - Eğer özellik sütunu BOŞSA → Başlıktan çıkardığın bilgiyi o özellik sütununa YAZ
   - Eğer özellik sütunu DOLUYSA → SÜTUNDAKİ DEĞERİ KORU, DEĞİŞTİRME! Başlıktan sadece sil
   - İSTİSNA: İşlemci/Model gibi kritik bilgiler her zaman başlıktan güncellenir
   - ÖRNEK: Başlık "HP Laptop Siyah 16GB" ve Renk_Temel boşsa → Renk: "Siyah" yaz
   - ÖRNEK: Başlık "HP Laptop Siyah" ve Renk_Temel "Gümüş" doluysa → Renk: "Gümüş" KORU, başlıktan "Siyah"ı sil ama sütuna yazma

3. **BAŞLIK TEMİZLİĞİ (KRİTİK - TEMPLATE SİSTEMİ):**

   TEMPLATE KURALLARI (ÇOK ÖNEMLİ):
   - Eğer _Template_Basliktan_Silinecek_Ozellikler alanı varsa, bu alandaki özellikleri başlıktan MUTLAKA SİL
   - Template'de OLMAYAN özellikler başlıkta KALACAK (ürünü tanımlayan özellikler)
   - Template'de OLAN özellikler başlıktan SİLİNECEK (çünkü zaten özellik sütunlarına yazıldı)
   - ÖRNEK: Başlık "Su Geçirmez Siyah Çanta", Template'de ["Renk_Temel", "Urun_Tipi"] var
     → "Siyah" (Renk) ve "Çanta" (Ürün Tipi) başlıktan SİLİNECEK
     → "Su Geçirmez" başlıkta KALACAK (template'de yok, ürünü tanımlıyor)
     → Sonuç: "Su Geçirmez"
   
   GENEL BAŞLIK TEMİZLİK KURALLARI:
   - MARKA İSMİNİ BAŞLIKTAN SİL (HP, Dell, Lenovo, Philips, AWOX, vb. - kategorinin markalarına göre)
   - Template'deki özellikleri başlıktan SİL (yukarıdaki kurala göre)
   - Özellik sütunlarına yazdığın bilgileri başlıktan SİL
   - Ürün kodları (CNT ile başlayanlar, model kodları) BAŞLIKTA KALSIN
   - Geriye sadece model adı, ürün kodu ve template'de olmayan özellikler kalsın

4. **ÜRÜN TİPİ OLUŞTURMA (KRİTİK - OLABİLDİĞİNCE GENEL TUT):**

   - Ürün Tipi sütunu YOKSA veya BOŞSA → Başlıktan ve kategoriden analiz ederek ÜRÜN TİPİ OLUŞTUR
   - ÜRÜN TİPİ MUTLAKA GENEL OLMALI! Sadece ana kategori adını yaz:
     * "X Klima" → Ürün Tipi: "Klima" (sadece "Klima"), "X" gibi nitelikler BAŞLIĞIN EN SONUNA eklenir
     * "Inverter Klima", "Dual Klima" → Ürün Tipi: "Klima"; başlık sonuna "Inverter", "Dual" vb. ekle
     * "Cam Su Isıtıcısı", "Çelik Su Isıtıcısı" → Ürün Tipi: "Su Isıtıcısı"; "Cam", "Çelik" başlıkta kalır
     * Laptop kategorisi: "Laptop" veya "Gaming Laptop" (sadece gaming belirginse)
     * Diğer kategoriler: Genel ad kullan (ör: "Telefon", "Tablet", "Monitör", "Klima", "Buzdolabı")
   - Olası eklemeler/nitelikler (Inverter, X, Pro, Plus, Mini vb.) ÜRÜN TİPİNE DEĞİL, BAŞLIĞIN SONUNA yaz
   - ÖRNEK: "X Klima 12000 BTU" → Ürün Tipi: "Klima", Başlık: "Model123 12000 BTU X"

5. **DEĞER STANDARDİZASYONU (ARALIK/ÇOKLU DEĞER İÇİN - KRİTİK - ÖĞREN VE UYGULA):**

   ARALIK/ÇOKLU DEĞER GÖRDÜĞÜNDE MUTLAKA TEK DEĞER SEÇ:
   
   - "2000 W ve altı" → "2000 W" (üst değeri seç, "ve altı" ifadesini kaldır)
   - "2000 W ve üstü" → "2000 W" (değeri koru, "ve üstü" ifadesini kaldır)
   - "50 Hz/60 Hz" → "60 Hz" (büyük olanı seç - frekans için genelde 60 Hz tercih edilir)
   - "40/50 Hz" → "50 Hz" (büyük olanı seç)
   - "1-2 L" veya "1,8-2 L" → "2 l" (üst değeri seç, küçük harf)
   - "1.5-2.0 L" → "2 l" (üst değeri seç, küçük harf)
   - "220-240 V" → "220 V" (alt değeri seç - standart voltaj) veya "240 V" (üst değer)
   - "16GB/32GB" → "32 GB" (büyük olanı seç, bilgisayar birimi büyük harf)
   - "501-1000 Watt" → "1000 W" (üst değeri seç)
   - "15+1 Program" veya "16 Program" → "16" (Sadece rakam, ek özellikleri dahil et)
   - "15 Programlı", "15 Program" → "15" (Sadece rakam)
   
   GENEL KURALLAR:
   - Aralık varsa (örn: "1-2 L", "220-240 V") → ÜST DEĞERİ seç (daha yüksek kapasite/özellik)
   - Çoklu değer varsa (örn: "50 Hz/60 Hz") → BÜYÜK OLANI seç
   - "ve altı", "ve üstü", "veya", "/" gibi ifadeleri kaldır, sadece tek değer yaz
   - Frekans için: 60 Hz > 50 Hz (daha yüksek frekans tercih edilir)
   - Kapasite için: Daha büyük değer tercih edilir
   - Voltaj için: Standart değer (220 V) veya üst değer seçilebilir
   - ÖNEMLİ: Asla aralık veya çoklu değer bırakma, MUTLAKA tek değer seç ve yaz!

6. **KATEGORİYE ÖZEL KURALLAR (ÖRNEKLER - YENİ KATEGORİLER İÇİN BENZER MANTIK UYGULA):**

   LAPTOP/DİZÜSTÜ BİLGİSAYAR için:
   - Disk: "1TBSSD+2TBSSD" → "2 TB" (büyük olan, sayı ve birim ayrı, SSD yazma - BİLGİSAYAR BİRİMİ BÜYÜK HARF)
   - RAM: "16GB" → "16 GB" (sayı ve birim ayrı - BİLGİSAYAR BİRİMİ BÜYÜK HARF)
   - Ekran: Sadece boyut (15.6 İnç), çözünürlük başlıkta kalsın
   - Gaming varsa → Ürün Tipi: "Gaming Laptop", yoksa "Laptop"
   
   KETTLE/SU ISITICISI için:
   - Kapasite (Hacimsel kapasite sütununa yazılacak): "1.8Lt" veya "1.8 Lt" veya "2 L" veya "1-2 L" → "2 l" formatında (aralık varsa üst değer, sayı ve birim ayrı, küçük harf)
   - Güç (Maksimum güç sütununa yazılacak): "2200W" veya "2000 W ve altı" → "2000 W" (tek değer, "ve altı" kaldır)
   - Frekans (Frekans sütununa yazılacak): "50 Hz/60 Hz" → "60 Hz" (büyük olanı seç)
   - Voltaj (Giriş Voltajı sütununa yazılacak): "220-240 V" → "220 V" (standart değer) veya "240 V" (üst değer)
   - Malzeme: "Çelik", "Inox" gibi bilgileri koru
   - Ürün Tipi: "Su Isıtıcısı" (her zaman)
   - ÖNEMLİ: Kapasite, güç, frekans, voltaj gibi değerler başlıktan SİLİNMELİ ama özellik sütununa TEK DEĞER olarak yazılmalı (aralık/çoklu değer varsa birini seç)
   - JSON çıktısında şu alanları kullan: "Kapasite", "Guc" (veya "Güç"), "Frekans", "Voltaj"

7. **STANDART KURALLAR (TÜM KATEGORİLER İÇİN):**

   - Full HD → FHD (her yerde)
   - Kısaltmaları aç (W11P → Windows 11 Pro, vb.)
   - Çelişkileri tespit et ve uyarı ver (özellikle kritik özellikler için)
   - Format standardizasyonu (16gb → 16 GB, 1.8 Lt → 1.8 Litre, vb.)
   - BİRİM YAZIMI (KRİTİK - BU FORMATLARI KULLAN): Sayı ile birim arasında BOŞLUK olmalı.
     * BİRİM FORMATLARI:
       - Güç (Watt): "W" (büyük harf) → "2200 W", "2000 W"
       - Basınç: "bar" → "5 bar"
       - Ağırlık: "kg" → "2 kg", "500 g"
       - Depolama: "GB", "TB", "MB", "KB" (büyük harf) → "16 GB", "1 TB"
       - Ekran boyutu: "inç" → "15.6 inç"
       - Hacim: "l" → "2 l"
       - Uzunluk: "cm", "m" → "40 cm"
     * Örnekler: "2200W"→"2200 W", "16gb"→"16 GB", "15.6inc"→"15.6 inç", "2kg"→"2 kg", "5bar"→"5 bar"
   - İngilizce renkleri Türkçeye çevir (Red → Kırmızı, Space Grey → Uzay Grisi)
   - Ürün kodları (CNT ile başlayanlar, model kodları) BAŞLIKTA KALSIN
   - ÖNEMLİ: Özellik sütunlarına yazdığın tüm bilgiler (kapasite, güç, boyut, RAM, Disk vb.) başlıktan SİLİNMELİ

8. **UYUŞMAZLIK KONTROLÜ:**
   - Eğer bir özellik sütunu DOLUYSA, başlıktaki bilgiyle KARŞILAŞTIR
   - Sadece AŞIRI ve bariz çelişkiler için uyarı ver (Örn: Başlık "Windows 11" ama sütun "FreeDOS")
   - Normal boyut farkları için uyarı verme (Örn: Başlık 16GB, Sütun 8GB)

9. **YENİ KATEGORİLER İÇİN:**
   - Kategorinin tipik özelliklerini analiz et
   - Başlıktan hangi bilgilerin çıkarılacağını belirle
   - O kategorinin standart formatlarını uygula
   - Genel kuralları (marka silme, kod koruma, vb.) uygula

10. **EKSİK SÜTUNLAR (_Eksik_Sutunlar varsa):**
   - _Eksik_Sutunlar listesindeki sütunlar boş; mümkün olduğunca çok sütunu doldur
   - Ürün adı, model kodu, marka, kategori bilgisinden çıkarabildiğin tüm değerleri yaz
   - "eksik_sutun_degerleri"nde Excel sütun adıyla ver. Format: W, bar, kg, GB, inç kuralına uy
   - Dayanağı olmayan tahmin yapma; ama ürün bilgisi bir değere işaret ediyorsa (örn. model kodu, başlık) doldur
   - Hiçbir ipucu yoksa boş bırak

11. **ÇELİŞKİ ÇÖZÜMÜ (uyari ile birlikte):**
   - Çelişki tespit ettiğinde sadece uyari verme; aynı yanıtta "celiski_cozum" ile doğru değeri belirt
   - celiski_cozum: {"ozellik_adi": "Isletim_Sistemi", "dogru_deger": "Windows 11", "kaynak": "baslik" veya "ozellik"}
   - Çelişki yoksa celiski_cozum: null

ÖNEMLİ: Önce başlıktan özellikleri çıkar ve özellik sütunlarına yaz, SONRA başlığı temizle!

ÇIKTIYI ŞU JSON FORMATINDA VER:

{
  "temiz_baslik": "Model adı ve ürün kodu (marka, kategori ismi ve template'deki özellikler olmadan, template'de olmayan özellikler kalacak)",
  "duzenlenmis_ozellikler": {
    // Kategorinin özelliklerine göre dinamik olarak doldur
    // Örnek Laptop: Renk, Isletim_Sistemi, RAM, Disk, Ekran, Islemci, Grafik_Karti, Urun_Tipi
    // Örnek KETTLE: Kapasite (Hacimsel kapasite için), Guc veya Güç (Maksimum güç için), Frekans, Voltaj (Giriş Voltajı için), Malzeme, Renk, Urun_Tipi
    // Yeni kategoriler için: O kategorinin tipik özelliklerini çıkar
  },
  "uyari": "null veya çelişki/uyuşmazlık açıklaması",
  "eksik_sutun_degerleri": {"Sütun_Adı": "değer", ...} veya {} (_Eksik_Sutunlar yoksa boş),
  "celiski_cozum": {"ozellik_adi": "...", "dogru_deger": "...", "kaynak": "baslik|ozellik"} veya null
}
"""

# Kısa prompt: daha hızlı yanıt (varsayılan); GEMINI_FAST=0 ile tam prompt kullanılır
system_instruction_compact = """Ürün katalog yöneticisi. (1) Başlıktan özellikleri çıkar, boş sütunlara yaz; dolu sütunlara dokunma. (2) Marka ve template'deki özellikleri başlıktan sil, model/kod kalsın. (3) Ürün Tipi: OLABİLDİĞİNCE GENEL tut (örn. "Klima" yaz, "X Klima" değil; "X" gibi nitelikler başlığın sonuna). (4) Birimler: W, bar, kg, GB, inç formatında yaz (örn: "2200 W", "16 GB", "15.6 inç"). (5) Aralık/çoklu değerde tek değer seç. (6) _Eksik_Sutunlar: Mümkün olduğunca çok sütunu doldur; ürün adı/model/marka bilgisinden çıkarabildiğini yaz. Dayanağı olmayan tahmin yapma; ipucu varsa doldur. (7) Çelişki varsa celiski_cozum ekle.
Çıktı JSON: {"temiz_baslik": "...", "duzenlenmis_ozellikler": {...}, "uyari": "...", "eksik_sutun_degerleri": {"Sütun_Adı": "değer"}, "celiski_cozum": {...} veya null}
"""

def _get_system_instruction():
    return system_instruction_compact if os.getenv("GEMINI_FAST", "1") == "1" else system_instruction

def urun_isle(row_dict, eksik_sutunlar=None, max_retries=3):
    """
    Ürün işleme: başlık temizleme, özellik çıkarma, eksik sütun doldurma ve çelişki çözümü TEK API çağrısında.
    
    Args:
        row_dict: Ürün verisi (Excel satırı)
        eksik_sutunlar: Boş Excel sütun adları listesi (örn. ["RAM Bellek Boyutu", "Renk (temel)"])
        max_retries: API retry sayısı
    """
    # 1. Excel'deki Türkçe sütun isimlerini teknik kodlara çevir
    teknik_veri = {}
    for excel_key, deger in row_dict.items():
        if pd.notna(deger):
            # Türkçe sütun ismini teknik koda çevir
            teknik_key = EXCEL_TO_TECHNICAL.get(excel_key, excel_key)
            teknik_veri[teknik_key] = deger
    
    # 2. Teknik kodları anlaşılır isimlere çevir (Mapping)
    anlasilir_veri = {}
    for teknik_key, deger in teknik_veri.items():
        yeni_key = SUTUN_HARITASI.get(teknik_key, teknik_key)  # Haritada yoksa eskisini kullan
        if pd.notna(deger):  # Boş hücreleri gönderme
            anlasilir_veri[yeni_key] = deger
    
    # 3. Kategori bilgisini daha belirgin ekle ve template'i bul
    template_ozellikler = None
    if 'Kategori' in row_dict:
        kategori = str(row_dict.get('Kategori', '')).strip()
        if pd.notna(kategori) and kategori and kategori != 'CATEGORY':
            anlasilir_veri['_Kategori_Bilgisi'] = kategori
            anlasilir_veri['_Kategori_Notu'] = f"Bu ürün '{kategori}' kategorisinde. Bu kategorinin tipik özelliklerine göre başlıktan bilgi çıkar ve uygun formatları uygula."
            
            # Template'i bul
            template_ozellikler = template_bul(kategori)
            if template_ozellikler:
                anlasilir_veri['_Template_Basliktan_Silinecek_Ozellikler'] = template_ozellikler
                anlasilir_veri['_Template_Notu'] = f"Bu kategoride başlıktan şu özellikler SİLİNECEK (template'de var): {', '.join(template_ozellikler)}. Template'de OLMAYAN özellikler başlıkta KALACAK."

    # 3b. Eksik sütunları ekle (tek çağrıda doldurulsun)
    if eksik_sutunlar:
        anlasilir_veri['_Eksik_Sutunlar'] = eksik_sutunlar
        anlasilir_veri['_Eksik_Notu'] = "Bu sütunlar boş. Mümkün olduğunca çok sütunu doldur; ürün adı/model/marka bilgisinden çıkarabildiğini yaz. Dayanağı olmayan tahmin yapma."

    # 4. Prompt oluştur
    prompt = f"GİRDİ VERİSİ:\n{json.dumps(anlasilir_veri, ensure_ascii=False)}"
    
    # 5. API İsteği - Retry mekanizması ile (ana thread'de; tam yanıt için)
    sys_instr = _get_system_instruction()
    for attempt in range(max_retries):
        try:
            response = model.generate_content(sys_instr + prompt)
            data = json.loads(response.text)
            # Boş/eksik yanıt kontrolü: temiz_baslik veya duzenlenmis_ozellikler dolu olmalı
            if not data.get("temiz_baslik") and not data.get("duzenlenmis_ozellikler"):
                raise ValueError("Gemini boş yanıt döndü")
            return data
        except (ValueError, json.JSONDecodeError) as e:
            if attempt < max_retries - 1:
                print(f"  ⏳ Boş/geçersiz yanıt, yeniden denenecek... ({attempt + 1}/{max_retries})", flush=True)
                time.sleep(3)
                continue
            return {"uyari": "API boş yanıt döndü", "temiz_baslik": row_dict.get("Başlık", row_dict.get("TITLE__TR_TR", "")), "duzenlenmis_ozellikler": {}}
        except Exception as e:
            error_str = str(e)
            
            # Rate limit hatası kontrolü
            if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                if attempt < max_retries - 1:
                    # Hata mesajından bekleme süresini çıkarmaya çalış
                    import re
                    wait_match = re.search(r'retry in (\d+\.?\d*)s', error_str, re.IGNORECASE)
                    if wait_match:
                        wait_time = float(wait_match.group(1)) + 2  # Biraz ekstra bekle
                    else:
                        wait_time = 40 + (attempt * 10)  # Varsayılan: 40, 50, 60 saniye
                    
                    print(f"  ⏳ Rate limit hatası, {wait_time:.1f} saniye bekleniyor... (Deneme {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"  ❌ Rate limit hatası devam ediyor, maksimum deneme sayısına ulaşıldı.")
                    return {"uyari": f"Rate Limit Hatası: API kotası aşıldı", "temiz_baslik": row_dict.get('Başlık', row_dict.get('TITLE__TR_TR', 'HATA'))}
            else:
                # Diğer hatalar
                print(f"  ❌ Hata oluştu: {error_str[:100]}")
                return {"uyari": f"API Hatası: {error_str[:200]}", "temiz_baslik": row_dict.get('Başlık', row_dict.get('TITLE__TR_TR', 'HATA'))}
    
    # Tüm denemeler başarısız
    return {"uyari": "Tüm denemeler başarısız oldu", "temiz_baslik": row_dict.get('Başlık', row_dict.get('TITLE__TR_TR', 'HATA'))}

def main():
    print(f"📂 Excel okunuyor: {GIRIS_DOSYASI}")
    print(f"📁 Çalışma dizini: {os.getcwd()}")
    if not os.path.exists(GIRIS_DOSYASI):
        print(f"❌ Dosya bulunamadı: {GIRIS_DOSYASI}")
        print(f"📋 Klasördeki Excel dosyaları: {[f for f in os.listdir('.') if f.endswith('.xlsx')]}")
        return
    try:
        df = pd.read_excel(GIRIS_DOSYASI)
        print(f"✅ Dosya okundu: {len(df)} satır bulundu")
    except Exception as e:
        print(f"❌ Dosya okunurken hata oluştu: {str(e)}")
        return
    
    # İlk satır teknik kodlar içeriyorsa atla (gerçek veriler index 1'den başlıyor)
    if len(df) > 0 and df.iloc[0].get('Başlık', '').startswith('TITLE'):
        print("⚠️  İlk satır teknik kodlar içeriyor, atlanıyor...")
        df = df.iloc[1:].reset_index(drop=True)
    
    # TEST İÇİN: Tüm satırları işle (limit yok)
    # TEST_LIMIT = 5
    # if len(df) > TEST_LIMIT:
    #     print(f"🧪 TEST MODU: Sadece ilk {TEST_LIMIT} satır işlenecek (toplam {len(df)} satır var)")
    #     df = df.head(TEST_LIMIT).copy()
    # Eğer çıktı dosyası varsa, işlenmiş ürünleri yükle
    islenmis_sku = set()
    sonuclar = []
    
    try:
        if os.path.exists(CIKIS_DOSYASI):
            df_mevcut = pd.read_excel(CIKIS_DOSYASI)
            # Sadece geçerli SHOP_SKU'ya sahip satırları say
            if 'SHOP_SKU' in df_mevcut.columns:
                # Boş olmayan SKU'lara sahip satırları filtrele
                gecerli_satirlar = df_mevcut[df_mevcut['SHOP_SKU'].notna() & (df_mevcut['SHOP_SKU'].astype(str).str.strip() != '')]
                islenmis_sku = set(gecerli_satirlar['SHOP_SKU'].astype(str))
                sonuclar = gecerli_satirlar.to_dict('records')
                islenmis_sayisi = len(gecerli_satirlar)
            else:
                # SHOP_SKU sütunu yoksa, tüm satırları kullan ama uyarı ver
                print("⚠️  UYARI: Çıktı dosyasında 'SHOP_SKU' sütunu bulunamadı!")
                islenmis_sku = set()
                sonuclar = []
                islenmis_sayisi = 0
            
            print(f"✅ Mevcut dosya bulundu: {islenmis_sayisi} ürün zaten işlenmiş.")
            kalan = len(df) - islenmis_sayisi
            print(f"🔄 Kalan {kalan} ürün işlenecek...")
    except Exception as e:
        print(f"ℹ️  Yeni dosya oluşturulacak: {str(e)}")
    
    print("🚀 İşlem başlıyor...")
    
    # Sadece işlenmemiş satırları işle
    islenen_sayisi = 0
    for index, row in df.iterrows():
        row_dict = row.to_dict()
        sku = str(row_dict.get('SHOP_SKU', ''))
        
        # Eğer bu ürün zaten işlenmişse atla
        if sku in islenmis_sku:
            continue
        
        # İlerleme göster
        islenen_sayisi += 1
        if islenen_sayisi % 1 == 0:
            print(f"İşleniyor: {islenen_sayisi}/{len(df) - len(sonuclar)} (Toplam: {index + 1}/{len(df)})")
        
        try:
            # Eksik sütunları hesapla (urun_isle tek çağrıda dolduracak)
            atlanacak_sutunlar = {'Başlık', 'SHOP_SKU', 'Uyari', 'Kategori'}
            eksik_sutunlar = []
            if os.getenv("GEMINI_EKSIK_SUTUN", "1") == "1":
                for sutun_adi in row_dict.keys():
                    if sutun_adi in atlanacak_sutunlar:
                        continue
                    mevcut = row_dict.get(sutun_adi, None)
                    if pd.notna(mevcut) and (not isinstance(mevcut, str) or str(mevcut).strip() != ''):
                        continue
                    eksik_sutunlar.append(sutun_adi)

            # Kategori bilgisini ekle (varsa)
            row_for_api = row_dict.copy()
            if 'Kategori' in row_dict:
                kategori = row_dict.get('Kategori', '')
                if pd.notna(kategori) and kategori:
                    row_for_api['_Kategori_Bilgisi'] = str(kategori)
            gemini_cikti = urun_isle(row_for_api, eksik_sutunlar=eksik_sutunlar if eksik_sutunlar else None)
            
            # Orijinal Excel yapısını koru, sadece güncellemeler yap
            # Orijinal satırı kopyala
            flat_result = row_dict.copy()
            
            # Başlığı güncelle
            flat_result['Başlık'] = gemini_cikti.get("temiz_baslik", row_dict.get('Başlık', ''))
            
            # Özellikleri güncelle (sadece boş olanları veya işlemci)
            ozellikler = gemini_cikti.get("duzenlenmis_ozellikler", {})
            
            # İşlemci her zaman güncellenir
            if "Islemci" in ozellikler:
                flat_result['İşlemci (tr_TR)'] = ozellikler.get("Islemci", row_dict.get('İşlemci (tr_TR)', ''))
            
            # Diğer özellikler sadece boşsa doldurulur
            if "Renk" in ozellikler and pd.isna(row_dict.get('Renk (temel)', None)):
                flat_result['Renk (temel)'] = ozellikler.get("Renk", '')
            
            if "Isletim_Sistemi" in ozellikler and pd.isna(row_dict.get('İşletim Sistemi', None)):
                isletim_sistemi = ozellikler.get("Isletim_Sistemi", '')
                # Full HD ifadelerini FHD'ye çevir
                if isletim_sistemi:
                    isletim_sistemi = isletim_sistemi.replace("Full HD", "FHD").replace("FullHD", "FHD").replace("Full High Definition", "FHD")
                flat_result['İşletim Sistemi'] = isletim_sistemi
            
            if "RAM" in ozellikler and pd.isna(row_dict.get('RAM Bellek Boyutu', None)):
                flat_result['RAM Bellek Boyutu'] = ozellikler.get("RAM", '')
            
            if "Disk" in ozellikler and pd.isna(row_dict.get('Sabit disk kapasitesi', None)):
                flat_result['Sabit disk kapasitesi'] = ozellikler.get("Disk", '')
            
            if "Ekran" in ozellikler and pd.isna(row_dict.get('Ekran Boyutu (inç)', None)):
                flat_result['Ekran Boyutu (inç)'] = ozellikler.get("Ekran", '')
            
            if "Grafik_Karti" in ozellikler and pd.isna(row_dict.get('Grafik Kartı', None)):
                grafik_karti = ozellikler.get("Grafik_Karti", '')
                # Full HD ifadelerini FHD'ye çevir
                if grafik_karti:
                    grafik_karti = grafik_karti.replace("Full HD", "FHD").replace("FullHD", "FHD").replace("Full High Definition", "FHD")
                flat_result['Grafik Kartı'] = grafik_karti
            
            # KETTLE/SU ISITICISI için özel sütunlar (aralık/çoklu değer varsa güncelle)
            if "Kapasite" in ozellikler:
                # Boşsa doldur, doluysa ama aralık/çoklu değer içeriyorsa güncelle
                mevcut_kapasite = str(row_dict.get('Hacimsel kapasite', '')).strip()
                if pd.isna(row_dict.get('Hacimsel kapasite', None)) or not mevcut_kapasite:
                    flat_result['Hacimsel kapasite'] = ozellikler.get("Kapasite", '')
                elif '-' in mevcut_kapasite or '/' in mevcut_kapasite:  # Aralık/çoklu değer varsa güncelle
                    flat_result['Hacimsel kapasite'] = ozellikler.get("Kapasite", mevcut_kapasite)
            
            if "Guc" in ozellikler or "Güç" in ozellikler:
                guc = ozellikler.get("Guc", ozellikler.get("Güç", ''))
                if guc:
                    mevcut_guc = str(row_dict.get('Maksimum güç', '')).strip()
                    if pd.isna(row_dict.get('Maksimum güç', None)) or not mevcut_guc:
                        flat_result['Maksimum güç'] = guc
                    elif 've altı' in mevcut_guc.lower() or 've üstü' in mevcut_guc.lower() or '-' in mevcut_guc or '/' in mevcut_guc:  # Aralık/çoklu değer varsa güncelle
                        flat_result['Maksimum güç'] = guc
            
            if "Frekans" in ozellikler:
                mevcut_frekans = str(row_dict.get('Frekans', '')).strip()
                if pd.isna(row_dict.get('Frekans', None)) or not mevcut_frekans:
                    flat_result['Frekans'] = ozellikler.get("Frekans", '')
                elif '/' in mevcut_frekans:  # Çoklu değer varsa güncelle
                    flat_result['Frekans'] = ozellikler.get("Frekans", mevcut_frekans)
            
            if "Voltaj" in ozellikler:
                mevcut_voltaj = str(row_dict.get('Giriş Voltajı', '')).strip()
                if pd.isna(row_dict.get('Giriş Voltajı', None)) or not mevcut_voltaj:
                    flat_result['Giriş Voltajı'] = ozellikler.get("Voltaj", '')
                elif '-' in mevcut_voltaj:  # Aralık varsa güncelle
                    flat_result['Giriş Voltajı'] = ozellikler.get("Voltaj", mevcut_voltaj)
            
            # Ürün Tipi: Her zaman oluştur (sütun yoksa veya boşsa)
            # Önce Gemini'den gelen değeri kontrol et
            if "Urun_Tipi" in ozellikler:
                flat_result['Ürün Tipi (tr_TR)'] = ozellikler.get("Urun_Tipi", '')
            # Eğer Gemini'den gelmediyse ve sütun boşsa, kategoriye göre belirle
            elif pd.isna(row_dict.get('Ürün Tipi (tr_TR)', None)) or str(row_dict.get('Ürün Tipi (tr_TR)', '')).strip() == '':
                kategori = str(row_dict.get('Kategori', '')).upper()
                baslik = str(row_dict.get('Başlık', '')).lower()
                
                if "KETTLE" in kategori or "SU ISITICISI" in kategori:
                    flat_result['Ürün Tipi (tr_TR)'] = "Su Isıtıcısı"
                elif "LAPTOP" in kategori or "DIZUSTU" in kategori or "BILGISAYAR" in kategori:
                    if "gaming" in baslik:
                        flat_result['Ürün Tipi (tr_TR)'] = "Gaming Laptop"
                    else:
                        flat_result['Ürün Tipi (tr_TR)'] = "Laptop"
                else:
                    # Diğer kategoriler için kategorinin kendisini kullan (genel isim)
                    kategori_adi = str(row_dict.get('Kategori', '')).strip()
                    if kategori_adi and kategori_adi != 'CATEGORY':
                        flat_result['Ürün Tipi (tr_TR)'] = kategori_adi
                    else:
                        flat_result['Ürün Tipi (tr_TR)'] = "Diğer"
            
            # Uyarı sütunu ekle - çelişki çözümü urun_isle tek çağrıda döndürüyor (celiski_cozum)
            yeni_uyari = gemini_cikti.get("uyari", '')
            celiski_cozum = gemini_cikti.get("celiski_cozum")
            if celiski_cozum and isinstance(celiski_cozum, dict):
                ozellik_adi = celiski_cozum.get("ozellik_adi", "")
                dogru_deger = celiski_cozum.get("dogru_deger", "")
                kaynak = celiski_cozum.get("kaynak", "")
                ters_harita = {
                    "Isletim_Sistemi": "İşletim Sistemi",
                    "Renk_Temel": "Renk (temel)",
                    "Renk_Uretici": "Renk (Üreticiye Göre) (tr_TR)",
                    "RAM_Boyutu": "RAM Bellek Boyutu",
                    "Disk_Kapasitesi": "Sabit disk kapasitesi",
                    "Ekran_Boyutu_Inc": "Ekran Boyutu (inç)",
                    "Grafik_Karti": "Grafik Kartı",
                    "Islemci_Modeli": "İşlemci (tr_TR)",
                    "Urun_Tipi": "Ürün Tipi (tr_TR)"
                }
                excel_sutun_ismi = ters_harita.get(ozellik_adi)
                if excel_sutun_ismi and excel_sutun_ismi in flat_result and dogru_deger:
                    flat_result[excel_sutun_ismi] = dogru_deger
                    print(f"  ✅ {excel_sutun_ismi} güncellendi: '{dogru_deger}'")
                    yeni_uyari = f"Çözüldü: {ozellik_adi} = {dogru_deger} (kaynak: {kaynak})"

            # Uyarıyı ekle
            if 'Uyari' not in flat_result:
                flat_result['Uyari'] = yeni_uyari if yeni_uyari and yeni_uyari != 'null' else ''
            else:
                mevcut_uyari = flat_result.get('Uyari', '')
                if pd.notna(yeni_uyari) and yeni_uyari and yeni_uyari != 'null':
                    flat_result['Uyari'] = f"{mevcut_uyari}; {yeni_uyari}" if mevcut_uyari else yeni_uyari

            # Eksik sütun değerleri - urun_isle tek çağrıda doldurdu (eksik_sutun_degerleri)
            eksik_degerler = gemini_cikti.get("eksik_sutun_degerleri") or {}
            if isinstance(eksik_degerler, dict):
                for sutun_adi, bulunan_deger in eksik_degerler.items():
                    if sutun_adi in flat_result and bulunan_deger and (not isinstance(bulunan_deger, str) or "bilinmiyor" not in str(bulunan_deger).lower()):
                        flat_result[sutun_adi] = str(bulunan_deger).strip() if isinstance(bulunan_deger, str) else bulunan_deger
                        print(f"  ✅ {sutun_adi} Gemini'den bulundu: {bulunan_deger}")
            
            sonuclar.append(flat_result)
            
            # Her 5 üründe bir ara kayıt yap (güvenlik için)
            if len(sonuclar) % 5 == 0:
                df_ara = pd.DataFrame(sonuclar)
                orijinal_sutunlar = list(df.columns)
                if 'Uyari' not in orijinal_sutunlar:
                    orijinal_sutunlar.append('Uyari')
                df_ara = df_ara.reindex(columns=orijinal_sutunlar)
                df_ara.to_excel(CIKIS_DOSYASI, index=False)
                print(f"  💾 Ara kayıt yapıldı: {len(sonuclar)} ürün kaydedildi")
            
        except KeyboardInterrupt:
            print("\n⚠️  İşlem kullanıcı tarafından durduruldu!")
            df_ara = pd.DataFrame(sonuclar)
            orijinal_sutunlar = list(df.columns)
            if 'Uyari' not in orijinal_sutunlar:
                orijinal_sutunlar.append('Uyari')
            df_ara = df_ara.reindex(columns=orijinal_sutunlar)
            df_ara.to_excel(CIKIS_DOSYASI, index=False)
            print(f"💾 Mevcut ilerleme kaydedildi: {len(sonuclar)} ürün")
            return
        except Exception as e:
            print(f"  ❌ Hata: {str(e)[:100]}")
            # Hata olsa bile sonucu ekle (uyarı ile)
            flat_result = {
                "Orijinal_Baslik": row_dict.get('Başlık', row_dict.get('TITLE__TR_TR', '')),
                "SHOP_SKU": sku,
                "Temiz_Baslik": row_dict.get('Başlık', row_dict.get('TITLE__TR_TR', '')),
                "Uyari": f"İşleme hatası: {str(e)[:200]}",
            }
            sonuclar.append(flat_result)
        
        # Rate limit için bekleme (GEMINI_DELAY ile ayarlanabilir, varsayılan 0.5s)
        time.sleep(float(os.getenv("GEMINI_DELAY", "0.5")))
    
    # Final kayıt - Sadece işlenmiş ürünleri kaydet, orijinal Excel yapısını koru
    if len(sonuclar) > 0:
        df_sonuc = pd.DataFrame(sonuclar)
        
        # Orijinal sütun sırasını koru
        orijinal_sutunlar = list(df.columns)
        # Uyarı sütunu yoksa ekle
        if 'Uyari' not in orijinal_sutunlar:
            orijinal_sutunlar.append('Uyari')
        
        # Sadece mevcut sütunları al (eksik sütunlar için boş değer)
        df_sonuc = df_sonuc.reindex(columns=orijinal_sutunlar)
        
        # Sadece işlenmiş ürünleri kaydet (tüm orijinal sütunları koru)
        df_sonuc.to_excel(CIKIS_DOSYASI, index=False)
        print(f"\n✅ Bitti! Toplam {len(sonuclar)} ürün işlendi. Dosya: '{CIKIS_DOSYASI}'")
        print(f"📋 Orijinal Excel yapısı korundu: {len(orijinal_sutunlar)} sütun")
        print(f"📊 Çıktı dosyasında sadece işlenmiş {len(sonuclar)} ürün var.")
    else:
        print("\n⚠️  İşlenecek yeni ürün bulunamadı!")

if __name__ == "__main__":
    main()
