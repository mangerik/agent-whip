"""
OpenCode AI worker for AgentWhip.

Worker that connects to OpenCode API for task execution.
"""

import time
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel

from agent_whip.config import OpenCodeConfig
from agent_whip.models.handover import HandoverContext
from agent_whip.models.task import Task, TaskResult
from agent_whip.workers.base import ExecutionError, Worker


class OpenCodeWorker(Worker):
    """
    Worker that uses OpenCode API.

    This worker sends tasks to OpenCode and interprets the response.
    Supports token tracking and handover when threshold is reached.
    """

    @property
    def name(self) -> str:
        """Get worker name."""
        return "opencode"

    def __init__(
        self,
        config: OpenCodeConfig,
        project_path: Path,
        handover_context: Optional[HandoverContext] = None,
    ):
        """Initialize OpenCode worker."""
        super().__init__(config, project_path, handover_context)
        self.api_key = config.api_key
        self.model = config.model or "default"
        self.base_url = getattr(config, "base_url", "https://api.opencode.com")
        self._client: Optional[httpx.AsyncClient] = None

        # Last API response for token tracking
        self._last_response: Optional[dict] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            # Use configured base_url
            base = self.base_url.rstrip("/")

            self._client = httpx.AsyncClient(
                base_url=base,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                },
                timeout=self.config.timeout,
            )
        return self._client

    async def execute(self, task: Task) -> TaskResult:
        """
        Execute a task using OpenCode API.

        Args:
            task: Task to execute

        Returns:
            TaskResult with execution outcome
        """
        start_time = time.time()
        self._current_task = task

        try:
            prompt = self.get_prompt_for_task(task)

            # Call OpenCode API
            response = await self._call_opencode(prompt)

            # Extract token usage before parsing
            token_usage = self._get_token_usage(response)

            # Track usage if token tracker is available
            if self._token_tracker:
                self._token_tracker.record_usage(
                    input_tokens=token_usage["input_tokens"],
                    output_tokens=token_usage["output_tokens"],
                )

            # Parse response
            result = self._parse_response(response, task.id)

            # Add duration and token usage
            result.duration_seconds = time.time() - start_time
            result.worker_used = self.name
            result.model_used = self.model

            # Attach token usage to result
            result.usage = token_usage

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

    async def _call_opencode(self, prompt: str) -> dict:
        """
        Call OpenCode API with the given prompt.

        Args:
            prompt: Prompt to send

        Returns:
            API response as dict
        """
        client = self._get_client()

        # OpenCode API format (adjust based on actual API spec)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": 4096,
        }

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()

        response_data = response.json()
        self._last_response = response_data
        return response_data

    def _get_token_usage(self, response: dict) -> dict:
        """
        Extract token usage from API response.

        Args:
            response: API response dict

        Returns:
            Dict with input_tokens, output_tokens, total_tokens
        """
        # Try common token usage fields
        usage = response.get("usage", {})
        if usage:
            return {
                "input_tokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)),
                "output_tokens": usage.get("completion_tokens", usage.get("output_tokens", 0)),
                "total_tokens": usage.get("total_tokens", 0),
            }

        # Alternative: estimate from prompt and completion
        # This is a fallback if usage is not provided
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    def _parse_response(self, response: dict, task_id: str) -> TaskResult:
        """
        Parse OpenCode API response into TaskResult.

        Args:
            response: API response
            task_id: Task ID for error messages

        Returns:
            Parsed TaskResult
        """
        try:
            # Extract content from response
            # Adjust based on actual OpenCode API response format
            if "choices" in response:
                # OpenAI-style format
                choices = response.get("choices", [])
                if choices and "message" in choices[0]:
                    content = choices[0]["message"].get("content", "")
                else:
                    content = ""
            elif "output" in response:
                # Direct output format
                content = response.get("output", "")
            elif "content" in response:
                # Nested content format
                content = response.get("content", "")
            else:
                content = str(response)

            if not content:
                return self.create_failure_result(
                    error="Empty response from OpenCode",
                    output=str(response),
                )

            # Try to parse structured response
            success = self._extract_success(content)
            artifacts = self._extract_artifacts(content)
            code_changes = self._extract_code_changes(content)

            if success:
                return self.create_success_result(
                    output=content,
                    artifacts=artifacts,
                    code_changes=code_changes,
                )
            else:
                error_msg = self._extract_error(content)
                return self.create_failure_result(
                    error=error_msg or "Task marked as failed by OpenCode",
                    output=content,
                )

        except Exception as e:
            return self.create_failure_result(
                error=f"Failed to parse response: {e}",
                output=str(response),
            )

    def _extract_success(self, text: str) -> bool:
        """
        Extract success status from response text.

        Looks for patterns like:
        - "Success: yes" / "Success: no"
        - "Status: success" / "Status: failed"
        - "Task completed successfully"
        """
        text_lower = text.lower()

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

        # Check for success patterns
        for pattern in success_patterns:
            if pattern in text_lower:
                return True

        # Default: assume success if no explicit failure
        return "error" not in text_lower and "failed" not in text_lower

    def _extract_error(self, text: str) -> str | None:
        """Extract error message from response text."""
        # Look for error patterns
        lines = text.split("\n")
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(p in line_lower for p in ["error:", "error -", "failed:"]):
                # Return this line and next few lines as error
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

        # Look for file paths in common patterns
        lines = text.split("\n")
        for line in lines:
            line_lower = line.lower()
            for prefix in ["created file:", "file:", "wrote:", "saved:", "artifact:"]:
                if prefix in line_lower:
                    # Extract path after prefix
                    parts = line.split(prefix, 1)
                    if len(parts) > 1:
                        path = parts[1].strip().strip("`'\"")
                        if path and path not in artifacts:
                            artifacts.append(path)

        return artifacts

    def _extract_code_changes(self, text: str) -> dict[str, str]:
        """Extract code changes from response."""
        changes = {}

        # Look for code blocks with file paths
        lines = text.split("\n")
        current_file = None
        current_code = []
        in_code_block = False

        for line in lines:
            # Check for file path in code block fence
            if line.strip().startswith("```"):
                if not in_code_block:
                    # Starting code block
                    fence = line.strip()
                    parts = fence.split(":", 1)
                    if len(parts) > 1:
                        current_file = parts[1].split()[0]
                    else:
                        current_file = None
                    in_code_block = True
                    current_code = []
                else:
                    # Ending code block
                    if current_file and current_code:
                        changes[current_file] = "\n".join(current_code)
                    in_code_block = False
                    current_file = None
                    current_code = []
            elif in_code_block:
                current_code.append(line)

        return changes

    def is_available(self) -> bool:
        """Check if worker is available."""
        return bool(self.api_key and self.api_key != "${OPENCODE_API_KEY}")

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class MockOpenCodeWorker(Worker):
    """
    Mock OpenCode worker for testing.

    This worker simulates task execution without calling the actual API.
    """

    @property
    def name(self) -> str:
        """Get worker name."""
        return "mock-opencode"

    def __init__(
        self,
        config: OpenCodeConfig,
        project_path: Path,
        handover_context: Optional[HandoverContext] = None,
    ):
        """Initialize mock worker."""
        super().__init__(config, project_path, handover_context)
        self.model = config.model or "mock-opencode"
        self.executed_tasks: list[Task] = []

        # Mock token usage
        self._mock_token_usage: int = 0

    async def execute(self, task: Task) -> TaskResult:
        """Simulate task execution."""
        import asyncio

        self.executed_tasks.append(task)

        # Simulate work
        await asyncio.sleep(0.1)

        # Simulate token usage (mock: ~1000 tokens per task)
        mock_input_tokens = 500
        mock_output_tokens = 500

        if self._token_tracker:
            self._token_tracker.record_usage(mock_input_tokens, mock_output_tokens)

        # Mock successful response
        result = self.create_success_result(
            output=f"[OpenCode] Mock execution of task: {task.description}\n"
                   f"Task ID: {task.id}\n"
                   f"Phase: {task.phase}\n"
                   f"Dependencies: {task.dependencies}\n"
                   f"Context: {task.context}",
            artifacts=[],
            code_changes={},
            duration=0.1,
        )

        # Attach mock usage
        result.usage = {
            "input_tokens": mock_input_tokens,
            "output_tokens": mock_output_tokens,
            "total_tokens": mock_input_tokens + mock_output_tokens,
        }

        return result

    def is_available(self) -> bool:
        """Mock worker is always available."""
        return True
