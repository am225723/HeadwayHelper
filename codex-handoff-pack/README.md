# Clinical AI Webapp – Codex Handoff

Welcome!  This directory contains everything a Codex agent or developer needs to build the next version of the Clinical AI Webapp described in the accompanying product and design specifications.

The existing project is a **FastAPI backend** with a **Next.js frontend** designed to automate and streamline clinical documentation for a psychiatry practice.  It pulls patient files from Google Drive, generates summaries, session notes and treatment plans using AI, and surfaces structured billing data.  However, the current code is only a scaffold; the features and workflow defined in the product spec are not yet implemented.

This handoff includes detailed specifications for the database schema, API routes, Drive automation, billing engine, and deployment.  It also contains a comprehensive implementation plan and a ready‑to‑run prompt for Codex.  Together, these documents outline how to transform the prototype into a fully operational system that meets the practice’s needs.

## Files

- **README.md** – you are here.  Introduces the handoff materials and summarises the goal of the project.
- **PRODUCT_SPEC.md** – (not part of this handoff) defines the overall product scope, user flows and features.  Refer to it for context.
- **DESIGN.md** – (not part of this handoff) captures the visual design tokens and aesthetic intent for the UI.
- **IMPLEMENTATION_PLAN.md** – breaks the work into discrete tasks across backend, frontend, database, drive automation, billing logic, and testing.
- **DATABASE_SCHEMA.md** – defines the relational schema (tables, columns and relations) required to support the new features.
- **API_CONTRACT.md** – enumerates all API endpoints, their methods, expected inputs and outputs, and error handling.
- **BILLING_ENGINE_SPEC.md** – explains the coding rules, allowed CPT codes, minute thresholds and reimbursement comparison logic.  It reflects the highest reimbursing valid option per encounter and applies modifier 25 when billing E/M with psychotherapy.
- **DRIVE_AUTOMATION_SPEC.md** – describes how the system should monitor Google Drive, classify files, and trigger generation workflows.
- **VERCEL_DEPLOYMENT_PLAN.md** – provides a step‑by‑step plan for deploying the backend and frontend to Vercel, including environment variables and project separation.
- **CODEX_PROMPT.md** – a self‑contained prompt instructing Codex to implement the work defined in this handoff.  It references the other documents and provides clear tasks.

## How to use these documents

1. **Read the Product and Design specifications** to understand the high‑level goals, user stories and visual tone.
2. **Review the Implementation Plan** to see how the work has been organised.  Tasks are grouped by functional area and include database migrations, new API endpoints, business logic, front‑end components, and tests.
3. **Study the Database Schema** and **API Contract** to familiarise yourself with the data model and service interfaces you need to implement.
4. **Implement the Billing Engine** according to the detailed rules.  It ensures that the highest reimbursing valid CPT code combination is chosen and that modifier 25 is applied when appropriate.
5. **Follow the Drive Automation Spec** to build a robust watcher that detects new intake, assessment and zoom note files in Google Drive and triggers the proper generation flows.
6. **Deploy to Vercel** using the deployment plan once the backend and frontend are ready.  This ensures that your app will run smoothly in the target environment.

By following these documents, a Codex agent should be able to implement all required functionality and deliver a polished, production‑ready version of the Clinical AI Webapp.
