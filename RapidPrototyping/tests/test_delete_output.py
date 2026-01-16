"""Tests for deleting a generated output file via API."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

from fastapi.testclient import TestClient


app_module = importlib.import_module("src.web.app")


def setup_project(base_dir: Path):
    project_id = "deltest01"
    project_dir = base_dir / project_id
    outputs_dir = project_dir / "outputs"
    uploads_dir = project_dir / "uploads"
    outputs_dir.mkdir(parents=True)
    uploads_dir.mkdir(parents=True)
    metadata = {
        "id": project_id,
        "project_name": "Delete Test",
        "customer_name": "Acme",
        "outputs": [],
    }
    (project_dir / "metadata.json").write_text(json.dumps(metadata))
    return project_id, outputs_dir


def test_delete_output_removes_file_and_updates_metadata(tmp_path, monkeypatch):
    # Point the app's storage to the temp directory
    monkeypatch.setattr(app_module, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(app_module.project_store, "base_dir", tmp_path)

    project_id, outputs_dir = setup_project(tmp_path)
    filename = "sample_note.md"
    file_path = outputs_dir / filename
    file_path.write_text("# Sample", encoding="utf-8")

    # Ensure metadata contains the output entry
    meta_path = tmp_path / project_id / "metadata.json"
    meta = json.loads(meta_path.read_text())
    meta.setdefault("outputs", []).append(filename)
    meta_path.write_text(json.dumps(meta))

    client = TestClient(app_module.app)

    # Sanity checks
    assert file_path.exists()
    meta_before = json.loads(meta_path.read_text())
    assert filename in meta_before.get("outputs", [])

    # Delete the file via API
    resp = client.delete(f"/api/outputs/{project_id}/{filename}")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "deleted"
    assert body.get("filename") == filename

    # File removed and metadata updated
    assert not file_path.exists()
    meta_after = json.loads(meta_path.read_text())
    assert filename not in meta_after.get("outputs", [])
