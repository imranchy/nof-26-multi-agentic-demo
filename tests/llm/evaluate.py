from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml

from app import config
from app.runtime import MultiAgentRuntime

QUERY_SET_DIR = ROOT / "tests" / "llm" / "query_sets"
DEFAULT_QUERY_SET = "operator_10_categories_v1.json"
BENCHMARK_CFG = ROOT / "tests" / "llm" / "benchmark_config.yaml"
RESULTS = ROOT / "tests" / "llm" / "results" / "v1"


def resolve_query_set(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = QUERY_SET_DIR / path
    path = path.resolve()
    if not path.exists():
        raise SystemExit(f"Query set not found: {path}")
    return path


def load_cases(query_set_path: Path) -> list[dict[str, Any]]:
    data = json.loads(query_set_path.read_text(encoding="utf-8"))
    if "cases" not in data or not isinstance(data["cases"], list):
        raise SystemExit(f"Invalid query set (missing cases list): {query_set_path}")
    return data["cases"]


def args_subset(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key, value in expected.items():
        if key not in actual:
            return False
        a = actual[key]
        if isinstance(value, str) and isinstance(a, str):
            if a.upper() != value.upper():
                return False
        elif a != value:
            return False
    return True


def argument_score(plan: list[dict[str, Any]], expected_by_tool: dict[str, dict[str, Any]]) -> bool:
    for tool, expected in expected_by_tool.items():
        matches = [step for step in plan if step.get("tool") == tool]
        if not matches or not any(args_subset(step.get("arguments", {}), expected) for step in matches):
            return False
    return True


def run_case(case: dict[str, Any], forecast_mode: str) -> dict[str, Any]:
    runtime = MultiAgentRuntime(forecast_mode=forecast_mode, use_llm=True)
    if case.get("setup_query"):
        runtime.ask(case["setup_query"])
    response = runtime.ask(case["query"])
    raw = response.routing_audit.get("mistral_proposed", [])
    executed = response.routing_audit.get("executed", [])
    expected_tools = case.get("expected_tools", [])
    raw_tools = [x.get("tool") for x in raw]
    executed_tools = [x.get("tool") for x in executed]
    expected_args = case.get("expected_args_by_tool", {})
    coordinator = response.routing_audit.get("coordinator", {})
    return {
        "id": case["id"],
        "category": case["category"],
        "query": case["query"],
        "setup_query": case.get("setup_query", ""),
        "expected_tools": expected_tools,
        "raw_tools": raw_tools,
        "executed_tools": executed_tools,
        "raw_tool_sequence_correct": raw_tools == expected_tools,
        "executed_tool_sequence_correct": executed_tools == expected_tools,
        "raw_arguments_correct": argument_score(raw, expected_args),
        "executed_arguments_correct": argument_score(executed, expected_args),
        "deterministic_correction": bool(response.routing_audit.get("deterministic_correction")),
        "coordinator_parse_failure": bool(coordinator.get("parse_failed")),
        "coordinator_fallback_used": bool(coordinator.get("fallback_used")),
        "raw_explanation_accepted": bool(response.grounding_passed),
        "guardrail_fallback": not response.grounding_passed,
        "final_safe_answer": bool(response.answer.strip()),
        "unsupported_numeric_claim": "unsupported_numeric_claim" in response.grounding_issues,
        "unsupported_categorical_claim": any(x in response.grounding_issues for x in (
            "unsupported_sla_state_claim", "unsupported_recommendation_claim", "false_change_claim", "traffic_capacity_confusion"
        )),
        "unsupported_causal_claim": "unsupported_causal_claim" in response.grounding_issues,
        "implementation_detail_exposed": "implementation_detail_exposed" in response.grounding_issues,
        "grounding_issues": response.grounding_issues,
        "answer": response.answer,
        "raw_llm_answer": response.raw_llm_answer or "",
    }


def rate(rows: list[dict[str, Any]], key: str) -> float:
    return sum(bool(r.get(key)) for r in rows) / len(rows) if rows else 0.0


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n": len(rows),
        "raw_tool_sequence_accuracy": rate(rows, "raw_tool_sequence_correct"),
        "raw_argument_accuracy": rate(rows, "raw_arguments_correct"),
        "executed_tool_sequence_accuracy": rate(rows, "executed_tool_sequence_correct"),
        "executed_argument_accuracy": rate(rows, "executed_arguments_correct"),
        "deterministic_correction_rate": rate(rows, "deterministic_correction"),
        "coordinator_parse_failure_rate": rate(rows, "coordinator_parse_failure"),
        "coordinator_fallback_rate": rate(rows, "coordinator_fallback_used"),
        "raw_explanation_accept_rate": rate(rows, "raw_explanation_accepted"),
        "guardrail_fallback_rate": rate(rows, "guardrail_fallback"),
        "final_safe_answer_rate": rate(rows, "final_safe_answer"),
        "unsupported_numeric_claim_rate": rate(rows, "unsupported_numeric_claim"),
        "unsupported_categorical_claim_rate": rate(rows, "unsupported_categorical_claim"),
        "unsupported_causal_claim_rate": rate(rows, "unsupported_causal_claim"),
        "implementation_detail_exposure_rate": rate(rows, "implementation_detail_exposed"),
    }


def evaluate_pass(m: dict[str, Any], thresholds: dict[str, float]) -> tuple[bool, list[str]]:
    failed=[]
    for key, threshold in thresholds.items():
        if float(m.get(key, 0.0)) + 1e-12 < float(threshold):
            failed.append(f"{key}={m.get(key,0):.3f} < {threshold:.3f}")
    return not failed, failed


def save(rows: list[dict[str, Any]], label: str, thresholds: dict[str, float]) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["category"]].append(row)
    summary = {
        "benchmark_version": "v1",
        "prompt_versions": {
            "coordinator": config.prompt_version("coordinator"),
            "explainer": config.prompt_version("explainer"),
            "operator_style": config.prompt_version("operator_style"),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall": metrics(rows),
        "by_category": {cat: metrics(items) for cat, items in sorted(groups.items())},
        "thresholds": thresholds,
    }
    for cat, m in summary["by_category"].items():
        passed, failures = evaluate_pass(m, thresholds)
        m["system_pass"] = passed
        m["threshold_failures"] = failures
    overall_pass, overall_failures = evaluate_pass(summary["overall"], thresholds)
    summary["overall"]["system_pass"] = overall_pass
    summary["overall"]["threshold_failures"] = overall_failures

    (RESULTS / f"{label}_details.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (RESULTS / f"{label}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (RESULTS / f"{label}_details.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = [
            "id","category","query","setup_query","expected_tools","raw_tools","executed_tools",
            "raw_tool_sequence_correct","raw_arguments_correct","executed_tool_sequence_correct","executed_arguments_correct",
            "deterministic_correction","coordinator_parse_failure","coordinator_fallback_used","raw_explanation_accepted",
            "guardrail_fallback","final_safe_answer","unsupported_numeric_claim","unsupported_categorical_claim",
            "unsupported_causal_claim","implementation_detail_exposed","grounding_issues","answer",
        ]
        writer=csv.DictWriter(fh,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            enc=dict(row)
            for key in ("expected_tools","raw_tools","executed_tools","grounding_issues"):
                enc[key]=json.dumps(enc.get(key,[]),ensure_ascii=False)
            writer.writerow(enc)
    print(json.dumps(summary["overall"], indent=2))
    print(f"Saved: {RESULTS / (label + '_summary.json')}")


def main() -> None:
    parser=argparse.ArgumentParser(description="Run NoF v1 Mistral operator benchmark without launching Streamlit.")
    parser.add_argument("--query-set", default=DEFAULT_QUERY_SET,
                        help=f"Query-set JSON filename in tests/llm/query_sets (default: {DEFAULT_QUERY_SET}).")
    parser.add_argument("--category", help="Run one named category from the selected query set.")
    parser.add_argument("--all", action="store_true", help="Run all cases in the selected query set.")
    parser.add_argument("--limit", type=int, default=None)
    args=parser.parse_args()

    benchmark_cfg=yaml.safe_load(BENCHMARK_CFG.read_text(encoding="utf-8"))["benchmark"]
    query_set_path=resolve_query_set(args.query_set)
    cases=load_cases(query_set_path)
    categories=sorted({c["category"] for c in cases})
    if not args.all and not args.category:
        print("Choose --category NAME or --all. Available categories:")
        for c in categories:
            print(f"  {c}")
        return
    if args.category:
        if args.category not in categories:
            raise SystemExit(f"Unknown category: {args.category}")
        cases=[c for c in cases if c["category"]==args.category]
        label=f"{query_set_path.stem}_{args.category}"
    else:
        label=f"{query_set_path.stem}_all"
    if args.limit:
        cases=cases[:args.limit]
    rows=[]
    for i,case in enumerate(cases,1):
        print(f"[{i}/{len(cases)}] {case['id']}: {case['query']}")
        try:
            rows.append(run_case(case,benchmark_cfg.get("forecast_mode","prepared")))
        except Exception as exc:
            rows.append({
                "id":case["id"],"category":case["category"],"query":case["query"],"setup_query":case.get("setup_query",""),
                "expected_tools":case.get("expected_tools",[]),"raw_tools":[],"executed_tools":[],
                "raw_tool_sequence_correct":False,"raw_arguments_correct":False,"executed_tool_sequence_correct":False,
                "executed_arguments_correct":False,"deterministic_correction":False,"coordinator_parse_failure":False,
                "coordinator_fallback_used":False,"raw_explanation_accepted":False,"guardrail_fallback":False,
                "final_safe_answer":False,"unsupported_numeric_claim":False,"unsupported_categorical_claim":False,
                "unsupported_causal_claim":False,"implementation_detail_exposed":False,
                "grounding_issues":[f"runtime_error:{type(exc).__name__}"],"answer":"","raw_llm_answer":"","error":str(exc),
            })
    save(rows,label,benchmark_cfg["pass_thresholds"])


if __name__ == "__main__":
    main()
