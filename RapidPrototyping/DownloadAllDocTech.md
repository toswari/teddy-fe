# Download All Docs – PDF/DOCX Tech Options

This document evaluates common **open-source** libraries and tools to convert existing Markdown-based project documents into **PDF** and **DOCX** for inclusion in ZIP downloads.

Focus is on Python-friendly tooling suitable for use in a FastAPI backend.

---

## 1. PDF Generation Options

### 1.1 WeasyPrint

**Overview**  
Python library that converts **HTML+CSS** to PDF using a modern CSS layout engine.

**Pros**
- Pure Python API; easy to integrate directly into FastAPI code.
- High-fidelity layout with good support for modern CSS (floats, flexbox, page breaks, @page, etc.).
- Actively maintained and widely used.
- No need for a separate headless browser.
- Good for text-heavy documents with some basic styling and branding.

**Cons**
- Requires system dependencies (Cairo, Pango, etc.), which slightly complicates Docker packaging.
- Input must be HTML, so Markdown needs a conversion step (e.g., `markdown` or `markdown-it` to HTML) before PDF.
- Not ideal for very complex, print-perfect publishing workflows compared to LaTeX-based tools.

**Fit for this project**  
Very good: we already produce Markdown; converting to HTML and then to PDF is straightforward and keeps everything in Python.

---

### 1.2 wkhtmltopdf (via `pdfkit` or similar)

**Overview**  
Command-line tool based on WebKit to convert HTML to PDF; typically driven from Python using wrappers like `pdfkit`.

**Pros**
- Mature and widely used in industry.
- Good rendering of typical web pages, including CSS.
- Simple HTML→PDF workflow; can reuse existing HTML templates.

**Cons**
- Requires installing the **wkhtmltopdf** binary in the container; platform-specific packaging can be finicky.
- Project is relatively stable but not very actively innovating; older rendering engine.
- Headless browser-style tool can be heavier than needed for simple documents.

**Fit for this project**  
Reasonable, but Dockerization becomes more complex. WeasyPrint usually offers a cleaner, more modern pure-Python path.

---

### 1.3 ReportLab (direct PDF drawing)

**Overview**  
Low-level Python library for programmatic PDF generation (drawing text, paragraphs, tables, graphics directly).

**Pros**
- Very mature and battle-tested.
- Fine-grained control over layout and graphics.
- Pure Python; no external binaries.

**Cons**
- Works at a lower abstraction level; building rich, styled documents from Markdown is significantly more work.
- Requires custom layout code for headings, lists, page breaks, etc.

**Fit for this project**  
Less ideal. Overkill and high implementation cost compared to HTML-based converters.

---

### 1.4 Pandoc (Markdown → PDF)

**Overview**  
Universal document converter (Haskell CLI) that can convert Markdown to many formats, including PDF (typically via LaTeX or wkhtmltopdf) and DOCX.

**Pros**
- Extremely flexible and powerful; supports Markdown → PDF, DOCX, HTML, etc.
- High-quality output, especially when using LaTeX.
- Single tool could handle **both PDF and DOCX**, simplifying format consistency.

**Cons**
- Requires installing the `pandoc` binary (and often LaTeX, depending on the PDF engine), which increases image size and complexity.
- Integration is via subprocess calls from Python; need to manage temp files and security around shell arguments.
- Heavier dependency footprint than a pure-Python approach.

**Fit for this project**  
Strong candidate if we want one tool for both PDF and DOCX and can tolerate larger images / more complex Docker setup.

---

## 2. DOCX Generation Options

### 2.1 python-docx

**Overview**  
Pure Python library for creating and modifying Microsoft Word `.docx` files.

**Pros**
- Native Python API; no external binary dependencies.
- Fine-grained control over Word document structure (paragraphs, runs, headings, tables, etc.).
- Widely used and actively maintained.

**Cons**
- No built-in Markdown parser; must either:
  - Write our own Markdown→DOCX mapping, or
  - Convert Markdown to an intermediate format (e.g., HTML) and walk the tree to build DOCX.
- Styling beyond basics (themes, complex layouts) requires more code.

**Fit for this project**  
Good, especially if we keep formatting modest and are comfortable writing a small Markdown→DOCX adapter.

---

### 2.2 Pandoc (Markdown → DOCX)

**Overview**  
Pandoc converts Markdown directly to `.docx` via its CLI.

**Pros**
- Excellent Markdown support (headings, lists, code blocks, tables) mapped to sensible DOCX structure.
- Handles both PDF and DOCX, enabling a unified conversion pipeline.
- Supports custom templates for consistent styling.

**Cons**
- Same as for PDF: external binary, possibly LaTeX toolchain for PDF use; larger Docker image.
- Integration via subprocess; need to manage timeouts, errors, and temporary files.

**Fit for this project**  
Very strong if we are comfortable relying on a CLI tool and slightly heavier container.

---

### 2.3 LibreOffice / soffice (headless)

**Overview**  
Use headless LibreOffice to convert between formats (e.g. HTML/Markdown → DOCX, or DOCX ↔ PDF) via CLI.

**Pros**
- Very powerful, supports many formats and complex documents.
- Can produce both DOCX and PDF from a single source.

**Cons**
- Heavy dependency; significantly increases container size and startup time.
- More complex to automate reliably in server environments.
- Overkill for relatively simple, text-oriented SE documents.

**Fit for this project**  
Not recommended; operational overhead outweighs benefits for our use case.

---

## 3. Recommended Approaches

### Option A – HTML + WeasyPrint (PDF) + python-docx (DOCX)

