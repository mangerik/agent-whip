"""
AgentWhip - AI Agent Orchestration for Autonomous Development

AgentWhip coordinates Claude Code/OpenCode workers to execute
development plans defined in plan.md files.
"""

__version__ = "0.1.0"

from agent_whip.models import (
    ExecutionPlan,
    ExecutionState,
    Task,
    TaskResult,
    TaskStatus,
)

__all__ = [
    "__version__",
    "ExecutionPlan",
    "ExecutionState",
    "Task",
    "TaskResult",
    "TaskStatus",
]
