import pytest
from app.recommendations.engine import generate_recommendations


def test_rec_group_3():
    """Тест: Для группы 3 советуют перенести встречи."""
    classification = {"group_id": 3, "group_name": "Встречи вне рабочего времени"}
    metrics = {"C_i_outside_hours": 1.0}

    recs = generate_recommendations(classification, metrics)

    # Проверяем, что есть совет про рабочее время
    assert any("рабочее время" in r or "перенести" in r for r in recs)


def test_rec_group_6():
    """Тест: Для группы 6 советуют проверить HR."""
    classification = {"group_id": 6, "group_name": "Конфликт HR"}
    metrics = {"H_i_hr_conflict": 0.8}

    recs = generate_recommendations(classification, metrics)

    # Проверяем совет про HR или статусы
    assert any("HR" in r or "синхронизации" in r for r in recs)


def test_rec_normal():
    """Тест: Для хорошей группы советуют продолжить в том же духе."""
    classification = {"group_id": 1, "group_name": "Актуальный график"}
    metrics = {"C_i_outside_hours": 0.0, "L_i_workload": 0.2}

    recs = generate_recommendations(classification, metrics)

    assert any("оптимален" in r.lower() or "продолжайте" in r.lower() for r in recs)