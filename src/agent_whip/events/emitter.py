"""
Event System for AgentWhip.

Emits and handles events during execution.
"""

from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from agent_whip.models.task import Task, TaskResult


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class EventType(str, Enum):
    """Types of events."""

    # Execution events
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_PAUSED = "execution_paused"
    EXECUTION_RESUMED = "execution_resumed"

    # Phase events
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"

    # Task events
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_RETRYING = "task_retrying"
    TASK_SKIPPED = "task_skipped"

    # QA events
    QA_STARTED = "qa_started"
    QA_COMPLETED = "qa_completed"
    QA_FAILED = "qa_failed"

    # State events
    STATE_SAVED = "state_saved"
    STATE_LOADED = "state_loaded"

    # Handover events
    HANDOVER_TRIGGERED = "handover_triggered"
    HANDOVER_COMPLETED = "handover_completed"
    HANDOVER_FAILED = "handover_failed"
    WORKER_HANDOVER_REQUESTED = "worker_handover_requested"

    # Token events
    TOKEN_THRESHOLD_REACHED = "token_threshold_reached"
    TOKEN_USAGE_UPDATED = "token_usage_updated"

    # Context events
    CONTEXT_UPDATED = "context_updated"


class Event(BaseModel):
    """An event emitted during execution."""

    type: EventType = Field(description="Event type")
    timestamp: datetime = Field(default_factory=_utcnow)
    data: dict[str, Any] = Field(default_factory=dict, description="Event data")


class EventHandler(BaseModel):
    """Handler for events."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    event_type: EventType
    handler: Callable[[Event], None]
    once: bool = Field(default=False, description="Remove after first call")


class EventEmitter(BaseModel):
    """
    Emits events to registered handlers.

    Provides pub/sub pattern for execution events.
    """

    # Private fields
    _handlers: dict[EventType, list[EventHandler]] = PrivateAttr(
        default_factory=lambda: defaultdict(list)
    )
    _history: list[Event] = PrivateAttr(default_factory=list)
    _max_history: int = PrivateAttr(default=1000)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def on(self, event_type: EventType, handler: Callable[[Event], None]) -> Callable:
        """
        Register an event handler.

        Can be used as decorator:

            @emitter.on(EventType.TASK_COMPLETED)
            def handle_task_completed(event):
                print(f"Task {event.data['task_id']} completed")
        """
        event_handler = EventHandler(event_type=event_type, handler=handler)
        self._handlers[event_type].append(event_handler)

        return handler

    def once(self, event_type: EventType, handler: Callable[[Event], None]) -> Callable:
        """
        Register a one-time event handler.

        Handler is removed after first call.
        """
        event_handler = EventHandler(event_type=event_type, handler=handler, once=True)
        self._handlers[event_type].append(event_handler)

        return handler

    def off(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Remove an event handler."""
        handlers = self._handlers.get(event_type, [])
        self._handlers[event_type] = [h for h in handlers if h.handler != handler]

    def emit(self, event_type: EventType, **data) -> None:
        """
        Emit an event.

        Args:
            event_type: Type of event to emit
            **data: Event data
        """
        event = Event(type=event_type, data=data)

        # Add to history
        self._add_to_history(event)

        # Call handlers
        handlers = self._handlers.get(event_type, []).copy()
        to_remove = []

        for event_handler in handlers:
            try:
                event_handler.handler(event)
                if event_handler.once:
                    to_remove.append(event_handler)
            except Exception as e:
                print(f"[EventEmitter] Error in handler for {event_type}: {e}")

        # Remove one-time handlers
        for handler in to_remove:
            self._handlers[event_type].remove(handler)

    def emit_task_started(self, task: Task) -> None:
        """Emit task started event."""
        self.emit(
            EventType.TASK_STARTED,
            task_id=task.id,
            phase=task.phase,
            description=task.description,
        )

    def emit_task_completed(self, task: Task, result: TaskResult) -> None:
        """Emit task completed event."""
        self.emit(
            EventType.TASK_COMPLETED,
            task_id=task.id,
            phase=task.phase,
            description=task.description,
            success=result.success,
            duration=result.duration_seconds,
            worker=result.worker_used,
        )

    def emit_task_failed(self, task: Task, result: TaskResult) -> None:
        """Emit task failed event."""
        self.emit(
            EventType.TASK_FAILED,
            task_id=task.id,
            phase=task.phase,
            description=task.description,
            error=result.error,
            duration=result.duration_seconds,
        )

    def emit_phase_started(self, phase_name: str) -> None:
        """Emit phase started event."""
        self.emit(
            EventType.PHASE_STARTED,
            phase=phase_name,
        )

    def emit_phase_completed(self, phase_name: str, task_count: int) -> None:
        """Emit phase completed event."""
        self.emit(
            EventType.PHASE_COMPLETED,
            phase=phase_name,
            task_count=task_count,
        )

    def emit_execution_started(self, plan_name: str, total_tasks: int) -> None:
        """Emit execution started event."""
        self.emit(
            EventType.EXECUTION_STARTED,
            plan=plan_name,
            total_tasks=total_tasks,
        )

    def emit_execution_completed(self, total_tasks: int, completed: int, failed: int) -> None:
        """Emit execution completed event."""
        self.emit(
            EventType.EXECUTION_COMPLETED,
            total_tasks=total_tasks,
            completed=completed,
            failed=failed,
        )

    def _add_to_history(self, event: Event) -> None:
        """Add event to history."""
        self._history.append(event)

        # Trim history if needed
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_history(
        self,
        event_type: Optional[EventType] = None,
        limit: Optional[int] = None,
    ) -> list[Event]:
        """
        Get event history.

        Args:
            event_type: Filter by event type (optional)
            limit: Max events to return (optional)

        Returns:
            List of events
        """
        events = self._history

        if event_type:
            events = [e for e in events if e.type == event_type]

        if limit:
            events = events[-limit:]

        return events

    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()

    def get_handler_count(self, event_type: Optional[EventType] = None) -> int:
        """Get number of registered handlers."""
        if event_type:
            return len(self._handlers.get(event_type, []))
        return sum(len(handlers) for handlers in self._handlers.values())


