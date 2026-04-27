"""
Bug Ticket Creator for AgentWhip.

Creates bug tickets from test failures.
"""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from agent_whip.models.state import PhaseState
from agent_whip.qa.engine import QAResult, TestResult


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class TicketPriority(str, Enum):
    """Bug ticket priority."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TicketStatus(str, Enum):
    """Bug ticket status."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class BugTicket(BaseModel):
    """A bug ticket from test failure."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(description="Ticket ID")
    title: str = Field(description="Ticket title")
    description: str = Field(description="Ticket description")
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM, description="Ticket priority")
    status: TicketStatus = Field(default=TicketStatus.OPEN, description="Ticket status")

    # Test info
    test_name: str = Field(description="Failed test name")
    phase: str = Field(description="Phase where test failed")
    error_message: Optional[str] = Field(default=None, description="Error message")

    # Metadata
    created_at: datetime = Field(default_factory=_utcnow)
    screenshots: list[str] = Field(default_factory=list, description="Screenshot paths")
    labels: list[str] = Field(default_factory=lambda: ["bug", "qa"], description="Ticket labels")


class TicketCreator(BaseModel):
    """
    Creates bug tickets from QA failures.

    Supports GitHub Issues and Jira (optional).
    """

    project_path: Path
    _should_create_tickets: bool = PrivateAttr(default=True)

    # Ticket configuration
    assignee: Optional[str] = Field(default=None, description="Default assignee")
    labels: list[str] = Field(default_factory=lambda: ["bug", "qa"], description="Default labels")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def create_tickets(
        self,
        qa_result: QAResult,
        phase: PhaseState,
    ) -> list[BugTicket]:
        """
        Create bug tickets from QA results.

        Args:
            qa_result: QA test results
            phase: Phase that was tested

        Returns:
            List of created tickets
        """
        if not qa_result.has_failures:
            return []

        tickets = []

        for failed_test in qa_result.get_failed_tests():
            ticket = self._create_ticket(failed_test, qa_result, phase)
            tickets.append(ticket)

        # Optionally post to external service
        if self._should_create_tickets:
            self._post_tickets(tickets)

        return tickets

    def _create_ticket(
        self,
        test: TestResult,
        qa_result: QAResult,
        phase: PhaseState,
    ) -> BugTicket:
        """Create a bug ticket from a failed test."""
        ticket_id = f"BUG-{phase.number}-{test.name[:10].replace(' ', '-').lower()}"

        # Determine priority based on test name
        priority = self._determine_priority(test)

        # Build description
        description = self._build_description(test, qa_result, phase)

        return BugTicket(
            id=ticket_id,
            title=f"[QA Failure] {test.name}",
            description=description,
            priority=priority,
            test_name=test.name,
            phase=phase.name,
            error_message=test.error,
            screenshots=qa_result.screenshots,
            labels=self.labels + [f"phase-{phase.number}"],
        )

    def _determine_priority(self, test: TestResult) -> TicketPriority:
        """Determine ticket priority from test."""
        name_lower = test.name.lower()

        # Critical tests
        if any(kw in name_lower for kw in ["critical", "auth", "security", "payment"]):
            return TicketPriority.CRITICAL

        # High priority
        if any(kw in name_lower for kw in ["important", "main", "core", "api"]):
            return TicketPriority.HIGH

        # Low priority
        if any(kw in name_lower for kw in ["ui", "cosmetic", "minor", "typo"]):
            return TicketPriority.LOW

        return TicketPriority.MEDIUM

    def _build_description(
        self,
        test: TestResult,
        qa_result: QAResult,
        phase: PhaseState,
    ) -> str:
        """Build ticket description."""
        lines = [
            f"## Test Failure",
            f"",
            f"**Test:** {test.name}",
            f"**Phase:** {phase.name}",
            f"**Status:** {test.status.value}",
            f"",
        ]

        if test.error:
            lines.extend([
                f"## Error",
                f"```\n{test.error}\n```",
                f"",
            ])

        if test.file:
            lines.extend([
                f"## Location",
                f"**File:** {test.file}",
                f"**Line:** {test.line or 'unknown'}",
                f"",
            ])

        if qa_result.screenshots:
            lines.extend([
                f"## Screenshots",
                f"",
            ])
            for screenshot in qa_result.screenshots:
                lines.append(f"- `{screenshot}`")
            lines.append("")

        lines.extend([
            f"## Summary",
            f"",
            f"- Total tests: {qa_result.total_tests}",
            f"- Passed: {qa_result.passed}",
            f"- Failed: {qa_result.failed}",
            f"- Failure rate: {qa_result.failure_rate:.1f}%",
            f"",
            f"---",
            f"*Created by AgentWhip QA*",
        ])

        return "\n".join(lines)

    def _post_tickets(self, tickets: list[BugTicket]) -> None:
        """
        Post tickets to external service.

        Currently just saves to file. Can be extended for GitHub/Jira.
        """
        # Save tickets to file for now
        tickets_dir = self.project_path / ".agent-whip" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)

        for ticket in tickets:
            ticket_file = tickets_dir / f"{ticket.id}.md"
            ticket_file.write_text(self._format_ticket_markdown(ticket))

    def _format_ticket_markdown(self, ticket: BugTicket) -> str:
        """Format ticket as markdown."""
        # Handle both enum and string values
        priority = ticket.priority.value if hasattr(ticket.priority, 'value') else ticket.priority
        status = ticket.status.value if hasattr(ticket.status, 'value') else ticket.status

        lines = [
            f"# {ticket.title}",
            f"",
            f"**ID:** {ticket.id}",
            f"**Priority:** {priority}",
            f"**Status:** {status}",
            f"**Created:** {ticket.created_at.isoformat()}",
            f"",
            ticket.description,
        ]

        if ticket.labels:
            lines.extend([
                f"",
                f"**Labels:** {', '.join(ticket.labels)}",
            ])

        return "\n".join(lines)

    def save_ticket_report(
        self,
        tickets: list[BugTicket],
        phase: PhaseState,
    ) -> Path:
        """
        Save a summary report of all tickets.

        Args:
            tickets: List of tickets
            phase: Phase context

        Returns:
            Path to report file
        """
        report_dir = self.project_path / ".agent-whip" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = _utcnow().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"qa_report_{phase.number}_{timestamp}.md"

        lines = [
            f"# QA Report - {phase.name}",
            f"",
            f"**Generated:** {_utcnow().isoformat()}",
            f"**Total Tickets:** {len(tickets)}",
            f"",
            f"## Summary",
            f"",
        ]

        # Count by priority
        by_priority = {}
        for ticket in tickets:
            by_priority[ticket.priority] = by_priority.get(ticket.priority, 0) + 1

        # Sort by priority (critical > high > medium > low)
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for priority, count in sorted(by_priority.items(), key=lambda x: priority_order.get(x[0] if isinstance(x[0], str) else x[0].value, 99)):
            prio_str = priority if isinstance(priority, str) else priority.value
            lines.append(f"- **{prio_str.upper()}:** {count}")

        lines.append("")
        lines.append("## Tickets")
        lines.append("")

        for ticket in tickets:
            prio_str = ticket.priority if isinstance(ticket.priority, str) else ticket.priority.value
            lines.extend([
                f"### {ticket.title}",
                f"",
                f"- **ID:** {ticket.id}",
                f"- **Priority:** {prio_str}",
                f"- **Test:** `{ticket.test_name}`",
                f"- **Error:** {ticket.error_message or 'N/A'}",
                f"",
            ])

        report_file.write_text("\n".join(lines))
        return report_file
