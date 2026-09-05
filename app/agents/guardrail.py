from __future__ import annotations

import numpy as np
import pandas as pd


class GuardrailAgent:
    REQUIRED = {
        "minute_of_day", "time", "enterprise_gbps", "ran_gbps", "pon_gbps",
        "total_gbps", "predicted_state", "prob_normal", "prob_degraded",
        "prob_failure_prone", "recommended_action",
    }

    def validate(self, frame: pd.DataFrame) -> list[str]:
        missing = self.REQUIRED - set(frame.columns)
        if missing:
            raise ValueError(f"Guardrail rejected output; missing columns: {sorted(missing)}")
        warnings: list[str] = []
        services = frame[["enterprise_gbps", "ran_gbps", "pon_gbps"]]
        if (services < 0).any().any():
            raise ValueError("Guardrail rejected negative traffic values.")
        if not np.allclose(services.sum(axis=1), frame["total_gbps"], atol=1e-6):
            raise ValueError("Guardrail rejected inconsistent aggregate traffic.")
        probs = frame[["prob_normal", "prob_degraded", "prob_failure_prone"]]
        if ((probs < 0) | (probs > 1)).any().any() or not np.allclose(probs.sum(axis=1), 1, atol=1e-5):
            raise ValueError("Guardrail rejected invalid class probabilities.")
        if frame["minute_of_day"].min() < 0 or frame["minute_of_day"].max() >= 1440:
            raise ValueError("Guardrail rejected invalid time values.")
        low = int((frame["prediction_confidence"] < 0.60).sum())
        if low:
            warnings.append(f"{low} intervals have classifier confidence below 0.60.")
        return warnings

