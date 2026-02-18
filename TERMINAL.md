# Terminal komutları – sırayla çalıştır

Proje klasöründe (`geminiproj`) **4 ayrı terminal** aç. Her birinde aşağıdaki komutlardan birini çalıştır.

---

## 1. Terminal – Redis

```bash
cd /Users/aysuyzdctn/Desktop/geminiproj
redis-server
```

Redis kurulu değilse: `brew install redis` sonra `brew services start redis`

---

## 2. Terminal – Celery worker

**Mutlaka proje klasöründen çalıştır** (`.env` ve `GEMINI_API_KEY` için):

```bash
cd /Users/aysuyzdctn/Desktop/geminiproj
celery -A celery_app.celery_app worker --loglevel=info
```

Başarılı olursa `celery@... ready` ve `[tasks] . process_catalog_job` görünür. İş gönderince `Task process_catalog_job[...] received` yazmalı.

---

## 3. Terminal – FastAPI (backend)

```bash
cd /Users/aysuyzdctn/Desktop/geminiproj
uvicorn api:app --reload
```

Backend: http://localhost:8000

---

## 4. Terminal – Streamlit (arayüz)

```bash
cd /Users/aysuyzdctn/Desktop/geminiproj
streamlit run streamlit_app.py
```

Tarayıcı: http://localhost:8501

---

## Özet sıra

1. `redis-server`
2. `celery -A celery_app.celery_app worker --loglevel=info`
3. `uvicorn api:app --reload`
4. `streamlit run streamlit_app.py`

Hepsini aynı anda açık tut. Durdurmak için ilgili terminalde **Ctrl+C**.
