from __future__ import annotations

import json
from urllib.request import urlopen

from app import config
from app.runtime import MultiAgentRuntime


def main() -> None:
    print("Checking deterministic forecast/SLA/policy pipeline...")
    runtime = MultiAgentRuntime(use_llm=True)
    evidence, _ = runtime.execute_tool_direct("compare_policies_at_time", {"time": "21:15"})
    print(json.dumps(evidence, indent=2))
    print(f"Validated intervals: {len(runtime.frame)}")

    with urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=5) as response:
        tags = json.loads(response.read())
    names = [item["name"] for item in tags.get("models", [])]
    present = any(name.startswith(config.OLLAMA_MODEL) for name in names)
    print(f"Ollama models: {names}")
    if not present:
        raise RuntimeError(f"Required model {config.OLLAMA_MODEL} is not installed")

    print("Checking Mistral routing...")
    result = runtime.ask("Show me the network and SC allocation status at 21:15.")
    print(result.answer)
    print(f"Selected tool: {result.plan.tool_name}")
    if result.plan.tool_name != "get_network_state_at_time":
        raise RuntimeError("Mistral selected the wrong verification tool")
    print("Installation verified.")


if __name__ == "__main__":
    main()
