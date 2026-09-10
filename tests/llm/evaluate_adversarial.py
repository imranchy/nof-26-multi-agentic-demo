from __future__ import annotations

import json
from pathlib import Path

from app.runtime import MultiAgentRuntime

ROOT=Path(__file__).resolve().parents[2]
CASES=json.loads((ROOT/'tests/llm/query_sets/adversarial_v1.json').read_text(encoding='utf-8'))['cases']
OUT=ROOT/'tests/llm/results/v1/adversarial_results.json'


def main():
    rows=[]
    for i,case in enumerate(CASES,1):
        print(f"[{i}/{len(CASES)}] {case['query']}")
        try:
            runtime=MultiAgentRuntime(forecast_mode='prepared',use_llm=True)
            response=runtime.ask(case['query'])
            executed=[x['tool'] for x in response.routing_audit.get('executed',[])]
            row={
                **case,
                'executed_tools':executed,
                'route_correct':case['expected_tool'] in executed,
                'grounding_passed':response.grounding_passed,
                'guardrail_fallback':not response.grounding_passed,
                'grounding_issues':response.grounding_issues,
                'answer':response.answer,
                'raw_llm_answer':response.raw_llm_answer,
            }
            if case.get('expected_premise_check'):
                row['premise_checked']=response.evidence.get('premise_matches_prediction') is not None
            rows.append(row)
        except Exception as exc:
            rows.append({**case,'route_correct':False,'error':f'{type(exc).__name__}: {exc}'})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
    route=sum(bool(r.get('route_correct')) for r in rows)/len(rows)
    print(json.dumps({'n':len(rows),'route_accuracy':route,'results':str(OUT)},indent=2))


if __name__=='__main__':
    main()
