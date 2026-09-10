from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app import config
from app.agents.forecast import ForecastAgent
from app.agents.sla import SLAAgent
from app.policy_engine import PolicySimulator


OUT = config.VALIDATION_DIR / "results"
OUT.mkdir(parents=True, exist_ok=True)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae_gbps": float(mean_absolute_error(y_true, y_pred)),
        "rmse_gbps": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "r2": float(r2_score(y_true, y_pred)),
    }


def build_ml_validation() -> dict:
    prepared = pd.read_csv(config.PRECOMPUTED_FORECAST).sort_values("minute_of_day")
    live = ForecastAgent(mode="live").forecast().sort_values("minute_of_day")
    target_day = int(prepared["scenario_id"].iloc[0])
    source = pd.read_csv(config.FORECAST_DATA)
    previous_day = target_day - 1
    previous = source[source["scenario_id"] == previous_day].sort_values("minute_of_day")
    if len(previous) != len(prepared):
        raise RuntimeError(f"Expected previous scenario {previous_day} to contain {len(prepared)} intervals; found {len(previous)}")

    rows = []
    live_diffs = {}
    for service in config.SERVICES:
        live_diffs[service] = float(np.max(np.abs(live[f"{service}_gbps"].to_numpy(float) - prepared[f"predicted_{service}_gbps"].to_numpy(float))))

    summary = {
        "target_scenario_id": target_day,
        "frozen_model_replay_max_abs_diff_gbps": live_diffs,
        "frozen_model_replay_matches_prepared_at_1e_5_gbps": all(v <= 1e-5 for v in live_diffs.values()),
        "persistence_baseline_scenario_id": previous_day,
        "comparison": "XGBoost day-ahead forecast and same-time previous-day persistence baseline, both evaluated against target-day actual traffic.",
        "services": {},
    }
    for service in config.SERVICES:
        actual = prepared[f"actual_{service}_gbps"].to_numpy(float)
        forecast = prepared[f"predicted_{service}_gbps"].to_numpy(float)
        persistence = previous[f"{service}_gbps"].to_numpy(float)
        xgb = regression_metrics(actual, forecast)
        base = regression_metrics(actual, persistence)
        summary["services"][service] = {"xgboost": xgb, "previous_day_baseline": base}
        for model_name, values in (("xgboost", xgb), ("previous_day_baseline", base)):
            rows.append({"service": service, "predictor": model_name, **values})

    table = pd.DataFrame(rows)
    table.to_csv(OUT / "ml_forecast_vs_persistence.csv", index=False)
    xgb_rows = table[table.predictor == "xgboost"]
    base_rows = table[table.predictor == "previous_day_baseline"]
    summary["xgboost_average_mae_gbps"] = float(xgb_rows.mae_gbps.mean())
    summary["xgboost_macro_mean_service_rmse_gbps"] = float(xgb_rows.rmse_gbps.mean())
    summary["xgboost_average_r2"] = float(xgb_rows.r2.mean())
    summary["persistence_average_mae_gbps"] = float(base_rows.mae_gbps.mean())
    summary["persistence_macro_mean_service_rmse_gbps"] = float(base_rows.rmse_gbps.mean())
    summary["persistence_average_r2"] = float(base_rows.r2.mean())

    reported = pd.read_csv(config.REGRESSION_METRICS)
    reported_avg = reported[(reported["model"] == "xgboost") & (reported["target"] == "average")]
    if not reported_avg.empty:
        rr = reported_avg.iloc[0]
        summary["xgboost_reported_average_row"] = {
            "mae_gbps": float(rr["mae"]),
            "rmse_gbps": float(rr["rmse"]),
            "r2": float(rr["r2"]),
            "note": "Values already stored by the original training/evaluation pipeline."
        }

    if config.CLASSIFIER_METADATA.exists():
        rf = json.loads(config.CLASSIFIER_METADATA.read_text(encoding="utf-8"))
        clean = rf.get("classification_reports", {}).get("clean_test", {})
        summary["random_forest"] = {
            "accuracy": clean.get("accuracy"),
            "macro_f1": clean.get("macro avg", {}).get("f1-score"),
            "weighted_f1": clean.get("weighted avg", {}).get("f1-score"),
            "failure_prone_precision": clean.get("failure_prone", {}).get("precision"),
            "failure_prone_recall": clean.get("failure_prone", {}).get("recall"),
            "failure_prone_f1": clean.get("failure_prone", {}).get("f1-score"),
            "limitation": rf.get("limitation"),
        }
    (OUT / "ml_validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def build_policy_replay() -> pd.DataFrame:
    frame = SLAAgent().assess(ForecastAgent().forecast())
    simulator = PolicySimulator(frame)
    rows = []
    for policy in ("PCA", "MBA", "SAA"):
        trace = simulator.replay(policy)
        rows.append(
            {
                "policy": policy,
                "intervals": len(trace),
                "mean_blocking_ratio": float(np.mean([x["overall_blocking_ratio_epoch"] for x in trace])),
                "max_blocking_ratio": float(np.max([x["overall_blocking_ratio_epoch"] for x in trace])),
                "mean_fresh_service_ratio": float(np.mean([x["fresh_service_ratio"] for x in trace])),
                "total_sc_reconfigurations": int(sum(x["reconfig_count"] for x in trace)),
                "reconfig_event_intervals": int(sum(x["reconfig_event"] for x in trace)),
                "mean_weighted_reconfig_cost": float(np.mean([x["weighted_reconfig_cost"] for x in trace])),
            }
        )
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "policy_replay_summary.csv", index=False)
    return result


def main() -> None:
    ml = build_ml_validation()
    policy = build_policy_replay()
    print(json.dumps(ml, indent=2))
    print(policy.to_string(index=False))
    print(f"Wrote validation artifacts to {OUT}")


if __name__ == "__main__":
    main()
