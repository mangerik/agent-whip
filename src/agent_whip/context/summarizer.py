"""
Context Summarizer for Handover.

Creates compact summaries of work done for continuation by new worker.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_whip.models import ExecutionPlan, ExecutionState, PhaseState, Task, TaskStatus
from agent_whip.models.handover import (
    DecisionRecord,
    HandoverContext,
    generate_handover_id,
)


class ContextSummarizer:
    """
    Summarizes context for handover between workers.

    Creates a compact representation of all work done, decisions made,
    and current state so a new worker can continue seamlessly.
    """

    def __init__(
        self,
        max_summary_length: int = 10000,
        include_artifacts: bool = True,
        include_decisions: bool = True,
    ):
        """
        Initialize context summarizer.

        Args:
            max_summary_length: Maximum length of work summary in characters
            include_artifacts: Whether to include file artifacts
            include_decisions: Whether to include decision records
        """
        self.max_summary_length = max_summary_length
        self.include_artifacts = include_artifacts
        self.include_decisions = include_decisions

    async def summarize_handover(
        self,
        state: ExecutionState,
        plan: ExecutionPlan,
        task: Task,
        work_done: str,
        from_worker_id: str,
    ) -> HandoverContext:
        """
        Generate handover context for current work.

        Args:
            state: Current execution state
            plan: Execution plan with all phases/tasks
            task: Current task being worked on
            work_done: Work completed so far (from task result)
            from_worker_id: ID of worker handing over

        Returns:
            HandoverContext with all necessary information
        """
        handover_id = generate_handover_id()

        # Get current phase info
        current_phase_obj = plan.get_phase(task.phase)
        phase_tasks = plan.get_tasks_for_phase(task.phase)

        # Calculate phase progress
        completed_in_phase = sum(
            1 for t in phase_tasks if t.status == TaskStatus.COMPLETED
        )
        phase_progress = (
            completed_in_phase / len(phase_tasks) if phase_tasks else 0.0
        )

        # Gather completed/pending/failed tasks
        tasks_completed = self._get_completed_task_ids(plan)
        tasks_pending = self._get_pending_task_ids(plan)
        tasks_failed = self._get_failed_task_ids(plan)

        # Gather artifacts
        files_created, files_modified = self._gather_artifacts(plan)

        # Extract decisions (if any)
        decisions = self._extract_decisions(state, plan)

        # Create work summary
        work_summary = self._create_work_summary(
            state=state,
            plan=plan,
            current_phase=task.phase,
            current_task=task,
            work_done=work_done,
            tasks_completed=len(tasks_completed),
            tasks_pending=len(tasks_pending),
        )

        # Create context snapshot
        context_snapshot = self._create_context_snapshot(state, plan)

        return HandoverContext(
            handover_id=handover_id,
            timestamp=datetime.now(timezone.utc),
            project_name=state.project_name,
            project_path=state.project_path,
            current_phase=task.phase,
            current_task=task.id,
            phase_progress=round(phase_progress, 2),
            work_summary=work_summary,
            tasks_completed=tasks_completed,
            tasks_pending=tasks_pending,
            tasks_failed=tasks_failed,
            files_created=files_created,
            files_modified=files_modified,
            decisions_made=decisions,
            context_snapshot=context_snapshot,
            from_worker_id=from_worker_id,
            tokens_used=0,  # Will be filled by caller
            session_duration=0.0,  # Will be filled by caller
            handover_reason="token_threshold",
        )

    def _get_completed_task_ids(self, plan: ExecutionPlan) -> list[str]:
        """Get list of completed task IDs."""
        return [
            task.id
            for phase in plan.phases
            for task in phase.tasks
            if task.status == TaskStatus.COMPLETED
        ]

    def _get_pending_task_ids(self, plan: ExecutionPlan) -> list[str]:
        """Get list of pending task IDs."""
        return [
            task.id
            for phase in plan.phases
            for task in phase.tasks
            if task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
        ]

    def _get_failed_task_ids(self, plan: ExecutionPlan) -> list[str]:
        """Get list of failed task IDs."""
        return [
            task.id
            for phase in plan.phases
            for task in phase.tasks
            if task.status == TaskStatus.FAILED
        ]

    def _gather_artifacts(
        self, plan: ExecutionPlan
    ) -> tuple[list[str], list[str]]:
        """
        Gather file artifacts from all completed tasks.

        Returns:
            Tuple of (files_created, files_modified)
        """
        files_created = set()
        files_modified = set()

        for phase in plan.phases:
            for task in phase.tasks:
                if task.result and task.result.artifacts:
                    for artifact in task.result.artifacts:
                        # Simple heuristic - could be improved
                        if "created" in artifact.lower() or "new" in artifact.lower():
                            files_created.add(artifact)
                        else:
                            files_modified.add(artifact)

                if task.result and task.result.code_changes:
                    files_modified.update(task.result.code_changes.keys())

        return sorted(files_created), sorted(files_modified)

    def _extract_decisions(
        self, state: ExecutionState, plan: ExecutionPlan
    ) -> list[DecisionRecord]:
        """
        Extract decisions made during execution.

        This is a placeholder - in production, this would parse
        task results for decision markers or use AI to extract.
        """
        decisions = []

        # For now, check if state has any stored decisions
        if hasattr(state, "decisions"):
            for d in state.decisions:
                decisions.append(
                    DecisionRecord(
                        timestamp=d.get("timestamp", datetime.now(timezone.utc)),
                        topic=d.get("topic", "unknown"),
                        decision=d.get("decision", ""),
                        rationale=d.get("rationale", ""),
                        alternatives=d.get("alternatives", []),
                    )
                )

        return decisions

    def _create_work_summary(
        self,
        state: ExecutionState,
        plan: ExecutionPlan,
        current_phase: str,
        current_task: Task,
        work_done: str,
        tasks_completed: int,
        tasks_pending: int,
    ) -> str:
        """
        Create a human-readable work summary.

        This provides a quick overview for the new worker.
        """
        lines = [
            f"# Work Summary for {state.project_name}",
            "",
            f"**Status**: {state.status.value}",
            f"**Progress**: {state.completed_tasks}/{state.total_tasks} tasks completed",
            f"**Current Phase**: {current_phase}",
            f"**Current Task**: {current_task.id} - {current_task.description}",
            "",
            "## Completed Work",
        ]

        # Add completed phases summary
        for phase in plan.phases:
            if phase.name == current_phase:
                break  # Don't summarize current phase yet

            phase_tasks = plan.get_tasks_for_phase(phase.name)
            completed_count = sum(
                1 for t in phase_tasks if t.status == TaskStatus.COMPLETED
            )

            if completed_count > 0:
                lines.append(f"\n### {phase.name}")
                lines.append(f"- Completed {completed_count}/{len(phase_tasks)} tasks")

                # Add brief task descriptions
                for task in phase_tasks:
                    if task.status == TaskStatus.COMPLETED:
                        lines.append(f"  - {task.id}: {task.description[:50]}...")

        # Add current work
        lines.extend([
            "",
            "## Current Work",
            "",
            f"Currently working on: {current_task.description}",
            "",
            "### Progress So Far:",
            work_done[:500] + "..." if len(work_done) > 500 else work_done,
            "",
            "## Remaining Work",
            "",
            f"- {tasks_pending} tasks remaining",
            f"- {len(plan.phases) - plan.phases.index(plan.get_phase(current_phase))} phases remaining",
        ])

        summary = "\n".join(lines)

        # Truncate if too long
        if len(summary) > self.max_summary_length:
            summary = summary[: self.max_summary_length - 3] + "..."

        return summary

    def _create_context_snapshot(
        self, state: ExecutionState, plan: ExecutionPlan
    ) -> dict:
        """
        Create a compact snapshot of current execution state.

        This is a minimal representation for the new worker.
        """
        return {
            "project": {
                "name": state.project_name,
                "path": state.project_path,
            },
            "execution": {
                "status": state.status.value,
                "total_phases": state.total_phases,
                "total_tasks": state.total_tasks,
                "completed_tasks": state.completed_tasks,
                "failed_tasks": state.failed_tasks,
                "started_at": state.started_at.isoformat() if state.started_at else None,
                "last_updated": state.last_updated.isoformat() if state.last_updated else None,
            },
            "current": {
                "phase": state.current_phase,
                "task": state.current_task,
            },
            "phases": [
                {
                    "name": phase.name,
                    "total_tasks": len(phase.tasks),
                    "completed_tasks": sum(
                        1 for t in phase.tasks if t.status == TaskStatus.COMPLETED
                    ),
                }
                for phase in plan.phases
            ],
        }

    async def summarize_phase(self, phase: PhaseState) -> dict:
        """
        Summarize a completed phase.

        Args:
            phase: Phase to summarize

        Returns:
            Dictionary with phase summary
        """
        total_tasks = phase.total_tasks
        completed = phase.completed_tasks
        failed = 0  # PhaseState doesn't track failed directly

        return {
            "phase_name": phase.name,
            "total_tasks": total_tasks,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "progress_percentage": round((completed / total_tasks * 100) if total_tasks > 0 else 0, 2),
            "task_ids": phase.task_ids,
        }

    async def summarize_task_history(
        self, tasks: list[Task]
    ) -> dict:
        """
        Summarize task execution history.

        Args:
            tasks: List of tasks to summarize

        Returns:
            Dictionary with task history summary
        """
        completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in tasks if t.status == TaskStatus.FAILED]
        pending = [t for t in tasks if t.status == TaskStatus.PENDING]

        return {
            "total_tasks": len(tasks),
            "completed": len(completed),
            "failed": len(failed),
            "pending": len(pending),
            "recently_completed": [
                {
                    "id": t.id,
                    "description": t.description[:100],
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                }
                for t in completed[-5:]  # Last 5 completed
            ],
        }
