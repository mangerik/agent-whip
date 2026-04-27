"""
Handover data models for AgentWhip.

Defines data structures for handover between workers.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict


class DecisionRecord(BaseModel):
    """Record of a decision made during execution."""

    timestamp: datetime
    topic: str
    decision: str
    rationale: str
    alternatives: list[str] = field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


@dataclass
class HandoverContext:
    """
    Context passed from one worker to another during handover.

    Contains all necessary information for a new worker to continue
    the work without losing context.
    """

    handover_id: str
    timestamp: datetime

    # Project context
    project_name: str
    project_path: str

    # Execution context
    current_phase: str
    current_task: str
    phase_progress: float  # 0.0 - 1.0

    # Work summary
    work_summary: str  # AI-generated or structured summary
    tasks_completed: list[str]  # Task IDs
    tasks_pending: list[str]  # Task IDs
    tasks_failed: list[str]  # Task IDs

    # Artifacts
    files_created: list[str]
    files_modified: list[str]
    decisions_made: list[DecisionRecord]

    # Context snapshot (compact)
    context_snapshot: dict  # Compact state dict

    # Metadata
    from_worker_id: str
    to_worker_id: Optional[str] = None
    tokens_used: int = 0
    session_duration: float = 0.0

    # Reason for handover
    handover_reason: str = "token_threshold"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "handover_id": self.handover_id,
            "timestamp": self.timestamp.isoformat(),
            "project_name": self.project_name,
            "project_path": self.project_path,
            "current_phase": self.current_phase,
            "current_task": self.current_task,
            "phase_progress": self.phase_progress,
            "work_summary": self.work_summary,
            "tasks_completed": self.tasks_completed,
            "tasks_pending": self.tasks_pending,
            "tasks_failed": self.tasks_failed,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "decisions_made": [d.model_dump() for d in self.decisions_made],
            "context_snapshot": self.context_snapshot,
            "from_worker_id": self.from_worker_id,
            "to_worker_id": self.to_worker_id,
            "tokens_used": self.tokens_used,
            "session_duration": self.session_duration,
            "handover_reason": self.handover_reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HandoverContext":
        """Create from dictionary."""
        return cls(
            handover_id=data["handover_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            project_name=data["project_name"],
            project_path=data["project_path"],
            current_phase=data["current_phase"],
            current_task=data["current_task"],
            phase_progress=data["phase_progress"],
            work_summary=data["work_summary"],
            tasks_completed=data["tasks_completed"],
            tasks_pending=data["tasks_pending"],
            tasks_failed=data["tasks_failed"],
            files_created=data["files_created"],
            files_modified=data["files_modified"],
            decisions_made=[
                DecisionRecord(**d) for d in data.get("decisions_made", [])
            ],
            context_snapshot=data["context_snapshot"],
            from_worker_id=data["from_worker_id"],
            to_worker_id=data.get("to_worker_id"),
            tokens_used=data.get("tokens_used", 0),
            session_duration=data.get("session_duration", 0.0),
            handover_reason=data.get("handover_reason", "token_threshold"),
        )


@dataclass
class HandoverResult:
    """Result of a handover operation."""

    success: bool
    handover_id: str

    from_worker_id: str
    to_worker_id: str

    context_summary: str
    tokens_preserved: int  # Estimated tokens in summary

    timestamp: datetime
    duration_ms: float

    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "handover_id": self.handover_id,
            "from_worker_id": self.from_worker_id,
            "to_worker_id": self.to_worker_id,
            "context_summary": self.context_summary,
            "tokens_preserved": self.tokens_preserved,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class HandoverRecord:
    """Record of a handover in the context document."""

    handover_id: str
    timestamp: datetime

    from_worker: str
    to_worker: str

    reason: str
    context_summary: str

    # Token info
    tokens_used_before: int
    tokens_preserved: int

    # Duration
    handover_duration_ms: float

    # Status
    success: bool
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "handover_id": self.handover_id,
            "timestamp": self.timestamp.isoformat(),
            "from_worker": self.from_worker,
            "to_worker": self.to_worker,
            "reason": self.reason,
            "context_summary": self.context_summary,
            "tokens_used_before": self.tokens_used_before,
            "tokens_preserved": self.tokens_preserved,
            "handover_duration_ms": self.handover_duration_ms,
            "success": self.success,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HandoverRecord":
        """Create from dictionary."""
        return cls(
            handover_id=data["handover_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            from_worker=data["from_worker"],
            to_worker=data["to_worker"],
            reason=data["reason"],
            context_summary=data["context_summary"],
            tokens_used_before=data["tokens_used_before"],
            tokens_preserved=data["tokens_preserved"],
            handover_duration_ms=data["handover_duration_ms"],
            success=data["success"],
            error=data.get("error"),
        )


def generate_handover_id() -> str:
    """Generate a unique handover ID."""
    now = datetime.now(timezone.utc)
    prefix = f"ho_{now.strftime('%Y%m%d_%H%M%S')}"
    unique_suffix = uuid4().hex[:8]
    return f"{prefix}_{unique_suffix}"
