# Download All Documents – Task Breakdown

Checklist to implement the feature that downloads all generated project documents as **PDFs or DOCX files** inside a single ZIP, using a **Python-only stack (Markdown→HTML, WeasyPrint, python-docx)**.

## 1. Backend – API & ZIP Generation

- [x] Confirm current project output directory structure (where discovery/proposal/SE guide files are written).
- [x] Add a new FastAPI route, e.g. `GET /api/projects/{project_id}/outputs/zip`.
- [x] In the handler, resolve the project path and enumerate all generated files for that project.
  - [x] Filter to supported source formats (initially markdown `.md`).
  - [x] If no files found, return an appropriate error response.
- [x] Add a `format` query parameter to the endpoint, supporting at least `pdf` and `docx` (default `pdf`).
- [x] Use **WeasyPrint** as the markdown→PDF solution (via Markdown→HTML→PDF) and add it to `requirements.txt`.
- [x] Use **python-docx** as the markdown/HTML→DOCX solution and add it to `requirements.txt`.
- [x] Implement utilities that convert a single markdown file to:
  - [x] HTML (shared step for both formats).
  - [x] PDF byte stream or temporary file from HTML using WeasyPrint (with defined page size and margins).
  - [x] DOCX byte stream or temporary file using python-docx, mapping headings/paragraphs/lists from Markdown/HTML.
- [x] Implement ZIP creation logic:
  - [x] For each source document, convert to the requested format.
  - [x] Add each resulting file into the ZIP with a clear filename and correct extension.
  - [x] Stream or buffer the ZIP for HTTP response.
- [x] Set correct response headers:
  - [x] `Content-Type: application/zip`.
  - [x] `Content-Disposition` with a sensible filename (e.g. `project-<id>-docs.zip`).
- [x] Add error handling and logging for:
  - [x] Missing project.
  - [x] No generated documents.
  - [x] PDF/DOCX conversion failures (WeasyPrint/python-docx).
  - [x] ZIP creation errors.

## 2. Frontend – UI Integration

- [x] Locate the Step 6 "Generate Final Documents" section in the SPA (HTML/JS under `src/web/static` or related API usage).
- [x] Add a "Download All" control in the Step 6 UI that allows choosing format:
  - [x] Either separate buttons ("Download All (PDF)", "Download All (DOCX)") or a format selector plus single button.
- [x] Wire the control to call the new API endpoint with the current project ID and `format` parameter.
- [x] Implement client-side download behavior:
  - [x] Handle binary ZIP responses and trigger the browser download.
  - [x] Show loading indicator while waiting for the response.
  - [x] Display error messages on failure (e.g. toast/banner).

## 3. Configuration & Docs

- [x] Document any new dependencies (WeasyPrint, python-docx, markdown) in `requirements.txt` and `README.md`.
- [x] Document the new endpoint in the API section of `README.md` (or a dedicated API doc file).
- [x] Optionally add configuration knobs (env vars) for:
  - [x] Page size (A4 vs Letter).
  - [x] Whether to include original markdown files in the ZIP.

## 4. Testing & Validation

- [x] Add unit tests for the markdown→PDF conversion helper (where practical).
- [x] Add tests for the ZIP generation logic (e.g., number of entries, filenames, basic PDF validation).
- [x] Add an API test that:
  - [x] Creates a fake project directory with a few `.md` files.
  - [x] Calls the `/outputs/zip` endpoint.
  - [x] Asserts a valid ZIP is returned and entries are present.
- [ ] Manual QA:
  - [ ] Generate all documents for a real project via the UI.
  - [ ] Click "Download All" and confirm:
    - [ ] ZIP downloads successfully.
    - [ ] All expected PDFs are inside.
    - [ ] PDFs open and render correctly in a viewer.
