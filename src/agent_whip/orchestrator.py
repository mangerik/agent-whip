"""
Main Orchestrator for AgentWhip.

Connects all components and manages the execution lifecycle.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from agent_whip.config import AgentWhipConfig, load_config
from agent_whip.context import ContextDocument, ContextSummarizer
from agent_whip.events import EventEmitter, EventType, ProgressEventHandler
from agent_whip.models import ExecutionPlan, ExecutionState, Task, TaskResult, TaskStatus
from agent_whip.models.state import ExecutionStatus
from agent_whip.parser import parse_plan_sync
from agent_whip.qa import QAEngine, QAResult
from agent_whip.queue import TaskQueue
from agent_whip.store import CheckpointManager, StateStore
from agent_whip.tracker import NextAction, ProgressTracker
from agent_whip.workers import HandoverManager, TokenTracker, WorkerManager


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class ExecutionOrchestrator(BaseModel):
    """
    Main orchestrator for AgentWhip.

    Coordinates all components to execute a plan.
    Supports worker handover when token threshold is reached.
    """

    project_path: Path
    config: AgentWhipConfig = Field(default_factory=AgentWhipConfig)
    use_mock_workers: bool = Field(default=False, description="Use mock workers for testing")
    use_flexible_parsing: bool = Field(default=False, description="Use AI-powered flexible parsing")

    # Core components
    _plan: Optional[ExecutionPlan] = PrivateAttr(default=None)
    _state: Optional[ExecutionState] = PrivateAttr(default=None)
    _queue: Optional[TaskQueue] = PrivateAttr(default=None)
    _tracker: Optional[ProgressTracker] = PrivateAttr(default=None)
    _worker_manager: Optional[WorkerManager] = PrivateAttr(default=None)
    _qa_engine: Optional[QAEngine] = PrivateAttr(default=None)
    _event_emitter: Optional[EventEmitter] = PrivateAttr(default=None)
    _state_store: Optional[StateStore] = PrivateAttr(default=None)
    _checkpoint_manager: Optional[CheckpointManager] = PrivateAttr(default=None)

    # Handover components
    _context_document: Optional[ContextDocument] = PrivateAttr(default=None)
    _handover_manager: Optional[HandoverManager] = PrivateAttr(default=None)
    _context_summarizer: Optional[ContextSummarizer] = PrivateAttr(default=None)

    # Execution control
    _running: bool = PrivateAttr(default=False)
    _paused: bool = PrivateAttr(default=False)
    _handover_enabled: bool = PrivateAttr(default=True)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def create(
        cls,
        project_path: Path,
        use_mock: bool = False,
        use_flexible: bool = False,
    ) -> "ExecutionOrchestrator":
        """Create and initialize orchestrator."""
        orchestrator = cls(
            project_path=project_path,
            use_mock_workers=use_mock,
            use_flexible_parsing=use_flexible,
        )
        orchestrator.initialize()
        return orchestrator

    def initialize(self):
        """Initialize all components."""
        # Load config
        self.config = load_config(self.project_path)
        self._handover_enabled = self.config.handover.enabled

        # Create event emitter first (other components may need it)
        self._event_emitter = EventEmitter()
        self._setup_event_handlers()

        # Parse plan
        plan_path = self.project_path / "plan.md"
        self._plan = parse_plan_sync(plan_path, flexible=self.use_flexible_parsing)

        # Create state
        self._state = ExecutionState(
            project_name=self._plan.project_name,
            project_path=str(self.project_path),
            plan_path=str(plan_path),
            total_phases=self._plan.total_phases,
            total_tasks=self._plan.total_tasks,
        )

        # Create task queue
        self._queue = TaskQueue.from_plan(self._plan)

        # Create progress tracker
        self._tracker = ProgressTracker(
            config=self.config,
            plan=self._plan,
            state=self._state,
        )

        # Create worker manager
        self._worker_manager = WorkerManager(
            config=self.config,
            project_path=self.project_path,
            use_mock=self.use_mock_workers,
        )
        self._worker_manager.initialize_workers()

        # Create QA engine
        self._qa_engine = QAEngine(
            config=self.config.qa,
            project_path=self.project_path,
        )

        # Create state store
        self._state_store = StateStore.create(
            project_path=self.project_path,
            store_type="json",  # TODO: use config
        )

        # Create checkpoint manager
        self._checkpoint_manager = CheckpointManager(
            store=self._state_store,
            checkpoint_interval=self.config.state.checkpoint_interval,
        )

        # Initialize handover components if enabled
        if self._handover_enabled:
            self._initialize_handover_components()

    def _setup_event_handlers(self):
        """Setup event handlers."""
        progress_handler = ProgressEventHandler(emitter=self._event_emitter)
        progress_handler.register()

        # Register handover event handler if enabled
        if self._handover_enabled:
            self._event_emitter.on(
                EventType.TOKEN_THRESHOLD_REACHED,
                self._handle_token_threshold,
            )
            self._event_emitter.on(
                EventType.HANDOVER_TRIGGERED,
                self._handle_handover_triggered,
            )

    def _initialize_handover_components(self):
        """Initialize handover-related components."""
        # Create context document
        self._context_document = ContextDocument(
            project_path=self.project_path,
        )
        self._context_document.initialize_from_plan(self._plan)

        # Create context summarizer
        self._context_summarizer = ContextSummarizer(
            max_summary_length=self.config.handover.max_summary_length,
            include_artifacts=self.config.handover.include_artifacts,
            include_decisions=self.config.handover.include_decisions,
        )

        # Create handover manager
        self._handover_manager = HandoverManager(
            summarizer=self._context_summarizer,
            state_store=self._state_store,
            context_document=self._context_document,
            event_emitter=self._event_emitter,
        )

        # Setup token trackers for workers
        self._setup_worker_token_trackers()

    def _setup_worker_token_trackers(self):
        """Setup token trackers for all workers."""
        if not self._worker_manager:
            return

        # Get token limit and threshold from config
        default_limit = self.config.handover.claude.max_tokens_per_session
        threshold = self.config.handover.token_threshold

        # Setup token tracker for each worker
        for worker_name, worker in self._worker_manager._workers.items():
            token_tracker = TokenTracker(
                worker_id=worker.worker_id if hasattr(worker, "worker_id") else worker_name,
                limit=default_limit,
                threshold=threshold,
                event_emitter=self._event_emitter,
            )
            worker.set_token_tracker(token_tracker)
            worker.set_event_emitter(self._event_emitter)

    def _handle_token_threshold(self, event):
        """Handle token threshold reached event."""
        worker_id = event.data.get("worker_id")
        usage = event.data.get("usage", {})
        percentage = event.data.get("percentage", 0)

        # Log the threshold event
        print(f"\n⚠️  Token threshold reached for worker {worker_id}")
        print(f"   Usage: {percentage:.1f}%")
        print(f"   Initiating handover...")

    async def _handle_handover_triggered(self, event):
        """Handle handover triggered event."""
        worker_id = event.data.get("from_worker_id")
        handover_id = event.data.get("handover_id")

        print(f"\n🔄 Handover {handover_id} initiated from worker {worker_id}")

        # The actual handover is handled by the worker manager
        # This event is for logging/notification purposes

    def load_saved_state(self) -> bool:
        """
        Load execution state and plan from persisted storage.

        Returns:
            True if a saved state was found and loaded, False otherwise.
        """
        if not self._state_store:
            return False

        loaded = self._state_store.load()
        if not loaded:
            return False

        state, plan = loaded
        self._state = state
        self._plan = plan
        self._queue = TaskQueue.from_plan_state(plan)
        self._tracker = ProgressTracker(
            config=self.config,
            plan=self._plan,
            state=self._state,
        )
        return True

    async def run(self) -> ExecutionState:
        """
        Run the execution from start to finish.

        Returns:
            Final execution state
        """
        if not self._plan:
            raise RuntimeError("Orchestrator not initialized")

        self._running = True
        self._state.mark_started()

        self._event_emitter.emit_execution_started(
            plan_name=self._plan.project_name,
            total_tasks=self._plan.total_tasks,
        )

        try:
            # Main execution loop
            while self._running and not self._is_complete():
                # Check for pause
                if self._paused:
                    await asyncio.sleep(0.1)
                    continue

                # Get next ready task
                ready_tasks = self._queue.get_ready()

                if not ready_tasks:
                    # No tasks ready, check if we can continue
                    if self._queue.is_empty and self._all_phases_complete():
                        break
                    await asyncio.sleep(0.1)
                    continue

                # Execute next task
                task = ready_tasks[0]
                await self._execute_task(task)

                # Checkpoint if needed
                if self._checkpoint_manager.should_checkpoint():
                    self._checkpoint_manager.checkpoint(self._state, self._plan)

            # Execution complete
            if self._state.status == ExecutionStatus.RUNNING:
                self._state.mark_completed()

        except Exception as e:
            self._state.mark_failed(str(e))
            self._event_emitter.emit(EventType.EXECUTION_FAILED, error=str(e))

        finally:
            self._running = False

        # Save final state
        self._state_store.save(self._state, self._plan)

        # Emit completion
        summary = self._tracker.get_progress_summary()
        self._event_emitter.emit_execution_completed(
            total_tasks=summary["total"],
            completed=summary["completed"],
            failed=summary["failed"],
        )

        return self._state

    async def _execute_task(self, task: Task) -> None:
        """Execute a single task."""
        # Mark as running
        self._queue.mark_running(task.id)
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = _utcnow()
        self._state.set_current_task(task.id, task.phase)

        self._event_emitter.emit_task_started(task)

        # Update context document
        if self._context_document:
            from agent_whip.context import ContextEventType
            self._context_document.save_context_update(
                ContextEventType.TASK_STARTED,
                {"task_id": task.id, "phase": task.phase},
            )

        # Execute
        try:
            result = await self._worker_manager.execute_task(task)

            # Update task
            task.result = result
            task.completed_at = _utcnow()

            # Evaluate result
            action = self._tracker.evaluate_task_result(task, result)

            if result.success:
                self._queue.mark_completed(task.id)
                task.status = TaskStatus.COMPLETED
                self._state.increment_completed()
                self._event_emitter.emit_task_completed(task, result)

                # Update context document on success
                if self._context_document:
                    from agent_whip.context import ContextEventType
                    self._context_document.append_task_completion(task.id, result)
            else:
                # Handle failure
                if action == NextAction.RETRY:
                    self._queue.requeue(task.id)
                    task.status = TaskStatus.RETRYING
                    task.attempts += 1
                    self._event_emitter.emit(
                        EventType.TASK_RETRYING,
                        task_id=task.id,
                        phase=task.phase,
                        attempts=task.attempts,
                    )
                elif action == NextAction.SKIP:
                    self._queue.mark_skipped(task.id)
                    task.status = TaskStatus.SKIPPED
                    self._state.increment_skipped()
                elif action == NextAction.ABORT:
                    self._queue.mark_failed(task.id)
                    task.status = TaskStatus.FAILED
                    self._state.increment_failed()
                    self._state.mark_aborted(f"Task {task.id} failed")
                    self._event_emitter.emit_task_failed(task, result)
                    raise RuntimeError(f"Task {task.id} failed, aborting")
                else:
                    self._queue.mark_failed(task.id)
                    task.status = TaskStatus.FAILED
                    self._state.increment_failed()
                    self._event_emitter.emit_task_failed(task, result)

            # Check if phase is complete
            if action == NextAction.RUN_QA:
                await self._run_qa_for_phase(task.phase)

            # Update context document state
            if self._context_document:
                self._context_document.update_current_state(self._state)

        except Exception as e:
            # Mark failed once; ABORT path may already have done this.
            already_marked_failed = task.status == TaskStatus.FAILED and task.id in self._queue.failed
            if not already_marked_failed:
                task.status = TaskStatus.FAILED
                self._queue.mark_failed(task.id)
                self._state.increment_failed()
                self._event_emitter.emit_task_failed(
                    task,
                    TaskResult(success=False, error=str(e)),
                )
            raise

    async def _run_qa_for_phase(self, phase_name: str) -> None:
        """Run QA tests for a phase."""
        phase = self._plan.get_phase(phase_name)
        if not phase:
            return

        self._event_emitter.emit(EventType.QA_STARTED, phase=phase_name)

        qa_result = await self._qa_engine.run_tests(phase)

        if qa_result.success:
            self._event_emitter.emit(EventType.QA_COMPLETED, phase=phase_name)
        else:
            self._event_emitter.emit(
                EventType.QA_FAILED,
                phase=phase_name,
                failed=qa_result.failed,
            )

            # Create bug tickets if configured
            if self.config.qa.create_tickets_on_failure:
                from agent_whip.qa import TicketCreator
                ticket_creator = TicketCreator(project_path=self.project_path)
                tickets = ticket_creator.create_tickets(qa_result, phase)

                self._event_emitter.emit(
                    EventType.QA_FAILED,
                    phase=phase_name,
                    tickets_created=len(tickets),
                )

    def pause(self) -> None:
        """Pause execution."""
        self._paused = True
        self._state.status = ExecutionStatus.PAUSED
        self._event_emitter.emit(EventType.EXECUTION_PAUSED)

    def resume(self) -> None:
        """Resume execution."""
        self._paused = False
        self._state.status = ExecutionStatus.RUNNING
        self._event_emitter.emit(EventType.EXECUTION_RESUMED)

    def stop(self) -> None:
        """Stop execution."""
        self._running = False
        self._state.status = ExecutionStatus.ABORTED

    def get_status(self) -> dict:
        """Get current execution status."""
        summary = self._tracker.get_progress_summary() if self._tracker else {}
        status_value = "idle"
        if self._state:
            status_value = self._state.status.value if hasattr(self._state.status, "value") else str(self._state.status)

        return {
            "status": status_value,
            "project": self._state.project_name if self._state else None,
            "current_phase": self._state.current_phase if self._state else None,
            "current_task": self._state.current_task if self._state else None,
            "progress": summary.get("progress", 0),
            "completed": summary.get("completed", 0),
            "failed": summary.get("failed", 0),
            "total": summary.get("total", 0),
            "handover_enabled": self._handover_enabled,
        }

    def get_handover_history(self) -> list:
        """Get handover history from context document."""
        if not self._context_document:
            return []
        return [h.to_dict() for h in self._context_document.get_handover_history()]

    def get_context_snapshot(self) -> dict:
        """Get current context snapshot for continuation."""
        if not self._context_document:
            return {}
        return self._context_document.get_current_context()

    def _is_complete(self) -> bool:
        """Check if execution is complete."""
        if not self._state:
            return False

        status_value = self._state.status.value if hasattr(self._state.status, "value") else str(self._state.status)
        return status_value in (
            ExecutionStatus.COMPLETED.value,
            ExecutionStatus.FAILED.value,
            ExecutionStatus.ABORTED.value,
        )

    def _all_phases_complete(self) -> bool:
        """Check if all phases are complete."""
        if not self._plan:
            return True

        for phase in self._plan.phases:
            phase_tasks = self._plan.get_tasks_for_phase(phase.name)
            for task in phase_tasks:
                if task.status not in (TaskStatus.COMPLETED, TaskStatus.SKIPPED):
                    return False

        return True
