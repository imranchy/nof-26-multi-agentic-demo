"""Backward-compatible wrapper for the v1 offline Mistral benchmark.

Preferred commands:
  python -m tests.llm.evaluate --category traffic_prediction
  python -m tests.llm.evaluate --all
"""
from tests.llm.evaluate import main

if __name__ == "__main__":
    main()
