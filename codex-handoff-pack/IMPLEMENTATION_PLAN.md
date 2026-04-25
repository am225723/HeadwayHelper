# Implementation Plan

This plan lays out the tasks required to turn the existing prototype into a fully featured clinical documentation system.  Work is organised into functional areas with milestones and priorities.  Follow this plan to ensure that all parts of the system—database, backend, front‑end, drive automation, billing logic, and deployment—are completed coherently.

## 1. Project setup

* **1.1 Unzip and commit source** – Unzip the `clinical-ai-webapp-v2.zip` in your repository and commit the extracted `backend` and `frontend` folders.  Delete the original zip to avoid confusion.
* **1.2 Version control and branches** – Create a `develop` branch for active work.  Use feature branches (e.g., `feature/drive-watcher`, `feature/billing-engine`) and merge via pull requests.
* **1.3 Tools and dependencies** – Ensure that `python>=3.10`, `fastapi`, `sqlalchemy`, `alembic`, `python-dotenv`, `google-api-python-client`, and Next.js v15 are installed.  Use `pipenv` or `poetry` to manage Python dependencies and `npm` to manage front‑end dependencies.

## 2. Database layer

* **2.1 Define models** – Create SQLAlchemy models corresponding to each table in DATABASE_SCHEMA.md.  Use relationships to define foreign keys and cascades.  Include `__repr__` methods for debugging.
* **2.2 Migrations** – Initialise Alembic in the `backend` project.  Create an initial migration based on existing tables, then a second migration to create the new tables (patients, source_documents, processed_files, output_documents, billing_summaries, processing_runs, review_statuses).
* **2.3 Repository layer** – Implement a repository module with helper functions for CRUD operations.  Avoid repeating SQL queries in route handlers.  Use async `session` from `fastapi_async_session` for concurrency.
* **2.4 Seed data (optional)** – Write a script to seed the database with a few test patients and sample files for local development.

## 3. Drive automation

* **3.1 Configure Drive API** – Use a service account or OAuth credentials to access Google Drive.  Store credentials in environment variables (`GOOGLE_SERVICE_ACCOUNT_JSON`).
* **3.2 Classification rules** – Implement a `classify_file(filename: str) -> FileType` function based on naming patterns:
  - If file name contains `intake` or `headway intake` → `INTAKE`
  - If file name contains `ASRS`, `PHQ9`, `GAD7` or `PHQ-9` → `ASSESSMENT`
  - If file name matches the zoom note pattern (e.g., `MMDDYY-zoomnote.pdf`) → `ZOOM_NOTE`
  - Otherwise unknown or fallback
* **3.3 Drive watcher** – Implement an asynchronous background task (e.g., using `AsyncIO` and `APScheduler`) that runs every few minutes.  It should:
  - List files in the configured patient root folder
  - Determine the patient folder each file belongs to
  - Classify unprocessed files using `classify_file`
  - Insert entries into `source_documents` and `processed_files`
  - Trigger the appropriate generation tasks based on source type and existing records (see section 4)
  - Log any errors
* **3.4 Testing** – Write unit tests for `classify_file` and integration tests for the watcher using a mock Drive service.

## 4. Document generation workflows

* **4.1 Source selection** – Implement functions that gather the correct source documents for each output type:
  - `get_summary_sources(patient_id)` → return the latest intake and all assessments
  - `get_session_note_source(patient_id)` → return a single zoom note selected by the user or chosen automatically based on date
  - `get_treatment_plan_sources(patient_id)` → return the existing summary, intake, assessments and latest session note
* **4.2 AI call wrappers** – Replace the placeholder `fake_ai_call` with a module that calls the selected LLM (e.g., OpenAI or Gemini).  Ensure that prompts and keys are loaded from environment variables and that timeouts and retries are handled gracefully.
* **4.3 Templating** – Continue to use the existing HTML templates stored in `backend/app/templates`.  After receiving AI outputs, replace the placeholders and render PDFs via `xhtml2pdf` or another library.  Save the PDF bytes to a temporary buffer.
* **4.4 Storage and indexing** – Upload generated PDFs back to the patient’s `output` folder in Google Drive.  Insert a record into `output_documents` with metadata (type, timestamp, drive_file_id).  Update `billing_summaries` using the billing engine.
* **4.5 Review workflows** – Provide an option to save immediately or to create a draft.  Drafts should be stored in the database with a status of `DRAFT`.  Approved documents are marked `FINAL` and saved to Drive.
* **4.6 Error handling** – If generation fails, store error details in `processing_runs` and allow re‑tries from the UI.

## 5. Billing engine

