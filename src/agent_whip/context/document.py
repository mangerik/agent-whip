"""
Context Document for persistent context tracking.

Maintains a persistent log of all context changes, handovers,
and progress for the project.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from agent_whip.models import ExecutionState, ExecutionPlan, Task, TaskResult
from agent_whip.models.handover import HandoverRecord


class ContextEventType(str, Enum):
    """Types of context events."""

    EXECUTION_STARTED = "execution_started"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    HANDOVER_TRIGGERED = "handover_triggered"
    HANDOVER_COMPLETED = "handover_completed"
    HANDOVER_FAILED = "handover_failed"
    PHASE_COMPLETED = "phase_completed"
    DECISION_MADE = "decision_made"
    CONTEXT_UPDATED = "context_updated"


@dataclass
class ContextEvent:
    """An event in the context log."""

    event_type: ContextEventType
    timestamp: datetime
    data: dict
    event_id: str = None

    def __post_init__(self):
        if self.event_id is None:
            self.event_id = f"evt_{uuid4().hex[:12]}"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContextEvent":
        """Create from dictionary."""
        return cls(
            event_type=ContextEventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data=data["data"],
            event_id=data.get("event_id"),
        )


from dataclasses import dataclass


class ContextDocument:
    """
    Persistent document tracking all context changes.

    Maintains an append-only log of events, handover history,
    and decisions for the project.
    """

    DEFAULT_PATH = ".agent-whip/context.json"
    MAX_ENTRIES_DEFAULT = 1000

    def __init__(
        self,
        project_path: Path,
        document_path: Optional[Path] = None,
        max_entries: int = MAX_ENTRIES_DEFAULT,
    ):
        """
        Initialize context document.

        Args:
            project_path: Path to the project
            document_path: Path to the context document (default: .agent-whip/context.json)
            max_entries: Maximum number of log entries to keep
        """
        self.project_path = project_path
        self.document_path = document_path or project_path / self.DEFAULT_PATH
        self.max_entries = max_entries

        # Document data
        self.project_name: Optional[str] = None
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None
        self.current_phase: Optional[str] = None
        self.current_task: Optional[str] = None

        self.handovers: list[HandoverRecord] = []
        self.context_log: list[ContextEvent] = []
        self.decisions: list[dict] = []

        # Load existing if available
        self._load()

    def _ensure_directory(self) -> None:
        """Ensure the document directory exists."""
        self.document_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        """Load existing document from disk."""
        if not self.document_path.exists():
            return

        try:
            with open(self.document_path, "r") as f:
                data = json.load(f)

            self.project_name = data.get("project_name")
            self.created_at = (
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            )
            self.updated_at = (
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else None
            )
            self.current_phase = data.get("current_phase")
            self.current_task = data.get("current_task")

            # Load handovers
            for h in data.get("handovers", []):
                self.handovers.append(HandoverRecord.from_dict(h))

            # Load context log
            for e in data.get("context_log", []):
                self.context_log.append(ContextEvent.from_dict(e))

            # Load decisions
            self.decisions = data.get("decisions", [])

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Corrupted file, start fresh
            self.handovers = []
            self.context_log = []
            self.decisions = []

    def _persist(self) -> None:
        """Save document to disk."""
        self._ensure_directory()
        self.updated_at = datetime.now(timezone.utc)

        if not self.created_at:
            self.created_at = self.updated_at

        # Compact log if too large
        if len(self.context_log) > self.max_entries:
            self.context_log = self.context_log[-self.max_entries :]

        data = {
            "project_name": self.project_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "current_phase": self.current_phase,
            "current_task": self.current_task,
            "handovers": [h.to_dict() for h in self.handovers],
            "context_log": [e.to_dict() for e in self.context_log],
            "decisions": self.decisions,
        }

        with open(self.document_path, "w") as f:
            json.dump(data, f, indent=2)

    def initialize_from_plan(self, plan: ExecutionPlan) -> None:
        """Initialize document from execution plan."""
        self.project_name = plan.project_name
        self.created_at = datetime.now(timezone.utc)
        self._persist()

    def save_context_update(
        self, event_type: ContextEventType, data: dict
    ) -> None:
        """
        Append an event to the context log.

        Args:
            event_type: Type of event
            data: Event data
        """
        event = ContextEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            data=data,
        )
        self.context_log.append(event)

        # Update current state based on event
        if event_type == ContextEventType.TASK_STARTED:
            self.current_task = data.get("task_id")
        elif event_type == ContextEventType.HANDOVER_TRIGGERED:
            self.current_phase = data.get("phase", self.current_phase)

        self._persist()

    def append_handover(self, handover: HandoverRecord) -> None:
        """
        Append a handover record.

        Args:
            handover: Handover record to append
        """
        self.handovers.append(handover)
        self._persist()

    def append_task_completion(self, task_id: str, result: TaskResult) -> None:
        """
        Append a task completion record.

        Args:
            task_id: ID of completed task
            result: Task result
        """
        self.save_context_update(
            ContextEventType.TASK_COMPLETED,
            {
                "task_id": task_id,
                "success": result.success,
                "duration_seconds": result.duration_seconds,
                "worker": result.worker_used,
            },
        )

    def append_decision(
        self,
        topic: str,
        decision: str,
        rationale: str,
        alternatives: Optional[list[str]] = None,
    ) -> None:
        """
        Append a decision record.

        Args:
            topic: Topic of the decision
            decision: The decision made
            rationale: Rationale for the decision
            alternatives: Alternative options considered
        """
        decision_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "decision": decision,
            "rationale": rationale,
            "alternatives": alternatives or [],
        }
        self.decisions.append(decision_record)

        # Also log as event
        self.save_context_update(
            ContextEventType.DECISION_MADE,
            decision_record,
        )

    def get_current_context(self) -> dict:
        """
        Get full current context for a new worker.

        Returns:
            Dictionary with all current context
        """
        return {
            "project": {
                "name": self.project_name,
                "path": str(self.project_path),
            },
            "current": {
                "phase": self.current_phase,
                "task": self.current_task,
            },
            "progress": {
                "handovers": len(self.handovers),
                "total_events": len(self.context_log),
                "decisions": len(self.decisions),
            },
            "handovers": [h.to_dict() for h in self.handovers[-10:]],  # Last 10
            "recent_events": [
                e.to_dict() for e in self.context_log[-100:]
            ],  # Last 100
            "decisions": self.decisions[-20:],  # Last 20
        }

    def get_handover_history(self) -> list[HandoverRecord]:
        """Get all handover records."""
        return self.handovers.copy()

    def get_recent_events(
        self, limit: int = 50, event_type: Optional[ContextEventType] = None
    ) -> list[ContextEvent]:
        """
        Get recent events from the log.

        Args:
            limit: Maximum number of events to return
            event_type: Optional filter by event type

        Returns:
            List of recent events
        """
        events = self.context_log

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:]

    def update_current_state(
        self,
        state: ExecutionState,
    ) -> None:
        """
        Update current execution state.

        Args:
            state: Current execution state
        """
        self.project_name = state.project_name
        self.current_phase = state.current_phase
        self.current_task = state.current_task
        self._persist()

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "project_name": self.project_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "current_phase": self.current_phase,
            "current_task": self.current_task,
            "handovers": [h.to_dict() for h in self.handovers],
            "context_log": [e.to_dict() for e in self.context_log],
            "decisions": self.decisions,
        }

    def clear(self) -> None:
        """Clear all context data (for testing)."""
        self.handovers = []
        self.context_log = []
        self.decisions = []
        self.current_phase = None
        self.current_task = None
        self._persist()
