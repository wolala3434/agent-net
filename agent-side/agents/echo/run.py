"""Echo / Summarizer Agent — Demo Agent (:9123).

A simple text-summarisation agent for single-agent testing and connectivity
validation.  Uses the ``@Agent`` decorator (Mode A — functional pattern).

Domain: nlp.summarization
Skill:  text-summarisation
"""

from __future__ import annotations

import argparse

from agent_internet import Agent, Skill, serve


def _mock_summarize(text: str) -> str:
    """Simple mock summariser — extract first sentence or truncate."""
    if not text:
        return ""

    # Try to extract the first meaningful sentence
    text = text.strip()
    for delimiter in ("。", ". ", "！", "？", "!", "?", "\n"):
        idx = text.find(delimiter)
        if idx != -1:
            return text[: idx + len(delimiter)]

    # Fallback: truncate to first 120 characters
    if len(text) > 120:
        return text[:117] + "..."
    return text


@Agent(
    name="Echo Summarizer",
    version="1.0.0",
    description="文本摘要服务 — 接收文本输入，返回简洁摘要。用于连通性测试和单Agent模式验证",
    provider={"name": "Agent Internet Demo", "contact": "demo@agentinternet.io"},
    skills=[
        Skill(
            id="text-summarisation",
            name="文本摘要",
            domains=["nlp.summarization"],
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "max_length": {"type": "integer"},
                },
                "required": ["text"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "original_length": {"type": "integer"},
                    "summary_length": {"type": "integer"},
                },
                "required": ["summary"],
            },
        )
    ],
    pricing={"model": "per_call", "unit_price": 0.01},
)
def handle_task(input_data: dict) -> dict:
    """Receive text and return a mock summary.

    This is a simple rule-based summariser suitable for testing and demo
    purposes.  A production deployment would replace this with an LLM or
    a dedicated NLP model.
    """
    text = input_data.get("text", "")
    max_length = input_data.get("max_length", 200)

    if not text:
        return {"summary": "", "original_length": 0, "summary_length": 0}

    summary = _mock_summarize(text)
    if len(summary) > max_length:
        summary = summary[: max_length - 3] + "..."

    return {
        "summary": summary,
        "original_length": len(text),
        "summary_length": len(summary),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9123)
    parser.add_argument("--registry", default="http://localhost:8000")
    args = parser.parse_args()
    serve(
        agent_fn=handle_task,
        host="0.0.0.0",
        port=args.port,
        registry_url=args.registry,
    )
