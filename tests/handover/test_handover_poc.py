"""
Proof-of-concept tests for Handover feature.

Tests the core functionality of worker handover when token threshold is reached.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from agent_whip.context import ContextDocument, ContextSummarizer, ContextEventType
from agent_whip.events import EventEmitter, EventType
from agent_whip.models import ExecutionPlan, ExecutionState, Phase, Task, TaskStatus
from agent_whip.models.handover import HandoverContext, HandoverRecord, generate_handover_id
from agent_whip.workers import HandoverManager, TokenTracker, TokenUsageStats
from agent_whip.store import StateStore
from agent_whip.config import HandoverConfig, AgentWhipConfig


class TestTokenTracker:
    """Test token tracking functionality."""

    def test_token_tracker_threshold_detection(self):
        """Test token tracker detects 85% threshold."""
        event_emitter = EventEmitter()
        tracker = TokenTracker(
            worker_id="test_worker",
            limit=200000,
            threshold=0.85,
            event_emitter=event_emitter,
        )

        # Track events
        threshold_events = []

        def on_threshold(event):
            threshold_events.append(event)

        event_emitter.on(EventType.TOKEN_THRESHOLD_REACHED, on_threshold)

        # Use 170,000 tokens (85% of 200,000)
        tracker.record_usage(input_tokens=85000, output_tokens=85000)

        assert tracker.should_trigger_handover() is True
        assert tracker.current_percentage == 85.0
        assert len(threshold_events) == 1

    def test_token_tracker_below_threshold(self):
        """Test token tracker doesn't trigger below threshold."""
        tracker = TokenTracker(
            worker_id="test_worker",
            limit=200000,
            threshold=0.85,
        )

        # Use 100,000 tokens (50% of 200,000)
        tracker.record_usage(input_tokens=50000, output_tokens=50000)

        assert tracker.should_trigger_handover() is False
        assert tracker.current_percentage == 50.0

    def test_token_tracker_remaining(self):
        """Test token tracker calculates remaining correctly."""
        tracker = TokenTracker(
            worker_id="test_worker",
            limit=200000,
            threshold=0.85,
        )

        tracker.record_usage(input_tokens=50000, output_tokens=50000)

        assert tracker.get_remaining_tokens() == 100000
        assert tracker.get_remaining_percentage() == 50.0

    def test_token_tracker_reset(self):
        """Test token tracker can be reset."""
        tracker = TokenTracker(
            worker_id="test_worker",
            limit=200000,
            threshold=0.85,
        )

        tracker.record_usage(input_tokens=85000, output_tokens=85000)
        assert tracker.should_trigger_handover() is True

        tracker.reset()
        assert tracker.should_trigger_handover() is False
        assert tracker.usage.total_tokens == 0

    def test_token_tracker_serialization(self):
        """Test token tracker can be serialized to dict."""
        tracker = TokenTracker(
            worker_id="test_worker",
            limit=200000,
            threshold=0.85,
        )

        tracker.record_usage(input_tokens=50000, output_tokens=30000)

        data = tracker.to_dict()
        assert data["worker_id"] == "test_worker"
        assert data["limit"] == 200000
        assert data["threshold"] == 0.85
        assert data["usage"]["total_tokens"] == 80000
        assert data["current_percentage"] == 40.0


class TestContextSummarizer:
    """Test context summarization functionality."""

    @pytest.fixture
    def mock_state(self):
        """Create mock execution state."""
        return ExecutionState(
            project_name="TestProject",
            project_path="/tmp/test",
            plan_path="/tmp/test/plan.md",
            total_phases=2,
            total_tasks=4,
        )

    @pytest.fixture
    def mock_plan(self):
        """Create mock execution plan."""
        phase1 = Phase(
            name="Phase 1",
            number=1,
            tasks=[
                Task(
                    id="TASK-001",
                    phase="Phase 1",
                    phase_number=1,
                    description="First task",
                    status=TaskStatus.COMPLETED,
                ),
                Task(
                    id="TASK-002",
                    phase="Phase 1",
                    phase_number=1,
                    description="Second task",
                    status=TaskStatus.PENDING,
                ),
            ],
        )
        phase2 = Phase(
            name="Phase 2",
            number=2,
            tasks=[
                Task(
                    id="TASK-003",
                    phase="Phase 2",
                    phase_number=2,
                    description="Third task",
                    status=TaskStatus.PENDING,
                ),
            ],
        )

        plan = ExecutionPlan(
            project_name="TestProject",
            phases=[phase1, phase2],
        )

        # Add results to completed task
        phase1.tasks[0].result = type("obj", (object,), {
            "success": True,
            "output": "Task completed successfully",
            "artifacts": ["src/main.py"],
            "code_changes": {"src/main.py": "print('hello')"},
        })()

        return plan

    @pytest.mark.asyncio
    async def test_summarize_handover(self, mock_state, mock_plan):
        """Test handover context summarization."""
        summarizer = ContextSummarizer()

        task = mock_plan.phases[0].tasks[1]  # TASK-002

        context = await summarizer.summarize_handover(
            state=mock_state,
            plan=mock_plan,
            task=task,
            work_done="Working on Phase 1",
            from_worker_id="worker_1",
        )

        assert context.handover_id is not None
        assert context.project_name == "TestProject"
        assert context.current_phase == "Phase 1"
        assert context.current_task == "TASK-002"
        assert context.phase_progress == 0.5  # 1/2 tasks completed
        assert "TASK-001" in context.tasks_completed
        assert "TASK-002" in context.tasks_pending
        assert "src/main.py" in context.files_created

    @pytest.mark.asyncio
    async def test_summarize_phase(self, mock_plan):
        """Test phase summarization."""
        summarizer = ContextSummarizer()

        summary = await summarizer.summarize_phase(mock_plan.phases[0])

        assert summary["phase_name"] == "Phase 1"
        assert summary["total_tasks"] == 2
        assert summary["completed_tasks"] == 1
        assert summary["progress_percentage"] == 50.0


