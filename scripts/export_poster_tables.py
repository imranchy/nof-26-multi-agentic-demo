from __future__ import annotations

from pathlib import Path

import pandas as pd

from app import config


def main() -> None:
    results = config.VALIDATION_DIR / "results"
    out = results / "poster_tables"
    out.mkdir(parents=True, exist_ok=True)
    for filename in ("ml_forecast_vs_persistence.csv", "policy_replay_summary.csv", "agent_semantic_category_summary.csv"):
        source = results / filename
        if source.exists():
            pd.read_csv(source).to_csv(out / filename, index=False)
    print(f"Poster-ready CSV tables copied to {out}")


if __name__ == "__main__":
    main()
