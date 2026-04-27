"""
Task queue for AgentWhip.

Manages task execution order based on dependencies.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from agent_whip.models.plan import ExecutionPlan
from agent_whip.models.task import Task, TaskStatus


class TaskQueue(BaseModel):
    """Queue for managing task execution order."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Task organization
    pending: set[str] = Field(default_factory=set, description="Pending task IDs")
    running: set[str] = Field(default_factory=set, description="Currently running task IDs")
    completed: set[str] = Field(default_factory=set, description="Completed task IDs")
    failed: set[str] = Field(default_factory=set, description="Failed task IDs")
    skipped: set[str] = Field(default_factory=set, description="Skipped task IDs")

    # Task lookup
    plan: ExecutionPlan = Field(description="Execution plan with all tasks")

    @classmethod
    def from_plan(cls, plan: ExecutionPlan) -> "TaskQueue":
        """Create a task queue from an execution plan."""
        queue = cls(plan=plan)

        # Initialize all tasks as pending
        for task in plan.tasks:
            queue.pending.add(task.id)

        return queue

    @classmethod
    def from_plan_state(cls, plan: ExecutionPlan) -> "TaskQueue":
        """
        Create a task queue from an execution plan with existing task statuses.

        This is used when resuming from saved state.
        """
        queue = cls(plan=plan)

        for task in plan.tasks:
            if task.status == TaskStatus.COMPLETED:
                queue.completed.add(task.id)
            elif task.status == TaskStatus.FAILED:
                queue.failed.add(task.id)
            elif task.status == TaskStatus.SKIPPED:
                queue.skipped.add(task.id)
            else:
                # Treat pending/retrying/in_progress as pending on resume.
                queue.pending.add(task.id)

        return queue

    def get_ready(self) -> list[Task]:
        """
        Get ONE task that is ready to execute.

        A task is ready if:
        1. It's pending
        2. All its dependencies are completed

        Returns:
            List with one ready task, or empty list if none ready
        """
        for task_id in list(self.pending):
            task = self.plan.get_task(task_id)
            if not task:
                continue

            # Check if all dependencies are satisfied
            deps_satisfied = all(
                dep_id in self.completed
                for dep_id in task.dependencies
            )

            if deps_satisfied:
                # Remove from pending and mark as running
                self.pending.remove(task_id)
                self.running.add(task_id)
                return [task]

        # No ready tasks
        return []

    def mark_running(self, task_id: str):
        """Mark a task as running."""
        if task_id in self.pending:
            self.pending.remove(task_id)
        self.running.add(task_id)

    def mark_completed(self, task_id: str):
        """Mark a task as completed."""
        if task_id in self.running:
            self.running.remove(task_id)
        self.completed.add(task_id)

    def mark_failed(self, task_id: str):
        """Mark a task as failed."""
        if task_id in self.running:
            self.running.remove(task_id)
        self.failed.add(task_id)

    def mark_skipped(self, task_id: str):
        """Mark a task as skipped."""
        if task_id in self.pending:
            self.pending.remove(task_id)
        elif task_id in self.running:
            self.running.remove(task_id)
        self.skipped.add(task_id)

    def requeue(self, task_id: str):
        """Re-queue a failed task for retry."""
        self.running.discard(task_id)
        self.failed.discard(task_id)
        self.pending.add(task_id)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.plan.get_task(task_id)

    @property
    def is_empty(self) -> bool:
        """Check if queue is empty (no pending or running tasks)."""
        return len(self.pending) == 0 and len(self.running) == 0

    @property
    def total_tasks(self) -> int:
        """Total number of tasks."""
        return self.plan.total_tasks

    @property
    def finished_tasks(self) -> int:
        """Number of finished tasks (completed + failed + skipped)."""
        return len(self.completed) + len(self.failed) + len(self.skipped)

    @property
    def progress_percentage(self) -> float:
        """Progress percentage."""
        if self.total_tasks == 0:
            return 0.0
        return (self.finished_tasks / self.total_tasks) * 100

    @property
    def has_failures(self) -> bool:
        """Check if there are any failed tasks."""
        return len(self.failed) > 0

    def get_blocked_tasks(self) -> list[Task]:
        """Get tasks that are blocked by incomplete dependencies."""
        blocked = []
        for task_id in self.pending:
            task = self.plan.get_task(task_id)
            if not task:
                continue

            # Check if any dependency is not completed
            blocked_deps = [
                dep_id for dep_id in task.dependencies
                if dep_id not in self.completed
            ]

            if blocked_deps:
                blocked.append(task)

        return blocked

    def get_summary(self) -> dict[str, int]:
        """Get queue summary."""
        return {
            "pending": len(self.pending),
            "running": len(self.running),
            "completed": len(self.completed),
            "failed": len(self.failed),
            "skipped": len(self.skipped),
            "total": self.total_tasks,
            "finished": self.finished_tasks,
            "progress": self.progress_percentage,
        }

    def can_complete(self) -> bool:
        """Check if all tasks can complete (no blocked by failed deps)."""
        for task_id in self.pending:
            task = self.plan.get_task(task_id)
            if not task:
                continue

            # Check if any dependency failed
            failed_deps = [
                dep_id for dep_id in task.dependencies
                if dep_id in self.failed
            ]

            if failed_deps:
                return False

        return True