class TestHandoverManager:
    """Test handover management functionality."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project directory."""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_components(self, temp_project):
        """Create mock components for handover manager."""
        event_emitter = EventEmitter()
        summarizer = ContextSummarizer()
        state_store = StateStore.create(temp_project, store_type="json")
        context_document = ContextDocument(temp_project)

        return {
            "summarizer": summarizer,
            "state_store": state_store,
            "context_document": context_document,
            "event_emitter": event_emitter,
        }

    @pytest.mark.asyncio
    async def test_trigger_handover(self, mock_components, temp_project):
        """Test triggering a handover."""
        manager = HandoverManager(**mock_components)

        # Create mock state and plan
        state = ExecutionState(
            project_name="TestProject",
            project_path=str(temp_project),
            plan_path=str(temp_project / "plan.md"),
            total_phases=1,
            total_tasks=1,
        )

        phase = Phase(
            name="Phase 1",
            number=1,
            tasks=[
                Task(
                    id="TASK-001",
                    phase="Phase 1",
                    phase_number=1,
                    description="Test task",
                    status=TaskStatus.IN_PROGRESS,
                )
            ],
        )

        from agent_whip.models import ExecutionPlan
        plan = ExecutionPlan(project_name="TestProject", phases=[phase])

        task = phase.tasks[0]
        task.result = type("obj", (object,), {
            "success": True,
            "output": "Work in progress",
        })()

        token_tracker = TokenTracker(
            worker_id="worker_1",
            limit=200000,
            threshold=0.85,
        )
        token_tracker.record_usage(170000, 0)

        result = await manager.trigger_handover(
            from_worker_id="worker_1",
            state=state,
            plan=plan,
            task=task,
            token_tracker=token_tracker,
        )

        assert result.success is True
        assert result.handover_id is not None
        assert result.from_worker_id == "worker_1"
        assert result.context_summary is not None

        # Check handover was recorded
        history = manager.get_handover_history()
        assert len(history) == 1
        assert history[0].handover_id == result.handover_id


class TestContextDocument:
    """Test context document functionality."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project directory."""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_context_document_persistence(self, temp_project):
        """Test context document persists correctly."""
        doc = ContextDocument(temp_project)

        # Add some events
        doc.save_context_update(
            ContextEventType.TASK_STARTED,
            {"task_id": "TASK-001", "phase": "Phase 1"},
        )

        # Verify in memory
        assert len(doc.context_log) == 1

        # Create new instance - should load from disk
        doc2 = ContextDocument(temp_project)
        assert len(doc2.context_log) == 1
        assert doc2.context_log[0].data["task_id"] == "TASK-001"

    def test_context_document_handover_record(self, temp_project):
        """Test handover record is saved correctly."""
        doc = ContextDocument(temp_project)

        record = HandoverRecord(
            handover_id="ho_test_001",
            timestamp=datetime.now(timezone.utc),
            from_worker="worker_1",
            to_worker="worker_2",
            reason="token_threshold",
            context_summary="Test summary",
            tokens_used_before=170000,
            tokens_preserved=5000,
            handover_duration_ms=100,
            success=True,
        )

        doc.append_handover(record)

        # Verify
        history = doc.get_handover_history()
        assert len(history) == 1
        assert history[0].handover_id == "ho_test_001"

    def test_context_document_decision(self, temp_project):
        """Test decision record is saved correctly."""
        doc = ContextDocument(temp_project)

        doc.append_decision(
            topic="Architecture choice",
            decision="Use FastAPI",
            rationale="Better async support",
            alternatives=["Flask", "Django"],
        )

        # Verify
        decisions = doc.decisions
        assert len(decisions) == 1
        assert decisions[0]["topic"] == "Architecture choice"
        assert decisions[0]["decision"] == "Use FastAPI"

    def test_context_document_current_context(self, temp_project):
        """Test getting current context snapshot."""
        doc = ContextDocument(temp_project)
        doc.project_name = "TestProject"
        doc.current_phase = "Phase 1"
        doc.current_task = "TASK-001"

        # Add some events
        doc.save_context_update(
            ContextEventType.TASK_COMPLETED,
            {"task_id": "TASK-001", "success": True},
        )

        context = doc.get_current_context()

        assert context["project"]["name"] == "TestProject"
        assert context["current"]["phase"] == "Phase 1"
        assert context["current"]["task"] == "TASK-001"
        assert len(context["recent_events"]) == 1