* **5.1 CPT code enumeration** – Define a constant list of allowed CPT codes (90785, 90792, 90832, 90833, 90834, 90836, 90837, 90838, 90839, 90840, 99202, 99203, 99204, 99205, 99212, 99213, 99214, 99215).【184629542025788†L120-L168】
* **5.2 Documentation support logic** – Implement a function that determines which CPT codes are supported by the documentation.  It should analyse the AI‑generated note, extract psychotherapy minutes, detect whether an E/M service was provided, and evaluate the complexity level.
* **5.3 Reimbursement ranking** – Load reimbursement values from the provided sheet (e.g., for Aetna, Anthem, Carelon, Cigna, Oscar/Optum, Oxford/Optum, Quest, United/Optum).  Sum reimbursements for combinations (E/M + add‑on psychotherapy) and rank them.  This ranking guides the choice of the highest reimbursing valid code【184629542025788†L120-L168】.
* **5.4 Modifier rule** – Apply modifier 25 to the E/M code whenever psychotherapy add‑on codes (90833/90836/90838) are billed together【184629542025788†L120-L168】.
* **5.5 Billing summary builder** – Implement `create_billing_summary(patient, date_of_service, service_name, icd10_codes, cpt_codes, minutes)` that returns a one‑line string for Headway and stores a record in `billing_summaries`.  Include copy‑to‑clipboard support in the UI.
* **5.6 Comparison panel** – For psychiatric evaluations, calculate reimbursement for 90792 versus E/M + add‑on psychotherapy combinations and present the comparison in the UI.【184629542025788†L120-L168】

## 6. API layer

* **6.1 Define Pydantic models** – Create request/response schemas for all endpoints in API_CONTRACT.md.  Include validation of query parameters and body payloads.
* **6.2 Implement routes** – For each path:
  - Validate inputs
  - Perform the database operations via the repository layer
  - Trigger drive automation or generation tasks asynchronously when appropriate
  - Return responses according to the contract with proper status codes
* **6.3 Authentication and roles** – Implement JWT‑based authentication.  Use roles to restrict operations (e.g., only providers can approve final documents, only admins can trigger generation or re‑classification).  Store user accounts and roles in the database.
* **6.4 Error handling** – Use FastAPI exception handlers to format errors consistently.  Include details like error type, message and optionally a correlation ID.

## 7. Front‑end layer

* **7.1 State management** – Use React Query or SWR to fetch data and manage caching.  Represent each patient’s status as a finite state machine to drive the UI.
* **7.2 Dashboard** – Create a page listing all patients with summary status badges (intake received, summary ready, session note generated, treatment plan ready).  Provide filters and search.
* **7.3 Patient detail page** – Display sources (intake, assessments, zoom notes), generated outputs, actions to generate each document, and billing summary.  Allow selecting a specific zoom note for session note generation.  Provide copy buttons for billing fields.
* **7.4 Review/edit screens** – When a draft is generated, show the AI‑generated text in a rich text area.  Allow editing before finalising.  Display the billing panel and reimbursement comparison.
* **7.5 Authentication UI** – Provide login and role selection screens.  Support logout and session persistence.
* **7.6 Design compliance** – Follow the design tokens and component guidelines from DESIGN.md.  Use Tailwind CSS or shadcn/ui and incorporate animation and accessibility best practices.

## 8. Testing

* **8.1 Backend unit tests** – Use `pytest` and `pytest-asyncio` to test the classification functions, billing engine, repository methods, and API routes.  Mock external services (Drive API and AI API).
* **8.2 Front‑end tests** – Use React Testing Library to test components and pages.  Test state transitions, form behaviour, and API interactions.
* **8.3 End‑to‑end tests** – Use Playwright or Cypress to simulate user flows: new intake arrives, summary generation, session note generation, treatment plan generation, billing copy, and user role enforcement.

## 9. Deployment

* **9.1 Environment variables** – Document and configure environment variables in `.env.example` for both backend and frontend.  Ensure secrets are loaded from Vercel environment settings during deployment.
* **9.2 Backend deployment** – Follow the steps in VERCEL_DEPLOYMENT_PLAN.md: add `backend/api/index.py` and `backend/vercel.json`, create the backend Vercel project with root directory `backend`, set environment variables, and deploy.
* **9.3 Frontend deployment** – Create a separate Vercel project with root directory `frontend`.  Set `NEXT_PUBLIC_API_BASE_URL` to the backend’s URL and deploy.  Configure custom domains if needed.
* **9.4 Monitoring and logs** – Use Vercel’s logging features and optionally integrate with Sentry or Datadog for error tracking.  Configure alerts for failed drive sync tasks or AI call errors.

## 10. Maintenance and future work

* **10.1 Incremental enhancements** – After the initial release, add features such as multi‑provider support, better assessment handling, automatic appointment reminders, and custom template editing.
* **10.2 Security hardening** – Conduct a security audit to ensure HIPAA compliance.  Encrypt sensitive data at rest, implement stricter access controls and audit logging.
* **10.3 Performance tuning** – Optimise asynchronous tasks, database queries and API response times.  Consider caching static content and using a message queue for heavy tasks.

By following this plan, you will create a robust, scalable clinical documentation system that automates much of the administrative burden for psychiatric practices.
