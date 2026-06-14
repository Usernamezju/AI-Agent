"""Planner — uses LLM to decompose a complex user query into an ExecutionPlan."""
from __future__ import annotations
import json
import re
from .models import SubTask, ExecutionPlan


class Planner:
    """LLM-based task planner that splits a query into dependent sub-tasks."""

    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    # ------------------------------------------------------------------
    def plan(self, user_query: str, tool_descriptions: str) -> ExecutionPlan:
        """Analyse *user_query* and return an ExecutionPlan.

        Graceful degradation: if the LLM response cannot be parsed, a
        single-task plan wrapping the original query is returned.
        """
        prompt = self._build_prompt(user_query, tool_descriptions)
        messages = [{"role": "user", "content": prompt}]

        try:
            raw = self._llm.chat(messages, temperature=0.2, max_tokens=2048)
            return self._parse(raw, user_query)
        except Exception:
            return self._single_task_plan(user_query)

    # ------------------------------------------------------------------
    def _build_prompt(self, user_query: str, tool_descriptions: str) -> str:
        return (
            "你是一个任务规划器。请将用户的复杂任务拆解为有依赖关系的子任务列表。\n\n"
            f"可用工具：\n{tool_descriptions}\n\n"
            "要求：\n"
            "- 每个子任务需能被单个 Agent 在几步内完成。\n"
            "- 无依赖的任务会被并行执行，有依赖的串行。\n"
            "- 最后一个任务通常是汇总前面结果的综合任务。\n"
            "- 如果任务简单无需拆分，直接返回单个任务。\n"
            "- 只返回 JSON，不要其他任何文字。\n\n"
            "JSON 格式：\n"
            '{"tasks": [\n'
            '  {"id": "t1", "description": "搜索X的定义", "depends_on": []},\n'
            '  {"id": "t2", "description": "根据t1的结果计算Y", "depends_on": ["t1"]}\n'
            "]}\n\n"
            f"用户任务：{user_query}"
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _parse(raw: str, user_query: str) -> ExecutionPlan:
        """Parse LLM JSON response into an ExecutionPlan. Falls back to single-task."""
        text = raw.strip()

        # Strip markdown fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        # Parse
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try extracting JSON object with regex
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group())
                except json.JSONDecodeError:
                    return Planner._single_task_plan(user_query)
            else:
                return Planner._single_task_plan(user_query)

        tasks_raw = data.get("tasks", [])
        if not isinstance(tasks_raw, list) or len(tasks_raw) == 0:
            return Planner._single_task_plan(user_query)

        tasks: list[SubTask] = []
        for raw_t in tasks_raw:
            tasks.append(SubTask(
                id=str(raw_t.get("id", "")),
                description=str(raw_t.get("description", "")),
                depends_on=[str(d) for d in raw_t.get("depends_on", [])],
            ))

        if not tasks:
            return Planner._single_task_plan(user_query)

        return ExecutionPlan(original_query=user_query, tasks=tasks)

    # ------------------------------------------------------------------
    @staticmethod
    def _single_task_plan(user_query: str) -> ExecutionPlan:
        return ExecutionPlan(
            original_query=user_query,
            tasks=[SubTask(id="t1", description=user_query, depends_on=[])],
        )
