import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict

MODEL_PATH = Path(__file__).parent.parent / "model" / "risk_model.pkl"

FEATURES = [
    "weekly_work_hours", "overtime_hours", "meeting_density",
    "consecutive_work_days", "conflict_count", "workload_trend", "night_weekend_hours"
]

class RiskPredictor:
    def __init__(self):
        self.model = None

    def load_model(self):
        # Загружает модель в память. Вызывается 1 раз при старте сервиса
        if self.model is None:
            self.model = joblib.load(MODEL_PATH)

    def _generate_recommendations(self, features: Dict) -> List[str]:
        recs = []
        if features.get("overtime_hours", 0) > 6:
            recs.append("Высокий овертайм: делегируйте вечерние задачи, добавьте буфер 1ч/день")
        if features.get("meeting_density", 0) > 0.65:
            recs.append("Meetings >65%: внедрите 'день без встреч', сократите длительность до 30 мин")
        if features.get("consecutive_work_days", 0) >= 6:
            recs.append("6+ дней подряд: запланируйте выходной, перераспределите нагрузку")
        if features.get("conflict_count", 0) >= 3:
            recs.append("Частые коллизии: синхронизируйте календари, заблокируйте фокус-время")
        if features.get("workload_trend", 0) > 0.25:
            recs.append("Нагрузка растёт: снизьте входящие задачи на 15-20% на след. спринт")
        return recs if recs else ["Риск низкий. График сбалансирован."]

    def predict(self, features: Dict) -> Dict:
        if self.model is None:
            self.load_model()

        X = pd.DataFrame([features])[FEATURES]
        score = float(np.clip(self.model.predict(X)[0], 0, 10))

        trend = features.get("workload_trend", 0)
        forecast = [round(np.clip(score + trend * (i + 1), 0, 10), 1) for i in range(3)]

        category = "low" if score < 4 else "medium" if score < 7 else "high"
        recommendations = self._generate_recommendations(features)

        return {
            "score": round(score, 1),
            "category": category,
            "forecast_3d": forecast,
            "recommendations": recommendations,
            "feature_importance": dict(zip(FEATURES, self.model.feature_importances_.round(3)))
        }


predictor = RiskPredictor()