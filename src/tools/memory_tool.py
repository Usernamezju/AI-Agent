"""Memory tools — allow the Agent to explicitly store and recall long-term facts."""
from __future__ import annotations
import json
from .base import BaseTool


class MemoryStoreTool(BaseTool):
    """Tool that lets the Agent save important information to long-term memory."""

    name = "memory_store"
    description = (
        "将重要信息存入长期记忆，供未来对话使用。"
        "当用户明确要求「记住」「存储」「记录」某件事时调用。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "要记住的事实或信息，一句话描述。",
            }
        },
        "required": ["content"],
    }

    def __init__(self, ltm, llm_client) -> None:
        self._ltm = ltm
        self._llm = llm_client

    def run(self, content: str) -> str:
        fact_id = self._ltm.add_fact(content)
        self._ltm.save()
        self._ltm.deduplicate(self._llm)
        self._ltm.save()
        return json.dumps(
            {"success": True, "stored": content, "id": fact_id[:8]},
            ensure_ascii=False,
        )


class MemoryRecallTool(BaseTool):
    """Tool that lets the Agent read back all stored long-term memories."""

    name = "memory_recall"
    description = (
        "读取所有长期记忆条目。"
        "当用户询问「你记得什么」「我之前说过什么」时调用。"
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, ltm) -> None:
        self._ltm = ltm

    def run(self) -> str:
        facts = self._ltm.get_all_facts()
        if not facts:
            return json.dumps({"facts": [], "message": "暂无长期记忆"}, ensure_ascii=False)
        return json.dumps(
            {"facts": [f["content"] for f in facts]},
            ensure_ascii=False,
        )
