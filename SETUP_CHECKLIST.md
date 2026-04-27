# Clinical AI Webapp Setup Checklist

## Local Setup

1. Backend env:
   - Copy `backend/.env.example` to `backend/.env`.
   - Set `JWT_SECRET_KEY` to a long random value.
   - For local testing, `DATABASE_URL=sqlite:///./clinical_ai.db` is supported.
   - For production, use Postgres, for example `postgresql+asyncpg://USERNAME:PASSWORD@HOST:5432/DBNAME`.

2. Frontend env:
   - Copy `frontend/.env.local.example` to `frontend/.env.local`.
   - Set `NEXT_PUBLIC_API_BASE_URL` to the deployed backend API URL ending in `/api`.

3. Seed the backend:
   - `cd backend`
   - `python -m app.seed`
   - Optional targeted runs:
     - `python -m app.seed --only admin`
     - `python -m app.seed --only rates`
     - `python -m app.seed --only templates`
     - `python -m app.seed --only settings`

4. Bootstrap admin:
   - Default setup env in `backend/.env.example`:
     - Email: `aleix@drzelisko.com`
     - Password: `Admin123`
     - Name: `Aleixander Puerta`
   - Change the password immediately after first login in any real environment.

## Production Assumptions

- Database: Postgres
- Storage: Google Drive
- Hosting: Vercel
- Primary AI provider: Perplexity
- Fallback: replacement Perplexity key first, Gemini when configured

## Required Backend Vercel Env Vars

- `APP_ENV=production`
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `ALLOWED_ORIGINS`
- `GOOGLE_DRIVE_ROOT_FOLDER_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `AI_PROVIDER=perplexity`
- `PERPLEXITY_API_KEY`
- `GEMINI_API_KEY` when fallback should be available
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_FULL_NAME` for intentional bootstrap seed runs

## Required Frontend Vercel Env Vars

- `NEXT_PUBLIC_APP_NAME`
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_ENABLE_DIAGNOSTICS`
- `NEXT_PUBLIC_ENABLE_REIMBURSEMENT_COMPARISON`

## Health Checks

- `/health`
- `/health/db`
- `/health/drive`
- `/health/ai`
- `/health/templates`

## Deployment Notes

- Backend entrypoint is `backend/api/index.py`.
- Backend Vercel routing is configured in `backend/vercel.json`.
- Run seeds intentionally; set `RUN_SEEDS_ON_STARTUP=true` only for controlled bootstrap deployments.
- Do not commit real API keys, JWT secrets, service account JSON, or production database URLs.
