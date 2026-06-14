"""Executor — runs sub-tasks in topological order with parallel execution."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from config.settings import settings
from .models import SubTask, ExecutionPlan


class Executor:
    """Topological scheduler that executes independent sub-tasks concurrently.

    Each sub-task gets its own fresh Agent instance so that MessageQueue
    and ConversationHistory are isolated.
    """

    def __init__(self, llm_provider: str | None = None, max_workers: int | None = None) -> None:
        self._provider = llm_provider
        self._max_workers = max_workers or settings.MULTI_AGENT_MAX_WORKERS

    # ------------------------------------------------------------------
    def run(self, plan: ExecutionPlan, event_queue=None) -> ExecutionPlan:
        """Execute all tasks in *plan*, respecting dependency order.

        Parameters
        ----------
        event_queue : queue.Queue | None
            When provided, ``{"type": "task_start"/"task_done", ...}``
            dicts are pushed for real-time streaming consumers.
        """
        while not plan.all_done():
            ready = plan.ready_tasks()
            if not ready:
                # Deadlock protection — no ready tasks but not all done
                break

            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                futures = {}
                for task in ready:
                    task.status = "running"
                    if event_queue:
                        event_queue.put({
                            "type": "task_start",
                            "task_id": task.id,
                            "description": task.description,
                        })
                    fut = pool.submit(self._run_task, task, plan)
                    futures[fut] = task

                for fut in as_completed(futures):
                    task = futures[fut]
                    try:
                        result = fut.result()
                        task.result = result
                        task.status = "done"
                    except Exception as exc:
                        task.result = f"Error: {exc}"
                        task.status = "error"

                    if event_queue:
                        event_queue.put({
                            "type": "task_done",
                            "task_id": task.id,
                            "status": task.status,
                            "result": task.result,
                        })

        return plan

    # ------------------------------------------------------------------
    def _run_task(self, task: SubTask, plan: ExecutionPlan) -> str:
        """Execute a single sub-task with a fresh Agent."""
        from src.core import Agent  # lazy import to avoid circular deps

        query = task.description

        # Inject dependency results as context
        if task.depends_on:
            deps_info: list[str] = []
            for dep_id in task.depends_on:
                dep = plan.get_task(dep_id)
                if dep and dep.result:
                    deps_info.append(f"- {dep_id} 的结果：{dep.result}")
            if deps_info:
                query = f"{query}\n\n已知信息：\n" + "\n".join(deps_info)

        agent = Agent(provider=self._provider, is_sub_agent=True)
        return agent.run(query)
