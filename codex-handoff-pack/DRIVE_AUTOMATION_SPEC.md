# Drive Automation Specification

The Drive automation layer is responsible for connecting to Google Drive, detecting new files in patient folders, classifying them by type, and triggering the appropriate document generation workflows.  This document outlines the design, functions and operational requirements for the Drive watcher.

## Goals

* **Continuous monitoring** – The system should periodically scan patient folders in Google Drive and detect newly uploaded files without manual intervention.
* **Accurate classification** – Files must be classified as `INTAKE`, `ASSESSMENT`, `ZOOM_NOTE`, or `UNKNOWN` based on their names and content when necessary.
* **Idempotency** – Each file should be processed exactly once.  Re‑processing must be avoided even if the watcher restarts.
* **Triggering workflows** – Once files are classified, the watcher must invoke the correct document generation workflow based on available sources and existing outputs.
* **Resynchronisation** – Provide endpoints to manually resynchronise a patient folder or the entire Drive when needed (e.g., initial onboarding or to recover from errors).

## Configuration

* `GOOGLE_DRIVE_ROOT_FOLDER_ID` – The root folder in Drive containing one subfolder per patient.  Each subfolder’s name or metadata corresponds to a patient record in the database.
* `GOOGLE_SERVICE_ACCOUNT_JSON` – A JSON string or path containing the service account credentials.  Use this with the Google Drive API client.
* `DRIVE_SCAN_INTERVAL` – Interval in seconds between scans.  A default of 300 seconds (5 minutes) is suggested.

## Classification rules

Implement a `classify_file(name: str) -> FileType` function that applies the following rules:

1. If the file name (case‑insensitive) contains the word `intake` or `headway intake`, classify as `INTAKE`.
2. If the file name contains one of the assessment identifiers:
   * `ASRS`
   * `PHQ9`
   * `GAD7`
   * `PHQ-9`
   classify as `ASSESSMENT`.
3. If the file name matches the zoom note pattern (a six‑digit date followed by `-zoomnote.pdf` or `-zoomnnote.pdf`), classify as `ZOOM_NOTE`.
4. Otherwise classify as `UNKNOWN` and do not trigger any generation until manually reviewed.

Future rules can include MIME type checks (e.g., `application/pdf`, `text/plain`) or scanning file contents.

## Watcher workflow

1. **Scan patient folders** – List all subfolders under `GOOGLE_DRIVE_ROOT_FOLDER_ID`.  For each folder, check if a `patients` record exists.  If not, create a new patient entry.
2. **List files** – For each patient folder, call `files.list()` using the Drive API.  Retrieve file IDs, names, MIME types and modified times.
3. **Deduplicate** – For each file, check if its `drive_file_id` exists in the `source_documents` table.  If so, skip processing.
4. **Classify** – Use `classify_file` to determine the file type.  Create a new `source_documents` row with `processed=false`.
5. **Insert into processed_files** – Immediately insert an entry into `processed_files` with the new `source_document_id` and the current timestamp.  This prevents duplicate processing across runs.
6. **Trigger workflows** – After classification, call a dispatch function that determines what to generate:
   * If a new `INTAKE` is detected, gather all `ASSESSMENT`s and generate a summary.
   * If a new `ASSESSMENT` is detected and an intake exists but no summary, generate a new summary.
   * If a new `ZOOM_NOTE` is detected, generate a session note for that note only.
   * After both a summary and at least one session note exist, generate a treatment plan.
7. **Update records** – Mark `source_documents.processed=true` once the generation job has started (even if it is asynchronous).  Handle errors by logging to `processing_runs`.
8. **Logging and errors** – Use structured logging to record scans, classifications and actions.  If the Drive API call fails, retry with exponential backoff.  Report persistent failures to an alerting channel.

## Manual resynchronisation

Provide API endpoints to trigger a resynchronisation:

* **Patient resync** – `/api/patients/{patient_id}/sources/resync` will scan only the selected patient folder.  It reclassifies unprocessed files and triggers generation as needed.
* **Global resync** – `/api/admin/drive-sync` will rescan all patient folders.  Admin role required.

Resync operations should be rate‑limited and should not re‑process files already flagged as processed.

## Persistent state

The watcher relies on two tables to maintain idempotency:

* `source_documents.processed` – A boolean indicating whether the file has been accounted for.
* `processed_files` – A log table that records each processed file with a timestamp.  This allows cross‑run deduplication and auditing.

If the watcher crashes mid‑run, files inserted into `source_documents` but not yet marked as processed will be picked up on the next scan.

## Testing

* Use mocks for Drive API calls to simulate new file uploads and ensure classification logic works.
* Write integration tests that simulate adding files to a temporary folder and assert that the correct generation tasks are triggered.
* Test resynchronisation endpoints to ensure they do not process files twice.

Implementing this specification will ensure that new intake, assessment and zoom note files automatically trigger the appropriate document generation workflows.
