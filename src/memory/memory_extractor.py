"""Memory extractor — uses LLM to pull long-term-worthy facts from a dialogue turn."""
from __future__ import annotations
import json


class MemoryExtractor:
    """Single-purpose LLM caller that extracts persistent facts from a Q&A pair."""

    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    # ------------------------------------------------------------------
    def extract(self, user_query: str, final_answer: str) -> list[str]:
        """Ask the LLM to identify long-term-worthy facts from one turn.

        Returns a list of fact strings (may be empty).
        """
        prompt = (
            "你是一个记忆提取器。给定一段对话，判断其中是否包含值得长期记住的用户信息。\n"
            '"值得记住"的标准：用户的姓名/身份/偏好/明确要求记住的事情/对未来有用的背景信息。\n'
            "不值得记住：临时任务、一次性计算结果、当前时间查询等。\n\n"
            f"对话内容：\n用户：{user_query}\n助手：{final_answer}\n\n"
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
        import re
        m = re.search(r"\[.*?\]", text, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group())
                if isinstance(result, list):
                    return [str(item) for item in result if item]
            except json.JSONDecodeError:
                pass

        return []
