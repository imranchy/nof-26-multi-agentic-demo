from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "models"
FORECAST_DATA = DATA_DIR / "source" / "scenarios_00200001_to_00200365_5min.csv"
ALLOCATION_DATA = DATA_DIR / "source" / "SC_Allocation_Output_Data_Dictionary.xlsx"
PRECOMPUTED_FORECAST = DATA_DIR / "prepared" / "xgboost_day_ahead_predictions.csv"
REGRESSION_METRICS = DATA_DIR / "prepared" / "day_ahead_metrics.csv"
FORECAST_MODEL = MODEL_DIR / "xgboost_day_ahead_model.joblib"
CLASSIFIER_MODEL = MODEL_DIR / "sla_random_forest.joblib"
CLASSIFIER_METADATA = MODEL_DIR / "sla_random_forest.metadata.json"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b")

SERVICES = ("enterprise", "ran", "pon")
CLASSIFIER_FEATURES = (
    "enterprise_gbps", "ran_gbps", "pon_gbps", "total_gbps",
    "hour_sin", "hour_cos", "minute_of_day_sin", "minute_of_day_cos",
)

