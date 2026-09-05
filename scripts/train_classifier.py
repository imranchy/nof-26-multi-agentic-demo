from __future__ import annotations

import json
import platform
import sys

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app import config


def load_training_data() -> tuple[pd.DataFrame, float]:
    raw = pd.read_excel(config.ALLOCATION_DATA, sheet_name="Sheet1", usecols=[
        "slot", "minute_of_day", "offered_new_total", "offered_new_ent",
        "offered_new_ran", "offered_new_pon", "blocked_new_total",
    ])
    df = raw.drop_duplicates(subset=["slot", "minute_of_day"]).dropna().copy()
    df["enterprise_gbps"] = df["offered_new_ent"]
    df["ran_gbps"] = df["offered_new_ran"]
    df["pon_gbps"] = df["offered_new_pon"]
    df["total_gbps"] = df[["enterprise_gbps", "ran_gbps", "pon_gbps"]].sum(axis=1)
    hour = df["minute_of_day"] // 60
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    df["minute_of_day_sin"] = np.sin(2 * np.pi * df["minute_of_day"] / 1440)
    df["minute_of_day_cos"] = np.cos(2 * np.pi * df["minute_of_day"] / 1440)
    ratio = (df["blocked_new_total"] / df["offered_new_total"].replace(0, np.nan)).fillna(0)
    positive = ratio[ratio > 0]
    threshold = float(positive.quantile(0.67)) if len(positive) else 0.02
    df["network_state"] = np.where(ratio == 0, "normal", np.where(ratio <= threshold, "degraded", "failure_prone"))
    return df, threshold


def main() -> None:
    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    df, threshold = load_training_data()
    x = df[list(config.CLASSIFIER_FEATURES)]
    y = df["network_state"]
    train_x, test_x, train_y, test_y = train_test_split(x, y, test_size=.25, random_state=42, stratify=y)
    rng_train = np.random.default_rng(42)
    rng_test = np.random.default_rng(43)
    noisy_columns = ["enterprise_gbps", "ran_gbps", "pon_gbps", "total_gbps"]
    train_x_noisy, test_x_noisy = train_x.copy(), test_x.copy()
    for column in noisy_columns:
        train_x_noisy[column] = (train_x[column] * (1 + rng_train.normal(0, .05, len(train_x)))).clip(lower=0)
        test_x_noisy[column] = (test_x[column] * (1 + rng_test.normal(0, .05, len(test_x)))).clip(lower=0)
    model = Pipeline([
        ("scale", StandardScaler()),
        ("model", RandomForestClassifier(class_weight="balanced", random_state=42, n_jobs=-1)),
    ])
    model.fit(train_x_noisy, train_y)
    clean_report = classification_report(test_y, model.predict(test_x), output_dict=True, zero_division=0)
    noisy_report = classification_report(test_y, model.predict(test_x_noisy), output_dict=True, zero_division=0)
    joblib.dump(model, config.CLASSIFIER_MODEL, compress=3)
    metadata = {
        "model": "RandomForestClassifier", "features": list(config.CLASSIFIER_FEATURES),
        "rows": len(df), "failure_threshold": threshold,
        "classification_reports": {"clean_test": clean_report, "noisy_test": noisy_report},
        "noise": {"type": "multiplicative_gaussian", "std": 0.05, "columns": noisy_columns},
        "python": sys.version, "platform": platform.platform(), "scikit_learn": sklearn.__version__,
        "limitation": "Simulator-derived surrogate evaluated with a random interval split from one scenario day.",
    }
    config.CLASSIFIER_METADATA.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    print(f"Saved: {config.CLASSIFIER_MODEL}")


if __name__ == "__main__":
    main()
