from typing import List
from datetime import datetime, timedelta
from app.schemas import (
    ConflictResolveRequest, ResolutionResponse, Recommendation,
    ConflictType
)
from app.llm.client import generate_conflict_explanation
import os


def resolve_conflict(request: ConflictResolveRequest) -> ResolutionResponse:
    conflict = request.conflict
    profile = request.profile
    tasks = request.tasks

    recommendations: List[Recommendation] = []
    status = "OPTIONS_PROVIDED"
    explanation = ""

    work_start_h = int(profile.workStart.split(":")[0])
    work_end_h = int(profile.workEnd.split(":")[0])
    ref_time = conflict.conflictDate or datetime.now()

    if conflict.type == ConflictType.OUTSIDE_WORK_HOURS:
        ref_h = ref_time.hour
        if ref_h < work_start_h:
            new_time = ref_time.replace(hour=work_start_h, minute=0)
            reason = f"Перенос на начало рабочего дня ({profile.workStart})"
        elif ref_h >= work_end_h:
            new_time = (ref_time + timedelta(days=1)).replace(hour=work_start_h, minute=0)
            reason = "Перенос на утро следующего рабочего дня"
        else:
            new_time = ref_time
            reason = "Время в пределах графика"

        recommendations.append(Recommendation(
            action="RESCHEDULE",
            suggested_start=new_time,
            suggested_duration_min=60,
            reason=reason,
            confidence=0.85,
            affected_user_ids=[conflict.userId]
        ))
        status = "AUTO_RESOLVED"
        explanation = f"Событие вне графика. Предложен перенос на {new_time.strftime('%H:%M')}."

    elif conflict.type == ConflictType.OVERLAPPING_EVENTS:
        new_time = ref_time + timedelta(hours=1)
        recommendations.append(Recommendation(
            action="RESCHEDULE",
            suggested_start=new_time,
            suggested_duration_min=30,
            reason="Найдено свободное окно через 1 час после текущего",
            confidence=0.7,
            affected_user_ids=[conflict.userId] + [t.initiatorId for t in tasks if t.id == conflict.eventId]
        ))
        recommendations.append(Recommendation(
            action="SPLIT",
            reason="Разделить встречу на две части по 30 мин в разные дни",
            confidence=0.6,
            affected_user_ids=[conflict.userId]
        ))

    elif conflict.type == ConflictType.OVERLOAD:
        recommendations.append(Recommendation(
            action="DELEGATE",
            reason="Передать задачу коллеге со схожей специализацией или меньшей загрузкой",
            confidence=0.75,
            affected_user_ids=[conflict.userId]
        ))
        recommendations.append(Recommendation(
            action="RESCHEDULE",
            reason="Отложить задачу на следующий спринт или неделю",
            confidence=0.6,
            affected_user_ids=[conflict.userId]
        ))
        status = "MANUAL_REVIEW"
        explanation = "Высокая перегрузка. Требуется ручное решение или делегирование."

    elif conflict.type == ConflictType.WORKDAY_EXCEPTION_CONFLICT:
        recommendations.append(Recommendation(
            action="KEEP",
            reason="Проверить статус исключения в HR-системе. Если подтверждено — оставить.",
            confidence=0.5,
            affected_user_ids=[conflict.userId]
        ))
        recommendations.append(Recommendation(
            action="CANCEL",
            reason="Отменить событие, если исключение не подтверждено HR",
            confidence=0.4,
            affected_user_ids=[conflict.userId]
        ))
        status = "MANUAL_REVIEW"
        explanation = "Конфликт с рабочими исключениями. Необходима сверка с HR."

    else:
        explanation = "Неизвестный тип конфликта. Требуется анализ вручную."
        status = "MANUAL_REVIEW"

    use_llm = os.getenv("USE_LLM_RECOMMENDATIONS", "false").lower() == "true"
    if use_llm and recommendations:
        best_rec = recommendations[0]
        time_str = best_rec.suggested_start.strftime(
            "%H:%M") if best_rec.suggested_start else "ближайшее свободное окно"


        llm_text = generate_conflict_explanation(
            conflict=conflict.model_dump(mode='json'),
            profile=profile.model_dump(mode='json'),
            action=best_rec.action,
            new_time=time_str
        )
        if llm_text:
            explanation = llm_text

    return ResolutionResponse(
        conflict_id=conflict.id,
        conflict_type=conflict.type.value,
        status=status,
        recommendations=recommendations,
        explanation=explanation
    )