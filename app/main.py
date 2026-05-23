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

load_dotenv()

app = FastAPI(
    title="WorkTime Risk Service",
    description="Анализ риска выгорания и актуализации графика",
    version="2.0.0"
)

@app.get("/health")
def health():
    return {"status": "ok", "service": "risk-service"}


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

    # Обогащаем объяснение через LLM, если включено
    if os.getenv("USE_LLM_RECOMMENDATIONS", "false").lower() == "true":
        llm_explanation = generate_recommendations(
            classification={"group_id": 0},
            metrics={},
            profile=conflict_request.profile.model_dump(),
            conflict=conflict_request.conflict.model_dump()
        )
        if llm_explanation:
            result.explanation = llm_explanation[0]

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