import numpy as np
import joblib
from pathlib import Path
from sklearn.neural_network import MLPClassifier
from typing import Dict, List

# Путь к модели
MODEL_PATH = Path(__file__).parent.parent.parent / "model" / "conflict_predictor.pkl"


class ConflictPredictor:
    def __init__(self):
        self.model = None
        self.load_model()

    def load_model(self):
        try:
            if MODEL_PATH.exists():
                self.model = joblib.load(MODEL_PATH)
            else:
                # Если модели нет, используем заглушку, чтобы демо не упало
                self.model = self._train_dummy_model()
        except Exception:
            self.model = self._train_dummy_model()

    def _train_dummy_model(self):
        # Обучает простую сеть на лету, если файла нет
        model = MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=50, random_state=42)
        # Фейковые данные: [workload, meeting_count, overtime] -> [Conflict, NoConflict]
        X = np.array([[0.8, 5, 10], [0.2, 1, 0], [0.9, 8, 15], [0.3, 2, 2]])
        y = np.array([1, 0, 1, 0])
        model.fit(X, y)
        return model

    def extract_features(self, profile: Dict, tasks: List[Dict]) -> np.ndarray:
        # 1. Workload (количество задач)
        task_count = len(tasks)
        # 2. Meetings density (сколько встреч)
        meetings = [t for t in tasks if t.get("type") == "MEETING"]
        meeting_count = len(meetings)
        # 3. Overtime risk (простая эвристика)
        overtime_risk = 0.5  # Заглушка, можно усложнить

        return np.array([[task_count, meeting_count, overtime_risk]])

    def predict(self, profile: Dict, tasks: List[Dict]) -> float:
        X = self.extract_features(profile, tasks)
        # predict_proba возвращает [[prob_0, prob_1]]
        probs = self.model.predict_proba(X)
        return float(probs[0][1])  # Вероятность конфликта (класс 1)


# Глобальный инстанс
predictor = ConflictPredictor()