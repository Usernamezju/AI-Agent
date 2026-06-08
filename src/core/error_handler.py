"""Error-recovery feedback loop — wraps errors as Observations so the LLM can self-correct."""
from __future__ import annotations
import json


def format_observation(message: str) -> str:
    """Wrap *message* as an Observation line for the LLM context."""
    return f"Observation: {message}"


def format_parse_error(raw_text: str) -> str:
    """Build an Observation that tells the LLM its output was unparseable."""
    return format_observation(json.dumps({
        "error": (
            "Your last response could not be parsed. Please follow the format exactly:\n"
            "Thought: <reasoning>\n"
            "Action: <tool_name>\n"
            "Action Input: {\"key\": \"value\"}\n\n"
            f"--- Raw text received ---\n{raw_text}\n--- End ---"
        )
    }, ensure_ascii=False))
