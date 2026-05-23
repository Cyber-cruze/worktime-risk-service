import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import IsolationForest
from typing import List, Dict

MODEL_PATH = Path(__file__).parent.parent.parent / "model" / "anomaly_detector.pkl"


class AnomalyDetector:
    def __init__(self):
        self.model = None
        self.load_model()

    def load_model(self):
        try:
            if MODEL_PATH.exists():
                self.model = joblib.load(MODEL_PATH)
            else:
                self.model = IsolationForest(contamination=0.1, random_state=42)
        except Exception:
            self.model = IsolationForest(contamination=0.1, random_state=42)

    def detect(self, activity_history: List[Dict]) -> Dict:
        if not activity_history:
            return {"is_anomalous": False, "anomaly_score": 0.0, "detected_patterns": [],
                    "action_required": "No action"}

        # Фичи: просто кол-во событий для демо
        X = np.array([[len(activity_history)]])

        # Если модель не обучена — обучаем на лету на фейковых данных
        try:
            # Проверяем, обучена ли модель
            _ = self.model.estimators_
        except AttributeError:
            # Обучаем на синтетике
            X_train = np.random.rand(100, 1) * 10
            X_train[-5:] = np.random.rand(5, 1) * 50  # аномалии
            self.model.fit(X_train)

        preds = self.model.predict(X)
        scores = self.model.score_samples(X)

        is_anomalous = bool(preds[0] == -1)
        score = float(abs(scores[0]))

        patterns = []
        if is_anomalous:
            patterns.append("High activity density")
            patterns.append("Unusual time patterns")

        return {
            "is_anomalous": is_anomalous,
            "anomaly_score": round(min(score, 1.0), 3),
            "detected_patterns": patterns,
            "action_required": "Review schedule manually" if is_anomalous else "No action"
        }


# Глобальный инстанс
detector = AnomalyDetector()