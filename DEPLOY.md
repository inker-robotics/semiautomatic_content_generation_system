# Deploying INKER Newsletter Automation (lowest cost)

## Architecture

| Component | Cheapest option | Cost |
|-----------|-----------------|------|
| Backend (FastAPI) | [Render](https://render.com) free web service | $0 |
| Frontend (Next.js) | [Vercel](https://vercel.com) hobby | $0 |
| Database | SQLite on Render disk (dev) or [Neon](https://neon.tech) Postgres free tier | $0 |
| Cron scheduler | GitHub Actions (included) | $0 |
| Email | Gmail SMTP (app password) | $0 |

**Total: $0/month** for low-volume internal use.

---

## How scheduling works

- **Publish days:** Monday, Tuesday, Friday
- **Generation:** One day before each publish day
  - Sunday → Monday edition
  - Monday → Tuesday edition
  - Thursday → Friday edition
- GitHub Actions runs **daily at 18:00 UTC** and calls `POST /api/generate/scheduled`
- The backend only starts a run when tomorrow is Mon/Tue/Fri

---

## 1. Deploy backend (Render)

1. Push this repo to GitHub
2. Create a **Web Service** on Render → connect repo → root directory: `backend`
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Set environment variables from `.env.example`
6. Set `CRON_SECRET` to a long random string
7. Set `BACKEND_URL` to your Render URL (e.g. `https://inker-api.onrender.com`)
8. Set `FRONTEND_URL` to your Vercel URL
9. Set `CORS_ORIGINS` to your Vercel URL

---

## 2. Deploy frontend (Vercel)

1. Import the repo → root directory: `frontend`
2. Set `NEXT_PUBLIC_API_URL` to your Render backend URL
3. Deploy

---

## 3. Enable automatic cron (GitHub Actions)

In GitHub → **Settings → Secrets and variables → Actions**, add:

| Secret | Value |
|--------|-------|
| `BACKEND_URL` | `https://your-backend.onrender.com` |
| `CRON_SECRET` | Same value as backend `CRON_SECRET` |

The workflow `.github/workflows/newsletter-scheduler.yml` will trigger daily.

You can also run it manually: **Actions → newsletter-scheduler → Run workflow**.

---

## 4. Email setup

1. Enable 2FA on Gmail
2. Create an [App Password](https://myaccount.google.com/apppasswords)
3. Set `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `MANAGER_EMAIL` on the backend

Manager receives:
- Full newsletter HTML preview (Student + Faculty editions)
- **Approve for Publishing** button
- **Review & Edit** button → opens `/review?token=...` with preview, edit feedback, and agent config tabs

---

## 5. Local development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `.env` in the project root and fill in values.

---

## 6. Customize day agents

Open **http://localhost:3000/agents** (or your Vercel URL `/agents`).

Edit scout/writer prompts and RSS feeds for:
- **Monday** — AI/ML research breakthroughs
- **Tuesday** — Product & industry innovations
- **Friday** — Tech awareness digest

Changes apply to the next scheduled run for that day.

---

## Optional: Docker

```bash
cp .env.example .env
# edit .env
docker compose up --build
```

---

## Manual test run

Dashboard → **Generate Next Scheduled Edition**

Or:

```bash
curl -X POST http://127.0.0.1:8000/api/generate/manual \
  -H "Content-Type: application/json" \
  -d "{\"publish_weekday\": 0}"
```

`publish_weekday`: `0` = Monday, `1` = Tuesday, `4` = Friday