class ProgressEventHandler(BaseModel):
    """
    Event handler that logs progress to console.

    Simple handler for development/debugging.
    """

    emitter: EventEmitter

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def register(self) -> None:
        """Register all progress event handlers."""
        self.emitter.on(EventType.EXECUTION_STARTED, self._on_execution_started)
        self.emitter.on(EventType.EXECUTION_COMPLETED, self._on_execution_completed)
        self.emitter.on(EventType.TASK_STARTED, self._on_task_started)
        self.emitter.on(EventType.TASK_COMPLETED, self._on_task_completed)
        self.emitter.on(EventType.TASK_FAILED, self._on_task_failed)
        self.emitter.on(EventType.PHASE_STARTED, self._on_phase_started)
        self.emitter.on(EventType.PHASE_COMPLETED, self._on_phase_completed)

    def _on_execution_started(self, event: Event) -> None:
        print(f"\n🚀 Execution started: {event.data.get('plan')}")

    def _on_execution_completed(self, event: Event) -> None:
        print(f"\n✅ Execution completed!")
        print(f"   Total: {event.data.get('total_tasks')}")
        print(f"   Completed: {event.data.get('completed')}")
        print(f"   Failed: {event.data.get('failed')}")

    def _on_task_started(self, event: Event) -> None:
        task_id = event.data.get("task_id")
        desc = event.data.get("description", "")
        print(f"⏳ [{task_id}] {desc[:50]}...")

    def _on_task_completed(self, event: Event) -> None:
        task_id = event.data.get("task_id")
        duration = event.data.get("duration", 0)
        print(f"✅ [{task_id}] completed in {duration:.1f}s")

    def _on_task_failed(self, event: Event) -> None:
        task_id = event.data.get("task_id")
        error = event.data.get("error", "Unknown error")
        print(f"❌ [{task_id}] failed: {error}")

    def _on_phase_started(self, event: Event) -> None:
        phase = event.data.get("phase")
        print(f"\n📋 Phase: {phase}")

    def _on_phase_completed(self, event: Event) -> None:
        phase = event.data.get("phase")
        count = event.data.get("task_count", 0)
        print(f"✓ Phase '{phase}' complete ({count} tasks)")
