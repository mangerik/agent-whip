"""
Execution state models for AgentWhip.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class ExecutionStatus(str, Enum):
    """Overall execution status."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class ExecutionState(BaseModel):
    """State of an execution run."""

    model_config = ConfigDict(use_enum_values=True)

    # Project info
    project_name: str = Field(description="Project name")
    project_path: str = Field(description="Absolute path to project")
    plan_path: str = Field(description="Path to plan.md")

    # Execution status
    status: ExecutionStatus = Field(default=ExecutionStatus.IDLE)
    current_phase: Optional[str] = Field(default=None, description="Currently executing phase")
    current_task: Optional[str] = Field(default=None, description="Currently executing task ID")

    # Progress tracking
    total_phases: int = Field(default=0, description="Total number of phases")
    completed_phases: int = Field(default=0, description="Number of completed phases")
    total_tasks: int = Field(default=0, description="Total number of tasks")
    completed_tasks: int = Field(default=0, description="Number of completed tasks")
    failed_tasks: int = Field(default=0, description="Number of failed tasks")
    skipped_tasks: int = Field(default=0, description="Number of skipped tasks")

    # Timestamps
    created_at: datetime = Field(default_factory=_utcnow)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    last_updated: datetime = Field(default_factory=_utcnow)

    # Additional metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    error_message: Optional[str] = Field(default=None, description="Error if failed")

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100

    @property
    def is_complete(self) -> bool:
        """Check if execution is complete."""
        return self.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.ABORTED)

    @property
    def is_running(self) -> bool:
        """Check if execution is currently running."""
        return self.status == ExecutionStatus.RUNNING

    def mark_started(self):
        """Mark execution as started."""
        self.status = ExecutionStatus.RUNNING
        self.started_at = _utcnow()
        self.last_updated = _utcnow()

    def mark_completed(self):
        """Mark execution as completed."""
        self.status = ExecutionStatus.COMPLETED
        self.completed_at = _utcnow()
        self.last_updated = _utcnow()

    def mark_failed(self, error: str):
        """Mark execution as failed."""
        self.status = ExecutionStatus.FAILED
        self.error_message = error
        self.completed_at = _utcnow()
        self.last_updated = _utcnow()

    def mark_aborted(self, error: str):
        """Mark execution as aborted."""
        self.status = ExecutionStatus.ABORTED
        self.error_message = error
        self.completed_at = _utcnow()
        self.last_updated = _utcnow()

    def increment_completed(self):
        """Increment completed tasks counter."""
        self.completed_tasks += 1
        self.last_updated = _utcnow()

    def increment_failed(self):
        """Increment failed tasks counter."""
        self.failed_tasks += 1
        self.last_updated = _utcnow()

    def increment_skipped(self):
        """Increment skipped tasks counter."""
        self.skipped_tasks += 1
        self.last_updated = _utcnow()

    def set_current_task(self, task_id: str, phase: str):
        """Set current executing task."""
        self.current_task = task_id
        self.current_phase = phase
        self.last_updated = _utcnow()


class PhaseState(BaseModel):
    """State of a single phase."""

    model_config = ConfigDict(use_enum_values=True)

    name: str = Field(description="Phase name (e.g., 'Phase 1: Setup')")
    number: int = Field(description="Phase number")
    description: Optional[str] = Field(default=None, description="Phase description")

    # Task tracking
    task_ids: list[str] = Field(default_factory=list, description="Task IDs in this phase")
    completed_tasks: int = Field(default=0, description="Completed tasks in this phase")
    total_tasks: int = Field(default=0, description="Total tasks in this phase")

    # Status
    status: ExecutionStatus = Field(default=ExecutionStatus.IDLE)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    # QA results
    qa_passed: Optional[bool] = Field(default=None, description="QA test results")
    qa_results: Optional[dict[str, Any]] = Field(default=None, description="Detailed QA results")

    @property
    def is_complete(self) -> bool:
        """Check if phase is complete."""
        return self.completed_tasks >= self.total_tasks and self.total_tasks > 0
