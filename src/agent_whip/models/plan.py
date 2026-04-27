"""
Execution plan models for AgentWhip.
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from agent_whip.models.task import Task, TaskStatus
from agent_whip.models.state import PhaseState


class PlanMetadata(BaseModel):
    """Metadata extracted from plan.md."""

    project_name: Optional[str] = Field(default=None, description="Project name from title")
    overview: Optional[str] = Field(default=None, description="Project overview")
    goals: list[str] = Field(default_factory=list, description="Project goals")
    dependencies: list[str] = Field(default_factory=list, description="External dependencies")
    success_criteria: list[str] = Field(default_factory=list, description="Success criteria")
    notes: list[str] = Field(default_factory=list, description="Additional notes")


class ExecutionPlan(BaseModel):
    """Parsed execution plan from plan.md."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Source
    source_path: Path = Field(description="Path to plan.md")
    raw_content: str = Field(description="Raw markdown content")

    # Metadata
    metadata: PlanMetadata = Field(default_factory=PlanMetadata)

    # Phases
    phases: list[PhaseState] = Field(default_factory=list, description="All phases")
    phase_map: dict[str, PhaseState] = Field(default_factory=dict, description="Phase name -> state")

    # Tasks
    tasks: list[Task] = Field(default_factory=list, description="All tasks")
    task_map: dict[str, Task] = Field(default_factory=dict, description="Task ID -> task")

    # Dependency graph (adjacency list)
    dependency_graph: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Task ID -> list of dependent task IDs"
    )

    # Reverse dependency graph
    reverse_dependency_graph: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Task ID -> list of tasks that depend on this"
    )

    @property
    def total_phases(self) -> int:
        """Total number of phases."""
        return len(self.phases)

    @property
    def total_tasks(self) -> int:
        """Total number of tasks."""
        return len(self.tasks)

    @property
    def project_name(self) -> str:
        """Get project name from metadata or default."""
        return self.metadata.project_name or "Unnamed Project"

    def add_phase(self, phase: PhaseState):
        """Add a phase to the plan."""
        self.phases.append(phase)
        self.phase_map[phase.name] = phase

    def add_task(self, task: Task):
        """Add a task to the plan."""
        self.tasks.append(task)
        self.task_map[task.id] = task

        # Update dependency graphs
        self.dependency_graph[task.id] = task.dependencies.copy()

        # Build reverse graph
        for dep_id in task.dependencies:
            if dep_id not in self.reverse_dependency_graph:
                self.reverse_dependency_graph[dep_id] = []
            self.reverse_dependency_graph[dep_id].append(task.id)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self.task_map.get(task_id)

    def get_phase(self, phase_name: str) -> Optional[PhaseState]:
        """Get phase by name."""
        return self.phase_map.get(phase_name)

    def get_phase_by_number(self, number: int) -> Optional[PhaseState]:
        """Get phase by number."""
        for phase in self.phases:
            if phase.number == number:
                return phase
        return None

    def get_tasks_for_phase(self, phase_name: str) -> list[Task]:
        """Get all tasks for a phase."""
        return [t for t in self.tasks if t.phase == phase_name]

    def get_ready_tasks(self) -> list[Task]:
        """Get tasks whose dependencies are all satisfied."""
        ready = []
        for task in self.tasks:
            if task.status not in (TaskStatus.PENDING, TaskStatus.RETRYING):
                continue

            # Check if all dependencies are completed
            deps_satisfied = True
            for dep_id in task.dependencies:
                dep_task = self.get_task(dep_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    deps_satisfied = False
                    break

            if deps_satisfied:
                ready.append(task)

        return ready

    def validate_dependencies(self) -> list[str]:
        """Validate dependencies. Returns list of errors."""
        errors = []

        # Check for circular dependencies using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(task_id: str, path: list[str]) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)
            path.append(task_id)

            for dep_id in self.dependency_graph.get(task_id, []):
                if dep_id not in self.task_map:
                    errors.append(f"Task '{task_id}' depends on non-existent task '{dep_id}'")
                    continue

                if dep_id not in visited:
                    if has_cycle(dep_id, path):
                        return True
                elif dep_id in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(dep_id)
                    cycle = " -> ".join(path[cycle_start:] + [dep_id])
                    errors.append(f"Circular dependency detected: {cycle}")
                    return True

            path.pop()
            rec_stack.remove(task_id)
            return False

        for task_id in self.task_map:
            if task_id not in visited:
                has_cycle(task_id, [])

        return errors
