"""
Integration tests for Task endpoints (protected)
"""
from unittest.mock import AsyncMock

# To run tests:
# PYTHONPATH=. uv run pytest todo/tests -v --tb=short

from fastapi.testclient import TestClient

TEST_TASK = {"title": "Learn FastAPI testing"}


# auth_token is a fixture that returns token
# and passes as parameter to this task
def test_create_task(client: TestClient, auth_token):
    """Test creating a task"""
    # Create task with token
    response = client.post(
        "/tasks",
        json={"title": "Learn FastAPI testing"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Learn FastAPI testing"
    assert "id" in data


def test_list_tasks(client: TestClient, auth_token):
    """Test listing tasks"""
    # Create a task first
    client.post(
        "/tasks",
        json={"title": 'Test task'},
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    # List tasks
    response = client.get(
        "/tasks",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_mark_task_done(client: TestClient, auth_token):
    """Test marking a task as done"""
    # Create task
    create_response = client.post(
        "/tasks",
        json={"title": "Complete this task"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    task_id = create_response.json()["id"]

    # Mark as done
    response = client.patch(
        f"/tasks/{task_id}/done",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    assert response.json()["done"] is True


def test_create_task_invalid_input(client: TestClient, auth_token):
    """Test creating task with invalid input (missing title or empty)"""
    response = client.post(
        "/tasks",
        json={"title": ""},  # Empty title should be invalid
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 422      # Pydantic validation error
    assert "Invalid input data" in response.json()["detail"]


def test_delete_task(client: TestClient, auth_token):
    """Test deleting a task"""
    # Create task
    create_response = client.post(
        "/tasks",
        json={"title": "Task to delete"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    task_id = create_response.json()["id"]

    # Delete task
    response = client.delete(
        f"/tasks/{task_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]


def test_delete_nonexistent_task(client: TestClient, auth_token):
    """Test deleting non-existent task"""
    response = client.delete(
        "/tasks/99999",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404


def test_protected_endpoint_without_token(client: TestClient):
    """Test that protected endpoints require authentication"""
    response = client.get("/tasks")
    assert response.status_code == 401


def test_invalid_token(client: TestClient):
    """Test using invalid token"""
    response = client.get(
        "/tasks",
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == 401


def test_expired_token_scenario(client: TestClient, registered_user):
    """Simulate expired token behavior (in real app you would set short expiry)"""
    # This is more of a manual test in real life
    pass

# ==================== Dashboard ===================================
def test_dashboard_success(client, auth_token, mock_arq_create_pool):
    """
    GET /dashboard should return stats, recent_tasks, and redis_available.
    Uses gather under the hood; we only assert the HTTP contract.
    """
    # seed a couple of tasks so stats/recent are non-empty
    headers = {"Authorization": f"Bearer {auth_token}"}
    client.post("/tasks", json={"title": "Dash task 1"}, headers=headers)
    client.post("/tasks", json={"title": "Dash task 2"}, headers=headers)

    # make ping succeed (ARQ pool is already mocked in conftest)
    mock_arq_create_pool.ping = AsyncMock(return_value=True)

    response = client.get("/dashboard", headers=headers)

    assert response.status_code == 200
    body = response.json()

    assert "stats" in body
    assert body["stats"]["total"] >= 2
    assert body["stats"]["pending"] >= 2
    assert "done" in body["stats"]

    assert "recent_tasks" in body
    assert isinstance(body["recent_tasks"], list)
    assert len(body["recent_tasks"]) >= 1

    assert body["redis_available"] is True


def test_dashboard_requires_auth(client):
    """Dashboard is protected — no token → 401."""
    response = client.get("/dashboard")
    assert response.status_code in (401, 403)


def test_dashboard_redis_down(client, auth_token, mock_arq_create_pool):
    """When Redis ping fails, redis_available should be False (API still 200)."""
    mock_arq_create_pool.ping = AsyncMock(side_effect=ConnectionError("down"))

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/dashboard", headers=headers)

    assert response.status_code == 200
    assert response.json()["redis_available"] is False