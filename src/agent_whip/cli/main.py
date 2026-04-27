"""
CLI for AgentWhip.
"""

import asyncio
import threading
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from agent_whip import __version__
from agent_whip.config import load_config
from agent_whip.orchestrator import ExecutionOrchestrator
from agent_whip.parser import parse_plan_sync

app = typer.Typer(
    name="agent-whip",
    help="AI Agent Orchestration for Autonomous Development",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()


@app.command()
def run(
    project_path: Path = typer.Option(
        Path("."),
        "--path",
        "-p",
        help="Path to project directory",
        exists=True,
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        "-m",
        help="Use mock workers (for testing)",
    ),
    flexible: bool = typer.Option(
        False,
        "--flexible",
        "-F",
        help="Use AI-powered flexible parsing (can handle any plan format)",
    ),
):
    """
    Start executing the plan.

    Example:
        agent-whip run
        agent-whip run --path /path/to/project
        agent-whip run --mock  # Use mock workers
    """
    console.print(f"[bold blue]AgentWhip v{__version__}[/bold blue]\n")

    project_path = project_path.resolve()

    # Check for plan.md
    plan_path = project_path / "plan.md"
    if not plan_path.exists():
        console.print(f"[red]✗ Plan file not found: {plan_path}[/red]")
        console.print("\n[hint]Create a plan.md file in your project directory.[/hint]")
        raise typer.Exit(1)

    # Validate plan first
    console.print("Validating plan...")
    try:
        execution_plan = parse_plan_sync(plan_path, flexible=flexible)
        console.print(f"  ✓ Project: [bold]{execution_plan.project_name}[/bold]")
        console.print(f"  ✓ Phases: {execution_plan.total_phases}")
        console.print(f"  ✓ Tasks: {execution_plan.total_tasks}")
    except FileNotFoundError:
        console.print(f"  [red]✗ Plan file not found: {plan_path}[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"  [red]✗ Invalid plan: {e}[/red]")
        raise typer.Exit(1)

    # Show plan summary
    _show_plan_summary(execution_plan)

    # Initialize orchestrator
    console.print("\nInitializing AgentWhip...")
    try:
        orchestrator = ExecutionOrchestrator.create(
            project_path=project_path,
            use_mock=mock,
            use_flexible=flexible,
        )
    except Exception as e:
        console.print(f"  [red]✗ Initialization failed: {e}[/red]")
        raise typer.Exit(1)

    # Check workers
    workers = orchestrator._worker_manager.get_available_workers() if orchestrator._worker_manager else []
    worker_info = ", ".join(workers) if workers else "No workers available"
    console.print(f"  ✓ Workers: {worker_info}")

    # Run execution
    console.print("\n[bold]Starting execution...[/bold]\n")

    try:
        # Run with asyncio (simplified - no progress display for now)
        state = asyncio.run(orchestrator.run())

        # Show final status
        _show_final_status(state, orchestrator)

    except KeyboardInterrupt:
        console.print("\n[yellow]Execution interrupted by user[/yellow]")
        raise typer.Exit(130)

    except Exception as e:
        console.print(f"\n[red]✗ Execution failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def validate(
    plan_path: Path = typer.Option(
        Path("plan.md"),
        "--plan",
        "-p",
        help="Path to plan.md file",
        exists=True,
    ),
    flexible: bool = typer.Option(
        False,
        "--flexible",
        "-F",
        help="Use AI-powered flexible parsing",
    ),
):
    """
    Validate a plan file.

    Example:
        agent-whip validate
        agent-whip validate --plan path/to/plan.md
        agent-whip validate --flexible
    """
    console.print(f"[bold blue]AgentWhip v{__version__} - Plan Validator[/bold blue]\n")

    try:
        plan = parse_plan_sync(plan_path, flexible=flexible)
        console.print("[green]✓ Plan structure valid[/green]")
        console.print(f"  Phases: {plan.total_phases}")
        console.print(f"  Tasks: {plan.total_tasks}")

        # Validate dependencies
        errors = plan.validate_dependencies()
        if errors:
            console.print("\n[red]✗ Dependency errors:[/red]")
            for error in errors:
                console.print(f"  - {error}")
            raise typer.Exit(1)
        else:
            console.print("[green]✓ Dependency graph valid (no cycles)[/green]")

        # Check task IDs
        task_ids = [t.id for t in plan.tasks]
        duplicates = [tid for tid in set(task_ids) if task_ids.count(tid) > 1]
        if duplicates:
            console.print(f"\n[red]✗ Duplicate task IDs: {duplicates}[/red]")
            raise typer.Exit(1)
        else:
            console.print("[green]✓ All task IDs unique[/green]")

        console.print("\n[bold green]Plan is ready to execute![/bold green]")

    except ValueError as e:
        console.print(f"\n[red]✗ Validation failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    project_path: Path = typer.Option(
        Path("."),
        "--path",
        "-p",
        help="Path to project directory",
        exists=True,
    ),
):
    """
    Show execution status.

    Example:
        agent-whip status
        agent-whip status --path /path/to/project
    """
    console.print(f"[bold blue]AgentWhip v{__version__} - Status[/bold blue]\n")

    project_path = project_path.resolve()

    # Check for state file
    state_file = project_path / ".agent-whip" / "state.json"
    if not state_file.exists():
        console.print("[yellow]No execution state found.[/yellow]")
        console.print("\n[hint]Run 'agent-whip run' to start execution.[/hint]")
        return

    # Load and show status
    try:
        orchestrator = ExecutionOrchestrator.create(project_path)
        if not orchestrator.load_saved_state():
            console.print("[red]✗ Failed to load saved state.[/red]")
            raise typer.Exit(1)
        status_dict = orchestrator.get_status()

        # Display status
        _show_status_table(status_dict)

    except Exception as e:
        console.print(f"[red]✗ Failed to load status: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def resume(
    project_path: Path = typer.Option(
        Path("."),
        "--path",
        "-p",
        help="Path to project directory",
        exists=True,
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        "-m",
        help="Use mock workers (for testing)",
    ),
):
    """
    Resume interrupted execution.

    Example:
        agent-whip resume
        agent-whip resume --path /path/to/project
    """
    console.print(f"[bold blue]AgentWhip v{__version__} - Resume[/bold blue]\n")

    project_path = project_path.resolve()

    # Check for state file
    state_file = project_path / ".agent-whip" / "state.json"
    if not state_file.exists():
        console.print("[yellow]No execution state found.[/yellow]")
        console.print("\n[hint]Run 'agent-whip run' to start execution.[/hint]")
        raise typer.Exit(1)

    # Load state and resume
    console.print("Loading execution state...")

    try:
        orchestrator = ExecutionOrchestrator.create(
            project_path=project_path,
            use_mock=mock,
        )
        if not orchestrator.load_saved_state():
            console.print("[red]✗ Failed to load saved state.[/red]")
            raise typer.Exit(1)

        status_dict = orchestrator.get_status()
        console.print(f"  Status: {status_dict['status']}")
        console.print(f"  Progress: {status_dict['progress']:.1f}%")

        if status_dict['status'] in ('completed', 'failed', 'aborted'):
            console.print("\n[yellow]Execution already finished.[/yellow]")
            console.print(f"[hint]Run 'agent-whip run' to start a new execution.[/hint]")
            return

        console.print("\n[bold]Resuming execution...[/bold]\n")

        # Resume execution (simplified - no progress display for now)
        state = asyncio.run(orchestrator.run())

        _show_final_status(state, orchestrator)

    except Exception as e:
        console.print(f"\n[red]✗ Resume failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def report(
    project_path: Path = typer.Option(
        Path("."),
        "--path",
        "-p",
        help="Path to project directory",
        exists=True,
    ),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path",
    ),
):
    """
    Generate execution report.

    Example:
        agent-whip report
        agent-whip report --output report.html
    """
    console.print(f"[bold blue]AgentWhip v{__version__} - Report[/bold blue]\n")

    project_path = project_path.resolve()

    # Check for state file
    state_file = project_path / ".agent-whip" / "state.json"
    if not state_file.exists():
        console.print("[yellow]No execution state found.[/yellow]")
        return

    # Generate report
    try:
        orchestrator = ExecutionOrchestrator.create(project_path)
        if not orchestrator.load_saved_state():
            console.print("[red]✗ Failed to load saved state.[/red]")
            raise typer.Exit(1)
        status_dict = orchestrator.get_status()

        # Display report
        _show_status_table(status_dict)
        _show_task_summary(orchestrator)

    except Exception as e:
        console.print(f"[red]✗ Report generation failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def test_connection(
    project_path: Path = typer.Option(
        Path("."),
        "--path",
        "-p",
        help="Path to project directory",
        exists=True,
    ),
    worker: str = typer.Option(
        None,
        "--worker",
        "-w",
        help="Specific worker to test (default: all)",
),
):
    """
    Test connection to AI providers.

    Example:
        agent-whip test-connection
        agent-whip test-connection --worker claude
    """
    console.print(f"[bold blue]AgentWhip v{__version__} - Connection Test[/bold blue]\n")

    project_path = project_path.resolve()

    # Load config
    try:
        config = load_config(project_path)
    except Exception as e:
        console.print(f"[red]✗ Failed to load config: {e}[/red]")
        raise typer.Exit(1)

    # Test Claude worker
    if worker in (None, "claude"):
        console.print("[bold]Testing Claude Worker...[/bold]")

        api_key = config.claude.api_key
        base_url = config.claude.base_url
        model = config.claude.model

        # Check API key
        if not api_key or api_key == "${ANTHROPIC_API_KEY}":
            console.print("  [yellow]⚠ API key not configured[/yellow]")
            console.print("    Set ANTHROPIC_API_KEY environment variable or add to agent-whip.yml")
        else:
            console.print(f"  ✓ API Key: {'*' * (len(api_key) - 4)}{api_key[-4:]}")
            console.print(f"  ✓ Base URL: {base_url}")
            console.print(f"  ✓ Model: {model}")

            # Test actual connection
            console.print("  Testing connection...", end=" ")
            try:
                result = asyncio.run(_test_claude_connection(api_key, base_url, model))
                if result["success"]:
                    console.print("[green]✓ Connected[/green]")
                    console.print(f"    Model: {result['model']}")
                    console.print(f"    Latency: {result['latency_ms']:.0f}ms")
                else:
                    console.print("[red]✗ Failed[/red]")
                    console.print(f"    Error: {result['error']}")
            except Exception as e:
                console.print(f"[red]✗ Connection failed: {e}[/red]")

    # Test OpenCode worker
    if worker in (None, "opencode"):
        console.print("\n[bold]Testing OpenCode Worker...[/bold]")

        api_key = config.opencode.api_key
        base_url = config.opencode.base_url if hasattr(config.opencode, 'base_url') else "https://api.opencode.com"
        model = config.opencode.model

        # Check API key
        if not api_key or api_key == "${OPENCODE_API_KEY}":
            console.print("  [yellow]⚠ API key not configured[/yellow]")
            console.print("    Set OPENCODE_API_KEY environment variable or add to agent-whip.yml")
        else:
            console.print(f"  ✓ API Key: {'*' * (len(api_key) - 4)}{api_key[-4:]}")
            console.print(f"  ✓ Base URL: {base_url}")
            console.print(f"  ✓ Model: {model}")

            # Test actual connection
            console.print("  Testing connection...", end=" ")
            try:
                result = asyncio.run(_test_opencode_connection(api_key, base_url, model))
                if result["success"]:
                    console.print("[green]✓ Connected[/green]")
                    console.print(f"    Model: {result['model']}")
                    console.print(f"    Latency: {result['latency_ms']:.0f}ms")
                else:
                    console.print("[red]✗ Failed[/red]")
                    console.print(f"    Error: {result['error']}")
            except Exception as e:
                console.print(f"[red]✗ Connection failed: {e}[/red]")

    # Show summary
    console.print("\n[bold]Configuration file:[/bold]")
    config_file = project_path / "agent-whip.yml"
    if config_file.exists():
        console.print(f"  ✓ {config_file}")
    else:
        console.print(f"  [yellow]⚠ No agent-whip.yml found (using defaults)[/yellow]")

    console.print("\n[hint]To configure workers, create agent-whip.yml:[/hint]")
    console.print("""
    claude:
      api_key: "${ANTHROPIC_API_KEY}"
      model: claude-opus-4-6
      base_url: https://api.anthropic.com
    """)


