"""Автотесты для API-эндпоинтов (FastAPI TestClient).

Проверяем:
  - GET /health — статус сервиса
  - POST /chat — AI чат-ассистент
  - POST /analyze — полный анализ риска
  - POST /conflicts/resolve — разрешение конфликта
  - POST /conflicts/resolve/batch — батчевая обработка
  - POST /ml/predict — ML-прогноз
  - POST /ml/score — оценка расписания
  - POST /ml/anomalies — обнаружение аномалий
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """TestClient — создаётся один раз на все тесты модуля."""
    return TestClient(app)


# ─────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────

class TestHealthEndpoint:
    """GET /health — проверка работоспособности."""

    def test_health_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "risk-service" in data["service"]

    def test_health_has_service_name(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "service" in data


# ─────────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────────

class TestChatEndpoint:
    """POST /chat — AI чат-ассистент."""

    def test_general_message(self, client):
        """Общий вопрос — ответ есть, tool_used=None."""
        resp = client.post("/chat", json={
            "message": "привет!",
            "profile": None,
            "tasks": [],
            "meetings": [],
            "history": [],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"]
        assert data["tool_used"] is None
        assert data["tool_data"] is None
        assert len(data["history"]) == 2

    def test_analyze_message(self, client):
        """Анализ риска — tool_used='analyze', есть tool_data."""
        resp = client.post("/chat", json={
            "message": "какой у меня риск выгорания?",
            "user_id": 1,
            "profile": {
                "work_hours": {"start": "09:00", "end": "18:00"},
                "timezone": "Europe/Moscow",
                "last_updated": "2026-05-20",
                "employment": "full-time",
            },
            "tasks": [{"hours": 5}],
            "meetings": [],
            "history": [],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_used"] == "analyze"
        assert data["tool_data"] is not None
        assert "risk_score" in data["tool_data"]

    def test_history_grows(self, client):
        """История растёт с каждым запросом."""
        resp = client.post("/chat", json={
            "message": "привет!",
            "profile": None,
            "tasks": [],
            "meetings": [],
            "history": [],
        })
        data = resp.json()
        assert len(data["history"]) == 2
        # Отправляем историю из первого ответа
        resp2 = client.post("/chat", json={
            "message": "что умеешь?",
            "profile": None,
            "tasks": [],
            "meetings": [],
            "history": data["history"],
        })
        data2 = resp2.json()
        assert len(data2["history"]) == 4

    def test_timestamp_in_response(self, client):
        """Ответ содержит timestamp в ISO формате."""
        resp = client.post("/chat", json={
            "message": "привет!",
            "profile": None,
            "tasks": [],
            "meetings": [],
            "history": [],
        })
        data = resp.json()
        assert "T" in data["timestamp"]


# ─────────────────────────────────────────────
# ANALYZE
# ─────────────────────────────────────────────

class TestAnalyzeEndpoint:
    """POST /analyze — полный анализ риска выгорания."""

    def test_analyze_perfect_employee(self, client):
        """Идеальный сотрудник — низкий риск."""
        resp = client.post("/analyze", json={
            "user_id": "u1",
            "profile": {
                "work_hours": {"start": "09:00", "end": "18:00"},
                "timezone": "Europe/Moscow",
                "last_updated": "2026-05-28",
                "employment": "full-time",
            },
            "tasks": [],
            "meetings": [],
            "hr_data": {"on_vacation": False},
            "conflicts": [],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_score"] == 0.0
        assert data["classification"]["group_id"] == 1

    def test_analyze_overloaded(self, client):
        """Перегруженный сотрудник — высокий риск."""
        resp = client.post("/analyze", json={
            "user_id": "u2",
            "profile": {
                "work_hours": {"start": "09:00", "end": "18:00"},
                "timezone": "UTC",
                "last_updated": "2026-05-28",
                "employment": "full-time",
            },
            "tasks": [{"hours": 40}, {"hours": 20}],
            "meetings": [],
            "hr_data": {"on_vacation": False},
            "conflicts": [],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_score"] > 0.0
        assert data["classification"]["group_id"] == 4

    def test_analyze_has_recommendations(self, client):
        """Ответ содержит рекомендации."""
        resp = client.post("/analyze", json={
            "user_id": "u3",
            "profile": {
                "work_hours": {"start": "09:00", "end": "18:00"},
                "timezone": "UTC",
                "last_updated": "2026-05-28",
                "employment": "full-time",
            },
            "tasks": [{"hours": 5}],
            "meetings": [],
            "hr_data": {"on_vacation": False},
            "conflicts": [],
        })
        data = resp.json()
        assert isinstance(data["recommendations"], list)

    def test_analyze_has_all_metrics(self, client):
        """Ответ содержит все 5 метрик."""
        resp = client.post("/analyze", json={
            "user_id": "u4",
            "profile": {
                "work_hours": {"start": "09:00", "end": "18:00"},
                "timezone": "UTC",
                "last_updated": "2026-05-28",
                "employment": "full-time",
            },
            "tasks": [],
            "meetings": [],
            "hr_data": {"on_vacation": False},
            "conflicts": [],
        })
        data = resp.json()
        metrics = data["metrics"]
        for key in ("A_i_freshness", "L_i_workload", "C_i_outside_hours", "Z_i_timezone", "H_i_hr_conflict"):
            assert key in metrics, f"Missing metric: {key}"


# ─────────────────────────────────────────────
# CONFLICTS / RESOLVE
# ─────────────────────────────────────────────

class TestConflictsResolveEndpoint:
    """POST /conflicts/resolve — разрешение конфликта."""

    def _conflict_request(self, conflict_type="OUTSIDE_WORK_HOURS"):
        return {
            "conflict": {
                "id": "conf-1",
                "userId": 1,
                "eventId": "event-1",
                "type": conflict_type,
                "description": "Встреча вне графика",
                "conflictDate": "2026-05-28T22:00:00",
                "severity": 3,
                "resolved": False,
                "detectedAt": "2026-05-28T10:00:00",
            },
            "profile": {
                "userId": 1,
                "name": "Иван",
                "surname": "Петров",
                "specialization": "Разработчик",
                "employmentType": "FULL_TIME",
                "timezone": "Europe/Moscow",
                "workStart": "09:00",
                "workEnd": "18:00",
                "updatedAt": "2026-05-28T10:00:00",
            },
            "tasks": [],
        }

    def test_resolve_outside_work_hours(self, client):
        """OUTSIDE_WORK_HOURS → AUTO_RESOLVED."""
        resp = client.post("/conflicts/resolve", json=self._conflict_request())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "AUTO_RESOLVED"
        assert data["conflict_type"] == "OUTSIDE_WORK_HOURS"

    def test_resolve_overlapping(self, client):
        """OVERLAPPING_EVENTS → OPTIONS_PROVIDED."""
        body = self._conflict_request("OVERLAPPING_EVENTS")
        body["conflict"]["conflictDate"] = "2026-05-28T14:00:00"
        resp = client.post("/conflicts/resolve", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "OPTIONS_PROVIDED"

    def test_resolve_overload(self, client):
        """OVERLOAD → MANUAL_REVIEW."""
        body = self._conflict_request("OVERLOAD")
        resp = client.post("/conflicts/resolve", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "MANUAL_REVIEW"

    def test_resolve_has_recommendations(self, client):
        """Ответ содержит рекомендации."""
        resp = client.post("/conflicts/resolve", json=self._conflict_request())
        data = resp.json()
        assert len(data["recommendations"]) >= 1


# ─────────────────────────────────────────────
# CONFLICTS / RESOLVE / BATCH
# ─────────────────────────────────────────────

class TestConflictsBatchEndpoint:
    """POST /conflicts/resolve/batch — батчевая обработка."""

    def _batch_request(self):
        return {
            "conflicts": [
                {
                    "conflict": {
                        "id": "conf-1",
                        "userId": 1,
                        "eventId": "event-1",
                        "type": "OUTSIDE_WORK_HOURS",
                        "description": "Встреча ночью",
                        "conflictDate": "2026-05-28T22:00:00",
                        "severity": 3,
                        "resolved": False,
                        "detectedAt": "2026-05-28T10:00:00",
                    },
                    "profile": {
                        "userId": 1,
                        "name": "Иван",
                        "surname": "Петров",
                        "specialization": "Разработчик",
                        "employmentType": "FULL_TIME",
                        "timezone": "Europe/Moscow",
                        "workStart": "09:00",
                        "workEnd": "18:00",
                        "updatedAt": "2026-05-28T10:00:00",
                    },
                    "tasks": [],
                },
                {
                    "conflict": {
                        "id": "conf-2",
                        "userId": 2,
                        "eventId": "event-2",
                        "type": "OVERLOAD",
                        "description": "Перегрузка",
                        "conflictDate": "2026-05-28T10:00:00",
                        "severity": 4,
                        "resolved": False,
                        "detectedAt": "2026-05-28T10:00:00",
                    },
                    "profile": {
                        "userId": 2,
                        "name": "Мария",
                        "surname": "Сидорова",
                        "specialization": "Тестировщик",
                        "employmentType": "FULL_TIME",
                        "timezone": "UTC",
                        "workStart": "09:00",
                        "workEnd": "18:00",
                        "updatedAt": "2026-05-28T10:00:00",
                    },
                    "tasks": [],
                },
            ]
        }

    def test_batch_success(self, client):
        """Батч из 2 конфликтов — все обработаны."""
        resp = client.post("/conflicts/resolve/batch", json=self._batch_request())
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_processed"] == 2
        assert data["success_count"] == 2
        assert data["error_count"] == 0

    def test_batch_results_count(self, client):
        """Количество результатов = количеству конфликтов."""
        resp = client.post("/conflicts/resolve/batch", json=self._batch_request())
        data = resp.json()
        assert len(data["results"]) == 2


# ─────────────────────────────────────────────
# ML ENDPOINTS
# ─────────────────────────────────────────────

class TestMLEndpoints:
    """POST /ml/predict, /ml/score, /ml/anomalies."""

    def _ml_request(self):
        return {
            "conflict": {
                "id": "conf-1",
                "userId": 1,
                "eventId": "event-1",
                "type": "OUTSIDE_WORK_HOURS",
                "description": "Тест",
                "conflictDate": "2026-05-28T14:00:00",
                "severity": 3,
                "resolved": False,
                "detectedAt": "2026-05-28T10:00:00",
            },
            "profile": {
                "userId": 1,
                "name": "Иван",
                "surname": "Петров",
                "specialization": "Разработчик",
                "employmentType": "FULL_TIME",
                "timezone": "Europe/Moscow",
                "workStart": "09:00",
                "workEnd": "18:00",
                "updatedAt": "2026-05-28T10:00:00",
            },
            "tasks": [
                {
                    "id": "task-1",
                    "initiatorId": 1,
                    "userIds": [1],
                    "title": "Ревью",
                    "description": "Ревью кода",
                    "type": "TASK",
                    "startTime": "2026-05-28T14:00:00",
                    "endTime": "2026-05-28T15:00:00",
                    "timezone": "Europe/Moscow",
                    "createdAt": "2026-05-27T10:00:00",
                    "updatedAt": "2026-05-27T10:00:00",
                }
            ],
        }

    def test_predict(self, client):
        """POST /ml/predict — вероятность конфликта."""
        resp = client.post("/ml/predict", json=self._ml_request())
        assert resp.status_code == 200
        data = resp.json()
        assert "conflict_probability" in data
        assert 0.0 <= data["conflict_probability"] <= 1.0
        assert "forecast_days" in data

    def test_score(self, client):
        """POST /ml/score — оценка качества расписания."""
        resp = client.post("/ml/score", json=self._ml_request())
        assert resp.status_code == 200
        data = resp.json()
        assert "quality_score" in data
        assert "grade" in data
        assert data["grade"] in ("A", "B", "C", "D")

    def test_anomalies(self, client):
        """POST /ml/anomalies — обнаружение аномалий."""
        resp = client.post("/ml/anomalies", json=self._ml_request())
        assert resp.status_code == 200
        data = resp.json()
        assert "is_anomalous" in data
        assert "anomaly_score" in data
        assert "detected_patterns" in data
        assert "action_required" in data