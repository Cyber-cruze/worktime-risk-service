import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
from typing import Dict, List

MODEL_PATH = Path(__file__).parent.parent.parent / "model" / "schedule_scorer.pkl"

class ScheduleScorer:
    def __init__(self):
        self.model = None
        self.load_model()

    def load_model(self):
        try:
            if MODEL_PATH.exists():
                self.model = joblib.load(MODEL_PATH)
            else:
                self.model = self._train_dummy_model()
        except Exception:
            self.model = self._train_dummy_model()

    def _train_dummy_model(self):
        model = GradientBoostingRegressor(random_state=42)
        X = np.array([[40, 5], [60, 10], [20, 2]])
        y = np.array([80, 40, 95])
        model.fit(X, y)
        return model

    def score(self, profile: Dict, tasks: List[Dict]) -> Dict:
        emp_type = profile.get("employmentType", "FULL_TIME")
        hours = 40 if emp_type == "FULL_TIME" else 20

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