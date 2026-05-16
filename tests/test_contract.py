import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.predictor import predictor


@pytest.fixture(autouse=True)
def ensure_model_loaded():
    predictor.load_model()
    yield


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["model_loaded"] is True


def test_predict_contract():
    payload = {
        "user_id": "test_001",
        "weekly_work_hours": 45.0,
        "overtime_hours": 5.0,
        "meeting_density": 0.5,
        "consecutive_work_days": 5,
        "conflict_count": 1,
        "workload_trend": 0.1,
        "night_weekend_hours": 2.0
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200

    data = response.json()

    assert "user_id" in data
    assert "score" in data
    assert "category" in data
    assert "forecast_3d" in data
    assert "recommendations" in data

    assert 0 <= data["score"] <= 10
    assert data["category"] in ["low", "medium", "high"]
    assert len(data["forecast_3d"]) == 3
    assert all(0 <= f <= 10 for f in data["forecast_3d"])
    assert isinstance(data["recommendations"], list)
    assert len(data["recommendations"]) >= 1


def test_validation_error():
    bad_payload = {
        "user_id": "test_002",
        "weekly_work_hours": 45.0,
        "overtime_hours": -5.0,
        "meeting_density": 0.5,
        "consecutive_work_days": 5,
        "conflict_count": 1,
        "workload_trend": 0.1,
        "night_weekend_hours": 2.0
    }
    response = client.post("/predict", json=bad_payload)
    assert response.status_code == 422