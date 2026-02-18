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
5. **Environment variables ekle:** Aynı serviste **Variables** kısmına şunları **mutlaka** ekleyin:
   - `GEMINI_API_KEY` = Gemini API anahtarınız (Google AI Studio’dan).
   - `CELERY_BROKER_URL` = Railway Redis URL’i. **Redis servisine tıkla** → **Variables** veya **Connect** → `REDIS_URL` veya `REDIS_PRIVATE_URL` değerini kopyala. Örnek: `redis://default:şifre@containers-us-west-xxx.railway.app:6379`. Aynı URL’i kullan (sonuna `/0` ekleyebilirsin: `.../0`).
   - `CELERY_RESULT_BACKEND` = Aynı Redis URL, sonuna `/1` ekle. Örnek: `redis://default:şifre@...railway.app:6379/1`.
   - **ÖNEMLİ:** Logda `transport: redis://localhost:6379` görüyorsan bu iki değişken tanımlı değil veya yanlış serviste. Ana (web) serviste Variables’a ekle, Redeploy yap.
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
- **Job dosyaları / 404 hatası:** Container yeniden başlayınca veya yeni deploy olunca disk sıfırlanır; `jobs/` silinir, bu yüzden "Durumu yenile" veya indirme **404 Not Found** verebilir. Job’ların **kalıcı** olması için aşağıdaki **Railway Volume** adımlarını uygulayın.
- **Hata alırsan:** Railway’de servis **Logs**’a bakın; Celery ve uvicorn çıktıları orada görünür.
- **"Failed to parse start command":** Start Command alanında sadece `bash start.sh` olmalı. Procfile’daki yorum satırı veya başka bir metin yapıştırdıysanız kaldırın; serviste **Settings** → **Deploy** → Start Command’ı silip boş bırakın (Procfile kullanılır) veya tam olarak `bash start.sh` yazın.

---

## 4. Job’ların kalıcı olması (404 önleme – Railway Volume)

Container restart veya yeni deploy sonrası job’lar silindiği için **404 Not Found** alıyorsan, job dosyalarını kalıcı diske taşı:

1. Railway projesinde **web servisine** (API + Celery çalışan servis) gir.
2. **Variables** → **+ New Variable** → **Add a Variable**.
3. **Raw Editor** ile ekle: `JOBS_BASE_DIR=/data/jobs`
4. **Settings** → **Volumes** → **Add Volume** → Mount path: `/data` → **Add**.
5. **Redeploy** yap (Deploy → **Redeploy** veya son commit’i tekrar pushla).

Bundan sonra job verisi `/data/jobs` altında kalıcı olur; yenileme ve indirme 404 vermemeli.
