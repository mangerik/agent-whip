"""
OpenCode CLI worker for AgentWhip.

Worker that uses the installed 'opencode' CLI via subprocess.
"""

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from agent_whip.config import OpenCodeConfig
from agent_whip.models.handover import HandoverContext
from agent_whip.models.task import Task, TaskResult
from agent_whip.workers.base import Worker


class OpenCodeCLIWorker(Worker):
    """
    Worker that uses OpenCode CLI via subprocess.

    This worker calls the 'opencode' command installed on the system.
    Falls back to API mode if CLI is not available.
    """

    @property
    def name(self) -> str:
        """Get worker name."""
        return "opencode-cli"

    def __init__(
        self,
        config: OpenCodeConfig,
        project_path: Path,
        handover_context: Optional[HandoverContext] = None,
    ):
        """Initialize OpenCode CLI worker."""
        super().__init__(config, project_path, handover_context)
        self.config = config
        self.model = config.model or "default"
        self.cli_path = self._find_opencode_cli()
        self._available = self.cli_path is not None

    def _find_opencode_cli(self) -> Optional[str]:
        """Find the opencode CLI executable."""
        # Check if 'opencode' command exists
        opencode_path = shutil.which("opencode")
        if opencode_path:
            return opencode_path

        # Check common paths
        common_paths = [
            Path.home() / ".local" / "bin" / "opencode",
            Path("/usr/local/bin/opencode"),
            Path("/opt/opencode/bin/opencode"),
        ]

        for path in common_paths:
            if path.exists() and os.access(path, os.X_OK):
                return str(path)

        return None

    async def execute(self, task: Task) -> TaskResult:
        """
        Execute a task using OpenCode CLI.

        Args:
            task: Task to execute

        Returns:
            TaskResult with execution outcome
        """
        import time

        start_time = time.time()
        self._current_task = task

        try:
            if not self.is_available():
                return self.create_failure_result(
                    error="OpenCode CLI not found. Install OpenCode CLI first.",
                    output="OpenCode CLI not available",
                )

            prompt = self.get_prompt_for_task(task)

            # Call OpenCode CLI
            response = await self._call_opencode_cli(prompt)

            # Parse response
            result = self._parse_response(response, task.id)

            # Add duration
            result.duration_seconds = time.time() - start_time
            result.worker_used = self.name
            result.model_used = self.model

            return result

        except Exception as e:
            duration = time.time() - start_time
            return self.create_failure_result(
                error=str(e),
                output=f"Execution failed: {e}",
                duration=duration,
            )
        finally:
            self._current_task = None

    async def _call_opencode_cli(self, prompt: str) -> str:
        """
        Call OpenCode CLI with the given prompt.

        Uses 'opencode run' command for non-interactive execution.
        """
        # Build command: opencode run "prompt"
        cmd = [
            self.cli_path,
            "run",
            prompt,
        ]

        # Create process
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.project_path,
        )

        # Wait for response
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenCode CLI failed: {error_msg}")

        return stdout.decode("utf-8", errors="replace")

    def _parse_response(self, response: str, task_id: str) -> TaskResult:
        """
        Parse OpenCode CLI response into TaskResult.

        Args:
            response: CLI output
            task_id: Task ID for error messages

        Returns:
            Parsed TaskResult
        """
        try:
            if not response or not response.strip():
                return self.create_failure_result(
                    error="Empty response from OpenCode CLI",
                    output="",
                )

            # Try to parse as JSON first (structured output mode)
            if response.strip().startswith("{"):
                try:
                    data = json.loads(response)
                    success = data.get("success", True)
                    output = data.get("output", response)
                    artifacts = data.get("artifacts", [])
                    code_changes = data.get("code_changes", {})

                    if success:
                        return self.create_success_result(
                            output=output,
                            artifacts=artifacts,
                            code_changes=code_changes,
                        )
                    else:
                        return self.create_failure_result(
                            error=data.get("error", "Task failed"),
                            output=output,
                        )
                except json.JSONDecodeError:
                    pass  # Fall through to text parsing

            # Parse as text
            success = self._extract_success(response)
            artifacts = self._extract_artifacts(response)
            code_changes = self._extract_code_changes(response)

            if success:
                return self.create_success_result(
                    output=response,
                    artifacts=artifacts,
                    code_changes=code_changes,
                )
            else:
                error_msg = self._extract_error(response)
                return self.create_failure_result(
                    error=error_msg or "Task marked as failed by OpenCode",
                    output=response,
                )

        except Exception as e:
            return self.create_failure_result(
                error=f"Failed to parse response: {e}",
                output=response[:500] if response else "",
            )

    def _extract_success(self, text: str) -> bool:
        """Extract success status from response text."""
        text_lower = text.lower()

        # Explicit failure indicators
        failure_patterns = [
            "success: no",
            "success: false",
            "status: failed",
            "status: failure",
            "task failed",
            "failed to complete",
            "✗ failed",
            "error: ",
        ]

        # Check for failure patterns first
        for pattern in failure_patterns:
            if pattern in text_lower:
                return False

        # Explicit success indicators
        success_patterns = [
            "success: yes",
            "success: true",
            "status: success",
            "status: completed",
            "task completed successfully",
            "successfully completed",
            "✓ success",
            "✓ done",
            "<done>",
        ]

        for pattern in success_patterns:
            if pattern in text_lower:
                return True

        # Default: assume success if no explicit failure
        return "error" not in text_lower and "failed" not in text_lower

    def _extract_error(self, text: str) -> str | None:
        """Extract error message from response text."""
        lines = text.split("\n")
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(p in line_lower for p in ["error:", "error -", "failed:"]):
                error_lines = [line.strip()]
                for j in range(i + 1, min(i + 3, len(lines))):
                    if lines[j].strip() and not lines[j].startswith("#"):
                        error_lines.append(lines[j].strip())
                    else:
                        break
                return " ".join(error_lines)

        return None

    def _extract_artifacts(self, text: str) -> list[str]:
        """Extract file paths/artifacts from response."""
        artifacts = []

        lines = text.split("\n")
        for line in lines:
            line_lower = line.lower()
            for prefix in ["created file:", "file:", "wrote:", "saved:", "artifact:"]:
                if prefix in line_lower:
                    parts = line.split(prefix, 1)
                    if len(parts) > 1:
                        path = parts[1].strip().strip("`'\"")
                        if path and path not in artifacts:
                            artifacts.append(path)

        return artifacts

    def _extract_code_changes(self, text: str) -> dict[str, str]:
        """Extract code changes from response."""
        changes = {}

        lines = text.split("\n")
        current_file = None
        current_code = []
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                if not in_code_block:
                    fence = line.strip()
                    parts = fence.split(":", 1)
                    if len(parts) > 1:
                        current_file = parts[1].split()[0]
                    else:
                        current_file = None
                    in_code_block = True
                    current_code = []
                else:
                    if current_file and current_code:
                        changes[current_file] = "\n".join(current_code)
                    in_code_block = False
                    current_file = None
                    current_code = []
            elif in_code_block:
                current_code.append(line)

        return changes

    def is_available(self) -> bool:
        """Check if OpenCode CLI is available."""
        return self._available


class MockOpenCodeCLIWorker(Worker):
    """
    Mock OpenCode CLI worker for testing.

    Simulates CLI execution without actually calling the CLI.
    """

    @property
    def name(self) -> str:
        """Get worker name."""
        return "mock-opencode-cli"

    def __init__(
        self,
        config: OpenCodeConfig,
        project_path: Path,
        handover_context: Optional[HandoverContext] = None,
    ):
        """Initialize mock worker."""
        super().__init__(config, project_path, handover_context)
        self.model = config.model or "mock-opencode-cli"
        self.executed_tasks: list[Task] = []

    async def execute(self, task: Task) -> TaskResult:
        """Simulate task execution."""
        import time

        self.executed_tasks.append(task)

        # Simulate work
        await asyncio.sleep(0.1)

        # Mock successful response
        result = self.create_success_result(
            output=f"[OpenCode CLI] Mock execution of task: {task.description}\n"
                   f"Task ID: {task.id}\n"
                   f"Phase: {task.phase}\n"
                   f"Dependencies: {task.dependencies}\n"
                   f"Context: {task.context}",
            artifacts=[],
            code_changes={},
            duration=0.1,
        )

        return result

    def is_available(self) -> bool:
        """Mock worker is always available."""
        return True
