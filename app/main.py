from fastapi import FastAPI
from app.schemas import RiskInput, RiskResponse

app = FastAPI(
    title="WorkTime Risk Service",
    description="API для оценки риска выгорания сотрудников",
    version="1.0.0"
)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "risk-service"}

@app.post("/predict", response_model=RiskResponse)
def predict_risk(data: RiskInput):
    """
    Принимает метрики сотрудника, возвращает скор риска и рекомендации.
    """
    # TODO: На этапе 3 сюда подключим model.predict()
    # Пока просто возвращаем фиктивный ответ, чтобы Java увидела, что API работает

    return {
        "user_id": data.user_id,
        "score": 5.0,
        "category": "medium",
        "forecast_3d": [5.1, 5.2, 5.3],
        "recommendations": ["[STUB] Сервис запущен. Логика модели подключается на следующем этапе."],
        "feature_importance": {}
    }