**Summary**  
Use Markdown → HTML for both formats. For PDF, feed HTML into WeasyPrint. For DOCX, either:
- Map Markdown directly to python-docx calls, or
- Parse the same HTML and map tags to DOCX elements.

**Pros**
- Pure-Python stack, good for containerization.
- Clear separation of concerns: HTML rendering + two format-specific writers.
- Fine-grained control if we need to tweak layout per format.

**Cons**
- Requires writing and maintaining custom conversion logic for DOCX (and some mapping glue for PDF styling).
- Two separate pipelines (PDF vs DOCX) to keep visually consistent.

**When to choose**  
If we want to avoid external binaries and keep runtime dependencies Python-only, with moderate engineering effort.

---

### Option B – Pandoc for Both PDF and DOCX

**Summary**  
Use Pandoc as a single conversion engine: Markdown → PDF and Markdown → DOCX via CLI calls from Python.

**Pros**
- Single, powerful toolchain for both output formats.
- High-quality and consistent formatting between PDF and DOCX.
- Less custom conversion code; mainly orchestration and error handling.

**Cons**
- Requires installing Pandoc (and potentially LaTeX) in the Docker image.
- Larger image size and more complex build.
- Need to manage subprocess calls, timeouts, and error parsing.

**When to choose**  
If we prioritize:
- High-quality output,
- Consistent formatting across PDF and DOCX, and
- Faster feature delivery over minimal dependencies.

---

### Option C – Hybrid (Pandoc for DOCX, WeasyPrint for PDF)

**Summary**  
Use WeasyPrint for PDF (HTML-based) and Pandoc or python-docx for DOCX.

**Pros**
- Allows using the best tool for each format.
- Can start with WeasyPrint + python-docx and later swap in Pandoc for one format if needed.

**Cons**
- More moving parts; two different engines to maintain.
- Less consistency between formats unless carefully tuned.

**When to choose**  
If we start with pure Python but later find DOCX quality lacking and want to selectively introduce Pandoc.

---

## 4. High-Level Recommendation

For this project, there are two realistic paths:

1. **Simplicity / Quality First – Pandoc-only pipeline**
   - Use Pandoc to produce both PDF and DOCX from Markdown.
   - Accept the heavier Docker image and CLI dependency.
   - Minimal custom formatting logic; faster to implement and easy to extend.

2. **Python-only Dependencies – WeasyPrint + python-docx**
   - Convert Markdown → HTML; use WeasyPrint for PDF.
   - Use python-docx with a simple Markdown/HTML mapping for DOCX.
   - More implementation work upfront, but keeps everything in Python and avoids external binaries.

The final choice should balance:
- **Operational constraints** (image size, allowed binaries), and
- **Desired output fidelity** and development time.

---

## 5. Implementation Outline – Python-only Dependencies (WeasyPrint + python-docx)

### 5.1 Dependency Footprint
- **Python packages**: `markdown`, `weasyprint`, `html2docx`, `python-docx` (plus transitives such as `tinycss2`, `cssselect2`).
- **System libs**: `libpango`, `libcairo`, `gdk-pixbuf` (available in Debian/Ubuntu base images; Alpine needs `pango`, `cairo`, `gdk-pixbuf`).
- **Optional helpers**: `Pillow` for inline image support if future docs embed charts/screenshots.
- Add OS dependencies in a dedicated Dockerfile layer so the base image cache remains stable.

### 5.2 Conversion Flow
1. **Markdown → HTML** via the `markdown` library with table/list extensions enabled.
2. **Shared styling**: inject a CSS block (fonts, heading sizes, list spacing, @page margin rules) reused by PDF and DOCX outputs.
3. **PDF path**: `weasyprint.HTML(string=html).write_pdf()` yields bytes; page size controlled through the shared CSS.
4. **DOCX path**: feed the same HTML into `html2docx` to emit a `BytesIO`; handle unsupported tags by falling back to plain paragraphs.
5. **ZIP assembly**: iterate project markdown files, convert per-requested format, and write each artifact into a `zipfile.ZipFile` backed by memory.

### 5.3 FastAPI Endpoint Strategy
- Route: `GET /api/projects/{project_id}/outputs/zip` with query params `format=pdf|docx` (default `pdf`) and optional `include_md=true|false`.
- Validations: confirm project folder exists, at least one markdown artifact is present, and the requested format is supported.
- Response: `StreamingResponse` with `Content-Type: application/zip` plus `Content-Disposition: attachment; filename="project-<id>-docs.zip"`.
- Logging: info-level log per download (project id, format, doc count) and error logs when conversions fail.

### 5.4 Error Handling & Observability
- **Conversion failures**: catch `WeasyPrintError` / `DocumentConversionError`, log offending filenames, and surface HTTP 500 with user-friendly text.
- **Empty projects**: return HTTP 404/400 instructing users to generate documents first.
- **Timeout/size safeguards**: limit markdown file size (e.g., 5 MB) and number of docs per request to avoid runaway conversions.
- **Metrics (future)**: emit counters for successful/failed downloads per format to monitor adoption.

### 5.5 Testing & QA Plan
- Unit tests covering markdown→HTML helpers to guarantee consistent CSS injection.
- Unit tests mocking WeasyPrint/python-docx to ensure converted bytes get written into the ZIP with the right filenames.
- Integration test hitting the FastAPI route via `TestClient`, validating headers and that the returned ZIP opens cleanly.
- Manual QA: run discovery/proposal flows, download both formats, open in Preview/Word, verify pagination, fonts, and list formatting.
