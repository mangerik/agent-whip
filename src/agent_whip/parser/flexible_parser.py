"""
Flexible plan parser using Claude AI.

This parser uses Claude to interpret any plan format and convert it
to the structured ExecutionPlan format that agent-whip uses.
"""

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from agent_whip.config import load_config
from agent_whip.models.plan import ExecutionPlan, PlanMetadata
from agent_whip.models.state import PhaseState
from agent_whip.models.task import Task, TaskStatus


class FlexibleParser(BaseModel):
    """
    Parser that uses Claude AI to interpret any plan format.

    This allows agent-whip to work with:
    - Free-form todo lists
    - Notion exports
    - GitHub Issues
    - Simple markdown notes
    - Any text format that describes tasks
    """

    project_path: Path = Field(description="Project path for context")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def parse(self, plan_path: Path) -> ExecutionPlan:
        """
        Parse any plan format using Claude AI.

        Args:
            plan_path: Path to plan file

        Returns:
            Parsed ExecutionPlan
        """
        # Read plan content
        if not plan_path.exists():
            raise FileNotFoundError(f"Plan file not found: {plan_path}")

        content = plan_path.read_text(encoding="utf-8")

        if not content.strip():
            raise ValueError(f"Plan file is empty: {plan_path}")

        # Use Claude to interpret the plan
        structured_plan = await self._interpret_with_claude(content, plan_path)

        # Build ExecutionPlan from Claude's response
        return self._build_execution_plan(structured_plan, plan_path, content)

    async def _interpret_with_claude(self, content: str, plan_path: Path) -> dict:
        """
        Send plan to Claude and get structured interpretation.

        Args:
            content: Raw plan content
            plan_path: Path to plan file

        Returns:
            Structured plan data as dict
        """
        import httpx

        # Load config for API access
        config = load_config(self.project_path)

        # Build prompt for Claude
        prompt = self._build_interpretation_prompt(content)

        # Call Claude API
        base_url = getattr(config.claude, "base_url", "https://api.anthropic.com")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url.rstrip('/')}/v1"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{base_url}/messages",
                headers={
                    "x-api-key": config.claude.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": config.claude.model or "claude-opus-4-6",
                    "max_tokens": 8192,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                }
            )
            response.raise_for_status()
            result = response.json()

        # Extract and parse Claude's response
        return self._extract_structured_plan(result, content)

    def _build_interpretation_prompt(self, content: str) -> str:
        """Build prompt for Claude to interpret the plan."""
        return f"""You are a task planning assistant. Your job is to extract a structured execution plan from the following plan content.

Plan content:
```
{content}
```

Your task:
1. Extract ALL tasks mentioned in the plan
2. Identify dependencies between tasks (e.g., "after X completes", "depends on X")
3. Group related tasks into phases if possible
4. Generate unique IDs for each task

Return your response as a JSON object with this exact structure:

{{
    "project_name": "Project name or 'Untitled Project'",
    "overview": "Brief description of what this plan is about",
    "phases": [
        {{
            "name": "Phase 1: Description",
            "number": 1,
            "description": "What this phase accomplishes"
        }}
    ],
    "tasks": [
        {{
            "id": "TASK-001",
            "phase": "Phase 1: Description",
            "description": "What needs to be done",
            "dependencies": [],
            "context": ["Additional notes or requirements"]
        }}
    ]
}}

Rules:
- Generate task IDs in format: TASK-001, TASK-002, etc.
- For dependencies, use the exact task IDs
- If no clear phases, put all tasks in "Phase 1: Implementation"
- Include context as an array of relevant notes or requirements
- Preserve ALL tasks from the original plan
- Be thorough - don't skip anything

Respond ONLY with the JSON object, no other text.
"""

    def _extract_structured_plan(self, claude_response: dict, original_content: str) -> dict:
        """Extract structured plan from Claude's response."""
        try:
            # Try to extract JSON from content
            content_blocks = claude_response.get("content", [])

            for block in content_blocks:
                if block.get("type") == "text":
                    text = block.get("text", "")

                    # Look for JSON in the response
                    # Try to find a complete JSON object
                    start_idx = text.find("{")
                    end_idx = text.rfind("}") + 1

                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = text[start_idx:end_idx]
                        return json.loads(json_str)

            # If no JSON found, try parsing the entire text as JSON
            for block in content_blocks:
                if block.get("type") == "text":
                    text = block.get("text", "").strip()
                    if text.startswith("{") and text.endswith("}"):
                        return json.loads(text)

        except (json.JSONDecodeError, KeyError) as e:
            # Fallback: create a simple plan from raw content
            return self._create_fallback_plan(original_content)

        # If still no valid plan, use fallback
        return self._create_fallback_plan(original_content)

    def _create_fallback_plan(self, content: str) -> dict:
        """Create a simple plan from raw content when JSON parsing fails."""
        lines = content.strip().split("\n")
        tasks = []
        task_counter = 1

        for line in lines:
            line = line.strip()
            # Skip empty lines and headers
            if not line or line.startswith("#"):
                continue
            # Skip lines that look like headers
            if line.startswith("---") or line.startswith("==="):
                continue

            # Try to extract tasks from various formats
            # Format: "- task", "1. task", "* task", "- [ ] task", etc.
            import re
            task_match = re.match(r"^[\s\-\*\d\[\]]+(.*)$", line)
            if task_match:
                task_desc = task_match.group(1).strip()
                # Clean up common prefixes
                task_desc = re.sub(r"^[\[\]x\s]+", "", task_desc)
                task_desc = re.sub(r"^\d+\.\s*", "", task_desc)

                if task_desc:
                    tasks.append({
                        "id": f"TASK-{task_counter:03d}",
                        "phase": "Phase 1: Execution",
                        "description": task_desc,
                        "dependencies": [],
                        "context": []
                    })
                    task_counter += 1

        return {
            "project_name": "Extracted Plan",
            "overview": "Tasks extracted from plan content",
            "phases": [{"name": "Phase 1: Execution", "number": 1, "description": "Execute tasks"}],
            "tasks": tasks
        }

    def _build_execution_plan(
        self,
        structured_plan: dict,
        source_path: Path,
        raw_content: str
    ) -> ExecutionPlan:
        """Build ExecutionPlan from structured data."""
        # Create metadata
        metadata = PlanMetadata(
            project_name=structured_plan.get("project_name", "Untitled Project"),
            overview=structured_plan.get("overview"),
        )

        # Create plan
        plan = ExecutionPlan(
            source_path=source_path,
            raw_content=raw_content,
            metadata=metadata,
        )

        # Add phases
        for phase_data in structured_plan.get("phases", []):
            phase = PhaseState(
                name=phase_data["name"],
                number=phase_data.get("number", 1),
                description=phase_data.get("description"),
            )
            plan.add_phase(phase)

        # Add tasks
        for task_data in structured_plan.get("tasks", []):
            task = Task(
                id=task_data["id"],
                phase=task_data.get("phase", "Phase 1: Execution"),
                phase_number=self._get_phase_number(plan, task_data.get("phase", "Phase 1: Execution")),
                description=task_data["description"],
                status=TaskStatus.PENDING,
                dependencies=task_data.get("dependencies", []),
                context=task_data.get("context", []),
            )
            plan.add_task(task)

        return plan

    def _get_phase_number(self, plan: ExecutionPlan, phase_name: str) -> int:
        """Get phase number from phase name."""
        for phase in plan.phases:
            if phase.name == phase_name:
                return phase.number
        return 1


async def parse_plan_flexible(plan_path: Path, project_path: Path) -> ExecutionPlan:
    """
    Parse a plan file using flexible AI-powered parsing.

    This function can handle any plan format by using Claude AI to interpret it.

    Args:
        plan_path: Path to plan file
        project_path: Project path for context

    Returns:
        Parsed ExecutionPlan

    Raises:
        FileNotFoundError: If plan file doesn't exist
        ValueError: If plan file is empty or parsing fails
    """
    parser = FlexibleParser(project_path=project_path)
    return await parser.parse(plan_path)
