# Yeni mimariyi online çalıştırma (Railway + Streamlit Cloud)

Bu rehber, **FastAPI + Celery + Redis + Streamlit** mimarisini bulutta çalıştırman için gerekli adımları anlatır. Backend (API + Worker) Railway’de, arayüz Streamlit Cloud’da çalışır.

---

## 1. Railway’de backend’i aç

1. **https://railway.app** → Giriş yap (GitHub ile).
2. **New Project** → **Deploy from GitHub repo** → `geminiproj` reponuzu seçin.
3. **Add Redis:** Project’e gir → **+ New** → **Database** → **Add Redis**. Redis otomatik oluşur; env’e `REDIS_URL` (veya benzeri) eklenir.
4. **Servisi ayarla:** GitHub’dan deploy edilen servise tıkla.
   - **Settings** → **Build:** Build Command boş bırakılabilir (veya `pip install -r requirements.txt`).  
   - **Settings** → **Deploy / Start Command:** Tam olarak `bash start.sh` yazın (başka metin veya yorum eklemeyin). Boş bırakırsanız Procfile’daki `web: bash start.sh` kullanılır.
   - **Settings** → **Root Directory:** Boş (repo kökü).
5. **Environment variables ekle:** Aynı serviste **Variables** kısmına şunları ekleyin:
   - `GEMINI_API_KEY` = Gemini API anahtarınız (Google AI Studio’dan).
   - `CELERY_BROKER_URL` = Redis URL. Railway’de Redis ekledikten sonra **Redis servisine tıkla** → **Connect** veya **Variables**’da gösterilen URL. Örnek: `redis://default:xxx@containers-us-west-xxx.railway.app:6379`. Broker için aynı URL’i kullanın (veya sonuna `/0` ekleyin: `.../0`).
   - `CELERY_RESULT_BACKEND` = Aynı Redis URL, farklı db: sonuna `/1` ekleyin. Örnek: `redis://default:xxx@...railway.app:6379/1`.
6. **Public URL ver:** Serviste **Settings** → **Networking** → **Generate Domain**. Örnek: `geminiproj-api.up.railway.app`. Bu adresi kopyalayın; Streamlit’te `BACKEND_URL` olarak kullanacaksınız. **HTTPS** kullanın: `https://geminiproj-api.up.railway.app`.

---

## 2. Streamlit Cloud’da arayüzü aç

1. **https://share.streamlit.io** → Giriş (GitHub).
2. **New app** → Repo: `geminiproj`, Branch: `main`, Main file path: `streamlit_app.py`.
3. **Advanced settings** → **Secrets** (TOML) içine şunu ekleyin:
   ```toml
   BACKEND_URL = "https://geminiproj-api.up.railway.app"
   ```
   Buradaki URL’i 1. adımda aldığınız Railway domain ile değiştirin (slash olmadan, https ile).
4. Deploy’a basın. Streamlit uygulaması açılınca backend’e bu URL üzerinden bağlanır.

---

## 3. Kontrol

- Streamlit sayfasında Excel yükleyip **İşlemi Başlat** deyin.
- **Sidebar’da “✅ API bağlı”** görünmeli.
- Job oluşturulup Celery worker (Railway’de) işleyecek; **Durumu yenile** ile ilerlemeyi görebilirsiniz.
- İş bitince **Temiz katalogu indir** ile Excel’i indirin.

---

## Özet: Senin yapacakların

| Adım | Nerede | Ne yapacaksın |
|------|--------|----------------|
| 1 | Railway | Yeni proje aç, repoyu bağla, Redis ekle. |
| 2 | Railway | Serviste Start Command: `bash start.sh`. |
| 3 | Railway | Variables: `GEMINI_API_KEY`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` (Redis URL’leri). |
| 4 | Railway | Networking’ten domain üret, HTTPS URL’i kopyala. |
| 5 | Streamlit Cloud | Yeni app, repo `geminiproj`, main file `streamlit_app.py`. |
| 6 | Streamlit Cloud | Secrets’a `BACKEND_URL = "https://...railway.app"` ekle (kendi URL’in). |
| 7 | Tarayıcı | Streamlit linkine gir, Excel yükle, işlemi başlat. |

---

## Notlar

- **Redis URL:** Railway Redis eklentisinde **Variables** veya **Connect** kısmında görünür. `REDIS_PRIVATE_URL` veya `REDIS_URL` olabilir; aynı değeri `CELERY_BROKER_URL` ve `CELERY_RESULT_BACKEND` için kullanın, backend için sonuna `/1` ekleyin (broker `/0` veya aynı).
- **Job dosyaları:** Şu an `jobs/` klasörü container içinde; deploy yenilenince silinir. Kalıcı depo istersen Railway Volume ekleyip `JOBS_BASE_DIR` ile bağlayabilirsiniz (ileride).
- **Hata alırsan:** Railway’de servis **Logs**’a bakın; Celery ve uvicorn çıktıları orada görünür.
- **"Failed to parse start command":** Start Command alanında sadece `bash start.sh` olmalı. Procfile’daki yorum satırı veya başka bir metin yapıştırdıysanız kaldırın; serviste **Settings** → **Deploy** → Start Command’ı silip boş bırakın (Procfile kullanılır) veya tam olarak `bash start.sh` yazın.
