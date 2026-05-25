import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
from typing import Dict, List

MODEL_PATH = Path(__file__).parent.parent.parent / "model" / "schedule_scorer.pkl"

N_FEATURES = 2

class ScheduleScorer:
    def __init__(self):
        self.model = None
        self.load_model()

    def load_model(self):
        try:
            if MODEL_PATH.exists():
                loaded = joblib.load(MODEL_PATH)
                expected = getattr(loaded, 'n_features_in_', None)
                if expected is not None and expected != N_FEATURES:
                    print(f"[scorer] pkl-модель ждёт {expected} фичей, нужно {N_FEATURES}. Используем dummy.")
                    self.model = self._train_dummy_model()
                else:
                    self.model = loaded
            else:
                self.model = self._train_dummy_model()
        except Exception as e:
            print(f"[scorer] Ошибка загрузки модели: {e}. Используем dummy.")
            self.model = self._train_dummy_model()

    def _train_dummy_model(self):
        model = GradientBoostingRegressor(random_state=42, n_estimators=50)
        X = np.array([
            [40, 2], [40, 5], [40, 8], [40, 12],
            [20, 1], [20, 3], [20, 5], [20, 8],
        ])
        y = np.array([90, 75, 55, 35, 95, 70, 45, 25])
        model.fit(X, y)
        return model

    def score(self, profile: Dict, tasks: List[Dict]) -> Dict:
        emp_type = str(profile.get("employmentType", profile.get("employment", "FULL_TIME"))).upper().replace("-", "_")
        hours = 20 if emp_type == "PART_TIME" else 40

        task_count = len(tasks)
        X = np.array([[hours, task_count]])

        raw_score = self.model.predict(X)[0]
        score = float(np.clip(raw_score, 0, 100))

        grade = "A" if score > 85 else "B" if score > 60 else "C" if score > 40 else "D"

        return {
            "quality_score": round(score, 1),
            "grade": grade,
            "breakdown": {
                "workload_balance": round(score * 0.6, 1),
                "focus_time_protection": round(score * 0.3, 1),
                "schedule_stability": round(score * 0.4, 1)
            }
        }


scorer = ScheduleScorer()