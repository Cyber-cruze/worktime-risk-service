import numpy as np
import joblib
from pathlib import Path
from sklearn.neural_network import MLPClassifier
from typing import Dict, List, Optional
from datetime import datetime, timezone
import zoneinfo

MODEL_PATH = Path(__file__).parent.parent.parent / "model" / "conflict_predictor.pkl"

N_FEATURES = 4


class ConflictPredictor:
    def __init__(self):
        self.model = None
        self._use_dummy = False
        self.load_model()

    def load_model(self):
        self.model = self._train_dummy_model()
        self._use_dummy = True

        if not MODEL_PATH.exists():
            print("[predictor] pkl не найден. Используем dummy.")
            return

        try:
            loaded = joblib.load(MODEL_PATH)
            expected = getattr(loaded, 'n_features_in_', None)
            if expected is not None and expected != N_FEATURES:

                return
            test_X = np.zeros((1, N_FEATURES))
            if expected is None:
                try:
                    loaded.predict_proba(test_X)
                except ValueError:
                    print("[predictor] pkl-модель несовместима по фичам. Используем dummy.")
                    return
            self.model = loaded
            self._use_dummy = False

        except Exception as e:
            print(f"[predictor] Ошибка загрузки pkl: {e}. Используем dummy.")

    def _train_dummy_model(self):
        model = MLPClassifier(hidden_layer_sizes=(16, 8), max_iter=500, random_state=42)
        X = np.array([
            [0.1, 0.0, 0.0, 0.0],
            [0.3, 0.1, 0.0, 0.1],
            [0.5, 0.3, 0.2, 0.3],
            [0.7, 0.4, 0.3, 0.5],
            [0.9, 0.6, 0.5, 0.7],
            [1.0, 0.8, 0.7, 0.9],
            [0.15, 0.0, 0.0, 0.0],
            [0.6, 0.2, 0.1, 0.4],
        ])
        y = np.array([0, 0, 0, 1, 1, 1, 0, 1])
        model.fit(X, y)
        return model

    def _calc_hours(self, start_str: str, end_str: str) -> float:
        try:
            start = datetime.fromisoformat(str(start_str))
            end = datetime.fromisoformat(str(end_str))
            return max((end - start).total_seconds() / 3600, 0)
        except Exception:
            return 0

    def _to_local_hour(self, dt_str: str, tz_name: str) -> int:
        try:
            dt = datetime.fromisoformat(str(dt_str))
            if dt.tzinfo is None:
                return dt.hour
            tz = zoneinfo.ZoneInfo(tz_name)
            return dt.astimezone(tz).hour
        except Exception:
            return 12

    def extract_features(
            self,
            profile: Dict,
            tasks: List[Dict],
            conflict: Optional[Dict] = None
    ) -> np.ndarray:
        employment = str(profile.get("employmentType", profile.get("employment", "FULL_TIME"))).upper().replace("-", "_")
        weekly_cap = 20.0 if employment == "PART_TIME" else 40.0

        work_start_h = int(profile.get("workStart", "09:00:00").split(":")[0])
        work_end_h = int(profile.get("workEnd", "18:00:00").split(":")[0])
        profile_tz = profile.get("timezone", "UTC")

        total_hours = 0.0
        meeting_hours = 0.0
        meeting_count = 0
        outside_count = 0

        for t in tasks:
            start = t.get("startTime", t.get("start_time", ""))
            end = t.get("endTime", t.get("end_time", ""))
            hours = self._calc_hours(start, end)
            total_hours += hours

            is_meeting = t.get("type", "").upper() == "MEETING"
            if is_meeting:
                meeting_hours += hours
                meeting_count += 1
                if start:
                    local_h = self._to_local_hour(start, profile_tz)
                    if local_h < work_start_h or local_h >= work_end_h:
                        outside_count += 1

        # Учитываем конфликт — он тоже встреча/событие
        if conflict:
            conflict_type = str(conflict.get("type", "")).upper()
            conflict_date = conflict.get("conflictDate", "")
            severity = conflict.get("severity", 0)

            # OUTSIDE_WORK_HOURS = встреча вне графика
            if conflict_type == "OUTSIDE_WORK_HOURS" and conflict_date:
                meeting_count += 1
                meeting_hours += 1.5  # типичная встреча ~1.5ч
                local_h = self._to_local_hour(conflict_date, profile_tz)
                if local_h < work_start_h or local_h >= work_end_h:
                    outside_count += 1

            # OVERLAPPING_EVENTS = доп. встреча
            elif conflict_type == "OVERLAPPING_EVENTS":
                meeting_count += 1
                meeting_hours += 1.0

            # OVERLOAD = доп. нагрузка
            elif conflict_type == "OVERLOAD":
                total_hours += severity * 1.5  # severity-зависимая нагрузка

            # WORKDAY_EXCEPTION_CONFLICT = критический конфликт
            elif conflict_type == "WORKDAY_EXCEPTION_CONFLICT":
                meeting_count += 1
                meeting_hours += 2.0
                outside_count += 1  # всегда вне графика при исключении

        workload_ratio = min(total_hours / weekly_cap, 1.5) if weekly_cap > 0 else 0
        meeting_ratio = min(meeting_hours / weekly_cap, 1.0) if weekly_cap > 0 else 0
        outside_ratio = (outside_count / meeting_count) if meeting_count > 0 else 0.0

        overtime_risk = outside_ratio * 0.5
        if employment == "PART_TIME" and total_hours > 4:
            overtime_risk += 0.3
        overtime_risk = min(overtime_risk, 1.0)

        return np.array([[workload_ratio, meeting_ratio, outside_ratio, overtime_risk]])

    def predict(
            self,
            profile: Dict,
            tasks: List[Dict],
            conflict: Optional[Dict] = None
    ) -> float:
        X = self.extract_features(profile, tasks, conflict)

        try:
            probs = self.model.predict_proba(X)
            prob = float(probs[0][1])
        except (ValueError, AttributeError) as e:
            print(f"[predictor] Ошибка предикта ({e}), пересоздаём dummy.")
            self.model = self._train_dummy_model()
            self._use_dummy = True
            probs = self.model.predict_proba(X)
            prob = float(probs[0][1])

        return round(min(max(prob, 0.05), 0.95), 3)

    def get_risk_factors(self, prob: float, conflict: Optional[Dict] = None) -> List[str]:
        """Возвращает осмысленные факторы риска вместо захардкоженных."""
        factors = []
        if conflict:
            ctype = str(conflict.get("type", "")).upper()
            severity = conflict.get("severity", 0)
            type_labels = {
                "OUTSIDE_WORK_HOURS": "Встречи вне рабочего графика",
                "OVERLAPPING_EVENTS": "Наложение событий в календаре",
                "OVERLOAD": "Превышение допустимой нагрузки",
                "WORKDAY_EXCEPTION_CONFLICT": "Конфликт с отпуском/исключением",
            }
            label = type_labels.get(ctype, ctype)
            if severity >= 4:
                factors.append(f"{label} (критичность {severity}/5)")
            elif severity >= 2:
                factors.append(label)

        if prob > 0.5 and not factors:
            factors.append("Высокая совокупная нагрузка")
        elif prob > 0.3 and not factors:
            factors.append("Умеренная нагрузка на график")

        if not factors:
            factors.append("Нагрузка в пределах нормы")

        return factors


predictor = ConflictPredictor()