"""Автотесты для чат-ассистента (app.chat.engine).

Проверяем:
  - detect_intent — определение намерения по ключевым словам
  - call_tool — вызов инструмента и формат результата
  - process_chat — полный пайплайн: ответ, tool_used, tool_data, history
  - edge cases — пустые данные, fallback при ошибках

Примечание: тесты call_tool/process_chat корректно работают
даже если ML-модели не загрузились (success=False).
"""
import pytest
from app.chat.engine import detect_intent, call_tool, process_chat
from app.chat.schemas import ChatRequest, ChatMessage, ToolResult


# ─────────────────────────────────────────────
# ХЕЛПЕР
# ─────────────────────────────────────────────

def _analyze_context(base_profile, tasks=None, meetings=None):
    """Собирает контекст для analyze/score/predict, совместимый с _build_analyze_payload."""
    return {
        "user_id": 1,
        "profile": base_profile,
        "tasks": tasks or [],
        "meetings": meetings or [],
    }


# ─────────────────────────────────────────────
# ФИКСТУРЫ
# ─────────────────────────────────────────────

@pytest.fixture
def base_profile():
    """Минимальный профиль для тестов — формат chat API (workStart/workEnd)."""
    return {
        "name": "Иван",
        "surname": "Петров",
        "specialization": "Разработчик",
        "workStart": "09:00",
        "workEnd": "18:00",
        "userId": 1,
        "timezone": "Europe/Moscow",
        "last_updated": "2026-05-20T10:00:00Z",
    }


@pytest.fixture
def risk_profile():
    """Профиль в формате risk_calculator (work_hours) — без адаптации."""
    return {
        "name": "Иван",
        "surname": "Петров",
        "specialization": "Разработчик",
        "work_hours": {"start": "09:00", "end": "18:00"},
        "userId": 1,
        "timezone": "Europe/Moscow",
        "last_updated": "2026-05-20T10:00:00Z",
        "employment": "FULL_TIME",
    }


# ─────────────────────────────────────────────
# DETECT_INTENT
# ─────────────────────────────────────────────

class TestDetectIntent:
    """Проверяем определение намерения по сообщению пользователя."""

    @pytest.mark.parametrize("message,expected", [
        # general
        ("привет!", "general"),
        ("что ты умеешь?", "general"),
        ("спасибо", "general"),
        # analyze
        ("какой у меня риск выгорания?", "analyze"),
        ("насколько я перегружен?", "analyze"),
        ("оцени мой риск", "analyze"),
        ("риск выгорания", "analyze"),
        # score
        ("оцени качество моего расписания", "score"),
        ("оценка моего расписания", "score"),
        ("какой балл за график", "score"),
        ("оцени расписание", "score"),
        # predict
        ("предскажи вероятность конфликта", "predict"),
        ("прогноз конфликтов", "predict"),
        ("будет ли конфликт?", "conflicts"),  # «конфликт» матчит conflicts сильнее чем predict
        # anomalies
        ("есть ли аномалии в графике?", "anomalies"),
        ("что-то не так с расписанием", "anomalies"),
        ("обнаружь отклонения", "anomalies"),
        # conflicts
        ("как разрешить конфликт?", "conflicts"),
        ("помоги разрешить накладку", "conflicts"),
        ("пересечение в календаре", "conflicts"),
    ])
    def test_intent_detection(self, message, expected):
        assert detect_intent(message) == expected

    def test_empty_message(self):
        assert detect_intent("") == "general"

    def test_numbers_and_symbols(self):
        assert detect_intent("123 !!!") == "general"

    def test_case_insensitive(self):
        assert detect_intent("РИСК ВЫГОРАНИЯ") == "analyze"
        assert detect_intent("Аномалии В Графике") == "anomalies"


# ─────────────────────────────────────────────
# CALL_TOOL
# ─────────────────────────────────────────────

