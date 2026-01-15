"""Tests for document download conversions and API endpoint."""

from __future__ import annotations

import importlib
import json
import zipfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from src.web import download_utils

app_module = importlib.import_module("src.web.app")


class TestMarkdownConversion:
    """Tests for markdown conversion helpers."""

    def test_render_markdown_to_html_includes_styles(self):
        """Ensure markdown rendering wraps content with CSS and markup."""
        html = download_utils.render_markdown_to_html("# Title", title="Doc Title")
        assert "Doc Title" in html
        assert "<h1" in html and "Title" in html
        assert download_utils.DEFAULT_CSS.strip()[:10] in html

    def test_render_markdown_to_html_respects_page_size_env(self, monkeypatch):
        """Ensure the DOWNLOAD_PAGE_SIZE toggle influences the stylesheet."""
        monkeypatch.setenv("DOWNLOAD_PAGE_SIZE", "A4")
        html = download_utils.render_markdown_to_html("# Title")
        assert "size: A4" in html

    def test_convert_markdown_file_dispatches_to_correct_format(self, tmp_path, monkeypatch):
        """Ensure convert_markdown_file routes to the expected formatter."""
        sample_file = tmp_path / "proposal.md"
        sample_file.write_text("# Sample Proposal", encoding="utf-8")

        call_tracker = {"pdf": 0, "docx": 0}

        def fake_pdf(html: str) -> bytes:
            call_tracker["pdf"] += 1
            assert "Sample Proposal" in html
            return b"PDF-BYTES"

        def fake_docx(html: str, **kwargs) -> bytes:
            call_tracker["docx"] += 1
            assert "Sample Proposal" in html
            return b"DOCX-BYTES"

        monkeypatch.setattr(download_utils, "html_to_pdf_bytes", fake_pdf)
        monkeypatch.setattr(download_utils, "html_to_docx_bytes", fake_docx)

        pdf_result = download_utils.convert_markdown_file(sample_file, "pdf")
        docx_result = download_utils.convert_markdown_file(sample_file, "docx")

        assert pdf_result == b"PDF-BYTES"
        assert docx_result == b"DOCX-BYTES"
        assert call_tracker == {"pdf": 1, "docx": 1}

        with pytest.raises(ValueError):
            download_utils.convert_markdown_file(sample_file, "txt")


class TestDownloadAllOutputsEndpoint:
    """Tests for the /api/projects/{project_id}/outputs/zip endpoint."""

    def setup_project(self, base_dir):
        project_id = "proj1234"
        project_dir = base_dir / project_id
        outputs_dir = project_dir / "outputs"
        uploads_dir = project_dir / "uploads"
        outputs_dir.mkdir(parents=True)
        uploads_dir.mkdir(parents=True)
        metadata = {"id": project_id, "project_name": "Test", "customer_name": "Acme"}
        (project_dir / "metadata.json").write_text(json.dumps(metadata))
        return project_id, outputs_dir

    def test_download_all_outputs_returns_zip(self, tmp_path, monkeypatch):
        """Ensure the endpoint streams a ZIP with converted files."""
        monkeypatch.setattr(app_module, "PROJECTS_DIR", tmp_path)
        monkeypatch.setattr(app_module.project_store, "base_dir", tmp_path)

        project_id, outputs_dir = self.setup_project(tmp_path)
        markdown_path = outputs_dir / "discovery_20240101.md"
        markdown_path.write_text("# Discovery Notes", encoding="utf-8")

        def fake_convert(path, target_format):
            return f"{path.stem}.{target_format}".encode()

        monkeypatch.setattr(app_module, "convert_markdown_file", fake_convert)

        client = TestClient(app_module.app)
        response = client.get(f"/api/projects/{project_id}/outputs/zip?format=pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            assert archive.namelist() == ["discovery_20240101.pdf"]
            assert archive.read("discovery_20240101.pdf") == b"discovery_20240101.pdf"

    def test_download_all_outputs_includes_markdown_when_requested(self, tmp_path, monkeypatch):
        """Ensure include_md flag adds original markdown files to the archive."""
        monkeypatch.setattr(app_module, "PROJECTS_DIR", tmp_path)
        monkeypatch.setattr(app_module.project_store, "base_dir", tmp_path)

        project_id, outputs_dir = self.setup_project(tmp_path)
        markdown_path = outputs_dir / "proposal_latest.md"
        markdown_path.write_text("# Proposal", encoding="utf-8")

        monkeypatch.setattr(app_module, "convert_markdown_file", lambda path, fmt: b"converted")

        client = TestClient(app_module.app)
        response = client.get(
            f"/api/projects/{project_id}/outputs/zip?format=docx&include_md=true"
        )

        assert response.status_code == 200
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            assert set(archive.namelist()) == {"proposal_latest.docx", "proposal_latest.md"}
            assert archive.read("proposal_latest.md").decode("utf-8").startswith("# Proposal")

    def test_download_all_outputs_honors_env_default_for_include_md(self, tmp_path, monkeypatch):
        """Ensure DOWNLOAD_INCLUDE_MD=true includes markdown even without the query param."""
        monkeypatch.setenv("DOWNLOAD_INCLUDE_MD", "true")
        monkeypatch.setattr(app_module, "PROJECTS_DIR", tmp_path)
        monkeypatch.setattr(app_module.project_store, "base_dir", tmp_path)

        project_id, outputs_dir = self.setup_project(tmp_path)
        markdown_path = outputs_dir / "proposal_latest.md"
        markdown_path.write_text("# Proposal", encoding="utf-8")

        monkeypatch.setattr(app_module, "convert_markdown_file", lambda path, fmt: b"converted")

        client = TestClient(app_module.app)
        response = client.get(f"/api/projects/{project_id}/outputs/zip?format=docx")

        assert response.status_code == 200
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            assert set(archive.namelist()) == {"proposal_latest.docx", "proposal_latest.md"}
