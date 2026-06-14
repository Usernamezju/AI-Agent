"""Data structures for the multi-agent system."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class SubTask:
    """A single sub-task within an execution plan."""
    id: str                                            # "t1", "t2", ...
    description: str                                   # what this sub-task needs to accomplish
    depends_on: list[str] = field(default_factory=list)  # ids of tasks that must finish first
    result: str = ""                                   # filled after execution
    status: str = "pending"                            # pending / running / done / error


@dataclass
class ExecutionPlan:
    """A full plan of sub-tasks with metadata and helper methods."""
    original_query: str
    tasks: list[SubTask] = field(default_factory=list)
    final_answer: str = ""

    # ------------------------------------------------------------------
    def get_task(self, task_id: str) -> SubTask | None:
        """Look up a task by id, or None if not found."""
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    # ------------------------------------------------------------------
    def all_done(self) -> bool:
        """True when every task has status 'done' (errors count as done)."""
        return all(t.status in ("done", "error") for t in self.tasks)

    # ------------------------------------------------------------------
    def ready_tasks(self) -> list[SubTask]:
        """Return pending tasks whose dependencies are all satisfied."""
        ready: list[SubTask] = []
        for t in self.tasks:
            if t.status != "pending":
                continue
            deps_met = True
            for dep_id in t.depends_on:
                dep = self.get_task(dep_id)
                if dep is None or dep.status not in ("done", "error"):
                    deps_met = False
                    break
            if deps_met:
                ready.append(t)
        return ready
