"""
Worker base classes for AgentWhip.
"""

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field

from agent_whip.models.handover import HandoverContext
from agent_whip.models.task import Task, TaskResult, TaskStatus

if TYPE_CHECKING:
    from agent_whip.events import EventEmitter
    from agent_whip.workers.token_tracker import TokenTracker


class WorkerConfig(BaseModel):
    """Base configuration for a worker."""

    name: str = Field(description="Worker name")
    api_key: str = Field(description="API key")
    model: str = Field(default="", description="Model identifier")
    max_concurrent: int = Field(default=1, description="Max concurrent tasks")
    timeout: int = Field(default=600, description="Task timeout in seconds")


class Worker(ABC):
    """
    Abstract base class for AI workers.

    Workers execute tasks by interacting with AI APIs (Claude, OpenCode, etc.).
    """

    def __init__(
        self,
        config: WorkerConfig,
        project_path: Path,
        handover_context: Optional[HandoverContext] = None,
    ):
        """
        Initialize the worker.

        Args:
            config: Worker configuration
            project_path: Path to the project
            handover_context: Optional context from previous worker handover
        """
        self.config = config
        self.project_path = project_path
        self._current_task: Optional[Task] = None
        self._handover_context: Optional[HandoverContext] = handover_context

        # Handover support (will be set by WorkerManager)
        self._token_tracker: Optional["TokenTracker"] = None
        self._event_emitter: Optional["EventEmitter"] = None

    @property
    def name(self) -> str:
        """Get worker name."""
        return self.config.name

    @property
    def worker_id(self) -> str:
        """Get unique worker ID."""
        return f"{self.name}_{id(self)}"

    @property
    def has_handover_context(self) -> bool:
        """Check if worker has handover context."""
        return self._handover_context is not None

    def set_token_tracker(self, token_tracker: "TokenTracker") -> None:
        """Set the token tracker for this worker."""
        self._token_tracker = token_tracker

    def set_event_emitter(self, event_emitter: "EventEmitter") -> None:
        """Set the event emitter for this worker."""
        self._event_emitter = event_emitter

    @abstractmethod
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute a task.

        Args:
            task: Task to execute

        Returns:
            TaskResult with execution outcome
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if worker is available to accept tasks."""
        pass

    async def execute_with_handover(self, task: Task) -> TaskResult:
        """
        Execute task with automatic handover when token threshold reached.

        This wraps the base execute method and:
        1. Tracks token usage
        2. Checks threshold after execution
        3. Emits handover event if needed

        Args:
            task: Task to execute

        Returns:
            TaskResult with execution outcome
        """
        result = await self.execute(task)

        # Track token usage if available
        if self._token_tracker and hasattr(result, "usage"):
            # Extract usage from result if available
            usage = getattr(result, "usage", None)
            if usage:
                input_tokens = getattr(usage, "input_tokens", 0)
                output_tokens = getattr(usage, "output_tokens", 0)
                self._token_tracker.record_usage(input_tokens, output_tokens)

        # Check if handover is needed
        if self._should_trigger_handover():
            await self._trigger_handover(task)

        return result

    def _should_trigger_handover(self) -> bool:
        """Check if handover should be triggered."""
        return (
            self._token_tracker is not None
            and self._token_tracker.should_trigger_handover()
        )

    async def _trigger_handover(self, task: Task) -> None:
        """
        Trigger handover to new worker.

        This emits an event that the orchestrator will handle.
        """
        if self._event_emitter:
            from agent_whip.events import EventType

            self._event_emitter.emit(
                EventType.WORKER_HANDOVER_REQUESTED,
                worker_id=self.worker_id,
                task_id=task.id,
                reason="token_threshold",
                usage=(
                    self._token_tracker.get_usage_stats().to_dict()
                    if self._token_tracker
                    else {}
                ),
            )

    def get_prompt_for_task(self, task: Task) -> str:
        """
        Build the prompt for a task.

        Args:
            task: Task to build prompt for

        Returns:
            Prompt string
        """
        prompt_parts = []

        # Add handover context if available
        if self._handover_context:
            prompt_parts.extend([
                "# Context from Previous Worker",
                "",
                f"You are continuing work from a previous worker that reached token limits.",
                f"**Project**: {self._handover_context.project_name}",
                f"**Current Phase**: {self._handover_context.current_phase}",
                f"**Current Task**: {self._handover_context.current_task}",
                "",
                "## Work Summary:",
                self._handover_context.work_summary,
                "",
                f"## Completed Tasks ({len(self._handover_context.tasks_completed)}):",
                ", ".join(self._handover_context.tasks_completed[:10]),
                (
                    "..." if len(self._handover_context.tasks_completed) > 10 else ""
                ),
                "",
                "## Artifacts Created:",
                "\n".join(f"  - {f}" for f in self._handover_context.files_created[:20]),
                "",
                "---",
                "",
            ])

        # Add current task
        prompt_parts.extend([
            f"# Task: {task.description}",
            f"Task ID: {task.id}",
            f"Phase: {task.phase}",
        ])

        # Add context from task
        if task.context:
            prompt_parts.append("\n## Context:")
            for ctx in task.context:
                prompt_parts.append(f"  {ctx}")

        # Add dependencies info
        if task.dependencies:
            prompt_parts.append("\n## Dependencies:")
            for dep_id in task.dependencies:
                prompt_parts.append(f"  - Completed: {dep_id}")

        prompt_parts.append("\n## Instructions:")
        prompt_parts.append("Execute this task and report back with:")
        prompt_parts.append("1. What you did")
        prompt_parts.append("2. Files changed (with paths)")
        prompt_parts.append("3. Success or failure")
        prompt_parts.append("4. Any errors encountered")

        return "\n".join(prompt_parts)

    def create_success_result(
        self,
        output: str,
        artifacts: list[str] | None = None,
        code_changes: dict[str, str] | None = None,
        duration: float = 0.0,
        usage: Optional["TokenUsage"] = None,
    ) -> TaskResult:
        """Create a successful task result."""
        return TaskResult(
            success=True,
            output=output,
            artifacts=artifacts or [],
            code_changes=code_changes or {},
            duration_seconds=duration,
            worker_used=self.name,
            model_used=self.config.model,
        )

    def create_failure_result(
        self,
        error: str,
        output: str = "",
        duration: float = 0.0,
    ) -> TaskResult:
        """Create a failed task result."""
        return TaskResult(
            success=False,
            output=output,
            error=error,
            artifacts=[],
            code_changes={},
            duration_seconds=duration,
            worker_used=self.name,
            model_used=self.config.model,
        )


class WorkerResult(BaseModel):
    """Result from a worker execution."""

    task_id: str
    result: TaskResult
    duration_seconds: float
    worker_name: str


class ExecutionError(Exception):
    """Exception raised when task execution fails."""

    def __init__(self, task_id: str, message: str):
        self.task_id = task_id
        self.message = message
        super().__init__(f"Task {task_id} failed: {message}")


class TimeoutError(ExecutionError):
    """Exception raised when task execution times out."""

    def __init__(self, task_id: str, timeout: int):
        super().__init__(task_id, f"Execution timed out after {timeout} seconds")
        self.timeout = timeout


# Import TokenUsage for type hint
class TokenUsage(BaseModel):
    """Token usage information."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
