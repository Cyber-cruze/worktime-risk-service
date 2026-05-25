from typing import List
from datetime import datetime, timedelta
from app.schemas import (
    ConflictResolveRequest, ResolutionResponse, Recommendation, ConflictType
)
import os


def _calc_task_hours(tasks) -> float:
    """Считает суммарные часы задач/встреч."""
    total = 0.0
    for t in tasks:
        try:
            start = t.startTime if hasattr(t, 'startTime') else t.get('startTime', '')
            end = t.endTime if hasattr(t, 'endTime') else t.get('endTime', '')
            if start and end:
                if hasattr(start, 'isoformat'):
                    # Уже datetime
                    total += (end - start).total_seconds() / 3600
                else:
                    from datetime import datetime as _dt
                    total += (_dt.fromisoformat(str(end)) - _dt.fromisoformat(str(start))).total_seconds() / 3600
        except Exception:
            pass
    return total


def _is_vacation_context(conflict, profile) -> bool:
    """Определяет, связан ли конфликт с отпуском."""
    desc = (conflict.description or "").lower()
    return "отпуск" in desc or "vacation" in desc or conflict.type == ConflictType.WORKDAY_EXCEPTION_CONFLICT


def resolve_conflict(request: ConflictResolveRequest) -> ResolutionResponse:
    conflict = request.conflict
    profile = request.profile
    tasks = request.tasks

    recommendations: List[Recommendation] = []
    status = "OPTIONS_PROVIDED"
    explanation = ""

    work_start_h = int(profile.workStart.split(":")[0])
    work_end_h = int(profile.workEnd.split(":")[0])
    work_start_str = profile.workStart[:5]
    work_end_str = profile.workEnd[:5]
    ref_time = conflict.conflictDate or datetime.now()

    # Контекст для LLM
    context_hints = []
    is_part_time = str(profile.employmentType).upper() == "PART_TIME"
    total_task_hours = _calc_task_hours(tasks)
    vacation_conflict = _is_vacation_context(conflict, profile)

    if is_part_time:
        context_hints.append(f"Сотрудник на PART_TIME (рабочие часы {work_start_str}–{work_end_str}). Перенос должен быть в рамках этого графика.")
    if vacation_conflict:
        context_hints.append("Конфликт связан с отпуском/исключением. При высокой критичности — рекомендовать отмену или перенос на после отпуска.")
    if total_task_hours > 0:
        context_hints.append(f"Суммарная нагрузка от задач: {total_task_hours:.1f}ч.")

    # === OUTSIDE_WORK_HOURS ===
    if conflict.type == ConflictType.OUTSIDE_WORK_HOURS:
        ref_h = ref_time.hour
        if ref_h < work_start_h:
            new_time = ref_time.replace(hour=work_start_h, minute=0)
            reason = f"Перенос на начало рабочего дня ({work_start_str})"
        elif ref_h >= work_end_h:
            new_time = (ref_time + timedelta(days=1)).replace(hour=work_start_h, minute=0)
            reason = f"Перенос на утро следующего рабочего дня ({work_start_str})"
        else:
            new_time = ref_time
            reason = "Время в пределах графика, конфликт не актуален"

        recommendations.append(Recommendation(
            action="RESCHEDULE", suggested_start=new_time, suggested_duration_min=60,
            reason=reason, confidence=0.9, affected_user_ids=[conflict.userId]
        ))
        status = "AUTO_RESOLVED"

    # === OVERLAPPING_EVENTS ===
    elif conflict.type == ConflictType.OVERLAPPING_EVENTS:
        # Для PART_TIME переносим на конец рабочего дня, а не +1ч слепо
        if is_part_time:
            new_time = ref_time.replace(hour=work_end_h - 1, minute=0)
            if new_time <= ref_time:
                new_time = (ref_time + timedelta(days=1)).replace(hour=work_start_h, minute=0)
        else:
            new_time = ref_time + timedelta(hours=1)

        recommendations.append(Recommendation(
            action="RESCHEDULE", suggested_start=new_time, suggested_duration_min=30,
            reason="Найдено свободное окно после текущего события", confidence=0.75,
            affected_user_ids=[conflict.userId] + [t.initiatorId for t in tasks if t.id == conflict.eventId]
        ))
        recommendations.append(Recommendation(
            action="SPLIT", reason="Разделить встречу на две части по 30 мин в разные дни",
            confidence=0.6, affected_user_ids=[conflict.userId]
        ))
        status = "OPTIONS_PROVIDED"

    # === OVERLOAD ===
    elif conflict.type == ConflictType.OVERLOAD:
        if is_part_time and total_task_hours > 4:
            recommendations.append(Recommendation(
                action="DELEGATE",
                reason=f"Нагрузка {total_task_hours:.1f}ч превышает лимит PART_TIME (4ч). Необходимо делегировать",
                confidence=0.85, affected_user_ids=[conflict.userId]
            ))
        else:
            recommendations.append(Recommendation(
                action="DELEGATE",
                reason="Передать задачу коллеге со схожей специализацией или меньшей загрузкой",
                confidence=0.75, affected_user_ids=[conflict.userId]
            ))

        # Перенос на начало следующего рабочего дня
        next_work = (ref_time + timedelta(days=1)).replace(
            hour=work_start_h, minute=0
        )
        recommendations.append(Recommendation(
            action="RESCHEDULE", suggested_start=next_work, suggested_duration_min=60,
            reason="Перенос задачи на следующий рабочий день для снижения перегрузки",
            confidence=0.6, affected_user_ids=[conflict.userId]
        ))
        status = "MANUAL_REVIEW"

    # === WORKDAY_EXCEPTION_CONFLICT ===
    elif conflict.type == ConflictType.WORKDAY_EXCEPTION_CONFLICT:
        severity = conflict.severity

        # Ключевая логика: высокая критичность + отпуск → CANCEL первый
        if severity >= 4 and vacation_conflict:
            # Сначала CANCEL — критический конфликт при отпуске
            recommendations.append(Recommendation(
                action="CANCEL",
                reason="Критический конфликт с отпуском/исключением — событие необходимо отменить",
                confidence=0.9, affected_user_ids=[conflict.userId]
            ))
            # Альтернатива: перенос на после отпуска
            next_work = (ref_time + timedelta(days=7)).replace(
                hour=work_start_h, minute=0
            )
            recommendations.append(Recommendation(
                action="RESCHEDULE", suggested_start=next_work, suggested_duration_min=60,
                reason="Альтернатива: перенос на после отпуска",
                confidence=0.7, affected_user_ids=[conflict.userId]
            ))
            status = "AUTO_RESOLVED"
        elif severity >= 3:
            # Средняя критичность — сначала проверка, потом отмена
            recommendations.append(Recommendation(
                action="KEEP",
                reason="Проверить статус исключения в HR-системе. Если подтверждено — оставить.",
                confidence=0.6, affected_user_ids=[conflict.userId]
            ))
            recommendations.append(Recommendation(
                action="CANCEL",
                reason="Отменить событие, если исключение не подтверждено HR",
                confidence=0.7, affected_user_ids=[conflict.userId]
            ))
            status = "MANUAL_REVIEW"
        else:
            # Низкая критичность
            recommendations.append(Recommendation(
                action="KEEP",
                reason="Низкая критичность — событие можно оставить под контролем",
                confidence=0.5, affected_user_ids=[conflict.userId]
            ))
            status = "OPTIONS_PROVIDED"

    else:
        explanation = "Неизвестный тип конфликта. Требуется анализ вручную."
        status = "MANUAL_REVIEW"

    # === LLM-блок ===
    use_llm = os.getenv("USE_LLM_RECOMMENDATIONS", "false").lower() == "true"
    if use_llm and recommendations:
        try:
            from app.llm.client import generate_conflict_explanation

            best_rec = recommendations[0]
            time_str = best_rec.suggested_start.strftime(
                "%H:%M") if best_rec.suggested_start else "ближайшее свободное окно"

            # Формируем сводку всех рекомендаций для LLM
            all_actions = "; ".join(
                f"{r.action} ({r.reason}, уверенность {r.confidence:.0%})"
                for r in recommendations
            )

            # Контекстные подсказки
            context_text = " | ".join(context_hints) if context_hints else "нет"

            llm_text = generate_conflict_explanation(
                conflict=conflict.model_dump(mode='json'),
                profile=profile.model_dump(mode='json'),
                action=best_rec.action,
                new_time=time_str,
                all_actions=all_actions,
                context_hints=context_text
            )

            if isinstance(llm_text, str) and llm_text.strip():
                explanation = llm_text
        except Exception as e:
            print(f"[resolver] LLM-пояснение недоступно: {e}. Используем fallback.")

    # Fallback explanation если LLM не использовался
    if not explanation:
        explanation = _fallback_explanation(conflict, recommendations, profile)

    return ResolutionResponse(
        conflict_id=conflict.id,
        conflict_type=conflict.type.value,
        status=status,
        recommendations=recommendations,
        explanation=explanation
    )


