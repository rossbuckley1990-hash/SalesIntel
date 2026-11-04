from fastapi.testclient import TestClient

from app.main import create_app


def test_version_endpoint_returns_app_name_and_version() -> None:
    client = TestClient(create_app())

    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json() == {
        "app_name": "SalesIntel API",
        "version": "0.1.0",
        "environment": "local",
    }

