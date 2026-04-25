# Codex Implementation Prompt

You are Codex, an AI software engineer.  Your task is to implement the next version of a **FastAPI + Next.js** clinical documentation application according to the specifications provided in this repository.  The goal is to transform the current prototype into a robust, production‑ready system that automatically generates clinical summaries, session notes, treatment plans and billing summaries from patient files stored in Google Drive.

The handoff includes several documents.  Read them carefully before coding:

* **PRODUCT_SPEC.md** – high‑level user stories and workflow requirements.
* **DESIGN.md** – design tokens and aesthetic guidelines for the user interface.
* **IMPLEMENTATION_PLAN.md** – outlines the tasks you need to complete across backend, frontend, database, drive automation and billing logic.
* **DATABASE_SCHEMA.md** – defines the database tables, fields and relations to support the new features.
* **API_CONTRACT.md** – lists all endpoints you must implement, including methods, request/response models and error handling.
* **BILLING_ENGINE_SPEC.md** – details the CPT coding logic, allowed codes, minute thresholds, modifier 25 rules, and reimbursement comparison algorithm.
* **DRIVE_AUTOMATION_SPEC.md** – describes how to monitor Google Drive, classify files (intake, assessment, zoom note, etc.), and trigger the correct generation workflow.
* **VERCEL_DEPLOYMENT_PLAN.md** – provides guidance on how to deploy the backend and frontend separately on Vercel when you are done.

## Key Implementation Objectives

1. **Database migrations** – Create the tables defined in DATABASE_SCHEMA.md using SQLAlchemy and Alembic.  Add indexes where appropriate, enforce foreign keys, and use proper types for timestamps, booleans and JSON fields.
2. **Drive file monitoring** – Implement the Drive watcher described in DRIVE_AUTOMATION_SPEC.md.  It should periodically poll Google Drive using the Drive API, classify new files based on naming rules (e.g., files containing “intake”, “ASRS”, “PHQ9”, “GAD7”, “PHQ-9” are assessments; zoom notes follow a defined pattern) and mark files as processed in the database once handled.  Use asynchronous tasks to avoid blocking the main server.
3. **Source selection logic** – Build the logic that selects the proper input files for each document type:
   * **Summary** = intake + assessments
   * **Session Note** = the selected zoom note only
   * **Treatment Plan** = summary + intake + assessments + latest session note
4. **AI integration** – Replace the placeholder `fake_ai_call` functions with real calls to your preferred LLM.  Ensure that the model responses conform to the JSON schemas expected by the templates.  Implement robust error handling and retries.
5. **Billing engine** – Implement the logic described in BILLING_ENGINE_SPEC.md.  Determine the correct ICD‑10 and CPT code combinations for each encounter, favour the highest reimbursing valid combination supported by documentation, and apply modifier 25 when an E/M service is billed with psychotherapy.  Provide a one‑line billing summary for Headway with patient name, date of service, service name, ICD‑10 codes, CPT codes, and psychotherapy duration.
6. **API endpoints** – Implement all routes detailed in API_CONTRACT.md using FastAPI, including authentication where needed, database access, background tasks, generation triggers, and output downloads.  Make sure to return proper HTTP status codes and error messages.
7. **Frontend components** – Build the necessary pages and components in Next.js that correspond to the new flows.  This includes a dashboard with patient status, patient detail pages that display sources and generated outputs, generation buttons with review options (save immediately vs. draft first), editing screens for drafts, billing summary panels, and status badges.  Use the design tokens from DESIGN.md and the visual guidelines described in the product spec.
8. **Role management** – Implement at least two user roles (provider and admin) with appropriate permissions.  Providers can review and approve drafts; admins can trigger generation, review classification, and copy billing summaries.  Use authentication via JWT or another secure mechanism.
9. **Testing** – Write unit tests and integration tests to verify the classification logic, billing engine, API endpoints, and database migrations.  Include at least one test per critical business rule (e.g., modifier 25 application, highest reimbursing combination selection).
10. **Deployment** – Follow VERCEL_DEPLOYMENT_PLAN.md to configure and deploy the backend and frontend as two separate projects on Vercel.  Use environment variables for secrets and ensure that the FastAPI entrypoint is correctly wired.

## Execution guidance

* Start by setting up the database models and migrations.  Confirm that the tables match DATABASE_SCHEMA.md.
* Implement the Drive automation tasks and test file classification using local sample data.  Ensure that the watcher writes processed files to the database.
* Build the billing engine module in isolation and write tests for each combination rule.  Use the reimbursement values from the provided sheet to rank code combinations.
* Flesh out the API routes one by one, integrating the database and business logic.  Use Pydantic models to enforce request and response schemas.
* Implement the front‑end pages next, consuming your API and reflecting the status of each patient and document generation.  Use environment variables for API base URLs.
* Finally, deploy the backend and frontend to Vercel as separate projects.  Verify that the environment variables are set correctly and that the app functions end‑to‑end.

Your output should be a working application that satisfies all the requirements in this handoff.  If anything is unclear, revisit the specification documents for guidance.
