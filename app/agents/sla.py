from __future__ import annotations

import joblib
import pandas as pd

from app import config


class SLAAgent:
    def __init__(self) -> None:
        if not config.CLASSIFIER_MODEL.exists():
            raise FileNotFoundError("SLA model missing. Run: python -m scripts.train_classifier")
        self.model = joblib.load(config.CLASSIFIER_MODEL)

    def assess(self, forecast: pd.DataFrame) -> pd.DataFrame:
        df = forecast.copy()
        features = list(config.CLASSIFIER_FEATURES)
        df["predicted_state"] = self.model.predict(df[features])
        probabilities = self.model.predict_proba(df[features])
        for index, label in enumerate(self.model.classes_):
            df[f"prob_{label}"] = probabilities[:, index]
        for label in ("normal", "degraded", "failure_prone"):
            if f"prob_{label}" not in df:
                df[f"prob_{label}"] = 0.0
        df["failure_probability"] = df["prob_failure_prone"]
        df["severity_score"] = (0.5 * df["prob_degraded"] + df["prob_failure_prone"]).clip(0, 1)
        df["prediction_confidence"] = df[["prob_normal", "prob_degraded", "prob_failure_prone"]].max(axis=1)
        return df
