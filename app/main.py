import os
import re
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.models import calculate_risk_score, classify_employee
from app.recommendations.engine import generate_recommendations
from app.schemas import ConflictResolveRequest, ResolutionResponse
from app.conflict.resolver import resolve_conflict
from app.schemas.ml_schemas import PredictionResponse, ScoreResponse, AnomalyResponse
from app.ml.predictor import predictor
from app.ml.scorer import scorer
from app.ml.anomaly import detector
from dotenv import load_dotenv

from app.schemas import (
    ConflictResolveBatchRequest, ConflictResolveBatchResponse,
    ConflictResolutionResult
)

from typing import List, Dict, Any
import traceback

load_dotenv()

app = FastAPI(
    title="WorkTime Risk Service",
    description="Анализ риска выгорания и актуализации графика",
    version="2.0.0"
)


def _camel_to_snake(name: str) -> str:
    """Конвертирует camelCase → snake_case."""
    s1 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    return re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s1).lower()


def _to_snake_case(obj: Any) -> Any:
    """Рекурсивно конвертирует все ключи dict из camelCase в snake_case."""
    if isinstance(obj, dict):
        return {_camel_to_snake(k): _to_snake_case(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_snake_case(i) for i in obj]
    return obj


@app.get("/health")
def health():
    return {"status": "ok", "service": "risk-service"}

@app.post("/conflicts/resolve/batch", response_model=ConflictResolveBatchResponse)
async def resolve_conflicts_batch(request: ConflictResolveBatchRequest):
    results: List[ConflictResolutionResult] = []
    success_count = 0
    error_count = 0

    for idx, conflict_req in enumerate(request.conflicts):
        try:
            resolution = resolve_conflict(conflict_req)

            results.append(ConflictResolutionResult(
                conflict_id=resolution.conflict_id,
                conflict_type=resolution.conflict_type,
                status=resolution.status,
                recommendations=[rec.model_dump() for rec in resolution.recommendations],
                explanation=resolution.explanation
            ))
            success_count += 1

        except Exception as e:

            print(f"Ошибка при обработке конфликта #{idx}: {e}")
            traceback.print_exc()

            results.append(ConflictResolutionResult(
                conflict_id=conflict_req.conflict.id,
                conflict_type=conflict_req.conflict.type.value,
                status="ERROR",
                recommendations=[],
                explanation=f"Не удалось разрешить конфликт: {str(e)}"
            ))
            error_count += 1

    return ConflictResolveBatchResponse(
        results=results,
        total_processed=len(request.conflicts),
        success_count=success_count,
        error_count=error_count
    )


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_user(request: AnalyzeRequest):
    try:
        # Конвертируем camelCase payload → snake_case для внутренней логики
        payload = _to_snake_case(request.model_dump())
        risk_result = calculate_risk_score(payload)
        classification = classify_employee(payload, risk_result)

        recommendations = generate_recommendations(
            classification=classification,
            metrics=risk_result["metrics"],
            profile=payload.get("profile"),
            hr_data=payload.get("hr_data"),
            meetings=payload.get("meetings"),
            conflict=None
        )

        return AnalyzeResponse(
            userId=request.userId,
            riskScore=risk_result["risk_score"],
            metrics=risk_result["metrics"],
            classification=classification,
            recommendations=recommendations
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal error: {type(e).__name__}: {str(e)}"}
        )

@app.post("/conflicts/resolve", response_model=ResolutionResponse)
def resolve(conflict_request: ConflictResolveRequest):
    try:
        result = resolve_conflict(conflict_request)
        return result
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal error: {type(e).__name__}: {str(e)}"}
        )


@app.post("/ml/predict", response_model=PredictionResponse)
def predict_conflict_api(request: ConflictResolveRequest):
    profile_dict = request.profile.model_dump()
    tasks_list = [t.model_dump() for t in request.tasks]
    conflict_dict = request.conflict.model_dump(mode='json')

    prob = predictor.predict(profile_dict, tasks_list, conflict_dict)
    factors = predictor.get_risk_factors(prob, conflict_dict)

    return PredictionResponse(
        conflict_probability=prob,
        top_risk_factors=factors,
        forecast_days=7
    )


@app.post("/ml/score", response_model=ScoreResponse)
def score_schedule_api(request: ConflictResolveRequest):
    profile_dict = request.profile.model_dump()
    tasks_list = [t.model_dump() for t in request.tasks]

    result = scorer.score(profile_dict, tasks_list)

    return ScoreResponse(
        user_id=request.profile.userId,
        quality_score=result["quality_score"],
        grade=result["grade"],
        breakdown=result["breakdown"]
    )


@app.post("/ml/anomalies", response_model=AnomalyResponse)
def detect_anomalies_api(request: ConflictResolveRequest):
    tasks_list = [t.model_dump() for t in request.tasks]

    result = detector.detect(tasks_list)

    return AnomalyResponse(
        is_anomalous=result["is_anomalous"],
        anomaly_score=result["anomaly_score"],
        detected_patterns=result["detected_patterns"],
        action_required=result["action_required"]
    )
