"""
Worker manager for AgentWhip.

Manages multiple workers and dispatches tasks to available workers.

Priority: CLI > API (based on mode setting)
- mode: "cli" - Use CLI only
- mode: "api" - Use API only
- mode: "auto" (default) - Try CLI first, fallback to API
"""

import asyncio
import shutil
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from agent_whip.config import AgentWhipConfig
from agent_whip.models.task import Task, TaskResult
from agent_whip.workers.base import Worker

# Import all worker types
from agent_whip.workers.claude import ClaudeWorker, MockClaudeWorker
from agent_whip.workers.claude_cli import ClaudeCLIWorker, MockClaudeCLIWorker
from agent_whip.workers.opencode import MockOpenCodeWorker, OpenCodeWorker
from agent_whip.workers.opencode_cli import MockOpenCodeCLIWorker, OpenCodeCLIWorker


class WorkerManager(BaseModel):
    """
    Manager for AI workers.

    Handles worker lifecycle and task dispatching.
    Priority: CLI > API (based on mode setting)
    """

    config: AgentWhipConfig = Field(description="AgentWhip configuration")
    project_path: Path = Field(description="Project path")
    use_mock: bool = Field(default=False, description="Use mock workers for testing")

    # Private fields
    _workers: dict[str, Worker] = PrivateAttr(default_factory=dict)
    _default_worker: Optional[Worker] = PrivateAttr(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def initialize_workers(self):
        """Initialize all configured workers.

        Strategy per worker:
        1. If use_mock: Use mock workers
        2. If mode == "cli": Try CLI only
        3. If mode == "api": Try API only (needs api_key)
        4. If mode == "auto": Try CLI first, fallback to API
        """

        # Initialize Claude worker
        self._init_claude_worker()

        # Initialize OpenCode worker
        self._init_opencode_worker()

        # Set default worker
        default_name = self.config.default_worker
        if default_name in self._workers:
            self._default_worker = self._workers[default_name]
        elif self._workers:
            # Use first available worker
            self._default_worker = next(iter(self._workers.values()))

    def _init_claude_worker(self):
        """Initialize Claude worker based on mode."""
        mode = self.config.claude.mode
        has_api_key = (
            self.config.claude.api_key and
            self.config.claude.api_key != "${ANTHROPIC_API_KEY}"
        )
        has_cli = shutil.which("claude") is not None

        # In mock mode, always use mock CLI worker
        if self.use_mock:
            self._workers["claude"] = MockClaudeCLIWorker(
                self.config.claude,
                self.project_path,
            )
            return

        # Mode: cli - Use CLI only
        if mode == "cli":
            if has_cli:
                self._workers["claude"] = ClaudeCLIWorker(
                    self.config.claude,
                    self.project_path,
                )
            return

        # Mode: api - Use API only
        if mode == "api":
            if has_api_key:
                self._workers["claude"] = ClaudeWorker(
                    self.config.claude,
                    self.project_path,
                )
            return

        # Mode: auto - Try CLI first, fallback to API
        if mode == "auto":
            if has_cli:
                self._workers["claude"] = ClaudeCLIWorker(
                    self.config.claude,
                    self.project_path,
                )
            elif has_api_key:
                self._workers["claude"] = ClaudeWorker(
                    self.config.claude,
                    self.project_path,
                )
            return

    def _init_opencode_worker(self):
        """Initialize OpenCode worker based on mode."""
        mode = self.config.opencode.mode
        has_api_key = (
            self.config.opencode.api_key and
            self.config.opencode.api_key != "${OPENCODE_API_KEY}"
        )
        has_cli = shutil.which("opencode") is not None

        # In mock mode, always use mock CLI worker
        if self.use_mock:
            self._workers["opencode"] = MockOpenCodeCLIWorker(
                self.config.opencode,
                self.project_path,
            )
            return

        # Mode: cli - Use CLI only
        if mode == "cli":
            if has_cli:
                self._workers["opencode"] = OpenCodeCLIWorker(
                    self.config.opencode,
                    self.project_path,
                )
            return

        # Mode: api - Use API only
        if mode == "api":
            if has_api_key:
                self._workers["opencode"] = OpenCodeWorker(
                    self.config.opencode,
                    self.project_path,
                )
            return

        # Mode: auto - Try CLI first, fallback to API
        if mode == "auto":
            if has_cli:
                self._workers["opencode"] = OpenCodeCLIWorker(
                    self.config.opencode,
                    self.project_path,
                )
            elif has_api_key:
                self._workers["opencode"] = OpenCodeWorker(
                    self.config.opencode,
                    self.project_path,
                )
            return

    def get_worker(self, name: Optional[str] = None) -> Optional[Worker]:
        """
        Get a worker by name.

        Args:
            name: Worker name (uses default if not specified)

        Returns:
            Worker or None if not found
        """
        if name:
            return self._workers.get(name)
        return self._default_worker

    def get_available_workers(self) -> list[str]:
        """Get list of available worker names."""
        return [
            name for name, worker in self._workers.items()
            if worker.is_available()
        ]

    async def execute_task(
        self,
        task: Task,
        worker_name: Optional[str] = None,
    ) -> TaskResult:
        """
        Execute a task using an available worker.

        Args:
            task: Task to execute
            worker_name: Specific worker to use (optional)

        Returns:
            TaskResult

        Raises:
            ValueError: If no worker available
        """
        worker = self.get_worker(worker_name)

        if worker is None:
            raise ValueError(f"No worker available (requested: {worker_name})")

        if not worker.is_available():
            raise ValueError(f"Worker '{worker_name}' is not available")

        return await worker.execute(task)

    async def execute_tasks_parallel(
        self,
        tasks: list[Task],
        max_concurrent: Optional[int] = None,
    ) -> dict[str, TaskResult]:
        """
        Execute multiple tasks in parallel.

        Args:
            tasks: Tasks to execute
            max_concurrent: Max concurrent tasks (uses config default)

        Returns:
            Dictionary mapping task IDs to results
        """
        if max_concurrent is None:
            max_concurrent = self._get_default_max_concurrent()

        results: dict[str, TaskResult] = {}

        async def execute_one(task: Task) -> tuple[str, TaskResult]:
            result = await self.execute_task(task)
            return task.id, result

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent or 3)

        async def bounded_execute(task: Task) -> tuple[str, TaskResult]:
            async with semaphore:
                return await execute_one(task)

        # Execute all tasks
        tasks_results = await asyncio.gather(
            *[bounded_execute(task) for task in tasks],
            return_exceptions=True,
        )

        # Collect results
        for item in tasks_results:
            if isinstance(item, Exception):
                # Handle exception
                continue
            task_id, result = item
            results[task_id] = result

        return results

    def _get_default_max_concurrent(self) -> int:
        """Get default concurrency from active worker config."""
        try:
            worker_config = self.config.get_worker_config(self.config.default_worker)
            return max(1, worker_config.max_concurrent)
        except ValueError:
            return 3

    def has_workers(self) -> bool:
        """Check if any workers are configured."""
        return len(self._workers) > 0

    async def cleanup(self):
        """Cleanup resources."""
        for worker in self._workers.values():
            if hasattr(worker, "close"):
                await worker.close()
