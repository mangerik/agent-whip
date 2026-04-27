"""
Workers for AgentWhip.

Priority: CLI > API (based on mode setting)
"""

from agent_whip.config import ClaudeConfig
from agent_whip.workers.base import ExecutionError, TimeoutError, Worker, WorkerConfig
from agent_whip.workers.claude import ClaudeWorker, MockClaudeWorker
from agent_whip.workers.claude_cli import ClaudeCLIWorker, MockClaudeCLIWorker
from agent_whip.workers.handover import HandoverManager, HandoverWorkerFactory
from agent_whip.workers.manager import WorkerManager
from agent_whip.workers.opencode import MockOpenCodeWorker, OpenCodeWorker
from agent_whip.workers.opencode_cli import MockOpenCodeCLIWorker, OpenCodeCLIWorker
from agent_whip.workers.token_tracker import TokenTracker, TokenUsageStats

__all__ = [
    "Worker",
    "WorkerConfig",
    "ClaudeConfig",
    "WorkerManager",
    # Claude workers
    "ClaudeWorker",
    "ClaudeCLIWorker",
    "MockClaudeWorker",
    "MockClaudeCLIWorker",
    # OpenCode workers
    "OpenCodeWorker",
    "OpenCodeCLIWorker",
    "MockOpenCodeWorker",
    "MockOpenCodeCLIWorker",
    # Utilities
    "ExecutionError",
    "TimeoutError",
    "TokenTracker",
    "TokenUsageStats",
    "HandoverManager",
    "HandoverWorkerFactory",
]
