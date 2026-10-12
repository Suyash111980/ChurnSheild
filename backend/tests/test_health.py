from fastapi.testclient import TestClient

from app.main import app


def test_public_health_endpoint():
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "churnshield-backend",
        "version": app.version,
    }
