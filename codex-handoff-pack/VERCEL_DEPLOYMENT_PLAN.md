# Vercel Deployment Plan

This document provides a step‑by‑step guide for deploying the Clinical AI Webapp to Vercel.  The project is split into two separate Vercel deployments: one for the **FastAPI backend** and another for the **Next.js frontend**.  Following this plan ensures that your app runs correctly in the serverless environment.

## 1. Prepare the repository

1. **Unzip and commit the source** – Ensure that the `backend` and `frontend` directories are present in the repository.  Remove the old `clinical-ai-webapp-v2.zip` file.
2. **Include Vercel configuration** – Add the following files to the `backend` directory:
   - `api/index.py` – Imports and exposes the FastAPI `app` from `backend/app/main.py`.
   - `vercel.json` – Configures the Python runtime and routing.
   - `.vercelignore` – Excludes unnecessary files from the backend bundle.
3. **Commit these files** and push to your main branch.

## 2. Backend deployment

1. **Create a new Vercel project** from your GitHub repository.  When prompted:
   - Select the repository.
   - Choose `backend` as the root directory.
   - Set the framework to **Python (FastAPI)**; Vercel will detect the Python runtime via `vercel.json`.
2. **Configure environment variables** for the backend:
   - `GOOGLE_DRIVE_ROOT_FOLDER_ID` – Root folder ID for patient data.
   - `GOOGLE_SERVICE_ACCOUNT_JSON` – Service account JSON string or secret reference.
   - `DATABASE_URL` – E.g., `postgresql+asyncpg://<user>:<password>@<host>/<db>`.
   - `ALLOWED_ORIGINS` – Comma‑separated list of allowed front‑end origins (e.g., `https://your-frontend.vercel.app`).
   - `PERPLEXITY_API_KEY` or `GEMINI_API_KEY` – If needed for AI calls.
   - Any other configuration variables defined in `backend/app/config.py`.
3. **Deploy** – Click “Deploy”.  Vercel will install dependencies, run the build and deploy the serverless function.  You will receive a URL like `https://your-backend-project.vercel.app`.
4. **Verify** – Call `/api/patients` to confirm the API is running.  The path may be under `/api` depending on the route configuration.

## 3. Frontend deployment

1. **Create a second Vercel project** from the same repository.  Select `frontend` as the root directory and choose **Next.js** as the framework.
2. **Set environment variables** for the frontend:
   - `NEXT_PUBLIC_API_BASE_URL` – Set to your backend URL, e.g., `https://your-backend-project.vercel.app/api`.  Variables prefixed with `NEXT_PUBLIC_` are exposed to the browser.
   - Any other build‑time variables required by your front‑end code.
3. **Deploy** – Click “Deploy”.  After the build completes, you’ll receive a URL like `https://your-frontend-project.vercel.app`.
4. **Verify** – Open the front‑end URL.  Ensure it communicates with the backend and displays patient data correctly.

## 4. Environment variables summary

| Variable                      | Backend | Frontend | Description                                           |
|------------------------------|:-------:|:--------:|-------------------------------------------------------|
| `GOOGLE_DRIVE_ROOT_FOLDER_ID`| ✅      | ❌       | Root Drive folder ID                                  |
| `GOOGLE_SERVICE_ACCOUNT_JSON`| ✅      | ❌       | Service account credentials                          |
| `DATABASE_URL`               | ✅      | ❌       | SQL database connection string                       |
| `ALLOWED_ORIGINS`            | ✅      | ❌       | CORS whitelist                                       |
| `PERPLEXITY_API_KEY`         | ✅      | ❌       | Primary AI API key                                   |
| `GEMINI_API_KEY`             | ✅      | ❌       | Backup AI API key                                    |
| `NEXT_PUBLIC_API_BASE_URL`   | ❌      | ✅       | Base URL for API calls from the browser              |
| `OTHER_ENV_VARS`             | ✅/❌   | ✅/❌    | Additional variables used by your code               |

Values prefixed with `NEXT_PUBLIC_` are exposed to the client; all others remain server‑side.

## 5. Post‑deployment steps

After deploying both projects, perform the following steps:

- **Environment management** – Use the Vercel Dashboard to add, edit, or remove environment variables.  If you change a variable, trigger a redeploy.
- **Database connection** – If using Postgres, consider a hosted provider (e.g., Supabase or Neon) and ensure SSL settings are correct.  Add the connection string to `DATABASE_URL`.
- **Cron jobs** – Vercel does not support persistent cron jobs.  To run the Drive watcher on a schedule, use an external scheduler (GitHub Actions, AWS Lambda, Cloud Run jobs) or Vercel’s scheduled functions.  Ensure the scheduled job has access to the same environment variables and network.
- **Logs and monitoring** – Use Vercel’s built‑in logging for serverless functions.  For advanced monitoring, integrate with Sentry or Datadog.
- **Custom domains** – Point your clinic’s domain to the front‑end project via Vercel’s domain settings.  Vercel will manage SSL automatically.

Following this plan will allow you to deploy both the FastAPI backend and the Next.js frontend to Vercel with minimal friction and appropriate configuration.
