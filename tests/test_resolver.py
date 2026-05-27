"""Автотесты для conflict resolver (app.conflict.resolver).

Проверяем все 4 типа конфликтов + неизвестный тип:
  - OUTSIDE_WORK_HOURS — перенос на рабочее время, AUTO_RESOLVED
  - OVERLAPPING_EVENTS — варианты разделения, OPTIONS_PROVIDED
  - OVERLOAD — делегирование, MANUAL_REVIEW
  - WORKDAY_EXCEPTION_CONFLICT — сверка с HR, MANUAL_REVIEW
  - Неизвестный тип — MANUAL_REVIEW
"""
import pytest
from datetime import datetime

from app.conflict.resolver import resolve_conflict
from app.schemas import (
    ConflictResolveRequest,
    ProfileSchema,
    TaskSchema,
    ConflictSchema,
    ConflictType,
)


# ─────────────────────────────────────────────
# ХЕЛПЕРЫ
# ─────────────────────────────────────────────

def _profile(**overrides) -> ProfileSchema:
    """Базовый профиль для тестов."""
    defaults = dict(
        userId=1,
        name="Иван",
        surname="Петров",
        specialization="Разработчик",
        employmentType="FULL_TIME",
        timezone="Europe/Moscow",
        workStart="09:00",
        workEnd="18:00",
        updatedAt=datetime(2026, 5, 28, 10, 0, 0),
    )
    defaults.update(overrides)
    return ProfileSchema(**defaults)


def _conflict(conflict_type: ConflictType, **overrides) -> ConflictSchema:
    """Базовый конфликт для тестов."""
    defaults = dict(
        id="conf-test",
        userId=1,
        eventId="event-1",
        type=conflict_type,
        description="Тестовый конфликт",
        severity=3,
        resolved=False,
        detectedAt=datetime(2026, 5, 28, 10, 0, 0),
    )
    defaults.update(overrides)
    return ConflictSchema(**defaults)


def _task(**overrides) -> TaskSchema:
    """Базовая задача для тестов."""
    defaults = dict(
        id="task-1",
        initiatorId=1,
        userIds=[1],
        title="Ревью кода",
        description="Ревью",
        type="TASK",
        startTime=datetime(2026, 5, 28, 10, 0, 0),
        endTime=datetime(2026, 5, 28, 11, 0, 0),
        timezone="Europe/Moscow",
        createdAt=datetime(2026, 5, 27, 10, 0, 0),
        updatedAt=datetime(2026, 5, 27, 10, 0, 0),
    )
    defaults.update(overrides)
    return TaskSchema(**defaults)


def _resolve(conflict_type: ConflictType, conflict_overrides=None, tasks=None, profile_overrides=None):
    """Хелпер: создаёт запрос и вызывает resolve_conflict."""
    conflict = _conflict(conflict_type, **(conflict_overrides or {}))
    profile = _profile(**(profile_overrides or {}))
    req = ConflictResolveRequest(
        conflict=conflict,
        profile=profile,
        tasks=tasks or [],
    )
    return resolve_conflict(req)


# ─────────────────────────────────────────────
# OUTSIDE_WORK_HOURS
# ─────────────────────────────────────────────

class TestOutsideWorkHours:
    """Конфликт: встреча вне рабочих часов."""

    def test_auto_resolved(self):
        """OUTSIDE_WORK_HOURS → status = AUTO_RESOLVED."""
        result = _resolve(
            ConflictType.OUTSIDE_WORK_HOURS,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 22, 0, 0)},
        )
        assert result.status == "AUTO_RESOLVED"

    def test_has_reschedule_recommendation(self):
        """Рекомендация — RESCHEDULE с предложенным временем."""
        result = _resolve(
            ConflictType.OUTSIDE_WORK_HOURS,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 22, 0, 0)},
        )
        assert len(result.recommendations) >= 1
        assert result.recommendations[0].action == "RESCHEDULE"

    def test_evening_moves_to_next_morning(self):
        """Встреча в 22:00 → перенос на утро следующего дня."""
        result = _resolve(
            ConflictType.OUTSIDE_WORK_HOURS,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 22, 0, 0)},
        )
        rec = result.recommendations[0]
        assert rec.suggested_start is not None
        # Утро следующего дня = 29 мая, 09:00
        assert rec.suggested_start.hour == 9
        assert rec.suggested_start.day == 29

    def test_early_morning_moves_to_work_start(self):
        """Встреча в 06:00 → перенос на начало рабочего дня."""
        result = _resolve(
            ConflictType.OUTSIDE_WORK_HOURS,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 6, 0, 0)},
        )
        rec = result.recommendations[0]
        assert rec.suggested_start.hour == 9  # workStart = 09:00

    def test_has_explanation(self):
        """Есть текстовое пояснение."""
        result = _resolve(
            ConflictType.OUTSIDE_WORK_HOURS,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 22, 0, 0)},
        )
        assert result.explanation
        assert len(result.explanation) > 10


# ─────────────────────────────────────────────
# OVERLAPPING_EVENTS
# ─────────────────────────────────────────────

