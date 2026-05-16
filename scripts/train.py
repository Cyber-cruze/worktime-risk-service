import os
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib

FEATURES = [
    "weekly_work_hours",
    "overtime_hours",
    "meeting_density",
    "consecutive_work_days",
    "conflict_count",
    "workload_trend",
    "night_weekend_hours"
]

def generate_synthetic_data(n=2000, seed=42):
    np.random.seed(seed)
    cluster = np.random.choice(["normal", "overloaded", "underloaded"], n, p=[0.7, 0.15, 0.15])

    df = pd.DataFrame({
        "weekly_work_hours": np.where(
            cluster == "overloaded", np.random.normal(58, 8, n),
            np.where(cluster == "underloaded", np.random.normal(28, 6, n), np.random.normal(40, 5, n))
        ),
        "overtime_hours": np.where(
            cluster == "overloaded", np.random.exponential(7, n),
            np.clip(np.random.exponential(2, n), 0, 5)
        ),

        "meeting_density": np.clip(
            np.random.beta(2, 5, n) + np.where(cluster == "overloaded", 0.2, -0.1), 0, 0.95
        ),
        "consecutive_work_days": np.where(
            cluster == "overloaded", np.random.randint(6, 14, n),
            np.random.randint(1, 6, n)
        ),
        "conflict_count": np.where(
            cluster == "overloaded", np.random.poisson(3, n),
            np.random.poisson(1, n)
        ),

        "workload_trend": np.where(
            cluster == "overloaded", np.random.normal(0.15, 0.2, n), np.random.normal(0, 0.2, n)
        ),
        "night_weekend_hours": np.where(
            cluster == "overloaded", np.random.uniform(2, 10, n), np.random.uniform(0, 3, n)
        )
    })


    X1 = np.clip(df["overtime_hours"] / 12, 0, 1)
    X2 = np.clip(df["meeting_density"] / 0.75, 0, 1)
    X3 = np.clip(df["consecutive_work_days"] / 14, 0, 1)
    X4 = np.clip(df["conflict_count"] / 6, 0, 1)
    X5 = np.clip(df["workload_trend"] * 1.5 + 0.5, 0, 1)

    df["risk_score"] = np.clip(
        10 * (0.35*X1 + 0.25*X2 + 0.20*X3 + 0.15*X4 + 0.05*X5) + np.random.normal(0, 0.3, n),
        0, 10
    )
    return df

def train_and_save():
    df = generate_synthetic_data()

    X = df[FEATURES]
    y = df["risk_score"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.08,
        min_samples_split=10,
        random_state=42
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    print(f"MAE: {mae:.3f}")

    model_dir = "../model"
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "risk_model.pkl")
    joblib.dump(model, model_path)

if __name__ == "__main__":
    train_and_save()