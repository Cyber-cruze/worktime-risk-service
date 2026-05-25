import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import IsolationForest
from typing import List, Dict
from datetime import datetime
import zoneinfo

MODEL_PATH = Path(__file__).parent.parent.parent / "model" / "anomaly_detector.pkl"

N_FEATURES = 4


class AnomalyDetector:
    def __init__(self):
        self.model = None
        self._use_dummy = False
        self.load_model()

    def load_model(self):
        self.model = self._train_dummy_model()
        self._use_dummy = True

        if not MODEL_PATH.exists():
            print("[anomaly] pkl не найден. Используем dummy.")
            return

        try:
            loaded = joblib.load(MODEL_PATH)
            expected = getattr(loaded, 'n_features_in_', None)
            if expected is not None and expected != N_FEATURES:
                return
            # Пробуем тестовый predict
            test_X = np.zeros((1, N_FEATURES))
            try:
                loaded.predict(test_X)
            except ValueError:
                print("[anomaly] pkl-модель несовместима по фичам. Используем dummy.")
                return
            self.model = loaded
            self._use_dummy = False
            print("[anomaly] pkl-модель загружена успешно.")
        except Exception as e:
            print(f"[anomaly] Ошибка загрузки pkl: {e}. Используем dummy.")

    def _train_dummy_model(self):
        """Калиброванная dummy IsolationForest на 4 фичи."""
        rng = np.random.RandomState(42)
        # Нормальные расписания: 2-5 событий, 4-8ч, плотность 0.4-0.7, окон >=1
        X_normal = np.column_stack([
            rng.uniform(2, 6, 80),     # event_count
            rng.uniform(4, 8, 80),     # total_hours
            rng.uniform(0.3, 0.7, 80), # density
            rng.uniform(0, 3, 80),     # gaps (есть окна)
        ])
        # Аномалии: 7+ событий, 9+ часов, плотность >0.85, окон нет
        X_anomaly = np.column_stack([
            rng.uniform(7, 12, 20),     # много событий
            rng.uniform(9, 14, 20),     # переработка
            rng.uniform(0.85, 1.0, 20), # почти без окон
            rng.uniform(-1, 0.5, 20),   # нет перерывов
        ])
        X = np.vstack([X_normal, X_anomaly])
        model = IsolationForest(contamination=0.2, random_state=42)
        model.fit(X)
        return model

    def _calc_hours(self, start_str: str, end_str: str) -> float:
        try:
            start = datetime.fromisoformat(str(start_str))
            end = datetime.fromisoformat(str(end_str))
            return max((end - start).total_seconds() / 3600, 0)
        except Exception:
            return 0

    def extract_features(self, tasks: List[Dict]) -> np.ndarray:
        """4 фичи: event_count, total_hours, density, gaps."""
        event_count = len(tasks)

        total_hours = 0.0
        intervals = []
        for t in tasks:
            start = t.get("startTime", t.get("start_time", ""))
            end = t.get("endTime", t.get("end_time", ""))
            hours = self._calc_hours(start, end)
            total_hours += hours
            try:
                intervals.append((
                    datetime.fromisoformat(str(start)),
                    datetime.fromisoformat(str(end))
                ))
            except Exception:
                pass

        # Сортируем по start
        intervals.sort(key=lambda x: x[0])

        # Плотность: занятое_время / (последний_end - первый_start)
        if len(intervals) >= 2:
            span_hours = (intervals[-1][1] - intervals[0][0]).total_seconds() / 3600
            density = total_hours / span_hours if span_hours > 0 else 0
        else:
            density = 0.5  # одно событие — средняя плотность

        # Количество окон (пауз >= 30 мин между событиями)
        gaps = 0
        for i in range(1, len(intervals)):
            gap_min = (intervals[i][0] - intervals[i-1][1]).total_seconds() / 60
            if gap_min >= 30:
                gaps += 1

        return np.array([[event_count, total_hours, min(density, 1.5), gaps]])

    def detect(self, tasks: List[Dict]) -> Dict:
        if not tasks:
            return {
                "is_anomalous": False,
                "anomaly_score": 0.0,
                "detected_patterns": [],
                "action_required": "Нет данных для анализа"
            }

        X = self.extract_features(tasks)

        # Rule-based проверки (быстрые и точные)
        event_count = len(tasks)
        total_hours = X[0][1]
        density = X[0][2]
        gaps = int(X[0][3])

        patterns = []
        rule_anomalous = False

        if event_count >= 7:
            patterns.append("Аномальная плотность графика: 7+ событий за день")
            rule_anomalous = True
        elif event_count >= 5 and density > 0.8:
            patterns.append("Высокая плотность: 5+ событий почти без перерывов")
            rule_anomalous = True

        if total_hours >= 9:
            patterns.append(f"Рабочий день превышает 9 часов ({total_hours:.1f}ч)")
            rule_anomalous = True

        if density > 0.9 and event_count >= 4:
            patterns.append("Почти нет свободных окон между событиями")
            rule_anomalous = True

        if gaps == 0 and event_count >= 4:
            patterns.append("Отсутствуют перерывы между событиями")
            rule_anomalous = True

        # ML-предикт (дополнительно к правилам)
        ml_anomalous = False
        ml_score = 0.0
        try:
            preds = self.model.predict(X)
            scores = self.model.score_samples(X)
            ml_anomalous = bool(preds[0] == -1)
            ml_score = float(abs(scores[0]))
            ml_score = min(ml_score, 1.0)
        except (ValueError, AttributeError) as e:
            print(f"[anomaly] ML-ошибка ({e}), пересоздаём dummy.")
            self.model = self._train_dummy_model()
            preds = self.model.predict(X)
            scores = self.model.score_samples(X)
            ml_anomalous = bool(preds[0] == -1)
            ml_score = min(float(abs(scores[0])), 1.0)

        # Итог: rule-based приоритетнее ML
        is_anomalous = rule_anomalous or ml_anomalous

        # Если rule-based сработал — добавляем ML-паттерн тоже
        if ml_anomalous and not patterns:
            patterns.append("ML-детектор обнаружил нетипичный паттерн расписания")

        # Итоговый score: комбинация rule-based и ML
        if rule_anomalous:
            anomaly_score = min(0.5 + len(patterns) * 0.15, 1.0)
        else:
            anomaly_score = ml_score if ml_anomalous else min(ml_score, 0.3)

        action = "Рекомендуется пересмотр графика" if is_anomalous else "Нагрузка в пределах нормы"

        return {
            "is_anomalous": is_anomalous,
            "anomaly_score": round(anomaly_score, 3),
            "detected_patterns": patterns,
            "action_required": action
        }


detector = AnomalyDetector()