class TestHandoverContext:
    """Test HandoverContext data model."""

    def test_handover_context_serialization(self):
        """Test handover context can be serialized."""
        context = HandoverContext(
            handover_id="ho_test_001",
            timestamp=datetime.now(timezone.utc),
            project_name="TestProject",
            project_path="/tmp/test",
            current_phase="Phase 1",
            current_task="TASK-001",
            phase_progress=0.5,
            work_summary="Test summary",
            tasks_completed=["TASK-001"],
            tasks_pending=["TASK-002"],
            tasks_failed=[],
            files_created=["src/main.py"],
            files_modified=[],
            decisions_made=[],
            context_snapshot={},
            from_worker_id="worker_1",
            tokens_used=100000,
            session_duration=300.0,
        )

        data = context.to_dict()

        assert data["handover_id"] == "ho_test_001"
        assert data["project_name"] == "TestProject"
        assert data["tasks_completed"] == ["TASK-001"]
        assert data["phase_progress"] == 0.5

    def test_handover_context_deserialization(self):
        """Test handover context can be deserialized."""
        data = {
            "handover_id": "ho_test_001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_name": "TestProject",
            "project_path": "/tmp/test",
            "current_phase": "Phase 1",
            "current_task": "TASK-001",
            "phase_progress": 0.5,
            "work_summary": "Test summary",
            "tasks_completed": ["TASK-001"],
            "tasks_pending": ["TASK-002"],
            "tasks_failed": [],
            "files_created": ["src/main.py"],
            "files_modified": [],
            "decisions_made": [],
            "context_snapshot": {},
            "from_worker_id": "worker_1",
            "tokens_used": 100000,
            "session_duration": 300.0,
            "handover_reason": "token_threshold",
        }

        context = HandoverContext.from_dict(data)

        assert context.handover_id == "ho_test_001"
        assert context.project_name == "TestProject"
        assert context.tasks_completed == ["TASK-001"]

    def test_generate_handover_id(self):
        """Test handover ID generation."""
        id1 = generate_handover_id()
        id2 = generate_handover_id()

        assert id1 != id2
        assert id1.startswith("ho_")
        assert len(id1) > 10


class TestIntegrationHandoverFlow:
    """Integration tests for complete handover flow."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project directory."""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_complete_handover_flow(self, temp_project):
        """Test complete handover flow from threshold to new worker."""
        # 1. Setup components
        event_emitter = EventEmitter()
        summarizer = ContextSummarizer()
        state_store = StateStore.create(temp_project, store_type="json")
        context_document = ContextDocument(temp_project)
        handover_manager = HandoverManager(
            summarizer=summarizer,
            state_store=state_store,
            context_document=context_document,
            event_emitter=event_emitter,
        )

        # 2. Create execution state and plan
        state = ExecutionState(
            project_name="TestProject",
            project_path=str(temp_project),
            plan_path=str(temp_project / "plan.md"),
            total_phases=1,
            total_tasks=1,
        )

        phase = Phase(
            name="Phase 1",
            number=1,
            tasks=[
                Task(
                    id="TASK-001",
                    phase="Phase 1",
                    phase_number=1,
                    description="Test task",
                    status=TaskStatus.IN_PROGRESS,
                )
            ],
        )

        from agent_whip.models import ExecutionPlan
        plan = ExecutionPlan(project_name="TestProject", phases=[phase])
        context_document.initialize_from_plan(plan)

        task = phase.tasks[0]
        task.result = type("obj", (object,), {
            "success": True,
            "output": "Task completed successfully",
            "artifacts": ["src/main.py"],
            "code_changes": {"src/main.py": "print('hello')"},
        })()

        # 3. Simulate worker reaching token threshold
        token_tracker = TokenTracker(
            worker_id="worker_1",
            limit=200000,
            threshold=0.85,
            event_emitter=event_emitter,
        )

        # Track events
        threshold_reached = False

        def on_threshold(event):
            nonlocal threshold_reached
            threshold_reached = True

        event_emitter.on(EventType.TOKEN_THRESHOLD_REACHED, on_threshold)

        # Use enough tokens to trigger threshold
        token_tracker.record_usage(170000, 0)

        assert threshold_reached is True
        assert token_tracker.should_trigger_handover() is True

        # 4. Trigger handover
        handover_result = await handover_manager.trigger_handover(
            from_worker_id="worker_1",
            state=state,
            plan=plan,
            task=task,
            token_tracker=token_tracker,
        )

        assert handover_result.success is True
        assert handover_result.handover_id is not None

        # 5. Verify handover was recorded
        handover_history = context_document.get_handover_history()
        assert len(handover_history) == 1
        assert handover_history[0].from_worker == "worker_1"

        # 6. Verify context document was updated
        current_context = context_document.get_current_context()
        assert current_context["project"]["name"] == "TestProject"
        assert current_context["progress"]["handovers"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
