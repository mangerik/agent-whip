"""
Configuration settings for AgentWhip.
"""

import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class WorkerMode:
    """Worker connection modes."""
    CLI = "cli"      # Use installed CLI (preferred)
    API = "api"      # Use API directly (fallback)
    AUTO = "auto"    # Try CLI first, fallback to API


class WorkerConfig(BaseModel):
    """Configuration for an AI worker."""

    mode: str = Field(default="auto", description="Connection mode: cli, api, or auto")
    api_key: str = Field(default="", description="API key for the worker")
    model: str = Field(default="", description="Model to use")
    max_concurrent: int = Field(default=3, description="Max concurrent tasks")
    timeout: int = Field(default=600, description="Task timeout in seconds")


class ClaudeConfig(WorkerConfig):
    """Claude-specific configuration."""

    model: str = Field(default="claude-opus-4-6", description="Claude model to use")
    base_url: str = Field(default="https://api.anthropic.com", description="API base URL")


class OpenCodeConfig(WorkerConfig):
    """OpenCode-specific configuration."""

    model: str = Field(default="default", description="OpenCode model to use")


class QAConfig(BaseModel):
    """QA configuration."""

    enabled: bool = Field(default=True, description="Enable QA testing")
    run_after_phase: bool = Field(default=True, description="Run QA after each phase")
    framework: str = Field(default="playwright", description="Testing framework")
    test_command: str = Field(default="npm test", description="Command to run tests")
    create_tickets_on_failure: bool = Field(default=True, description="Create tickets on failure")


class StateConfig(BaseModel):
    """State storage configuration."""

    store: str = Field(default="sqlite", description="Storage backend (sqlite/json)")
    path: str = Field(default=".agent-whip/state.db", description="State file path")
    backup_path: str = Field(default=".agent-whip/backup/", description="Backup directory")
    checkpoint_interval: int = Field(default=60, description="Checkpoint interval in seconds")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Log level")
    file: str = Field(default=".agent-whip/agent-whip.log", description="Log file path")
    format: str = Field(default="text", description="Log format (text/json)")


class NotificationConfig(BaseModel):
    """Notification configuration."""

    enabled: bool = Field(default=False, description="Enable notifications")
    slack_webhook: Optional[str] = Field(default=None, description="Slack webhook URL")
    notify_on: list[str] = Field(
        default_factory=lambda: ["phase_complete", "task_failed", "qa_failed", "completion"],
        description="Events to notify on"
    )


class ProjectConfig(BaseModel):
    """Project-specific configuration."""

    name: str = Field(default="", description="Project name")


class ExecutionConfig(BaseModel):
    """Execution configuration."""

    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Base retry delay in seconds")
    task_timeout: int = Field(default=600, description="Task timeout in seconds")
    continue_on_error: bool = Field(default=False, description="Continue on task failure")


class HandoverWorkerConfig(BaseModel):
    """Handover configuration for individual workers."""

    max_tokens_per_session: int = Field(
        default=200000, description="Token limit per worker session"
    )
    enable_auto_summarize: bool = Field(
        default=True, description="Enable automatic summarization on handover"
    )


class HandoverConfig(BaseModel):
    """Handover configuration for worker continuity."""

    enabled: bool = Field(default=True, description="Enable handover feature")
    token_threshold: float = Field(
        default=0.85, description="Token threshold (0.0-1.0) for triggering handover"
    )

    # Per-worker settings
    claude: HandoverWorkerConfig = Field(default_factory=HandoverWorkerConfig)
    opencode: HandoverWorkerConfig = Field(default_factory=HandoverWorkerConfig)

    # Context preservation
    context_document_enabled: bool = Field(default=True, description="Enable context document")
    context_document_path: str = Field(
        default=".agent-whip/context.json", description="Path to context document"
    )
    max_context_entries: int = Field(
        default=1000, description="Maximum entries in context log"
    )

    # Summarization
    max_summary_length: int = Field(
        default=10000, description="Maximum summary length in characters"
    )
    include_artifacts: bool = Field(default=True, description="Include artifacts in summary")
    include_decisions: bool = Field(default=True, description="Include decisions in summary")


