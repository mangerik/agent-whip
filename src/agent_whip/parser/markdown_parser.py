"""
Markdown plan parser for AgentWhip.

Parses plan.md files and extracts phases, tasks, and dependencies.
"""

import re
from pathlib import Path
from typing import Optional

from agent_whip.models.plan import ExecutionPlan, PlanMetadata
from agent_whip.models.state import PhaseState
from agent_whip.models.task import Task, TaskStatus


class MarkdownParser:
    """Parser for plan.md markdown files."""

    # Regex patterns
    PROJECT_TITLE_RE = re.compile(r"^#\s+Project\s+Plan:\s*(.+)$", re.IGNORECASE)
    PHASE_HEADING_RE = re.compile(r"^###\s+Phase\s+(\d+):\s*(.+)$", re.IGNORECASE)
    TASK_RE = re.compile(r"^\s*-\s+\[\s*\]\s*(.+)$")
    DEPENDS_RE = re.compile(r"Depends\s+on:\s*(.+)$", re.IGNORECASE)
    H2_RE = re.compile(r"^##\s+(.+)$")

    def __init__(self, content: str, source_path: Path):
        """Initialize parser with markdown content."""
        self.content = content
        self.source_path = source_path
        self.lines = content.split("\n")
        self.metadata = PlanMetadata()
        self.phases: list[PhaseState] = []
        self.tasks: list[Task] = []

    def parse(self) -> ExecutionPlan:
        """Parse the markdown and return an ExecutionPlan."""
        self._parse_metadata()
        self._parse_phases_and_tasks()

        plan = ExecutionPlan(
            source_path=self.source_path,
            raw_content=self.content,
            metadata=self.metadata,
        )

        # Add phases
        for phase in self.phases:
            plan.add_phase(phase)

        # Add tasks
        for task in self.tasks:
            plan.add_task(task)

        # Update phase task counts
        for phase in plan.phases:
            phase_tasks = plan.get_tasks_for_phase(phase.name)
            phase.task_ids = [t.id for t in phase_tasks]
            phase.total_tasks = len(phase_tasks)

        return plan

    def _parse_metadata(self):
        """Parse metadata from the markdown."""
        current_section = None
        current_list: list[str] = []

        for line in self.lines:
            # Check for project title
            title_match = self.PROJECT_TITLE_RE.match(line)
            if title_match:
                self.metadata.project_name = title_match.group(1).strip()
                continue

            # Check for H2 sections
            h2_match = self.H2_RE.match(line)
            if h2_match:
                # Save previous section
                self._save_section(current_section, current_list)
                current_section = h2_match.group(1).strip().lower()
                current_list = []
                continue

            # Collect list items
            stripped = line.strip()
            if stripped.startswith("- ") and current_section:
                current_list.append(stripped[2:].strip())

        # Save last section
        self._save_section(current_section, current_list)

    def _save_section(self, section: Optional[str], items: list[str]):
        """Save a section to metadata."""
        if not section:
            return

        if "overview" in section and items:
            self.metadata.overview = items[0] if items else None
        elif "goal" in section:
            self.metadata.goals.extend(items)
        elif "depend" in section and "success" not in section:
            self.metadata.dependencies.extend(items)
        elif "success" in section:
            self.metadata.success_criteria.extend(items)
        elif "note" in section:
            self.metadata.notes.extend(items)

    def _parse_phases_and_tasks(self):
        """Parse phases and tasks from the markdown."""
        current_phase: Optional[PhaseState] = None
        task_counter = 0
        phase_task_counter = 0
        i = 0

        while i < len(self.lines):
            line = self.lines[i]

            # Check for phase heading
            phase_match = self.PHASE_HEADING_RE.match(line)
            if phase_match:
                # Save previous phase
                current_phase = self._create_phase(phase_match, current_phase, phase_task_counter)
                if current_phase:
                    self.phases.append(current_phase)
                phase_task_counter = 0
                i += 1
                continue

            # Check for task line
            if current_phase:
                task_match = self.TASK_RE.match(line)
                if task_match:
                    # Collect context lines that follow this task
                    context_lines = []
                    j = i + 1
                    while j < len(self.lines):
                        next_line = self.lines[j]
                        # Stop at next phase, next task, or blank line
                        if self.PHASE_HEADING_RE.match(next_line):
                            break
                        if self.TASK_RE.match(next_line):
                            break
                        if not next_line.strip():
                            break  # Stop at blank line
                        # Collect indented lines as context
                        context_lines.append(next_line.strip())
                        j += 1

                    # Create task with collected context
                    task = self._create_task(
                        task_match,
                        current_phase,
                        context_lines,
                        task_counter
                    )
                    self.tasks.append(task)
                    phase_task_counter += 1
                    task_counter += 1
                    i = j  # Skip to after the context lines
                    continue

            i += 1

    def _create_phase(
        self,
        match: re.Match,
        prev_phase: Optional[PhaseState],
        task_counter: int
    ) -> Optional[PhaseState]:
        """Create a PhaseState from a regex match."""
        if prev_phase:
            prev_phase.total_tasks = task_counter
            prev_phase.completed_tasks = 0

        phase_num = int(match.group(1))
        phase_name = match.group(2).strip()
        full_name = f"Phase {phase_num}: {phase_name}"

        return PhaseState(
            name=full_name,
            number=phase_num,
            description=None,
        )

    def _create_task(
        self,
        match: re.Match,
        phase: PhaseState,
        context: list[str],
        task_counter: int
    ) -> Task:
        """Create a Task from a regex match."""
        task_desc = match.group(1).strip()

        # Extract task ID if present (format: "TASK-001 Description")
        task_id = None
        id_match = re.match(r"^([A-Za-z0-9_-]+)\s+(.+)$", task_desc)
        if id_match:
            potential_id = id_match.group(1)
            # Check if it looks like a task ID (all caps or has hyphen/underscore)
            if potential_id.isupper() or "-" in potential_id or "_" in potential_id:
                task_id = potential_id
                task_desc = id_match.group(2)

        # Generate task ID if not present
        if not task_id:
            task_id = f"P{phase.number}-T{task_counter + 1:03d}"

        # Extract dependencies from context
        dependencies: list[str] = []
        cleaned_context: list[str] = []
        for ctx_line in context:
            dep_match = self.DEPENDS_RE.search(ctx_line)
            if dep_match:
                deps_str = dep_match.group(1).strip()
                # Parse comma-separated dependencies
                for dep in deps_str.split(","):
                    dep = dep.strip()
                    if dep:
                        dependencies.append(dep)
            else:
                cleaned_context.append(ctx_line)

        return Task(
            id=task_id,
            phase=phase.name,
            phase_number=phase.number,
            description=task_desc,
            status=TaskStatus.PENDING,
            dependencies=dependencies,
            context=cleaned_context,
        )


def parse_plan(plan_path: Path) -> ExecutionPlan:
    """
    Parse a plan.md file and return an ExecutionPlan.

    Args:
        plan_path: Path to the plan.md file

    Returns:
        Parsed ExecutionPlan

    Raises:
        FileNotFoundError: If plan.md doesn't exist
        ValueError: If plan.md is invalid
    """
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan file not found: {plan_path}")

    content = plan_path.read_text(encoding="utf-8")

    if not content.strip():
        raise ValueError(f"Plan file is empty: {plan_path}")

    parser = MarkdownParser(content, plan_path)
    plan = parser.parse()

    # Validate the plan
    errors = plan.validate_dependencies()
    if errors:
        raise ValueError(f"Plan validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    if not plan.phases:
        raise ValueError(f"No phases found in plan: {plan_path}")

    if not plan.tasks:
        raise ValueError(f"No tasks found in plan: {plan_path}")

    return plan
