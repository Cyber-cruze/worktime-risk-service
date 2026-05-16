from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.schemas import RiskInput, RiskResponse
from app.predictor import predictor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Загружает модель при старте приложения и освобождает ресурсы при остановке."""
    print("Loading ML model...")
    predictor.load_model()
    print("Model loaded. Risk Service is ready.")
    yield


app = FastAPI(
    title="WorkTime Risk Service",
    description="API для оценки риска выгорания сотрудников",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "risk-service", "model_loaded": predictor.model is not None}


@app.post("/predict", response_model=RiskResponse)
def predict_risk(data: RiskInput):
    """Принимает метрики сотрудника, возвращает скор риска и рекомендации."""
    features = data.model_dump(exclude={'user_id'})

    # Получаем предсказание от ML-модуля
    result = predictor.predict(features)

    # Возвращаем полный ответ
    return {
        "user_id": data.user_id,
        **result
    }