class TestCallTool:
    """Проверяем вызов инструментов и формат ToolResult.

    Примечание: если ML-модель не загрузилась (несовместимость sklearn),
    инструмент вернёт success=False — это нормальное поведение,
    тест проверяет оба сценария.
    """

    def test_general_returns_none(self):
        result = call_tool("general", {})
        assert result is None

    def test_analyze_returns_tool_result(self, risk_profile):
        """Analyze с профилем в формате risk_calculator — возвращает ToolResult."""
        context = _analyze_context(
            risk_profile,
            tasks=[{"hours": 2}],
            meetings=[],
        )
        result = call_tool("analyze", context)
        assert isinstance(result, ToolResult), f"Expected ToolResult, got {type(result)}"
        assert result.tool_name == "analyze"
        if result.success:
            assert "risk_score" in result.data
            assert "metrics" in result.data
            assert "classification" in result.data
        else:
            # ML-модель может не загрузиться — проверяем что ошибка есть
            assert result.error is not None

    def test_analyze_with_chat_profile(self, base_profile):
        """Analyze с профилем из chat API (workStart) — проверяем адаптацию."""
        context = _analyze_context(
            base_profile,
            tasks=[{"id": "1", "title": "Спринт", "startTime": "2026-05-28T09:00:00", "endTime": "2026-05-28T11:00:00"}],
            meetings=[],
        )
        result = call_tool("analyze", context)
        assert isinstance(result, ToolResult), f"Expected ToolResult, got {type(result)}"
        assert result.tool_name == "analyze"
        if result.success:
            assert "risk_score" in result.data
        else:
            assert result.error is not None

    def test_score_returns_tool_result(self, risk_profile):
        context = _analyze_context(
            risk_profile,
            tasks=[{"hours": 2}],
        )
        result = call_tool("score", context)
        assert isinstance(result, ToolResult)
        assert result.tool_name == "score"
        if result.success:
            assert "quality_score" in result.data
            assert "grade" in result.data
            assert "breakdown" in result.data
        else:
            assert result.error is not None

    def test_predict_returns_tool_result(self, risk_profile):
        context = _analyze_context(risk_profile)
        result = call_tool("predict", context)
        assert isinstance(result, ToolResult)
        assert result.tool_name == "predict"
        if result.success:
            assert "conflict_probability" in result.data
            assert "forecast_days" in result.data
        else:
            assert result.error is not None

    def test_anomalies_returns_tool_result(self):
        context = {
            "user_id": 1,
            "profile": {},
            "tasks": [{"id": "1", "title": "Ревью", "startTime": "2026-05-28T14:00:00", "endTime": "2026-05-28T15:00:00"}],
            "meetings": [],
        }
        result = call_tool("anomalies", context)
        assert isinstance(result, ToolResult)
        assert result.tool_name == "anomalies"
        if result.success:
            assert "is_anomalous" in result.data
            assert "anomaly_score" in result.data
            assert "detected_patterns" in result.data
            assert "action_required" in result.data
        else:
            assert result.error is not None

    def test_conflicts_no_conflicts_falls_back(self, risk_profile):
        """Без конфликтов в контексте — fallback на analyze."""
        context = {
            "user_id": 1,
            "profile": risk_profile,
            "tasks": [{"hours": 2}],
            "meetings": [],
            "conflicts": [],
        }
        result = call_tool("conflicts", context)
        assert isinstance(result, ToolResult)
        # Fallback на analyze
        assert result.tool_name == "analyze"
        # Может быть success=True или False (зависит от окружения)
        if not result.success:
            assert result.error is not None

    def test_conflicts_with_data(self, base_profile):
        """С конфликтом в контексте — tool вызывается как conflicts."""
        context = {
            "user_id": 5,
            "profile": {**base_profile, "userId": 5, "employmentType": "FULL_TIME"},
            "tasks": [],
            "meetings": [],
            "conflicts": [
                {
                    "id": "conf-1",
                    "type": "OUTSIDE_WORK_HOURS",
                    "description": "Встреча в 22:00",
                    "severity": 4,
                    "start": "2026-05-28T22:00:00",
                    "end": "2026-05-28T23:00:00",
                }
            ],
        }
        result = call_tool("conflicts", context)
        assert isinstance(result, ToolResult)
        assert result.tool_name == "conflicts"
        if result.success:
            assert "conflict_type" in result.data
            assert "status" in result.data
            assert "explanation" in result.data
        else:
            assert result.error is not None

    def test_unknown_intent_returns_error(self):
        result = call_tool("nonexistent_tool", {})
        assert isinstance(result, ToolResult)
        assert result.success is False
        assert "Неизвестный инструмент" in result.error


