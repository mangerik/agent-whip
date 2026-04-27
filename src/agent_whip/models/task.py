"""
Task models for AgentWhip.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    """Status of a task in execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class Task(BaseModel):
    """A task to be executed."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(description="Unique task identifier")
    phase: str = Field(description="Phase name this task belongs to")
    phase_number: int = Field(description="Phase number (1-indexed)")
    description: str = Field(description="Task description")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current status")
    dependencies: list[str] = Field(default_factory=list, description="List of task IDs this task depends on")
    context: list[str] = Field(default_factory=list, description="Additional context lines")
    attempts: int = Field(default=0, description="Number of execution attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = Field(default=None, description="When task started")
    completed_at: Optional[datetime] = Field(default=None, description="When task completed")

    # Result
    result: Optional["TaskResult"] = Field(default=None, description="Execution result")


class TaskResult(BaseModel):
    """Result of a task execution."""

    model_config = ConfigDict(use_enum_values=True)

    success: bool = Field(description="Whether the task succeeded")
    output: str = Field(default="", description="Task output/logs")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    artifacts: list[str] = Field(default_factory=list, description="Files/paths created")
    code_changes: dict[str, str] = Field(
        default_factory=dict,
        description="Files that were changed {path: diff}"
    )

    # Execution metadata
    duration_seconds: float = Field(default=0.0, description="Execution duration")
    worker_used: str = Field(default="", description="Which worker executed this")
    model_used: str = Field(default="", description="AI model used")

    # Token usage (optional, for handover tracking)
    usage: Optional[dict] = Field(
        default=None,
        description="Token usage info {input_tokens, output_tokens, total_tokens}"
    )


# Update forward references
Task.model_rebuild()
