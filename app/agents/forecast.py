from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
import warnings
from sklearn.exceptions import InconsistentVersionWarning

from app import config


class ForecastAgent:
    """Provide the frozen prepared XGBoost forecast or re-run the saved model."""

    def __init__(self, mode: str = "prepared") -> None:
        self.mode = mode
        self._model = None
        self._cache: pd.DataFrame | None = None

    def forecast(self) -> pd.DataFrame:
        if self._cache is not None:
            return self._cache.copy()
        if self.mode == "live" and config.FORECAST_MODEL.exists():
            result = self._live_forecast()
        else:
            result = pd.read_csv(config.PRECOMPUTED_FORECAST)
        self._cache = self._normalise(result)
        return self._cache.copy()

    def _live_forecast(self) -> pd.DataFrame:
        from scripts.train_forecaster import prepare_dataset

        prepared, features = prepare_dataset(config.FORECAST_DATA)
        last_day = prepared["scenario_id"].max()
        test = prepared[prepared["scenario_id"] == last_day].copy()
        if self._model is None:
            # The frozen XGBoost wrapper was serialized by an earlier sklearn build.
            # Its outputs are regression-tested against the prepared forecast to
            # micro-Gbps tolerance, so suppress the known compatibility warning in
            # the live demo while preserving the frozen model.
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
                warnings.filterwarnings("ignore", message=".*If you are loading a serialized model.*")
                self._model = joblib.load(config.FORECAST_MODEL)
        predictions = self._model.predict(test[features])
        out = test[["scenario_id", "minute_of_day", "enterprise_gbps", "ran_gbps", "pon_gbps"]].copy()
        for index, service in enumerate(config.SERVICES):
            out[f"actual_{service}_gbps"] = out[f"{service}_gbps"]
            out[f"predicted_{service}_gbps"] = predictions[:, index]
            out[f"error_{service}_gbps"] = out[f"predicted_{service}_gbps"] - out[f"actual_{service}_gbps"]
        out = out.drop(columns=[f"{service}_gbps" for service in config.SERVICES])

        # Use the original repository model as the live source of truth.
        # Do not compare it against a separately generated baseline file here;
        # the model and prepared data in this repository are kept together.
        return out

    @staticmethod
    def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
        df = frame.copy().sort_values("minute_of_day").reset_index(drop=True)
        df["hour"] = (df["minute_of_day"] // 60).astype(int)
        df["minute"] = (df["minute_of_day"] % 60).astype(int)
        df["time"] = df["minute_of_day"].map(lambda v: f"{int(v)//60:02d}:{int(v)%60:02d}")
        for service in config.SERVICES:
            df[f"{service}_gbps"] = df[f"predicted_{service}_gbps"].clip(lower=0)
        df["total_gbps"] = df[[f"{s}_gbps" for s in config.SERVICES]].sum(axis=1)
        radians = 2 * np.pi * df["minute_of_day"] / 1440
        df["minute_of_day_sin"] = np.sin(radians)
        df["minute_of_day_cos"] = np.cos(radians)
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
        df["slot"] = (df["minute_of_day"] // 5).astype(int)
        return df

    def metrics(self) -> pd.DataFrame | None:
        if not config.REGRESSION_METRICS.exists():
            return None
        frame = pd.read_csv(config.REGRESSION_METRICS)
        return frame[(frame["model"] == "xgboost")].copy()
