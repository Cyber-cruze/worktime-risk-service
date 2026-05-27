from typing import Dict, Any, Optional, List
from app.chat.schemas import ToolResult


# 1. ANALYZE — полный анализ риска выгорания
def tool_analyze(context: Dict[str, Any]) -> ToolResult:

    try:
        from app.models import calculate_risk_score, classify_employee
        from app.recommendations.engine import generate_recommendations

        payload = _build_analyze_payload(context)
        risk_result = calculate_risk_score(payload)
        classification = classify_employee(payload, risk_result)

        recommendations = generate_recommendations(
            classification=classification,
            metrics=risk_result["metrics"],
            profile=payload.get("profile"),
            hr_data=payload.get("hr_data"),
            meetings=payload.get("meetings"),
            conflict=None,
        )

        return ToolResult(
            tool_name="analyze",
            success=True,
            data={
                "risk_score": risk_result["risk_score"],
                "metrics": risk_result["metrics"],
                "classification": classification,
                "recommendations": recommendations,
            },
        )
    except Exception as e:
        return ToolResult(tool_name="analyze", success=False, error=str(e))


# 2. PREDICT — ML-прогноз вероятности конфликта
def tool_predict(context: Dict[str, Any]) -> ToolResult:
    try:
        from app.ml.predictor import predictor

        profile_dict = context.get("profile", {})
        tasks_list = context.get("tasks", [])
        prob = predictor.predict(profile_dict, tasks_list)

        return ToolResult(
            tool_name="predict",
            success=True,
            data={
                "conflict_probability": prob,
                "forecast_days": 7,
            },
        )
    except Exception as e:
        return ToolResult(tool_name="predict", success=False, error=str(e))


# 3. SCORE — оценка качества расписания
def tool_score(context: Dict[str, Any]) -> ToolResult:
    try:
        from app.ml.scorer import scorer

        profile_dict = context.get("profile", {})
        tasks_list = context.get("tasks", [])
        result = scorer.score(profile_dict, tasks_list)

        return ToolResult(
            tool_name="score",
            success=True,
            data={
                "quality_score": result["quality_score"],
                "grade": result["grade"],
                "breakdown": result["breakdown"],
            },
        )
    except Exception as e:
        return ToolResult(tool_name="score", success=False, error=str(e))


# 4. ANOMALIES — обнаружение аномалий в графике
def tool_anomalies(context: Dict[str, Any]) -> ToolResult:
    try:
        from app.ml.anomaly import detector

        tasks_list = context.get("tasks", [])
        result = detector.detect(tasks_list)

        return ToolResult(
            tool_name="anomalies",
            success=True,
            data={
                "is_anomalous": result["is_anomalous"],
                "anomaly_score": result["anomaly_score"],
                "detected_patterns": result["detected_patterns"],
                "action_required": result["action_required"],
            },
        )
    except Exception as e:
        return ToolResult(tool_name="anomalies", success=False, error=str(e))


