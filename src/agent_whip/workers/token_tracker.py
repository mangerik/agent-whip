"""
Token Tracker for Worker Sessions.

Tracks token usage and detects when threshold is reached for handover.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from agent_whip.events import EventEmitter, EventType


@dataclass
class TokenUsageStats:
    """Statistics for token usage."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Tracking
    api_calls: int = 0
    started_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None

    @property
    def usage_percentage(self, limit: int) -> float:
        """Calculate usage as percentage of limit."""
        if limit <= 0:
            return 0.0
        return (self.total_tokens / limit) * 100

    @property
    def session_duration_seconds(self) -> float:
        """Get session duration in seconds."""
        if not self.started_at:
            return 0.0
        end = self.last_updated or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "api_calls": self.api_calls,
            "usage_percentage": round(self.total_tokens, 2),
            "session_duration_seconds": round(self.session_duration_seconds, 2),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


@dataclass
class TokenThresholdEvent:
    """Event emitted when token threshold is reached."""

    worker_id: str
    limit: int
    threshold: float
    usage: TokenUsageStats
    percentage: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "worker_id": self.worker_id,
            "limit": self.limit,
            "threshold": self.threshold,
            "usage": self.usage.to_dict(),
            "percentage": round(self.percentage, 2),
            "timestamp": self.timestamp.isoformat(),
        }


class TokenTracker:
    """
    Tracks token usage for a worker session.

    Detects when token usage reaches threshold and triggers handover.
    """

    def __init__(
        self,
        worker_id: str,
        limit: int,
        threshold: float = 0.85,
        event_emitter: Optional[EventEmitter] = None,
    ):
        """
        Initialize token tracker.

        Args:
            worker_id: ID of the worker being tracked
            limit: Token limit for the session
            threshold: Threshold (0.0-1.0) for triggering handover (default 0.85 = 85%)
            event_emitter: Optional event emitter for threshold events
        """
        self.worker_id = worker_id
        self.limit = limit
        self.threshold = threshold
        self._event_emitter = event_emitter

        self.usage = TokenUsageStats(
            started_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )

        self._threshold_triggered = False
        self._last_warning_percentage = 0.0

    @property
    def threshold_reached(self) -> bool:
        """Check if threshold has been reached."""
        return self._threshold_triggered

    @property
    def current_percentage(self) -> float:
        """Get current usage percentage."""
        return self.usage.usage_percentage(self.limit)

    def record_usage(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        Record token usage from an API call.

        Args:
            input_tokens: Input tokens used
            output_tokens: Output tokens used
        """
        self.usage.input_tokens += input_tokens
        self.usage.output_tokens += output_tokens
        self.usage.total_tokens += input_tokens + output_tokens
        self.usage.api_calls += 1
        self.usage.last_updated = datetime.now(timezone.utc)

        # Emit usage update event
        if self._event_emitter:
            self._event_emitter.emit(
                EventType.TOKEN_USAGE_UPDATED,
                worker_id=self.worker_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=self.usage.total_tokens,
                percentage=self.current_percentage,
            )

        # Check threshold
        self._check_threshold()

    def _check_threshold(self) -> None:
        """Check if threshold has been reached and emit event if so."""
        if self._threshold_triggered:
            return  # Already triggered

        percentage = self.current_percentage
        threshold_percentage = self.threshold * 100

        if percentage >= threshold_percentage:
            self._threshold_triggered = True

            if self._event_emitter:
                event = TokenThresholdEvent(
                    worker_id=self.worker_id,
                    limit=self.limit,
                    threshold=self.threshold,
                    usage=self.usage,
                    percentage=percentage,
                )
                self._event_emitter.emit(
                    EventType.TOKEN_THRESHOLD_REACHED,
                    **event.to_dict(),
                )

    def should_trigger_handover(self) -> bool:
        """
        Check if handover should be triggered.

        Returns:
            True if threshold has been reached
        """
        return self._threshold_triggered

    def get_usage_stats(self) -> TokenUsageStats:
        """Get current usage statistics."""
        return self.usage

    def get_remaining_tokens(self) -> int:
        """Get remaining tokens before limit."""
        return max(0, self.limit - self.usage.total_tokens)

    def get_remaining_percentage(self) -> float:
        """Get remaining percentage before limit."""
        if self.limit <= 0:
            return 0.0
        return (self.get_remaining_tokens() / self.limit) * 100

    def reset(self) -> None:
        """Reset tracker for new session."""
        self.usage = TokenUsageStats(
            started_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )
        self._threshold_triggered = False
        self._last_warning_percentage = 0.0

    def set_worker_id(self, worker_id: str) -> None:
        """Update worker ID (useful for handover)."""
        self.worker_id = worker_id

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "worker_id": self.worker_id,
            "limit": self.limit,
            "threshold": self.threshold,
            "usage": self.usage.to_dict(),
            "threshold_reached": self._threshold_triggered,
            "current_percentage": round(self.current_percentage, 2),
            "remaining_tokens": self.get_remaining_tokens(),
            "remaining_percentage": round(self.get_remaining_percentage(), 2),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TokenTracker":
        """Create from dictionary (for deserialization)."""
        tracker = cls(
            worker_id=data["worker_id"],
            limit=data["limit"],
            threshold=data["threshold"],
        )
        tracker.usage = TokenUsageStats(
            input_tokens=data["usage"]["input_tokens"],
            output_tokens=data["usage"]["output_tokens"],
            total_tokens=data["usage"]["total_tokens"],
            api_calls=data["usage"]["api_calls"],
            started_at=datetime.fromisoformat(data["usage"]["started_at"]) if data["usage"].get("started_at") else None,
            last_updated=datetime.fromisoformat(data["usage"]["last_updated"]) if data["usage"].get("last_updated") else None,
        )
        tracker._threshold_triggered = data.get("threshold_reached", False)
        return tracker
