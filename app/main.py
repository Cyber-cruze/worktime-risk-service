from fastapi import FastAPI
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.models import calculate_risk_score, classify_employee
from app.recommendations.engine import generate_recommendations
from app.schemas import ConflictResolveRequest, ResolutionResponse
from app.conflict.resolver import resolve_conflict

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