class AgentWhipConfig(BaseModel):
    """Main configuration for AgentWhip."""

    # Project
    project: ProjectConfig = Field(default_factory=ProjectConfig)

    # Workers
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    opencode: OpenCodeConfig = Field(default_factory=OpenCodeConfig)
    default_worker: str = Field(default="claude", description="Default worker to use")

    # Execution
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)

    # QA
    qa: QAConfig = Field(default_factory=QAConfig)

    # State
    state: StateConfig = Field(default_factory=StateConfig)

    # Handover
    handover: HandoverConfig = Field(default_factory=HandoverConfig)

    # Logging
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Notifications
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)

    @classmethod
    def load_from_dict(cls, data: dict[str, Any]) -> "AgentWhipConfig":
        """Load config from dictionary, expanding environment variables."""
        expanded = _expand_env_vars(data)
        return cls(**expanded)

    @classmethod
    def load_from_file(cls, path: Path) -> "AgentWhipConfig":
        """Load config from YAML file."""
        import yaml

        if not path.exists():
            # Return default config
            return cls()

        data = yaml.safe_load(path.read_text()) or {}
        return cls.load_from_dict(data)

    def get_worker_config(self, worker: str) -> WorkerConfig:
        """Get configuration for a specific worker."""
        if worker == "claude":
            return self.claude
        elif worker == "opencode":
            return self.opencode
        else:
            raise ValueError(f"Unknown worker: {worker}")


def _expand_env_vars(data: Any) -> Any:
    """Recursively expand environment variables in strings."""
    if isinstance(data, str):
        # Expand ${VAR} and $VAR
        import re

        pattern = re.compile(r"\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)")

        def replace_env(match: re.Match) -> str:
            var_name = match.group(1) or match.group(2)
            return os.getenv(var_name, match.group(0))

        return pattern.sub(replace_env, data)
    elif isinstance(data, dict):
        return {k: _expand_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_expand_env_vars(item) for item in data]
    else:
        return data


def find_config_file(project_path: Path) -> Optional[Path]:
    """Find agent-whip.yml in project directory."""
    config_files = [
        project_path / "agent-whip.yml",
        project_path / "agent-whip.yaml",
        project_path / ".agent-whip.yml",
        project_path / ".agent-whip.yaml",
    ]

    for config_file in config_files:
        if config_file.exists():
            return config_file

    return None


def load_claude_settings() -> dict[str, str]:
    """Load Claude settings from ~/.claude/settings.json if available."""
    import json

    claude_settings_path = Path.home() / ".claude" / "settings.json"

    if not claude_settings_path.exists():
        return {}

    try:
        data = json.loads(claude_settings_path.read_text())
        env_vars = data.get("env", {})

        settings = {}
        if auth_token := env_vars.get("ANTHROPIC_AUTH_TOKEN"):
            settings["api_key"] = auth_token
        if base_url := env_vars.get("ANTHROPIC_BASE_URL"):
            settings["base_url"] = base_url
        if model := env_vars.get("ANTHROPIC_MODEL"):
            settings["model"] = model

        return settings
    except Exception:
        return {}


def load_config(project_path: Path) -> AgentWhipConfig:
    """Load configuration from project directory."""
    config_file = find_config_file(project_path)

    if config_file:
        config = AgentWhipConfig.load_from_file(config_file)
    else:
        config = AgentWhipConfig()

    # Merge with Claude settings if not explicitly set
    claude_settings = load_claude_settings()

    if claude_settings:
        # Apply Claude settings if not already configured
        if not config.claude.api_key or config.claude.api_key == "${ANTHROPIC_API_KEY}":
            config.claude.api_key = claude_settings.get("api_key", "")

        if claude_settings.get("base_url"):
            config.claude.base_url = claude_settings["base_url"]

        if claude_settings.get("model") and config.claude.model == "claude-opus-4-6":
            config.claude.model = claude_settings["model"]

    # Also support ANTHROPIC_AUTH_TOKEN env var (in addition to ANTHROPIC_API_KEY)
    if not config.claude.api_key or config.claude.api_key == "${ANTHROPIC_API_KEY}":
        if auth_token := os.getenv("ANTHROPIC_AUTH_TOKEN"):
            config.claude.api_key = auth_token
        elif api_key := os.getenv("ANTHROPIC_API_KEY"):
            config.claude.api_key = api_key

    # Support ANTHROPIC_BASE_URL env var
    if base_url := os.getenv("ANTHROPIC_BASE_URL"):
        config.claude.base_url = base_url

    return config