def _fallback_explanation(conflict, recommendations, profile) -> str:
    """Детерминированный fallback для explanation."""
    name = f"{profile.name} {profile.surname}".strip()
    best = recommendations[0] if recommendations else None
    if not best:
        return f"{name}, обнаружен конфликт. Требуется ручной анализ."

    work_start = profile.workStart[:5]
    work_end = profile.workEnd[:5]

    if conflict.type == ConflictType.OUTSIDE_WORK_HOURS:
        t = best.suggested_start.strftime("%H:%M") if best.suggested_start else "рабочее время"
        return f"{name}, событие вне рабочих часов ({work_start}–{work_end}). Перенесено на {t}."
    elif conflict.type == ConflictType.OVERLAPPING_EVENTS:
        return f"{name}, обнаружено наложение событий. {best.reason.lower()}."
    elif conflict.type == ConflictType.OVERLOAD:
        return f"{name}, высокая перегрузка. {best.reason.lower()}."
    elif conflict.type == ConflictType.WORKDAY_EXCEPTION_CONFLICT:
        if conflict.severity >= 4:
            return f"{name}, критический конфликт с отпуском/исключением (критичность {conflict.severity}/5). Рекомендуется отмена события."
        return f"{name}, конфликт с рабочим исключением. {best.reason.lower()}."
    return f"{name}, обнаружен конфликт типа {conflict.type.value}. {best.reason.lower()}."