async def _test_claude_connection(api_key: str, base_url: str, model: str) -> dict:
    """Test Claude API connection."""
    import time

    import httpx

    # Ensure base_url ends with /v1
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"

    start_time = time.time()

    try:
        async with httpx.AsyncClient(
            base_url=base,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=30.0,
        ) as client:
            response = await client.post(
                "/messages",
                json={
                    "model": model,
                    "max_tokens": 10,
                    "messages": [
                        {"role": "user", "content": "Hi"}
                    ],
                },
            )

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return {
                    "success": True,
                    "model": model,
                    "latency_ms": latency_ms,
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                }

    except httpx.ConnectError as e:
        return {
            "success": False,
            "error": f"Connection failed: {e}",
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Connection timed out",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def _test_opencode_connection(api_key: str, base_url: str, model: str) -> dict:
    """Test OpenCode API connection."""
    import time

    import httpx

    start_time = time.time()

    try:
        async with httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            },
            timeout=30.0,
        ) as client:
            # OpenCode API format (adjust based on actual API spec)
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": "Hi"}
                ],
                "max_tokens": 10,
            }

            response = await client.post("/chat/completions", json=payload)

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return {
                    "success": True,
                    "model": model,
                    "latency_ms": latency_ms,
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                }

    except httpx.ConnectError as e:
        return {
            "success": False,
            "error": f"Connection failed: {e}",
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Connection timed out",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def _create_progress_display(orchestrator: ExecutionOrchestrator):
    """Create a live progress display."""
    from rich.live import Live

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage}"),
        console=console,
        transient=True,
    )

    task_id = progress.add_task(
        description="Initializing...",
        total=100,
    )

    # Update progress periodically
    stop_progress = False

    def update_progress():
        while not stop_progress:
            try:
                status = orchestrator.get_status()
                total = status.get("total", 1)
                completed = status.get("completed", 0)

                percentage = (completed / total * 100) if total > 0 else 0

                current_task = status.get("current_task")
                description = f"Working on {current_task}" if current_task else "Processing..."

                progress.update(
                    task_id,
                    description=description,
                    completed=int(percentage),
                )

                if orchestrator._is_complete():
                    break

            except Exception:
                pass  # Silently continue on error

            import time
            time.sleep(0.1)

    thread = threading.Thread(target=update_progress, daemon=True)
    thread.start()

    # Return a Live context manager
    return Live(progress, console=console, refresh_per_second=4)


