from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.multioutput import MultiOutputRegressor

from app import config

TARGETS = [f"{service}_gbps" for service in config.SERVICES]


def prepare_dataset(path):
    df = pd.read_csv(path).drop_duplicates().dropna().sort_values(["scenario_id", "minute_of_day"]).copy()
    df["day_index"] = df.scenario_id - df.scenario_id.min()
    day = df["day_index"] % 7
    df["is_weekend"] = day.isin([5, 6]).astype(int)
    # Retain the paper's original training convention (source hour is 1..24).
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    for name, period, value in [("day_of_week", 7, day), ("minute_of_day", 1440, df.minute_of_day)]:
        df[f"{name}_sin"] = np.sin(2 * np.pi * value / period)
        df[f"{name}_cos"] = np.cos(2 * np.pi * value / period)
    daily = df.groupby("scenario_id")[TARGETS].mean()
    for target in TARGETS:
        daily[f"{target}_daily_mean_lag_1d"] = daily[target].shift(1)
        daily[f"{target}_daily_mean_rolling_7d"] = daily[target].shift(1).rolling(7, min_periods=2).mean()
    df = df.merge(daily.drop(columns=TARGETS), left_on="scenario_id", right_index=True)
    df = df.sort_values(["minute_of_day", "scenario_id"])
    for target in TARGETS:
        grouped = df.groupby("minute_of_day")[target]
        df[f"{target}_lag_1d"] = grouped.shift(1)
        df[f"{target}_lag_7d"] = grouped.shift(7)
        df[f"{target}_rolling_7d_mean"] = grouped.transform(lambda x: x.shift(1).rolling(7, min_periods=2).mean())
        df[f"{target}_rolling_7d_std"] = grouped.transform(lambda x: x.shift(1).rolling(7, min_periods=2).std())
    features = ["hour_sin", "hour_cos", "minute_of_day_sin", "minute_of_day_cos", "day_of_week_sin", "day_of_week_cos", "is_weekend"]
    for target in TARGETS:
        features += [f"{target}_lag_1d", f"{target}_lag_7d", f"{target}_rolling_7d_mean", f"{target}_rolling_7d_std", f"{target}_daily_mean_lag_1d", f"{target}_daily_mean_rolling_7d"]
    return df.dropna(subset=features).sort_values(["scenario_id", "minute_of_day"]), features


def main() -> None:
    from xgboost import XGBRegressor

    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    df, features = prepare_dataset(config.FORECAST_DATA)
    last_day = df.scenario_id.max()
    train, test = df[df.scenario_id < last_day], df[df.scenario_id == last_day]
    model = MultiOutputRegressor(XGBRegressor(objective="reg:squarederror", n_estimators=300, max_depth=6, learning_rate=.05, subsample=.9, colsample_bytree=.9, random_state=42, n_jobs=-1))
    model.fit(train[features], train[TARGETS])
    pred = model.predict(test[features])
    metrics = {}
    for i, target in enumerate(TARGETS):
        metrics[target] = {"r2": r2_score(test[target], pred[:, i]), "rmse": mean_squared_error(test[target], pred[:, i]) ** .5, "mae": mean_absolute_error(test[target], pred[:, i])}
    joblib.dump(model, config.FORECAST_MODEL, compress=3)
    print(json.dumps({"training_days": int(train.scenario_id.nunique()), "test_day": int(last_day), "features": features, "metrics": metrics}, indent=2))
    print(f"Saved: {config.FORECAST_MODEL}")


if __name__ == "__main__":
    main()
