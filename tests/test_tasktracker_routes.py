# tests/test_tasktracker_routes.py

import os
import pytest
from src.app import create_app
from src.services.db_bootstrap import init_db
from tests.utils import generate_test_token


@pytest.fixture
def client(tmp_path):
    test_db = tmp_path / "test.sqlite3"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["SECRET_KEY"] = "supersecretkey"
    os.environ["ADMIN_USER"] = "admin"
    os.environ["ADMIN_PASS"] = "secret"

    app = create_app({"TESTING": True})
    with app.app_context():
        init_db()
    return app.test_client()


@pytest.fixture
def auth_header():
    token = generate_test_token(user_id="admin", secret_key="supersecretkey")
    return {"Authorization": f"Bearer {token}"}


def test_create_and_retrieve_task(client, auth_header):
    payload = {"user_id": 1, "title": "Test Task"}
    resp = client.post("/tasks/", json=payload, headers=auth_header)
    assert resp.status_code == 201
    task_id = resp.get_json()["id"]

    get_resp = client.get(f"/tasks/{task_id}", headers=auth_header)
    assert get_resp.status_code == 200
    task = get_resp.get_json()
    assert task["title"] == "Test Task"
    assert task["user_id"] == 1


def test_retrieve_task_by_id(client, auth_header):
    payload = {"user_id": 2, "title": "Another Task"}
    resp = client.post("/tasks/", json=payload, headers=auth_header)
    task_id = resp.get_json()["id"]

    view_resp = client.get(f"/tasks/{task_id}", headers=auth_header)
    assert view_resp.status_code == 200
    assert view_resp.get_json()["id"] == task_id


def test_update_task_status(client, auth_header):
    payload = {"user_id": 3, "title": "Update Me"}
    create_resp = client.post("/tasks/", json=payload, headers=auth_header)
    task_id = create_resp.get_json()["id"]

    update_resp = client.put(f"/tasks/{task_id}", json={"status": "done"}, headers=auth_header)
    assert update_resp.status_code == 200

    get_resp = client.get(f"/tasks/{task_id}", headers=auth_header)
    assert get_resp.get_json()["status"] == "done"


def test_delete_task_by_id(client, auth_header):
    payload = {"user_id": 4, "title": "Delete Me"}
    create_resp = client.post("/tasks/", json=payload, headers=auth_header)
    task_id = create_resp.get_json()["id"]

    delete_resp = client.delete(f"/tasks/{task_id}", headers=auth_header)
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/tasks/{task_id}", headers=auth_header)
    assert get_resp.status_code == 404


def test_auth_required(client):
    payload = {"user_id": 99, "title": "Should Fail"}
    resp = client.post("/tasks/", json=payload)
    assert resp.status_code == 401


def test_create_task_without_token(client):
    response = client.post("/tasks/", json={"user_id": 1, "title": "Test Task"})
    assert response.status_code == 401


def test_create_task_with_invalid_token(client):
    headers = {"Authorization": "Bearer invalidtoken"}
    response = client.post("/tasks/", json={"user_id": 1, "title": "Test Task"}, headers=headers)
    assert response.status_code == 401


def test_create_task_with_valid_token(client):
    token = generate_test_token(user_id="admin", secret_key="supersecretkey")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/tasks/", json={"user_id": 1, "title": "Test Task"}, headers=headers)
    assert response.status_code == 201
