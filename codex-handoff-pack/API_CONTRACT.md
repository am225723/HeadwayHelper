# API Contract

This document defines the REST API for the Clinical AI Webapp.  Each endpoint is described with its HTTP method, URL path, description, request parameters, request body, response model and error codes.  Use FastAPI to implement these routes and Pydantic models for validation.

## Conventions

- All endpoints return JSON bodies with `application/json` content type.
- Response models follow the PascalCase naming convention (e.g., `PatientDetail`, `GenerateResponse`).
- Pagination parameters (`page`, `size`) are optional and default to sensible values.
- Authentication is required for most endpoints and uses Bearer JWTs in the `Authorization` header.  Login and registration endpoints are unauthenticated.
- Error responses return a consistent JSON structure: `{ "detail": "Error message" }` and appropriate HTTP status codes.

## Authentication

### POST /api/auth/register
Register a new user (admin or provider).

**Request Body**
```json
{
  "email": "string",
  "password": "string",
  "role": "ADMIN" | "PROVIDER"
}
```

**Responses**
* `201 Created` – Registration succeeded, returns user id and role.
* `400 Bad Request` – Email already exists or invalid role.

### POST /api/auth/login
Authenticate and obtain a JWT.

**Request Body**
```json
{
  "email": "string",
  "password": "string"
}
```

**Responses**
* `200 OK` – Returns `{ "access_token": "...", "token_type": "bearer" }`.
* `401 Unauthorized` – Invalid credentials.

## Patient endpoints

### GET /api/patients
Retrieve a paginated list of patients.

**Query Parameters**
* `page` (int, optional) – Page number (default 1).
* `size` (int, optional) – Page size (default 25).

**Responses**
* `200 OK` – Returns `{ "items": [PatientDetail], "page": int, "size": int, "total": int }`.

### GET /api/patients/{patient_id}
Retrieve details for a specific patient including sources and generated outputs.

**Responses**
* `200 OK` – Returns `PatientDetail`.
* `404 Not Found` – Patient not found.

### POST /api/patients
Create a new patient (admin only).

**Request Body**
```json
{
  "name": "string",
  "drive_folder_id": "string"
}
```

**Responses**
* `201 Created` – Returns the newly created `PatientDetail`.
* `400 Bad Request` – Invalid input.
* `403 Forbidden` – User not authorised to create patients.

## Source document endpoints

### GET /api/patients/{patient_id}/sources
List source documents for a patient.

**Responses**
* `200 OK` – Returns `SourceDocumentsResponse` with grouped files by type.
* `404 Not Found` – Patient not found.

### POST /api/patients/{patient_id}/sources/resync
Trigger a manual resynchronisation of the patient’s Drive folder.  This will reclassify any new files and trigger generation if appropriate.  Admin role required.

**Responses**
* `202 Accepted` – Returns `{ "message": "Resync started" }`.
* `404 Not Found` – Patient not found.
* `403 Forbidden` – User not authorised to trigger resync.

## Generation endpoints

### POST /api/patients/{patient_id}/generate/summary
Generate a patient summary.  Optionally create a draft or save the PDF immediately.  Provider or admin.

**Request Body**
```json
{
  "save_pdf": true | false
}
```

**Responses**
* `202 Accepted` – Generation job started.  Returns job id and current status.
* `400 Bad Request` – Missing source documents or other validation errors.
* `404 Not Found` – Patient not found.

### POST /api/patients/{patient_id}/generate/session-note
Generate a session note from a specific zoom note.  The body must include the `source_document_id` of the selected zoom note and whether to save the PDF immediately.

**Request Body**
```json
{
  "source_document_id": "uuid",
  "save_pdf": true | false
}
```

**Responses**
* `202 Accepted` – Generation started.
* `400 Bad Request` – Invalid source selection.
* `404 Not Found` – Patient or source document not found.

### POST /api/patients/{patient_id}/generate/treatment-plan
Generate a treatment plan using the summary, intake, assessments and latest session note.

**Request Body**
```json
{
  "save_pdf": true | false
}
```

**Responses**
* `202 Accepted` – Generation started.
* `400 Bad Request` – Missing required source documents.
* `404 Not Found` – Patient not found.

### GET /api/outputs/{output_id}
Download a generated PDF.

**Responses**
* `200 OK` – Returns the PDF bytes with `application/pdf` content type.
* `404 Not Found` – Output document not found.

## Billing endpoints

### GET /api/patients/{patient_id}/billing/latest
Retrieve the latest billing summary for a patient.

**Responses**
* `200 OK` – Returns `BillingSummary`.
* `404 Not Found` – No billing summary available.

### POST /api/patients/{patient_id}/billing/recalculate
Recalculate the billing summary for a given output document.  Use this after editing a draft.  Provider or admin.

**Request Body**
```json
{
  "output_document_id": "uuid"
}
```

**Responses**
* `200 OK` – Returns the updated `BillingSummary`.
* `404 Not Found` – Output document not found.

## Review endpoints

### POST /api/outputs/{output_id}/review
Submit a review decision for a draft document.

**Request Body**
```json
{
  "status": "APPROVED" | "REJECTED",
  "comments": "optional string"
}
```

**Responses**
* `200 OK` – Review recorded.
* `404 Not Found` – Output document not found.
* `400 Bad Request` – Invalid status or missing comments for rejection.

### GET /api/review/queue
List all draft documents that require review (provider role).

**Responses**
* `200 OK` – Returns a list of review items with document metadata and status.
* `403 Forbidden` – User not authorised to review.

## Admin operations

### POST /api/admin/drive-sync
Trigger a full Drive synchronisation across all patient folders.  Should be restricted to admin users.

**Responses**
* `202 Accepted` – Sync started.
* `403 Forbidden` – User not authorised.

## Error handling

The API returns standard HTTP error codes and messages.  Define custom exception handlers in FastAPI to return JSON errors such as:

```json
{
  "detail": "Patient not found"
}
```

For validation errors, let FastAPI return a 422 status with detailed validation errors.

## Notes

* All endpoints except registration and login require authentication.
* Use Pydantic models for request and response bodies to ensure type safety.
* Use `Depends(get_current_user)` in route handlers to enforce role permissions.
* Consider implementing rate limiting for generation endpoints to avoid abuse.

Implementing this contract will provide a clean, well-documented API for the front‑end and third‑party consumers.
