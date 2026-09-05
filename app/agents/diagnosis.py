from __future__ import annotations

from typing import Any

import pandas as pd


class DiagnosisAgent:
    @staticmethod
    def diagnose(row: pd.Series, previous: pd.Series | None = None) -> dict[str, Any]:
        loads = {name: float(row[f"{name}_gbps"]) for name in ("enterprise", "ran", "pon")}
        dominant = max(loads, key=loads.get)
        total = float(row["total_gbps"])
        result: dict[str, Any] = {
            "dominant_service": dominant.upper(),
            "dominant_load_gbps": round(loads[dominant], 2),
            "dominant_share_percent": round(100 * loads[dominant] / total, 1) if total else 0,
        }
        if previous is not None:
            result["total_change_from_previous_gbps"] = round(
                total - float(previous["total_gbps"]), 2
            )
        return result

