import pytest
from app.models.risk_calculator import calculate_risk_score
from datetime import date, timedelta


def test_perfect_employee():
    """Тест: Идеальный сотрудник (риск должен быть 0 или около того)."""
    payload = {
        "user_id": "u1",
        "profile": {
            "work_hours": {"start": "09:00", "end": "18:00"},
            "timezone": "Europe/Moscow",
            "last_updated": date.today().isoformat(),  # Свежие данные
            "employment": "full-time"
        },
        "tasks": [],
        "meetings": [],
        "conflicts": [],
        "hr_data": {"on_vacation": False}
    }

    result = calculate_risk_score(payload)
    # Риск должен быть минимальным
    assert result["risk_score"] == 0.0
    assert result["metrics"]["A_i_freshness"] == 1.0


def test_stale_data_risk():
    """Тест: Устаревшие данные повышают риск."""
    # Данные обновлены 30 дней назад
    old_date = (date.today() - timedelta(days=30)).isoformat()
    payload = {
        "user_id": "u2",
        "profile": {"last_updated": old_date, "work_hours": {"start": "09:00", "end": "18:00"}, "timezone": "UTC",
                    "employment": "full"},
        "tasks": [], "meetings": [], "conflicts": [], "hr_data": {}
    }

    result = calculate_risk_score(payload)
    # Свежесть A_i должна упасть
    assert result["metrics"]["A_i_freshness"] < 0.5
    # Риск должен вырасти из-за (1 - A_i)
    assert result["risk_score"] > 0.0


def test_workload_risk():
    """Тест: Высокая нагрузка дает высокий риск."""
    payload = {
        "user_id": "u3",
        "profile": {"last_updated": date.today().isoformat(), "work_hours": {"start": "09:00", "end": "18:00"},
                    "timezone": "UTC", "employment": "full"},
        "tasks": [{"hours": 40}, {"hours": 20}],
        "meetings": [], "conflicts": [], "hr_data": {}
    }

    result = calculate_risk_score(payload)
    # Нагрузка L_i должна быть максимизирована (1.0)
    assert result["metrics"]["L_i_workload"] == 1.0
    assert result["risk_score"] == 0.2