"""
Plan parser for AgentWhip.
"""

from agent_whip.parser.markdown_parser import MarkdownParser, parse_plan as parse_plan_strict
from agent_whip.parser.flexible_parser import FlexibleParser, parse_plan_flexible

__all__ = ["MarkdownParser", "FlexibleParser", "parse_plan", "parse_plan_strict", "parse_plan_flexible", "parse_plan_sync"]


def parse_plan_sync(plan_path, project_path=None, flexible=False):
    """
    Synchronous wrapper for parse_plan.

    This function can be called from sync code. It will run the async
    parsing in a new event loop if needed.

    Args:
        plan_path: Path to plan.md file
        project_path: Project path (for flexible mode context)
        flexible: If True, use flexible AI parsing. If False (default),
                  tries strict parsing first, falls back to flexible on error.

    Returns:
        Parsed ExecutionPlan

    Raises:
        FileNotFoundError: If plan file doesn't exist
        ValueError: If plan file is empty or parsing fails
    """
    import asyncio
    from pathlib import Path as PathLib

    plan_path = PathLib(plan_path) if not isinstance(plan_path, PathLib) else plan_path

    if project_path is None:
        project_path = plan_path.parent

    if flexible:
        # Use flexible mode directly - need to run async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(parse_plan_flexible(plan_path, project_path))
        finally:
            loop.close()

    # Try strict parsing first
    try:
        return parse_plan_strict(plan_path)
    except (ValueError, KeyError) as e:
        # Strict parsing failed, fall back to flexible
        from rich.console import Console

        console = Console()
        console.print(f"[yellow]⚠ Strict parsing failed: {e}[/yellow]")
        console.print("[cyan]🔄 Switching to flexible AI-powered parsing...[/cyan]")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(parse_plan_flexible(plan_path, project_path))
        finally:
            loop.close()


async def parse_plan(plan_path, project_path=None, flexible=False):
    """
    Parse a plan file with automatic fallback to flexible mode.

    Args:
        plan_path: Path to plan.md file
        project_path: Project path (for flexible mode context)
        flexible: If True, use flexible AI parsing. If False (default),
                  tries strict parsing first, falls back to flexible on error.

    Returns:
        Parsed ExecutionPlan

    Raises:
        FileNotFoundError: If plan file doesn't exist
        ValueError: If plan file is empty or parsing fails
    """
    from pathlib import Path as PathLib

    plan_path = PathLib(plan_path) if not isinstance(plan_path, PathLib) else plan_path

    if project_path is None:
        project_path = plan_path.parent

    if flexible:
        # Use flexible mode directly
        return await parse_plan_flexible(plan_path, project_path)

    # Try strict parsing first
    try:
        return parse_plan_strict(plan_path)
    except (ValueError, KeyError) as e:
        # Strict parsing failed, fall back to flexible
        import asyncio
        from rich.console import Console

        console = Console()
        console.print(f"[yellow]⚠ Strict parsing failed: {e}[/yellow]")
        console.print("[cyan]🔄 Switching to flexible AI-powered parsing...[/cyan]")

        return await parse_plan_flexible(plan_path, project_path)
