from __future__ import annotations

import json
from urllib.request import urlopen

from app import config
from app.runtime import MultiAgentRuntime


def main() -> None:
    print("Checking specialist-agent pipeline...")
    runtime = MultiAgentRuntime(use_llm=True)
    evidence = runtime._execute_tool("diagnose_highest_risk", {}, [])
    print(json.dumps(evidence, indent=2))
    print(f"Validated intervals: {len(runtime.frame)}")
    try:
        with urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=3) as response:
            tags = json.loads(response.read())
        names = [item["name"] for item in tags.get("models", [])]
        print("Ollama: available")
        print(f"Models: {names}")
        present = any(name.startswith(config.OLLAMA_MODEL) for name in names)
        print(f"Required model present: {present}")
        if not present:
            raise RuntimeError(f"Required model {config.OLLAMA_MODEL} is not installed")
        print("Checking Mistral tool selection and execution...")
        result = runtime.ask("When is RAN traffic expected to peak?")
        print(result.answer)
        print(f"Selected tool: {result.evidence['selected_tool']}")
        if result.evidence["selected_tool"] != "find_service_peak":
            raise RuntimeError("Mistral selected the wrong verification tool")
    except Exception as exc:
        raise RuntimeError(f"Ollama Mistral tool-calling verification failed: {exc}") from exc


if __name__ == "__main__":
    main()
