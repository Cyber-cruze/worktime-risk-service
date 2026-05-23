import numpy as np
import joblib
from pathlib import Path
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import GradientBoostingRegressor, IsolationForest


def train():
    print("Training ml models...")
    model_dir = Path(__file__).parent.parent / "model"
    model_dir.mkdir(exist_ok=True)

    # 1. Генерируем данные
    np.random.seed(42)
    n_samples = 500

    # Признаки: [task_count, meeting_count, overtime_risk]
    X = np.random.rand(n_samples, 3)

    # 2. Обучаем Predictor 
    # Если задач много или встреч много -> конфликт (1)
    y_pred = ((X[:, 0] > 0.6) | (X[:, 1] > 0.7)).astype(int)
    predictor = MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=200, random_state=42)
    predictor.fit(X, y_pred)
    joblib.dump(predictor, model_dir / "conflict_predictor.pkl")
    print("conflict_predictor.pkl saved")

    # 3. Обучаем Scorer (GBM)
    # Признаки: [hours, conflicts] -> Score 0-100
    X_score = np.random.rand(n_samples, 2) * 100
    y_score = 100 - (X_score[:, 0] * 0.5 + X_score[:, 1] * 2)
    scorer = GradientBoostingRegressor(random_state=42)
    scorer.fit(X_score, y_score)
    joblib.dump(scorer, model_dir / "schedule_scorer.pkl")
    print("schedule_scorer.pkl saved")

    # 4. Обучаем Anomaly Detector
    # Признаки: [activity_count]
    X_anom = np.random.rand(n_samples, 1) * 10
    X_anom[-10:] = np.random.rand(10, 1) * 50
    detector = IsolationForest(contamination=0.05, random_state=42)
    detector.fit(X_anom)
    joblib.dump(detector, model_dir / "anomaly_detector.pkl")
    print("anomaly_detector.pkl saved")


if __name__ == "__main__":
    train()