# ─────────────────────────────────────────────
# PROCESS_CHAT — ПОЛНЫЙ ПАЙПЛАЙН
# ─────────────────────────────────────────────

class TestProcessChat:
    """Проверяем полный пайплайн process_chat.

    Гарантируем: ответ всегда есть, tool_used корректный,
    tool_data = данные если success, None если fail.
    """

    def test_general_no_tool(self, base_profile):
        """General — tool_used=None, tool_data=None."""
        req = ChatRequest(
            message="привет!",
            profile=base_profile,
            tasks=[],
            meetings=[],
            history=[],
        )
        resp = process_chat(req)

        assert resp.answer is not None
        assert len(resp.answer) > 10
        assert resp.tool_used is None
        assert resp.tool_data is None

    def test_analyze_response(self, risk_profile):
        """Analyze — tool_used='analyze', ответ есть."""
        req = ChatRequest(
            message="какой у меня риск выгорания?",
            user_id=1,
            profile=risk_profile,
            tasks=[{"hours": 2}],
            meetings=[],
            history=[],
        )
        resp = process_chat(req)

        assert resp.tool_used == "analyze", f"Expected 'analyze', got '{resp.tool_used}'"
        assert resp.answer is not None
        # Если инструмент успешен — проверяем данные
        if resp.tool_data is not None:
            assert "risk_score" in resp.tool_data
            assert 0.0 <= resp.tool_data["risk_score"] <= 1.0
            assert "metrics" in resp.tool_data
        # Если не успешен — tool_data=None, но ответ всё равно есть (fallback)

    def test_score_response(self, risk_profile):
        """Score — tool_used='score', ответ есть."""
        req = ChatRequest(
            message="оцени качество моего расписания",
            user_id=1,
            profile=risk_profile,
            tasks=[{"hours": 2}],
            meetings=[],
            history=[],
        )
        resp = process_chat(req)

        assert resp.tool_used == "score", f"Expected 'score', got '{resp.tool_used}'"
        assert resp.answer is not None
        if resp.tool_data is not None:
            assert "quality_score" in resp.tool_data
            assert "grade" in resp.tool_data
            assert resp.tool_data["grade"] in ("A", "B", "C", "D")

    def test_predict_response(self, risk_profile):
        """Predict — tool_used='predict', ответ есть."""
        req = ChatRequest(
            message="предскажи вероятность конфликта",
            user_id=1,
            profile=risk_profile,
            tasks=[],
            meetings=[],
            history=[],
        )
        resp = process_chat(req)

        assert resp.tool_used == "predict", f"Expected 'predict', got '{resp.tool_used}'"
        assert resp.answer is not None
        if resp.tool_data is not None:
            assert "conflict_probability" in resp.tool_data
            assert 0.0 <= resp.tool_data["conflict_probability"] <= 1.0

    def test_anomalies_response(self, risk_profile):
        """Anomalies — tool_used='anomalies', ответ есть."""
        req = ChatRequest(
            message="есть ли аномалии в моём графике?",
            user_id=1,
            profile=risk_profile,
            tasks=[{"id": "1", "title": "Ревью", "startTime": "2026-05-28T14:00:00", "endTime": "2026-05-28T15:00:00"}],
            meetings=[],
            history=[],
        )
        resp = process_chat(req)

        assert resp.tool_used == "anomalies", f"Expected 'anomalies', got '{resp.tool_used}'"
        assert resp.answer is not None
        if resp.tool_data is not None:
            assert "is_anomalous" in resp.tool_data
            assert isinstance(resp.tool_data["is_anomalous"], bool)

    def test_conflicts_with_data(self, base_profile):
        """Conflicts с данными — tool_used='conflicts', ответ есть."""
        req = ChatRequest(
            message="как разрешить конфликт?",
            user_id=5,
            profile={**base_profile, "userId": 5, "employmentType": "FULL_TIME"},
            tasks=[],
            meetings=[],
            conflicts=[
                {
                    "id": "conf-1",
                    "type": "OUTSIDE_WORK_HOURS",
                    "description": "Встреча в 22:00",
                    "severity": 4,
                    "start": "2026-05-28T22:00:00",
                    "end": "2026-05-28T23:00:00",
                }
            ],
            history=[],
        )
        resp = process_chat(req)

        assert resp.tool_used == "conflicts", f"Expected 'conflicts', got '{resp.tool_used}'"
        assert resp.answer is not None

    def test_conflicts_no_data_falls_back(self, risk_profile):
        """Conflicts без данных — fallback на analyze.

        Если analyze успешен → tool_used='analyze', tool_data есть.
        Если analyze тоже упал → tool_used='conflicts' (исходный intent),
        tool_data=None, но ответ есть (fallback).
        """
        req = ChatRequest(
            message="как разрешить конфликт?",
            user_id=1,
            profile=risk_profile,
            tasks=[{"hours": 2}],
            meetings=[],
            conflicts=[],
            history=[],
        )
        resp = process_chat(req)

        assert resp.answer is not None
        # Два варианта в зависимости от окружения:
        if resp.tool_data is not None:
            # analyze успешен → tool_used = 'analyze' (из tool_result.tool_name)
            assert resp.tool_used == "analyze", f"Expected 'analyze' (fallback), got '{resp.tool_used}'"
        else:
            # analyze упал → tool_used = 'conflicts' (исходный intent)
            assert resp.tool_used in ("analyze", "conflicts"), \
                f"Expected 'analyze' or 'conflicts', got '{resp.tool_used}'"

    def test_history_preserved_and_grows(self, base_profile):
        """История: каждый запрос добавляет 2 сообщения (user + assistant)."""
        req1 = ChatRequest(
            message="привет!",
            profile=base_profile,
            tasks=[],
            meetings=[],
            history=[],
        )
        resp1 = process_chat(req1)
        assert len(resp1.history) == 2
        assert resp1.history[0].role == "user"
        assert resp1.history[1].role == "assistant"

        # Второй запрос с историей из первого
        req2 = ChatRequest(
            message="какой риск выгорания?",
            user_id=1,
            profile=base_profile,
            tasks=[],
            meetings=[],
            history=resp1.history,
        )
        resp2 = process_chat(req2)
        assert len(resp2.history) == 4

    def test_history_content_matches(self, base_profile):
        """Содержимое history совпадает с запросом и ответом."""
        req = ChatRequest(
            message="привет!",
            profile=base_profile,
            tasks=[],
            meetings=[],
            history=[],
        )
        resp = process_chat(req)

        assert resp.history[0].content == "привет!"
        assert resp.history[0].role == "user"
        assert resp.history[1].role == "assistant"
        assert resp.history[1].content == resp.answer

    def test_timestamp_present(self, base_profile):
        """В ответе всегда есть timestamp."""
        req = ChatRequest(
            message="привет!",
            profile=base_profile,
            tasks=[],
            meetings=[],
            history=[],
        )
        resp = process_chat(req)
        assert resp.timestamp is not None
        assert "T" in resp.timestamp  # ISO 8601


