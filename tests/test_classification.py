import pytest
from app.models.risk_calculator import calculate_risk_score
from app.models.classifier import classify_employee


def test_group_1_normal():
    """Тест: Нормальный график -> Группа 1."""
    payload = {
        "user_id": "u1",
        "profile": {"work_hours": {"start": "09:00", "end": "18:00"}, "last_updated": "2026-05-20", "timezone": "UTC",
                    "employment": "full"},
        "tasks": [{"hours": 5}],
        "meetings": [{"start": "2026-05-21T10:00:00", "end": "2026-05-21T11:00:00"}],
        "conflicts": [],
        "hr_data": {"on_vacation": False}
    }

    risk_res = calculate_risk_score(payload)
    group = classify_employee(payload, risk_res)

    assert group["group_id"] == 1
    assert "Актуальный" in group["group_name"]


def test_group_3_outside_hours():
    """Тест: Встречи ночью -> Группа 3."""
    payload = {
        "user_id": "u2",
        "profile": {"work_hours": {"start": "09:00", "end": "18:00"}, "last_updated": "2026-05-20", "timezone": "UTC",
                    "employment": "full"},
        "tasks": [],
        "meetings": [
            {"start": "2026-05-21T22:00:00", "end": "2026-05-21T23:00:00"},  # Ночь
            {"start": "2026-05-21T23:00:00", "end": "2026-05-22T00:00:00"}  # Ночь
        ],
        "conflicts": [],
        "hr_data": {"on_vacation": False}
    }

    risk_res = calculate_risk_score(payload)
    group = classify_employee(payload, risk_res)

    assert group["group_id"] == 3
    assert "Встречи вне" in group["group_name"]


def test_group_6_hr_conflict():
    """Тест: В отпуске, но есть встречи -> Группа 6."""
    payload = {
        "user_id": "u3",
        "profile": {"work_hours": {"start": "09:00", "end": "18:00"}, "last_updated": "2026-05-20", "timezone": "UTC",
                    "employment": "full"},
        "tasks": [],
        "meetings": [{"start": "2026-05-21T10:00:00", "end": "2026-05-21T11:00:00"}],
        "conflicts": [],
        "hr_data": {"on_vacation": True}  # Официально в отпуске!
    }

    risk_res = calculate_risk_score(payload)
    group = classify_employee(payload, risk_res)

    assert group["group_id"] == 6
    assert "Конфликт HR" in group["group_name"]