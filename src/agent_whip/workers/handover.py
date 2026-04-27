"""
Handover Manager for AgentWhip.

Coordinates handover between workers when token threshold is reached.
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_whip.context import ContextDocument, ContextSummarizer
from agent_whip.events import EventEmitter, EventType
from agent_whip.models import ExecutionPlan, ExecutionState, Task
from agent_whip.models.handover import (
    HandoverContext,
    HandoverRecord,
    HandoverResult,
)
from agent_whip.store import StateStore
from agent_whip.workers.token_tracker import TokenTracker


class HandoverManager:
    """
    Manages handover between workers.

    Coordinates the process of summarizing context, creating new worker,
    and transferring work when token limit is reached.
    """

    def __init__(
        self,
        summarizer: ContextSummarizer,
        state_store: StateStore,
        context_document: ContextDocument,
        event_emitter: EventEmitter,
        config: Optional[dict] = None,
    ):
        """
        Initialize handover manager.

        Args:
            summarizer: Context summarizer
            state_store: State store for persistence
            context_document: Context document for tracking
            event_emitter: Event emitter
            config: Optional configuration
        """
        self.summarizer = summarizer
        self.state_store = state_store
        self.context_document = context_document
        self.event_emitter = event_emitter
        self.config = config or {}

        # Track active handovers
        self._active_handovers: dict[str, HandoverContext] = {}

    async def trigger_handover(
        self,
        from_worker_id: str,
        state: ExecutionState,
        plan: ExecutionPlan,
        task: Task,
        token_tracker: TokenTracker,
    ) -> HandoverResult:
        """
        Trigger handover from one worker to another.

        Args:
            from_worker_id: ID of worker handing over
            state: Current execution state
            plan: Execution plan
            task: Current task being worked on
            token_tracker: Token tracker showing usage

        Returns:
            HandoverResult with handover details
        """
        start_time = time.time()

        try:
            # 1. Generate handover context
            work_done = task.result.output if task.result else ""
            handover_context = await self.summarizer.summarize_handover(
                state=state,
                plan=plan,
                task=task,
                work_done=work_done,
                from_worker_id=from_worker_id,
            )

            # Add token info
            handover_context.tokens_used = token_tracker.usage.total_tokens
            handover_context.session_duration = (
                token_tracker.usage.session_duration_seconds
            )

            # 2. Emit handover triggered event
            self.event_emitter.emit(
                EventType.HANDOVER_TRIGGERED,
                handover_id=handover_context.handover_id,
                from_worker_id=from_worker_id,
                tokens_used=handover_context.tokens_used,
                context_summary=handover_context.work_summary[:500],
            )

            # 3. Save to context document
            handover_record = HandoverRecord(
                handover_id=handover_context.handover_id,
                timestamp=handover_context.timestamp,
                from_worker=from_worker_id,
                to_worker="",  # Will be filled when new worker created
                reason="token_threshold",
                context_summary=handover_context.work_summary,
                tokens_used_before=handover_context.tokens_used,
                tokens_preserved=len(
                    handover_context.work_summary
                ),  # Rough estimate
                handover_duration_ms=0,  # Will be updated
                success=True,
            )

            # 4. Store for retrieval by new worker
            self._active_handovers[handover_context.handover_id] = handover_context

            # 5. Persist to state store
            self.state_store.save_handover_context(handover_context)

            duration_ms = (time.time() - start_time) * 1000
            handover_record.handover_duration_ms = duration_ms

            # 6. Save to context document
            self.context_document.append_handover(handover_record)
            self.context_document.save_context_update(
                event_type=EventType.HANDOVER_TRIGGERED,
                data={
                    "handover_id": handover_context.handover_id,
                    "from_worker": from_worker_id,
                    "reason": "token_threshold",
                },
            )

            # 7. Emit completion event
            self.event_emitter.emit(
                EventType.HANDOVER_COMPLETED,
                handover_id=handover_context.handover_id,
                from_worker_id=from_worker_id,
                duration_ms=duration_ms,
            )

            return HandoverResult(
                success=True,
                handover_id=handover_context.handover_id,
                from_worker_id=from_worker_id,
                to_worker_id="",  # Will be filled when new worker created
                context_summary=handover_context.work_summary,
                tokens_preserved=handover_record.tokens_preserved,
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
            )

        except Exception as e:
            # Handle failure
            duration_ms = (time.time() - start_time) * 1000

            self.event_emitter.emit(
                EventType.HANDOVER_FAILED,
                from_worker_id=from_worker_id,
                error=str(e),
                duration_ms=duration_ms,
            )

            return HandoverResult(
                success=False,
                handover_id="",
                from_worker_id=from_worker_id,
                to_worker_id="",
                context_summary="",
                tokens_preserved=0,
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                error=str(e),
            )

    def get_pending_handover(self, handover_id: str) -> Optional[HandoverContext]:
        """
        Get a pending handover context.

        Args:
            handover_id: ID of handover to retrieve

        Returns:
            HandoverContext if found, None otherwise
        """
        return self._active_handovers.get(handover_id)

    def complete_handover(
        self, handover_id: str, to_worker_id: str
    ) -> None:
        """
        Mark a handover as completed with the new worker ID.

        Args:
            handover_id: ID of handover
            to_worker_id: ID of new worker taking over
        """
        handover_context = self._active_handovers.get(handover_id)
        if handover_context:
            handover_context.to_worker_id = to_worker_id

            # Update in context document
            for record in self.context_document.handovers:
                if record.handover_id == handover_id:
                    record.to_worker = to_worker_id
                    break

            self.context_document._persist()

            # Remove from active
            del self._active_handovers[handover_id]

    def get_handover_history(self) -> list[HandoverRecord]:
        """Get all handover records."""
        return self.context_document.get_handover_history()

    def get_active_handovers(self) -> list[HandoverContext]:
        """Get all active (pending) handovers."""
        return list(self._active_handovers.values())


class HandoverWorkerFactory:
    """
    Factory for creating workers with handover context.

    This is used by the WorkerManager to create new workers
    that can continue from where the previous worker left off.
    """

    def __init__(
        self,
        handover_manager: HandoverManager,
    ):
        """
        Initialize factory.

        Args:
            handover_manager: Handover manager for context retrieval
        """
        self.handover_manager = handover_manager

    def create_worker_with_context(
        self,
        worker_class: type,
        handover_id: str,
        **kwargs,
    ):
        """
        Create a new worker with handover context.

        Args:
            worker_class: Worker class to instantiate
            handover_id: ID of handover context
            **kwargs: Additional arguments for worker

        Returns:
            New worker instance with context
        """
        handover_context = self.handover_manager.get_pending_handover(
            handover_id
        )
        if not handover_context:
            raise ValueError(f"No pending handover found: {handover_id}")

        # Create worker with context
        worker = worker_class(
            **kwargs,
            handover_context=handover_context,
        )

        # Mark handover as complete
        self.handover_manager.complete_handover(
            handover_id,
            to_worker_id=worker.name if hasattr(worker, "name") else "unknown",
        )

        return worker
