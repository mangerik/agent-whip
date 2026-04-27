from pathlib import Path

import pytest

from agent_whip.config import AgentWhipConfig
from agent_whip.models.plan import ExecutionPlan, PlanMetadata
from agent_whip.models.state import ExecutionStatus, PhaseState
from agent_whip.models.task import Task, TaskResult, TaskStatus
from agent_whip.orchestrator import ExecutionOrchestrator
from agent_whip.queue import TaskQueue
from agent_whip.tracker import NextAction
from agent_whip.workers.manager import WorkerManager


def _build_plan() -> ExecutionPlan:
    plan = ExecutionPlan(
        source_path=Path("plan.md"),
        raw_content="",
        metadata=PlanMetadata(project_name="Test Project"),
    )
    phase = PhaseState(name="Phase 1: Setup", number=1)
    plan.add_phase(phase)
    return plan


def _write_minimal_plan(tmp_path: Path) -> None:
    (tmp_path / "plan.md").write_text(
        "\n".join(
            [
                "# Project Plan: Demo",
                "",
                "## Phases",
                "",
                "### Phase 1: Setup",
                "",
                "- [ ] SETUP-001 First task",
            ]
        ),
        encoding="utf-8",
    )


def test_requeue_from_running_moves_task_back_to_pending() -> None:
    plan = _build_plan()
    task = Task(id="TASK-001", phase="Phase 1: Setup", phase_number=1, description="Do work")
    plan.add_task(task)

    queue = TaskQueue.from_plan(plan)
    queue.mark_running(task.id)

    queue.requeue(task.id)

    assert task.id in queue.pending
    assert task.id not in queue.running
    assert task.id not in queue.failed


def test_execution_plan_get_ready_tasks_respects_dependencies() -> None:
    plan = _build_plan()
    task_1 = Task(id="TASK-001", phase="Phase 1: Setup", phase_number=1, description="First")
    task_2 = Task(
        id="TASK-002",
        phase="Phase 1: Setup",
        phase_number=1,
        description="Second",
        dependencies=["TASK-001"],
    )
    plan.add_task(task_1)
    plan.add_task(task_2)

    ready = plan.get_ready_tasks()
    assert [task.id for task in ready] == ["TASK-001"]

    task_1.status = TaskStatus.COMPLETED
    task_2.status = TaskStatus.PENDING
    ready_after_completion = plan.get_ready_tasks()
    assert [task.id for task in ready_after_completion] == ["TASK-002"]


@pytest.mark.asyncio
async def test_abort_path_counts_failed_task_once(tmp_path: Path) -> None:
    _write_minimal_plan(tmp_path)
    orchestrator = ExecutionOrchestrator.create(project_path=tmp_path, use_mock=True)
    task = orchestrator._plan.tasks[0]

    class _FailingWorkerManager:
        async def execute_task(self, _: Task) -> TaskResult:
            return TaskResult(success=False, error="forced failure")

    class _AbortTracker:
        def evaluate_task_result(self, _task: Task, _result: TaskResult) -> NextAction:
            return NextAction.ABORT

    orchestrator._worker_manager = _FailingWorkerManager()
    orchestrator._tracker = _AbortTracker()

    with pytest.raises(RuntimeError):
        await orchestrator._execute_task(task)

    assert orchestrator._state.failed_tasks == 1
    assert task.id in orchestrator._queue.failed


def test_orchestrator_load_saved_state_restores_queue_and_status(tmp_path: Path) -> None:
    _write_minimal_plan(tmp_path)
    first = ExecutionOrchestrator.create(project_path=tmp_path, use_mock=True)
    task = first._plan.tasks[0]

    task.status = TaskStatus.COMPLETED
    first._state.status = ExecutionStatus.PAUSED
    first._state.completed_tasks = 1
    first._state_store.save(first._state, first._plan)

    second = ExecutionOrchestrator.create(project_path=tmp_path, use_mock=True)
    loaded = second.load_saved_state()

    assert loaded is True
    assert second.get_status()["status"] == "paused"
    assert second.get_status()["completed"] == 1
    assert task.id in second._queue.completed
    assert task.id not in second._queue.pending


def test_worker_manager_uses_worker_max_concurrency(tmp_path: Path) -> None:
    config = AgentWhipConfig()
    config.claude.max_concurrent = 7
    manager = WorkerManager(config=config, project_path=tmp_path)

    assert manager._get_default_max_concurrent() == 7
