"""
Test real CLI workers (not mock).
"""
import asyncio
from pathlib import Path

from agent_whip.config import AgentWhipConfig
from agent_whip.models.task import Task
from agent_whip.workers.claude_cli import ClaudeCLIWorker
from agent_whip.workers.opencode_cli import OpenCodeCLIWorker


async def test_real_claude_cli():
    """Test real Claude CLI worker."""
    print("\n=== Testing Real Claude CLI Worker ===\n")

    config = AgentWhipConfig()
    worker = ClaudeCLIWorker(
        config=config.claude,
        project_path=Path.cwd(),
    )

    print(f"CLI path: {worker.cli_path}")
    print(f"Available: {worker.is_available()}")

    if not worker.is_available():
        print("❌ Claude CLI not available")
        return

    # Simple task
    task = Task(
        id="TEST-001",
        phase="Test",
        phase_number=1,
        description="Say hello in one line"
    )

    print(f"\nExecuting task: {task.description}")

    try:
        result = await worker.execute(task)

        print(f"\n✓ Success: {result.success}")
        print(f"  Worker: {result.worker_used}")
        print(f"  Duration: {result.duration_seconds:.2f}s")
        print(f"\n  Output:")
        print(f"  {result.output[:500]}")

    except Exception as e:
        print(f"\n❌ Error: {e}")


async def test_real_opencode_cli():
    """Test real OpenCode CLI worker."""
    print("\n=== Testing Real OpenCode CLI Worker ===\n")

    config = AgentWhipConfig()
    worker = OpenCodeCLIWorker(
        config=config.opencode,
        project_path=Path.cwd(),
    )

    print(f"CLI path: {worker.cli_path}")
    print(f"Available: {worker.is_available()}")

    if not worker.is_available():
        print("❌ OpenCode CLI not available")
        return

    # Simple task
    task = Task(
        id="TEST-002",
        phase="Test",
        phase_number=1,
        description="Say hello in one line"
    )

    print(f"\nExecuting task: {task.description}")

    try:
        result = await worker.execute(task)

        print(f"\n✓ Success: {result.success}")
        print(f"  Worker: {result.worker_used}")
        print(f"  Duration: {result.duration_seconds:.2f}s")
        print(f"\n  Output:")
        print(f"  {result.output[:500]}")

    except Exception as e:
        print(f"\n❌ Error: {e}")


async def test_worker_manager_auto():
    """Test WorkerManager in auto mode (real CLI)."""
    print("\n=== Testing WorkerManager (Auto Mode) ===\n")

    config = AgentWhipConfig()
    # Default mode is "auto"

    from agent_whip.workers.manager import WorkerManager

    manager = WorkerManager(
        config=config,
        project_path=Path.cwd(),
        use_mock=False,  # Use real CLI
    )

    manager.initialize_workers()

    print(f"Workers initialized: {list(manager._workers.keys())}")

    for name, worker in manager._workers.items():
        print(f"  {name}: {type(worker).__name__} (available: {worker.is_available()})")

    if not manager.has_workers():
        print("\n❌ No workers available")
        return

    # Test execution
    task = Task(
        id="TEST-003",
        phase="Test",
        phase_number=1,
        description="Reply with just 'Hello World'"
    )

    print(f"\nExecuting task with default worker...")

    try:
        result = await manager.execute_task(task)

        print(f"\n✓ Success: {result.success}")
        print(f"  Worker used: {result.worker_used}")
        print(f"  Duration: {result.duration_seconds:.2f}s")
        print(f"\n  Output:")
        print(f"  {result.output[:500]}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all real CLI tests."""
    await test_real_claude_cli()
    await test_real_opencode_cli()
    await test_worker_manager_auto()

    print("\n" + "="*50)
    print("Test Complete")
    print("="*50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
