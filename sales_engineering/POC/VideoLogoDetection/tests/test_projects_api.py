"""API smoke tests for /api/projects."""
from __future__ import annotations


def test_list_projects_returns_seed(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert data


def test_create_project_endpoint(client):
    response = client.post(
        "/api/projects",
        json={"name": "New Project", "description": "Testing"},
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["name"] == "New Project"
