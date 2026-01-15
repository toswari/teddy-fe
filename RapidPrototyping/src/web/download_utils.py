"""Utilities for converting generated markdown outputs into PDF and DOCX."""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Iterable

from markdown import markdown as markdown_to_html
from weasyprint import HTML
from docx import Document
from html2docx import HTML2Docx

try:  # html2docx>=1.0 removed add_html helper
    from html2docx import add_html as _add_html  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - depends on installed version
    _add_html = None

DEFAULT_CSS = """
body {
    font-family: 'Inter', 'Helvetica', 'Arial', sans-serif;
    font-size: 12pt;
    line-height: 1.5;
    color: #1f2937;
}
h1, h2, h3, h4, h5, h6 {
    font-weight: 600;
    color: #111827;
}
code, pre {
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    background-color: #f3f4f6;
    border-radius: 6px;
}
pre {
    padding: 12px;
    overflow-x: auto;
}
ul, ol {
    padding-left: 24px;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
}
th, td {
    border: 1px solid #e5e7eb;
    padding: 8px;
    text-align: left;
}
blockquote {
    border-left: 4px solid #3b82f6;
    padding-left: 12px;
    color: #4b5563;
    font-style: italic;
}
"""

MARKDOWN_EXTENSIONS: Iterable[str] = [
    "extra",
    "sane_lists",
    "tables",
    "toc",
]

ALLOWED_PAGE_SIZES = {"LETTER", "A4"}
DEFAULT_PAGE_SIZE = "LETTER"


def _resolve_page_size() -> str:
    """Return the configured page size with a safe fallback."""
    env_value = os.getenv("DOWNLOAD_PAGE_SIZE", DEFAULT_PAGE_SIZE).strip().upper()
    return env_value if env_value in ALLOWED_PAGE_SIZES else DEFAULT_PAGE_SIZE


def _build_stylesheet(page_size: str | None = None) -> str:
    """Create the CSS string including page-size controls."""
    resolved_size = (page_size or _resolve_page_size())
    page_rule = f"@page {{ size: {resolved_size}; margin: 1in; }}\n"
    return page_rule + DEFAULT_CSS


def render_markdown_to_html(markdown_text: str, title: str | None = None) -> str:
    """Convert markdown text into a styled HTML document string."""
    body_html = markdown_to_html(markdown_text, extensions=MARKDOWN_EXTENSIONS)
    document_title = title or "Clarifai Document"
    stylesheet = _build_stylesheet()
    return (
        "<!DOCTYPE html><html><head>"
        f"<meta charset='utf-8'><title>{document_title}</title>"
        f"<style>{stylesheet}</style>"
        "</head><body>"
        f"{body_html}"
        "</body></html>"
    )


def html_to_pdf_bytes(html_content: str) -> bytes:
    """Render HTML content to PDF bytes using WeasyPrint."""
    buffer = BytesIO()
    HTML(string=html_content).write_pdf(target=buffer)
    return buffer.getvalue()


def _build_docx_from_html(html_content: str, title: str) -> Document:
    """Convert HTML to a python-docx Document regardless of html2docx version."""
    if _add_html is not None:
        document = Document()
        document.core_properties.title = title
        _add_html(document, html_content)
        return document

    parser = HTML2Docx(title)
    parser.feed(html_content)
    parser.close()
    return parser.doc


def html_to_docx_bytes(html_content: str, title: str | None = None) -> bytes:
    """Render HTML content to DOCX bytes using python-docx/html2docx."""
    document_title = title or "Clarifai Document"
    document = _build_docx_from_html(html_content, document_title)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def convert_markdown_file(file_path: Path, target_format: str) -> bytes:
    """Convert a markdown file into the requested format and return bytes."""
    markdown_text = file_path.read_text(encoding="utf-8")
    html_document = render_markdown_to_html(markdown_text, title=file_path.stem)

    if target_format == "pdf":
        return html_to_pdf_bytes(html_document)
    if target_format == "docx":
        return html_to_docx_bytes(html_document, title=file_path.stem)

    raise ValueError(f"Unsupported target format: {target_format}")


def is_markdown_file(path: Path) -> bool:
    """Return True if the file uses a markdown extension."""
    return path.suffix.lower() in {".md", ".markdown"}