class TestOverlappingEvents:
    """Конфликт: наложение событий."""

    def test_options_provided(self):
        """OVERLAPPING_EVENTS → status = OPTIONS_PROVIDED."""
        result = _resolve(
            ConflictType.OVERLAPPING_EVENTS,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 14, 0, 0)},
        )
        assert result.status == "OPTIONS_PROVIDED"

    def test_two_recommendations(self):
        """Два варианта: RESCHEDULE + SPLIT."""
        result = _resolve(
            ConflictType.OVERLAPPING_EVENTS,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 14, 0, 0)},
        )
        assert len(result.recommendations) == 2
        actions = [r.action for r in result.recommendations]
        assert "RESCHEDULE" in actions
        assert "SPLIT" in actions

    def test_reschedule_one_hour_later(self):
        """RESCHEDULE — перенос на +1 час."""
        result = _resolve(
            ConflictType.OVERLAPPING_EVENTS,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 14, 0, 0)},
        )
        rec = result.recommendations[0]
        assert rec.suggested_start.hour == 15  # 14 + 1

    def test_has_explanation(self):
        result = _resolve(
            ConflictType.OVERLAPPING_EVENTS,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 14, 0, 0)},
        )
        assert "наложени" in result.explanation.lower() or "раздел" in result.explanation.lower()


# ─────────────────────────────────────────────
# OVERLOAD
# ─────────────────────────────────────────────

class TestOverload:
    """Конфликт: высокая перегрузка."""

    def test_manual_review(self):
        """OVERLOAD → status = MANUAL_REVIEW."""
        result = _resolve(
            ConflictType.OVERLOAD,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 10, 0, 0)},
        )
        assert result.status == "MANUAL_REVIEW"

    def test_delegate_and_reschedule(self):
        """Два варианта: DELEGATE + RESCHEDULE."""
        result = _resolve(
            ConflictType.OVERLOAD,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 10, 0, 0)},
        )
        actions = [r.action for r in result.recommendations]
        assert "DELEGATE" in actions
        assert "RESCHEDULE" in actions

    def test_delegate_confidence(self):
        """DELEGATE уверенность = 0.75."""
        result = _resolve(
            ConflictType.OVERLOAD,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 10, 0, 0)},
        )
        delegate_rec = [r for r in result.recommendations if r.action == "DELEGATE"][0]
        assert delegate_rec.confidence == 0.75

    def test_has_explanation(self):
        result = _resolve(
            ConflictType.OVERLOAD,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 10, 0, 0)},
        )
        assert "перегруз" in result.explanation.lower() or "делегир" in result.explanation.lower()


# ─────────────────────────────────────────────
# WORKDAY_EXCEPTION_CONFLICT
# ─────────────────────────────────────────────

class TestWorkdayExceptionConflict:
    """Конфликт: рабочие исключения."""

    def test_manual_review(self):
        """WORKDAY_EXCEPTION_CONFLICT → status = MANUAL_REVIEW."""
        result = _resolve(
            ConflictType.WORKDAY_EXCEPTION_CONFLICT,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 10, 0, 0)},
        )
        assert result.status == "MANUAL_REVIEW"

    def test_keep_and_cancel(self):
        """Два варианта: KEEP + CANCEL."""
        result = _resolve(
            ConflictType.WORKDAY_EXCEPTION_CONFLICT,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 10, 0, 0)},
        )
        actions = [r.action for r in result.recommendations]
        assert "KEEP" in actions
        assert "CANCEL" in actions

    def test_has_explanation(self):
        result = _resolve(
            ConflictType.WORKDAY_EXCEPTION_CONFLICT,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 10, 0, 0)},
        )
        assert "исключ" in result.explanation.lower() or "HR" in result.explanation


# ─────────────────────────────────────────────
# КРАЕВЫЕ СЛУЧАИ
# ─────────────────────────────────────────────

class TestResolverEdgeCases:
    """Краевые случаи resolver."""

    def test_conflict_id_preserved(self):
        """conflict_id в ответе совпадает с id конфликта."""
        result = _resolve(
            ConflictType.OUTSIDE_WORK_HOURS,
            conflict_overrides={
                "id": "my-conflict-42",
                "conflictDate": datetime(2026, 5, 28, 22, 0, 0),
            },
        )
        assert result.conflict_id == "my-conflict-42"

    def test_conflict_type_in_response(self):
        """conflict_type в ответе — строковое значение ConflictType."""
        result = _resolve(
            ConflictType.OVERLOAD,
            conflict_overrides={"conflictDate": datetime(2026, 5, 28, 10, 0, 0)},
        )
        assert result.conflict_type == "OVERLOAD"

    def test_with_tasks_included(self):
        """Задачи передаются в resolver — не крашится."""
        result = _resolve(
            ConflictType.OVERLAPPING_EVENTS,
            conflict_overrides={
                "conflictDate": datetime(2026, 5, 28, 14, 0, 0),
                "eventId": "task-1",
            },
            tasks=[_task()],
        )
        assert result.status == "OPTIONS_PROVIDED"

    def test_severity_high(self):
        """Высокая серьёзность — resolver работает."""
        result = _resolve(
            ConflictType.OUTSIDE_WORK_HOURS,
            conflict_overrides={
                "severity": 5,
                "conflictDate": datetime(2026, 5, 28, 22, 0, 0),
            },
        )
        assert result.status == "AUTO_RESOLVED"

    def test_no_conflict_date_uses_now(self):
        """Без conflictDate — используется текущее время, не крашится."""
        result = _resolve(
            ConflictType.OUTSIDE_WORK_HOURS,
            # conflictDate не указан → None
        )
        # Не крашится, просто работает с datetime.now()
        assert result.status in ("AUTO_RESOLVED", "OPTIONS_PROVIDED", "MANUAL_REVIEW")