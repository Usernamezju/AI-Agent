"""Orchestrator — top-level coordinator: plan → execute → synthesize."""
from __future__ import annotations
import queue
import threading
from typing import Generator
from src.llm import create_llm_client
from src.tools import register_all_tools, tool_registry
from .models import ExecutionPlan
from .planner import Planner
from .executor import Executor


class Orchestrator:
    """Coordinates the multi-agent pipeline for a single user query.

    Usage::

        orch = Orchestrator()
        # Blocking
        result = orch.run("比较中美两国2023年GDP")
        print(result["final_answer"])

        # Streaming (for UI)
        for event in orch.run_stream("比较中美两国2023年GDP"):
            print(event)
    """

    def __init__(self, provider: str | None = None) -> None:
        register_all_tools()
        self._provider = provider
        self._llm = create_llm_client(provider)
        self._tool_desc = tool_registry.generate_descriptions()
        self._planner = Planner(self._llm)
        self._executor = Executor(provider)

    # ------------------------------------------------------------------
    # Blocking API
    # ------------------------------------------------------------------

    def run(self, user_query: str) -> dict:
        """Execute the full pipeline and return ``{"plan": ..., "final_answer": ...}``.

        If the planner produces a single-task plan, the executor call is
        skipped and the single Agent's result becomes the final answer
        directly (degraded single-agent path).
        """
        plan = self._planner.plan(user_query, self._tool_desc)

        # Single-task degradation — skip executor overhead
        if len(plan.tasks) == 1 and plan.tasks[0].depends_on == []:
            from src.core import Agent  # lazy import
            agent = Agent(provider=self._provider, is_sub_agent=True)
            plan.tasks[0].status = "done"
            plan.tasks[0].result = agent.run(plan.tasks[0].description)
            plan.final_answer = plan.tasks[0].result
        else:
            plan = self._executor.run(plan)
            plan.final_answer = self._synthesize(user_query, plan)

        return {"plan": plan, "final_answer": plan.final_answer}

    # ------------------------------------------------------------------
    # Streaming API (for UI)
    # ------------------------------------------------------------------

    def run_stream(self, user_query: str) -> Generator[dict, None, None]:
        """Generator that yields events for real-time UI rendering.

        Events yielded::

            {"type": "plan",    "tasks": [...]}
            {"type": "task_start", "task_id": "t1", "description": "..."}
            {"type": "task_done",  "task_id": "t1", "status": "done", "result": "..."}
            {"type": "finished",   "answer": "..."}
        """
        plan = self._planner.plan(user_query, self._tool_desc)

        # Emit plan event
        yield {
            "type": "plan",
            "tasks": [
                {"id": t.id, "description": t.description,
                 "depends_on": t.depends_on, "status": t.status}
                for t in plan.tasks
            ],
        }

        # Single-task degradation
        if len(plan.tasks) == 1 and plan.tasks[0].depends_on == []:
            from src.core import Agent
            task = plan.tasks[0]
            yield {"type": "task_start", "task_id": task.id, "description": task.description}
            agent = Agent(provider=self._provider, is_sub_agent=True)
            task.result = agent.run(task.description)
            task.status = "done"
            yield {"type": "task_done", "task_id": task.id, "status": "done", "result": task.result}
            plan.final_answer = task.result
        else:
            # Execute in background thread, collect events via queue
            event_queue: queue.Queue = queue.Queue()

            def _execute() -> None:
                self._executor.run(plan, event_queue)
                event_queue.put(None)  # sentinel

            thread = threading.Thread(target=_execute, daemon=True)
            thread.start()

            while True:
                event = event_queue.get()
                if event is None:
                    break
                yield event

            thread.join()

            plan.final_answer = self._synthesize(user_query, plan)

        yield {"type": "finished", "answer": plan.final_answer}

    # ------------------------------------------------------------------
    def _synthesize(self, original_query: str, plan: ExecutionPlan) -> str:
        """Merge all sub-task results into a coherent final answer."""
        results_text = ""
        for t in plan.tasks:
            results_text += f"[{t.id}] {t.description}\n结果：{t.result}\n\n"

        prompt = (
            f"用户的原始问题是：{original_query}\n\n"
            f"各子任务的执行结果如下：\n{results_text}\n"
            "请根据以上所有结果，给出完整、连贯的最终回答。"
        )

        messages = [{"role": "user", "content": prompt}]
        try:
            return self._llm.chat(messages, temperature=0.5, max_tokens=1024)
        except Exception:
            # Fallback: concatenate results
            return "\n\n".join(f"[{t.id}] {t.result}" for t in plan.tasks)
