"""
Claude AI worker for AgentWhip.
"""

import asyncio
import time
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel

from agent_whip.config import ClaudeConfig
from agent_whip.models.handover import HandoverContext
from agent_whip.models.task import Task, TaskResult
from agent_whip.workers.base import ExecutionError, Worker


class ClaudeWorker(Worker):
    """
    Worker that uses Anthropic's Claude API.

    This worker sends tasks to Claude and interprets the response.
    Supports token tracking and handover when threshold is reached.
    """

    @property
    def name(self) -> str:
        """Get worker name."""
        return "claude"

    def __init__(
        self,
        config: ClaudeConfig,
        project_path: Path,
        handover_context: Optional[HandoverContext] = None,
    ):
        """Initialize Claude worker."""
        super().__init__(config, project_path, handover_context)
        self.api_key = config.api_key
        self.model = config.model or "claude-opus-4-6"
        self.base_url = getattr(config, "base_url", "https://api.anthropic.com")
        self._client: Optional[httpx.AsyncClient] = None

        # Last API response for token tracking
        self._last_response: Optional[dict] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            # Use configured base_url, ensure it ends with /v1
            base = self.base_url.rstrip("/")
            if not base.endswith("/v1"):
                base = f"{base}/v1"

            self._client = httpx.AsyncClient(
                base_url=base,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                timeout=self.config.timeout,
            )
        return self._client

    async def execute(self, task: Task) -> TaskResult:
        """
        Execute a task using Claude API.

        Args:
            task: Task to execute

        Returns:
            TaskResult with execution outcome
        """
        start_time = time.time()
        self._current_task = task

        try:
            prompt = self.get_prompt_for_task(task)

            # Call Claude API
            response = await self._call_claude(prompt)

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

    async def _call_claude(self, prompt: str) -> dict:
        """
        Call Claude API with the given prompt.

        Args:
            prompt: Prompt to send

        Returns:
            API response as dict
        """
        client = self._get_client()

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        response = await client.post("/messages", json=payload)
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
        usage = response.get("usage", {})
        return {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        }

    def _parse_response(self, response: dict, task_id: str) -> TaskResult:
        """
        Parse Claude API response into TaskResult.

        Args:
            response: API response
            task_id: Task ID for error messages

        Returns:
            Parsed TaskResult
        """
        try:
            # Extract content from response
            content = response.get("content", [])
            if not content:
                return self.create_failure_result(
                    error="Empty response from Claude",
                    output="No content in API response",
                )

            # Get text content
            text_content = ""
            for block in content:
                if block.get("type") == "text":
                    text_content += block.get("text", "")

            if not text_content:
                return self.create_failure_result(
                    error="No text content in response",
                    output=str(response),
                )

            # Try to parse structured response
            # Look for patterns like "Success: yes/no" or parse as structured data
            success = self._extract_success(text_content)
            artifacts = self._extract_artifacts(text_content)
            code_changes = self._extract_code_changes(text_content)

            if success:
                return self.create_success_result(
                    output=text_content,
                    artifacts=artifacts,
                    code_changes=code_changes,
                )
            else:
                error_msg = self._extract_error(text_content)
                return self.create_failure_result(
                    error=error_msg or "Task marked as failed by Claude",
                    output=text_content,
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
        # e.g., "Created file: src/main.py" or "File: /path/to/file"
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
        # ```python:src/main.py
        # or
        # File: src/main.py
        # ```python
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
        return bool(self.api_key and self.api_key != "${ANTHROPIC_API_KEY}")

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class MockClaudeWorker(Worker):
    """
    Mock Claude worker for testing.

    This worker simulates task execution without calling the actual API.
    """

    @property
    def name(self) -> str:
        """Get worker name."""
        return "mock-claude"

    def __init__(
        self,
        config: ClaudeConfig,
        project_path: Path,
        handover_context: Optional[HandoverContext] = None,
    ):
        """Initialize mock worker."""
        super().__init__(config, project_path, handover_context)
        self.model = config.model or "mock-claude"
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
            output=f"Mock execution of task: {task.description}\n"
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
