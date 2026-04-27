"""
State Store for AgentWhip.

Persists execution state to disk for resumption.
"""

import json
import shutil
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, PrivateAttr

from agent_whip.models.plan import ExecutionPlan
from agent_whip.models.state import ExecutionState
from agent_whip.models.task import Task, TaskStatus


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class StoreType(str, Enum):
    """Type of state store."""

    JSON = "json"
    SQLITE = "sqlite"


class StateStore(BaseModel):
    """
    Base class for state storage.

    Handles persistence of execution state and tasks.
    """

    project_path: Path
    state_path: Path
    backup_path: Path
    store_type: StoreType = StoreType.JSON

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def create(
        cls,
        project_path: Path,
        state_path: Optional[Path] = None,
        backup_path: Optional[Path] = None,
        store_type: StoreType = StoreType.JSON,
    ) -> "StateStore":
        """Create a state store."""
        # Default paths
        if state_path is None:
            state_path = project_path / ".agent-whip" / "state.json"

        if backup_path is None:
            backup_path = project_path / ".agent-whip" / "backup"

        # Ensure directories exist
        state_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.mkdir(parents=True, exist_ok=True)

        return cls(
            project_path=project_path,
            state_path=state_path,
            backup_path=backup_path,
            store_type=store_type,
        )

    def save(
        self,
        state: ExecutionState,
        plan: ExecutionPlan,
    ) -> None:
        """
        Save execution state and plan.

        Args:
            state: Execution state to save
            plan: Execution plan with task states
        """
        if self.store_type == StoreType.JSON:
            self._save_json(state, plan)
        else:
            raise NotImplementedError(f"Store type {self.store_type} not implemented")

    def load(self) -> Optional[tuple[ExecutionState, ExecutionPlan]]:
        """
        Load execution state and plan.

        Returns:
            Tuple of (state, plan) or None if not found
        """
        if not self.state_path.exists():
            return None

        if self.store_type == StoreType.JSON:
            return self._load_json()
        else:
            raise NotImplementedError(f"Store type {self.store_type} not implemented")

    def _save_json(self, state: ExecutionState, plan: ExecutionPlan) -> None:
        """Save to JSON file."""
        # Create backup first
        self._create_backup()

        data = {
            "state": state.model_dump(mode="json"),
            "plan": self._serialize_plan(plan),
            "saved_at": _utcnow().isoformat(),
        }

        # Write to temp file first, then rename (atomic write)
        temp_path = self.state_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, indent=2, default=str))
        temp_path.replace(self.state_path)

    def _load_json(self) -> Optional[tuple[ExecutionState, ExecutionPlan]]:
        """Load from JSON file."""
        content = self.state_path.read_text()
        data = json.loads(content)

        state = ExecutionState(**data["state"])
        plan = self._deserialize_plan(data["plan"])

        return state, plan

    def _serialize_plan(self, plan: ExecutionPlan) -> dict:
        """Serialize plan to JSON-serializable dict."""
        return {
            "source_path": str(plan.source_path),
            "raw_content": plan.raw_content,
            "metadata": plan.metadata.model_dump(),
            "phases": [p.model_dump() for p in plan.phases],
            "tasks": [t.model_dump() for t in plan.tasks],
            "dependency_graph": plan.dependency_graph,
            "reverse_dependency_graph": plan.reverse_dependency_graph,
        }

    def _deserialize_plan(self, data: dict) -> ExecutionPlan:
        """Deserialize plan from dict."""
        from agent_whip.models.plan import PlanMetadata

        plan = ExecutionPlan(
            source_path=Path(data["source_path"]),
            raw_content=data["raw_content"],
            metadata=PlanMetadata(**data["metadata"]),
        )

        # Restore phases
        for phase_data in data["phases"]:
            from agent_whip.models.state import PhaseState
            phase = PhaseState(**phase_data)
            plan.add_phase(phase)

        # Restore tasks
        for task_data in data["tasks"]:
            task = Task(**task_data)
            plan.add_task(task)

        # Restore graphs
        plan.dependency_graph = data["dependency_graph"]
        plan.reverse_dependency_graph = data["reverse_dependency_graph"]

        return plan

    def _create_backup(self) -> None:
        """Create backup of current state."""
        if self.state_path.exists():
            timestamp = _utcnow().strftime("%Y%m%d_%H%M%S")
            backup_name = f"state_{timestamp}.json"
            backup_file = self.backup_path / backup_name

            shutil.copy2(self.state_path, backup_file)

            # Keep only last 10 backups
            self._cleanup_backups(keep=10)

    def _cleanup_backups(self, keep: int = 10) -> None:
        """Remove old backups, keeping only the most recent."""
        backups = sorted(
            self.backup_path.glob("state_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for old_backup in backups[keep:]:
            old_backup.unlink()

    def clear(self) -> None:
        """Clear saved state."""
        if self.state_path.exists():
            self.state_path.unlink()

    def exists(self) -> bool:
        """Check if state exists."""
        return self.state_path.exists()

    def get_last_modified(self) -> Optional[datetime]:
        """Get last modification time of state."""
        if not self.state_path.exists():
            return None

        return datetime.fromtimestamp(self.state_path.stat().st_mtime)


class CheckpointManager(BaseModel):
    """
    Manages checkpoints for state persistence.

    Creates periodic checkpoints during execution.
    """

    store: StateStore
    checkpoint_interval: int = 60  # seconds
    _last_checkpoint: Optional[datetime] = PrivateAttr(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def should_checkpoint(self) -> bool:
        """Check if a checkpoint should be created."""
        if self._last_checkpoint is None:
            return True

        elapsed = (_utcnow() - self._last_checkpoint).total_seconds()
        return elapsed >= self.checkpoint_interval

    def checkpoint(
        self,
        state: ExecutionState,
        plan: ExecutionPlan,
    ) -> None:
        """Create a checkpoint."""
        self.store.save(state, plan)
        self._last_checkpoint = _utcnow()

    def force_checkpoint(
        self,
        state: ExecutionState,
        plan: ExecutionPlan,
    ) -> None:
        """Force a checkpoint regardless of interval."""
        self.checkpoint(state, plan)
