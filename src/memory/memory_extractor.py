"""Memory extractor — uses LLM to pull long-term-worthy facts from a dialogue turn."""
from __future__ import annotations
import json
import re


class MemoryExtractor:
    """Single-purpose LLM caller that extracts persistent facts from a Q&A pair."""

    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    # ------------------------------------------------------------------
    def extract(self, user_query: str, final_answer: str,
                existing_facts: list[str] | None = None) -> list[str]:
        """Ask the LLM to identify long-term-worthy facts from one turn.

        *existing_facts* (when provided) are listed in the prompt so the LLM
        can avoid re-extracting information that is already stored.

        Returns a list of fact strings (may be empty).  Facts that contradict
        an existing memory are prefixed with ``[UPDATE]``.
        """
        existing_block = ""
        if existing_facts:
            lines = ["已有记忆（请勿重复提取）："]
            for f in existing_facts:
                lines.append(f"- {f}")
            existing_block = "\n".join(lines) + "\n\n"

        prompt = (
            "你是一个记忆提取器。给定一段对话，判断其中是否包含值得长期记住的用户信息。\n"
            '"值得记住"的标准：用户的姓名/身份/偏好/明确要求记住的事情/对未来有用的背景信息。\n'
            "不值得记住：临时任务、一次性计算结果、当前时间查询等。\n\n"
            f"{existing_block}"
            f"新增对话：\n用户：{user_query}\n助手：{final_answer}\n\n"
            "规则：\n"
            "- 如果新对话中的信息已在「已有记忆」中体现，不要再提取。\n"
            "- 如果新信息与已有记忆矛盾（如名字不同），只提取更新后的值，\n"
            "  并在内容前加 [UPDATE] 前缀，调用方负责替换旧条目。\n"
            "- 如果是全新信息，正常提取。\n\n"
            "请以 JSON 数组返回提取到的事实列表（每条不超过 50 字），\n"
            "如果没有值得记住的信息，返回空数组 []。\n"
            "只返回 JSON，不要其他文字。\n"
            '格式：["事实1", "事实2"]'
        )

        messages = [{"role": "user", "content": prompt}]
        try:
            raw = self._llm.chat(messages, temperature=0.1, max_tokens=600)
        except Exception:
            return []

        return self._parse(raw)

    # ------------------------------------------------------------------
    def deduplicate(self, facts: list[str]) -> list[str]:
        """Ask the LLM to merge semantically similar entries, keeping
        the more complete version.  Returns the merged list.

        A low temperature (0.1) ensures deterministic output.
        When *facts* has fewer than 2 items no LLM call is made.
        """
        if len(facts) < 2:
            return list(facts)

        facts_json = json.dumps(facts, ensure_ascii=False)
        prompt = (
            "以下是记忆列表，请合并语义重复的条目，保留信息更完整的那条，\n"
            "输出合并后的列表（JSON 数组，每条不超过 50 字）。\n"
            "只返回 JSON，不要其他内容。\n\n"
            f"{facts_json}"
        )

        messages = [{"role": "user", "content": prompt}]
        try:
            raw = self._llm.chat(messages, temperature=0.1, max_tokens=600)
            result = self._parse(raw)
            if result:
                return result
        except Exception:
            pass

        return list(facts)

    # ------------------------------------------------------------------
    @staticmethod
    def _parse(raw: str) -> list[str]:
        """Robustly parse the LLM JSON response. Returns [] on any failure."""
        text = raw.strip()

        # Try direct JSON parse first
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return [str(item) for item in result if item]
        except json.JSONDecodeError:
            pass

        # Try extracting a JSON array from within the text
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group())
                if isinstance(result, list):
                    return [str(item) for item in result if item]
            except json.JSONDecodeError:
                pass

        return []
