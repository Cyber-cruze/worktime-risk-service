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


app = FastAPI(
    title="WorkTime Risk Service",
    description="Анализ риска выгорания и актуализации графика",
    version="2.0.0"
)

@app.get("/health")
def health():
    return {"status": "ok", "service": "risk-service"}


# Основной эндпоинт: принимает данные сотрудника, считает риски, классифицирует и дает советы
@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_user(request: AnalyzeRequest):

    # 1. Конвертируем Pydantic модель в dict для расчетов
    payload = request.model_dump()

    # 2. Считаем риск и метрики
    risk_result = calculate_risk_score(payload)

    # 3. Определяем группу (1-9)
    classification = classify_employee(payload, risk_result)

    # 4. Генерируем рекомендации
    recommendations = generate_recommendations(classification, risk_result["metrics"])

    # 5. Собираем ответ
    return AnalyzeResponse(
        user_id=request.user_id,
        risk_score=risk_result["risk_score"],
        metrics=risk_result["metrics"],
        classification=classification,
        recommendations=recommendations
    )

@app.post("/conflicts/resolve", response_model=ResolutionResponse)
def resolve(conflict_request: ConflictResolveRequest):
    return resolve_conflict(conflict_request)


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