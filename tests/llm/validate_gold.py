from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "tests" / "llm" / "query_sets" / "operator_10_categories_v1.json"


def main() -> None:
    data = json.loads(GOLD.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    assert data.get("version") == "v1"
    assert data.get("categories") == 10
    assert data.get("queries_per_category") == 10
    assert data.get("total_queries") == 100
    assert len(cases) == 100
    counts = Counter(c["category"] for c in cases)
    assert len(counts) == 10
    assert set(counts.values()) == {10}
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))
    banned = ("xgboost", "random forest", "classifier confidence", "rf-v1", "xgb-v1")
    for case in cases:
        q = (case.get("setup_query", "") + " " + case["query"]).lower()
        assert not any(term in q for term in banned), case["id"]
        assert case.get("expected_tools"), case["id"]
        assert all(isinstance(x, str) for x in case["expected_tools"])
    print("Gold benchmark valid: 100 queries, 10 categories, 10 queries per category, no model-specific operator wording.")
    for category, count in sorted(counts.items()):
        print(f"  {category}: {count}")


if __name__ == "__main__":
    main()
