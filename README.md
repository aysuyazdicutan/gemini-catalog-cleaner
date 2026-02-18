# Gemini Ürün Katalog Temizleme Projesi

Bu proje, Google Gemini AI kullanarak Excel dosyasındaki ham ürün verilerini temizleyen ve standardize eden bir Python scriptidir.

## Kurulum

1. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

2. API Key'i ayarlayın:
   - `.env.example` dosyasını `.env` olarak kopyalayın:
   ```bash
   cp .env.example .env
   ```
   - `.env` dosyasını açın ve Google Gemini API key'inizi ekleyin:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
   - API key almak için: https://makersuite.google.com/app/apikey

## Kullanım

### Yerel Kullanım (Python Script)

1. Excel dosyanızı proje klasörüne koyun ve `main.py` içinde `GIRIS_DOSYASI` değişkenini güncelleyin.
2. Scripti çalıştırın:
```bash
python main.py
```

3. İşlem tamamlandığında `temizlenmis_katalog.xlsx` dosyası oluşturulacaktır.

### Streamlit Web Uygulaması (FastAPI + Celery + Redis ile)

1. Gerekli servisleri başlatın:
   - Redis (örnek macOS/Homebrew):
     ```bash
     redis-server
     ```
   - Celery worker:
     ```bash
     celery -A celery_app.celery_app worker --loglevel=info
     ```
   - FastAPI backend (uvicorn):
     ```bash
     uvicorn api:app --reload
     ```

2. Streamlit uygulamasını başlatın:
```bash
streamlit run streamlit_app.py
```

3. Tarayıcıda açılan sayfada:
   - Excel dosyanızı yükleyin
   - "Start / Continue Process" butonuna tıklayın
   - Arka planda FastAPI + Celery üzerinden işlenen dosya tamamlandığında temizlenmiş dosyayı indirin

### Streamlit Cloud Deployment

1. GitHub'a push edin
2. https://share.streamlit.io adresine gidin
3. Repo'nuzu bağlayın
4. Main file: `streamlit_app.py`
5. Secrets → TOML formatında ekleyin:
   ```toml
   GEMINI_API_KEY = "your_api_key_here"
   ```

## Özellikler

- Başlıklardan gereksiz bilgileri temizler
- Kısaltmaları tanır ve açılımlarını yapar
- Renk ve teknik terimleri Türkçe'ye çevirir
- Veri formatlarını standardize eder
- Çelişkileri tespit eder ve uyarı verir

## Notlar

- API rate limit'i nedeniyle her satır arasında 1 saniye bekleme yapılır
- Test için script içinde `df.iterrows()` yerine `df.iterrows()[:5]` kullanabilirsiniz





