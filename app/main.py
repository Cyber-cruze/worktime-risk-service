import os
from fastapi import FastAPI
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
    ConflictResolveRequest, ResolutionResponse,
    ConflictResolveBatchRequest, ConflictResolveBatchResponse,
    ConflictResolutionResult
)


from app.conflict.resolver import resolve_conflict
from typing import List
import traceback

load_dotenv()

app = FastAPI(
    title="WorkTime Risk Service",
    description="Анализ риска выгорания и актуализации графика",
    version="2.0.0"
)

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
                recommendations=[rec.dict() for rec in resolution.recommendations],
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

    payload = request.model_dump()
    risk_result = calculate_risk_score(payload)
    classification = classify_employee(payload, risk_result)

    recommendations = generate_recommendations(
        classification=classification,
        metrics=risk_result["metrics"],
        profile=payload.get("profile"),
        conflict=None
    )

    return AnalyzeResponse(
        user_id=request.user_id,
        risk_score=risk_result["risk_score"],
        metrics=risk_result["metrics"],
        classification=classification,
        recommendations=recommendations
    )

@app.post("/conflicts/resolve", response_model=ResolutionResponse)
def resolve(conflict_request: ConflictResolveRequest):
    result = resolve_conflict(conflict_request)
    return result


@app.post("/ml/predict", response_model=PredictionResponse)
def predict_conflict_api(request: ConflictResolveRequest):
    profile_dict = request.profile.model_dump()
    tasks_list = [t.model_dump() for t in request.tasks]

    prob = predictor.predict(profile_dict, tasks_list)

    return PredictionResponse(
        conflict_probability=prob,
        top_risk_factors=["High meeting density"] if prob > 0.5 else ["Normal load"],
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