# 5. CONFLICTS — разрешение конфликта
def tool_resolve_conflict(context: Dict[str, Any]) -> ToolResult:

    try:
        from app.conflict.resolver import resolve_conflict
        from app.schemas import (
            ConflictResolveRequest, ProfileSchema,
            TaskSchema, ConflictSchema,
        )
        from datetime import datetime as _dt

        conflicts = context.get("conflicts", [])
        if not conflicts:
            return ToolResult(
                tool_name="conflicts",
                success=False,
                error="Нет конфликтов для разрешения",
            )

        # Берём первый неразрешённый конфликт
        conflict_data = conflicts[0]
        profile_data = context.get("profile", {})
        tasks_data = context.get("tasks", [])

        # Адаптация: дополняем недостающие обязательные поля ConflictSchema
        if "userId" not in conflict_data:
            conflict_data["userId"] = profile_data.get("userId", 0)
        if "eventId" not in conflict_data:
            conflict_data["eventId"] = conflict_data.get("id", "unknown")
        if "detectedAt" not in conflict_data:
            conflict_data["detectedAt"] = conflict_data.get("conflictDate", _dt.utcnow().isoformat())
        if "resolved" not in conflict_data:
            conflict_data["resolved"] = False

        # Адаптация: ProfileSchema — добавляем недостающие поля
        if "employmentType" not in profile_data:
            profile_data["employmentType"] = profile_data.get("employment", "FULL_TIME")
        if "timezone" not in profile_data:
            profile_data["timezone"] = "UTC"
        if "updatedAt" not in profile_data:
            profile_data["updatedAt"] = profile_data.get("last_updated", _dt.utcnow().isoformat())
        if "userId" not in profile_data:
            profile_data["userId"] = 0

        # Собираем Pydantic-объекты
        conflict_obj = ConflictSchema(**conflict_data)
        profile_obj = ProfileSchema(**profile_data)

        # Адаптация: TaskSchema — пропускаем задачи без обязательных полей
        tasks_objs = []
        for t in tasks_data:
            try:
                if "initiatorId" not in t:
                    t["initiatorId"] = profile_data.get("userId", 0)
                if "userIds" not in t:
                    t["userIds"] = [profile_data.get("userId", 0)]
                if "type" not in t:
                    t["type"] = "TASK"
                if "timezone" not in t:
                    t["timezone"] = profile_data.get("timezone", "UTC")
                if "createdAt" not in t:
                    t["createdAt"] = _dt.utcnow().isoformat()
                if "updatedAt" not in t:
                    t["updatedAt"] = _dt.utcnow().isoformat()
                if "description" not in t:
                    t["description"] = t.get("title", "")
                tasks_objs.append(TaskSchema(**t))
            except Exception:
                continue

        req = ConflictResolveRequest(
            conflict=conflict_obj,
            profile=profile_obj,
            tasks=tasks_objs,
        )
        result = resolve_conflict(req)

        # Сериализуем рекомендации с преобразованием datetime в строку
        def _serialize(obj):
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_serialize(i) for i in obj]
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            return obj

        return ToolResult(
            tool_name="conflicts",
            success=True,
            data={
                "conflict_id": result.conflict_id,
                "conflict_type": result.conflict_type,
                "status": result.status,
                "recommendations": [_serialize(r.model_dump()) for r in result.recommendations],
                "explanation": result.explanation,
            },
        )
    except Exception as e:
        return ToolResult(tool_name="conflicts", success=False, error=str(e))


# Хелперы
def _build_analyze_payload(context: Dict[str, Any]) -> Dict[str, Any]:

    profile = context.get("profile", {})
    tasks = context.get("tasks", [])
    meetings = context.get("meetings", [])
    conflicts = context.get("conflicts", [])
    hr_data = context.get("hr_data", {})

    # Адаптация: ProfileSchema -> AnalyzeRequest.Profile формат
    if "workStart" in profile and "work_hours" not in profile:
        # Это формат из conflict_schemas — преобразуем в формат risk_calculator
        last_updated = (
                profile.get("updatedAt")
                or profile.get("last_updated")
                or ""
        )
        profile = {
            "work_hours": {
                "start": profile.get("workStart", "09:00:00")[:5],
                "end": profile.get("workEnd", "18:00:00")[:5],
            },
            "timezone": profile.get("timezone", "UTC"),
             "last_updated": last_updated,
            "employment": profile.get("employmentType", profile.get("employment", "FULL_TIME")),
        }

    # Адаптация: TaskSchema (startTime/endTime) -> Task (hours)
    adapted_tasks = []
    for t in tasks:
        if "hours" not in t:
            from datetime import datetime as _dt
            try:
                st = _dt.fromisoformat(str(t.get("startTime", t.get("start", ""))))
                en = _dt.fromisoformat(str(t.get("endTime", t.get("end", ""))))
                hours = round((en - st).total_seconds() / 3600, 2)
            except Exception:
                hours = 1.0
            adapted_tasks.append({"hours": hours})
        else:
            adapted_tasks.append({"hours": t["hours"]})

    # Адаптация: Meeting
    adapted_meetings = []
    for m in meetings:
        if "start" not in m and "startTime" in m:
            adapted_meetings.append({
                "start": str(m["startTime"]),
                "end": str(m.get("endTime", m["startTime"])),
            })
        else:
            adapted_meetings.append(m)

    return {
        "user_id": str(context.get("user_id", "unknown")),
        "profile": profile,
        "tasks": adapted_tasks,
        "meetings": adapted_meetings,
        "hr_data": hr_data or {"official_schedule": "09:00-18:00", "on_vacation": False},
        "conflicts": conflicts,
    }


# Реестр инструментов
TOOL_REGISTRY = {
    "analyze": tool_analyze,
    "predict": tool_predict,
    "score": tool_score,
    "anomalies": tool_anomalies,
    "conflicts": tool_resolve_conflict,
}