def _show_plan_summary(plan):
    """Show a summary table of the plan."""
    table = Table(title="\nPlan Summary", show_header=True, header_style="bold magenta")
    table.add_column("Phase", style="cyan", width=30)
    table.add_column("Tasks", justify="right", style="green")
    table.add_column("Description", style="white")

    for phase in plan.phases:
        tasks = plan.get_tasks_for_phase(phase.name)
        desc = phase.description or "-"
        table.add_row(phase.name, str(len(tasks)), desc)

    console.print(table)


def _show_final_status(state, orchestrator):
    """Show final execution status."""
    status = state.status.value

    if status == "completed":
        console.print(f"\n[bold green]✓ Execution completed![/bold green]")
    elif status == "failed":
        console.print(f"\n[bold red]✗ Execution failed[/bold red]")
    elif status == "aborted":
        console.print(f"\n[bold yellow]⚠ Execution aborted[/bold yellow]")
    else:
        console.print(f"\n[bold]Execution status: {status}[/bold]")

    # Show summary
    summary = orchestrator.get_status()
    console.print(f"  Completed: {summary['completed']}/{summary['total']}")
    if summary['failed'] > 0:
        console.print(f"  Failed: {summary['failed']}")


def _show_status_table(status_dict: dict):
    """Show status as a table."""
    table = Table(title="Execution Status", show_header=True)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    for key, value in status_dict.items():
        if key == "progress":
            value = f"{value:.1f}%"
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)


def _show_task_summary(orchestrator):
    """Show task summary."""
    if not orchestrator._plan:
        return

    table = Table(title="Task Summary", show_header=True)
    table.add_column("Phase", style="cyan")
    table.add_column("Completed", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Total", justify="right")

    for phase in orchestrator._plan.phases:
        tasks = orchestrator._plan.get_tasks_for_phase(phase.name)
        completed = sum(1 for t in tasks if t.status.value == "completed")
        failed = sum(1 for t in tasks if t.status.value == "failed")
        table.add_row(phase.name, str(completed), str(failed), str(len(tasks)))

    console.print(table)


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
