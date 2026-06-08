"""Text parser — extracts Thought / Action / Action Input / Final Answer from raw LLM output."""
from __future__ import annotations
import json
import re


class ParseResult:
    def __init__(self, thought: str = "", action: str | None = None,
                 action_input: dict | None = None, final_answer: str | None = None,
                 raw_text: str = "") -> None:
        self.thought = thought
        self.action = action
        self.action_input = action_input
        self.final_answer = final_answer
        self.raw_text = raw_text

    @property
    def is_finished(self) -> bool:
        return self.final_answer is not None

    @property
    def has_action(self) -> bool:
        return self.action is not None

    def __repr__(self) -> str:
        return f"<ParseResult action={self.action!r} has_input={self.action_input is not None} finished={self.is_finished}>"


def parse_response(raw: str) -> ParseResult:
    """Parse raw LLM output into structured fields."""
    text = raw.strip()

    # Final Answer 优先检查
    fa = re.search(r"(?:^|\n)\s*Final\s+Answer\s*[:：]\s*(.*)", text, re.IGNORECASE | re.DOTALL)
    if fa:
        return ParseResult(thought=_extract_thought(text), final_answer=fa.group(1).strip(), raw_text=text)

    thought = _extract_thought(text)
    action = _extract_action(text)
    action_input = _extract_action_input(text) if action else None
    return ParseResult(thought=thought, action=action, action_input=action_input, raw_text=text)


def _extract_thought(text: str) -> str:
    m = re.search(r"(?:^|\n)\s*Thought\s*[:：]\s*(.*?)(?=\n\s*(?:Action|Final\s+Answer)[:：]|$)",
                  text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _extract_action(text: str) -> str | None:
    m = re.search(r"(?:^|\n)\s*Action\s*[:：]\s*(\S+)", text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _extract_action_input(text: str) -> dict | None:
    # Strategy 1: ```json fences
    m = re.search(r"Action\s*Input\s*[:：]\s*```(?:json)?\s*(\{.*?\})\s*```", text, re.IGNORECASE | re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except json.JSONDecodeError: pass

    # Strategy 2: bare JSON on same/next lines
    m = re.search(r"Action\s*Input\s*[:：]\s*(\{.*?\})\s*(?:Action|Final\s+Answer|Thought|$)",
                  text, re.IGNORECASE | re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except json.JSONDecodeError: pass

    # Fallback: grab raw text, strip fences, try parse
    m = re.search(r"Action\s*Input\s*[:：]\s*(.*?)(?=\n\s*(?:Action|Final\s+Answer|Thought)[:：]|$)",
                  text, re.IGNORECASE | re.DOTALL)
    if m:
        candidate = re.sub(r"^```(?:json)?\s*", "", m.group(1).strip())
        candidate = re.sub(r"\s*```$", "", candidate)
        try: return json.loads(candidate)
        except json.JSONDecodeError: return {"__parse_error__": candidate}

    return None


def describe_parse_error(action_input: dict | None) -> str | None:
    """Return a human-friendly error message if action_input contains a parse failure."""
    if action_input is None:
        return "Action Input is missing. You MUST provide a JSON argument block after 'Action Input:'."
    raw = action_input.get("__parse_error__")
    if raw:
        return (f"Failed to parse Action Input as JSON. Received:\n```\n{raw}\n```\n"
                f"Please output valid JSON in the Action Input block.")
    return None