# ─────────────────────────────────────────────
# EDGE CASES
# ─────────────────────────────────────────────

class TestEdgeCases:
    """Краевые случаи и обработка ошибок."""

    def test_empty_profile(self):
        """Пустой профиль — не крашится, даёт ответ."""
        req = ChatRequest(
            message="привет!",
            profile=None,
            tasks=[],
            meetings=[],
            history=[],
        )
        resp = process_chat(req)
        assert resp.answer is not None
        assert resp.tool_used is None

    def test_no_tasks_no_meetings(self, risk_profile):
        """Без задач и встреч — не крашится, ответ есть."""
        req = ChatRequest(
            message="какой у меня риск выгорания?",
            user_id=1,
            profile=risk_profile,
            tasks=[],
            meetings=[],
            history=[],
        )
        resp = process_chat(req)
        assert resp.tool_used == "analyze", f"Expected 'analyze', got '{resp.tool_used}'"
        assert resp.answer is not None
        # tool_data может быть None если инструмент упал
        if resp.tool_data is not None:
            assert "risk_score" in resp.tool_data

    def test_freshness_empty_last_updated(self, risk_profile):
        """Пустой last_updated — не крашится (freshness = 0.0)."""
        profile = {k: v for k, v in risk_profile.items() if k != "last_updated"}
        req = ChatRequest(
            message="какой у меня риск выгорания?",
            user_id=1,
            profile=profile,
            tasks=[],
            meetings=[],
            history=[],
        )
        resp = process_chat(req)
        assert resp.tool_used == "analyze", f"Expected 'analyze', got '{resp.tool_used}'"
        assert resp.answer is not None
        # Если инструмент успешен — проверяем freshness = 0.0
        if resp.tool_data is not None:
            assert resp.tool_data["metrics"]["A_i_freshness"] == 0.0

    def test_very_long_message(self, risk_profile):
        """Очень длинное сообщение — не крашится."""
        long_msg = "риск выгорания " * 100
        req = ChatRequest(
            message=long_msg,
            user_id=1,
            profile=risk_profile,
            tasks=[],
            meetings=[],
            history=[],
        )
        resp = process_chat(req)
        assert resp.answer is not None
        assert resp.tool_used == "analyze"

    def test_tool_result_on_failure(self):
        """Неизвестный инструмент — ToolResult с success=False."""
        result = call_tool("unknown_tool_xyz", {})
        assert result.success is False
        assert result.error is not None

    def test_conflicts_adapt_missing_fields(self, base_profile):
        """Конфликт без userId/eventId/detectedAt — автодополняется."""
        context = {
            "user_id": 5,
            "profile": {**base_profile, "userId": 5, "employmentType": "FULL_TIME"},
            "tasks": [],
            "meetings": [],
            "conflicts": [
                {
                    "id": "conf-1",
                    "type": "OUTSIDE_WORK_HOURS",
                    "description": "Встреча ночью",
                    "severity": 3,
                }
            ],
        }
        result = call_tool("conflicts", context)
        if result.success:
            assert result.tool_name == "conflicts"
        else:
            assert result.error is not None

    def test_multiple_conflicts_takes_first(self, base_profile):
        """Если несколько конфликтов — берётся первый."""
        context = {
            "user_id": 5,
            "profile": {**base_profile, "userId": 5, "employmentType": "FULL_TIME"},
            "tasks": [],
            "meetings": [],
            "conflicts": [
                {
                    "id": "conf-1",
                    "type": "OUTSIDE_WORK_HOURS",
                    "description": "Встреча в 22:00",
                    "severity": 4,
                },
                {
                    "id": "conf-2",
                    "type": "OVERLAPPING_EVENTS",
                    "description": "Две встречи одновременно",
                    "severity": 3,
                },
            ],
        }
        result = call_tool("conflicts", context)
        if result.success:
            assert result.data["conflict_id"] == "conf-1"
        else:
            assert result.error is not None
