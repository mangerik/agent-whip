"""
Progress Tracker (Tukang Cambuk) for AgentWhip.

Evaluates task completion and decides next actions.
"""

import time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from agent_whip.config import AgentWhipConfig
from agent_whip.models.plan import ExecutionPlan
from agent_whip.models.state import ExecutionState, ExecutionStatus
from agent_whip.models.task import Task, TaskResult, TaskStatus


class NextAction(str, Enum):
    """Next action after task evaluation."""

    CONTINUE = "continue"  # Move to next task
    RETRY = "retry"  # Retry the same task
    SKIP = "skip"  # Skip this task
    ABORT = "abort"  # Abort entire execution
    RUN_QA = "run_qa"  # Run QA tests
    COMPLETE = "complete"  # Execution complete


class RetryStrategy(BaseModel):
    """Retry strategy configuration."""

    max_attempts: int = Field(default=3, description="Maximum retry attempts")
    base_delay: float = Field(default=1.0, description="Base delay in seconds")
    max_delay: float = Field(default=60.0, description="Maximum delay in seconds")
    exponential_backoff: bool = Field(default=True, description="Use exponential backoff")

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt."""
        if self.exponential_backoff:
            delay = self.base_delay * (2 ** attempt)
        else:
            delay = self.base_delay * (attempt + 1)

        return min(delay, self.max_delay)


class ProgressTracker(BaseModel):
    """
    Tracks execution progress and decides next actions.

    This is the "Tukang Cambuk" that ensures tasks keep moving.
    """

    config: AgentWhipConfig = Field(description="AgentWhip configuration")
    plan: ExecutionPlan = Field(description="Execution plan")
    state: ExecutionState = Field(description="Current execution state")

    # Private fields
    _retry_counts: dict[str, int] = PrivateAttr(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def create(
        cls,
        config: AgentWhipConfig,
        plan: ExecutionPlan,
    ) -> "ProgressTracker":
        """Create a new progress tracker."""
        state = ExecutionState(
            project_name=plan.project_name,
            project_path=str(plan.source_path.parent),
            plan_path=str(plan.source_path),
            total_phases=plan.total_phases,
            total_tasks=plan.total_tasks,
        )

        return cls(config=config, plan=plan, state=state)

    def evaluate_task_result(self, task: Task, result: TaskResult) -> NextAction:
        """
        Evaluate task result and decide next action.

        Args:
            task: The task that was executed
            result: The execution result

        Returns:
            NextAction to take
        """
        if result.success:
            return self._handle_success(task, result)
        else:
            return self._handle_failure(task, result)

    def _handle_success(self, task: Task, result: TaskResult) -> NextAction:
        """Handle successful task execution."""
        # Reset retry count
        if task.id in self._retry_counts:
            del self._retry_counts[task.id]

        # Check if phase is complete
        if self._is_phase_complete(task.phase):
            return NextAction.RUN_QA

        return NextAction.CONTINUE

    def _handle_failure(self, task: Task, result: TaskResult) -> NextAction:
        """Handle failed task execution."""
        retry_count = self._retry_counts.get(task.id, 0)
        max_retries = task.max_retries or self.config.execution.max_retries

        if retry_count < max_retries:
            # Increment retry count
            self._retry_counts[task.id] = retry_count + 1

            # Calculate delay
            strategy = RetryStrategy(
                max_attempts=max_retries,
                base_delay=self.config.execution.retry_delay,
            )
            delay = strategy.calculate_delay(retry_count)

            # Log retry decision
            self._log_retry(task, retry_count + 1, delay, result.error)

            return NextAction.RETRY

        # Max retries exceeded
        if self.config.execution.continue_on_error:
            self._log_skip(task, result.error)
            return NextAction.SKIP
        else:
            self._log_abort(task, result.error)
            return NextAction.ABORT

    def should_run_qa(self, phase_name: str) -> bool:
        """
        Check if QA should run for a phase.

        Args:
            phase_name: Phase to check

        Returns:
            True if QA should run
        """
        if not self.config.qa.enabled:
            return False

        if not self.config.qa.run_after_phase:
            return False

        # Check if phase is complete
        return self._is_phase_complete(phase_name)

    def _is_phase_complete(self, phase_name: str) -> bool:
        """Check if all tasks in a phase are complete."""
        phase_tasks = self.plan.get_tasks_for_phase(phase_name)

        for task in phase_tasks:
            if task.status not in (TaskStatus.COMPLETED, TaskStatus.SKIPPED):
                return False

        return True

    def is_execution_complete(self) -> bool:
        """Check if entire execution is complete."""
        return all(
            task.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
            for task in self.plan.tasks
        )

    def get_next_phase(self, current_phase: str) -> Optional[str]:
        """Get the next phase after current."""
        current_number = None

        # Find current phase number
        for phase in self.plan.phases:
            if phase.name == current_phase:
                current_number = phase.number
                break

        if current_number is None:
            return None

        # Get next phase
        return self.plan.get_phase_by_number(current_number + 1)

    def get_failed_dependencies(self, task_id: str) -> list[str]:
        """Get failed dependencies for a task."""
        task = self.plan.get_task(task_id)
        if not task:
            return []

        failed = []
        for dep_id in task.dependencies:
            dep_task = self.plan.get_task(dep_id)
            if dep_task and dep_task.status == TaskStatus.FAILED:
                failed.append(dep_id)

        return failed

    def can_proceed(self, task_id: str) -> tuple[bool, str]:
        """
        Check if a task can proceed.

        Returns:
            (can_proceed, reason)
        """
        task = self.plan.get_task(task_id)
        if not task:
            return False, "Task not found"

        # Check dependencies
        failed_deps = self.get_failed_dependencies(task_id)
        if failed_deps:
            return False, f"Dependencies failed: {', '.join(failed_deps)}"

        # Check if dependencies are complete
        incomplete_deps = []
        for dep_id in task.dependencies:
            dep_task = self.plan.get_task(dep_id)
            if dep_task and dep_task.status != TaskStatus.COMPLETED:
                incomplete_deps.append(dep_id)

        if incomplete_deps:
            return False, f"Dependencies not complete: {', '.join(incomplete_deps)}"

        return True, "OK"

    def get_progress_summary(self) -> dict:
        """Get progress summary."""
        completed = sum(1 for t in self.plan.tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.plan.tasks if t.status == TaskStatus.FAILED)
        skipped = sum(1 for t in self.plan.tasks if t.status == TaskStatus.SKIPPED)
        running = sum(1 for t in self.plan.tasks if t.status == TaskStatus.IN_PROGRESS)

        return {
            "total": self.plan.total_tasks,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "running": running,
            "pending": self.plan.total_tasks - completed - failed - skipped - running,
            "progress": (completed / self.plan.total_tasks * 100) if self.plan.total_tasks > 0 else 0,
        }

    def _log_retry(self, task: Task, attempt: int, delay: float, error: Optional[str]):
        """Log retry decision."""
        # TODO: Use proper logger
        print(f"[Tukang Cambuk] Retrying {task.id} (attempt {attempt}/{task.max_retries}) after {delay}s")
        if error:
            print(f"  Error: {error}")

    def _log_skip(self, task: Task, error: Optional[str]):
        """Log skip decision."""
        print(f"[Tukang Cambuk] Skipping {task.id} after max retries")
        if error:
            print(f"  Error: {error}")

    def _log_abort(self, task: Task, error: Optional[str]):
        """Log abort decision."""
        print(f"[Tukang Cambuk] Aborting execution due to {task.id} failure")
        if error:
            print(f"  Error: {error}")
