# Download All Documents as PDF (ZIP)

## Overview
Add features that let users download **all generated documents for a project** in a single ZIP file, with each document converted to either **PDF** or **DOCX**, using a **Python-only stack (WeasyPrint + python-docx)**.

Target UI: the project modal Step 6 "Generate Final Documents" screen in the web app, adding a "Download All" action.

## User Stories
- As a **Solution Engineer**, I want to **download all generated documents for a project at once** so that I can easily share a complete project package with the customer.
- As a **Solution Engineer**, I want to **download all documents as editable Word (DOCX)** so that I can quickly tweak wording and formatting before sharing.

## Functional Requirements

1. **Download All Entry Point**
  - A new "Download All" control is available on the Step 6 screen for a project.
  - The control can:
    - Either offer **two options** (e.g. "Download All (PDF)" and "Download All (DOCX)"), or
    - Provide a format selector (PDF/DOCX) next to a single "Download All" button.
  - When activated, it triggers a backend API to generate and return a **single ZIP file** in the requested format.

2. **Documents Included**
   - All generated documents for the given project are included.
   - At minimum, this covers any of the following that exist for the project:
     - Discovery questions
     - Proposal
     - Compute analysis & ROI
     - SE implementation guide(s)
   - The feature must work regardless of **which subset** of documents has been generated (e.g., only proposal + discovery).

3. **Document Conversion (PDF & DOCX)**
   - Source of truth is the existing Markdown (`.md`) files for each generated document.
   - Conversion pipeline is Python-only:
     - Markdown → HTML (e.g., via the `markdown` Python package).
     - HTML → **PDF** via **WeasyPrint**.
     - Markdown/HTML → **DOCX** via **python-docx** with a simple mapping for headings, paragraphs, and lists.
   - For **PDF**:
     - Retain basic formatting (headings, lists, code blocks, tables where possible).
     - Use a consistent page layout (A4 or US Letter) with reasonable margins.
   - For **DOCX**:
     - Generate a Word-compatible `.docx` file with headings, lists, and basic styling.
     - Preserve logical structure (title, sections) where possible.

4. **ZIP Structure & Naming**
   - The HTTP response is a `application/zip` download.
   - Default ZIP filename pattern: `project-<project_id>-docs.zip` or `project-<slug>-docs.zip`.
   - Inside the ZIP, each document is named clearly, using the chosen format's extension, e.g.:
     - `discovery_<timestamp>.pdf` or `discovery_<timestamp>.docx`
     - `proposal_<timestamp>.pdf` or `proposal_<timestamp>.docx`
     - `compute_analysis_<timestamp>.pdf` or `compute_analysis_<timestamp>.docx`
     - `se_guide_<timestamp>.pdf` or `se_guide_<timestamp>.docx`
   - If multiple versions of the same type exist (e.g. multiple SE guides), each gets a unique filename.

5. **Backend API**
   - New endpoint (example): `GET /api/projects/{project_id}/outputs/zip`
     - **Inputs**:
       - `project_id` (path param) – required.
       - Optional query params:
         - `format=pdf|docx` (default: `pdf`).
         - `include_md=true|false` – whether to also include original markdown files in the ZIP (default: `false`).
     - **Output**:
       - On success: HTTP 200 with a streamed ZIP file and appropriate `Content-Type` / `Content-Disposition` headers.
       - On error: JSON error with HTTP 4xx/5xx.

6. **File Discovery Logic**
   - The backend knows how to locate all generated files for a project based on the existing project storage layout (e.g. under `projects/<project_id>/` or similar, matching current implementation).
   - Only existing generated files are included; missing docs are silently skipped (no hard failure).
   - If **no** generated documents exist for the project:
     - The endpoint returns a `400` or `404` with a clear error message (e.g. "No generated documents found for this project").

7. **Performance & Resource Constraints**
  - PDF/DOCX conversion and ZIP streaming should be done efficiently:
     - Avoid loading the entire ZIP into memory if possible (prefer streaming/temporary files).
   - Reasonable limits should be documented or enforced:
     - Maximum number of documents per request.
     - Maximum total size (or rely on existing project-level limits).

8. **Error Handling**
  - If a single document fails to convert to PDF/DOCX, the system:
     - Logs the error with the filename and reason.
     - Optionally excludes only that document while still returning the rest, **or** fails the whole request with a clear message (choose and document behavior).
   - Client receives meaningful error messages for:
    - Non-existent project.
    - No documents available.
    - Internal PDF/DOCX conversion or ZIP errors.

9. **Security & Access Control**
   - The download endpoint follows the same access rules as existing project/document APIs.
   - No path traversal or arbitrary file access is allowed; the endpoint is restricted to the project’s own directory.

10. **UX Behavior**
   - From the UI, clicking "Download All":
     - Shows a loading state/spinner while the ZIP is being prepared.
     - Initiates a file download when ready.
     - Surfaces any backend error as a user-readable toast/message.

## Non-Requirements / Out of Scope (for now)

- Persistent caching of generated PDFs (they may be generated on the fly for each request).
- Fine-grained selection of which documents to include; initial implementation is "all available" only.
- Advanced PDF styling beyond a clean, readable default.
