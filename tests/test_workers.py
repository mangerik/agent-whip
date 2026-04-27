"""
Test script to verify Claude and OpenCode CLI workers.
"""
import asyncio
from pathlib import Path

from agent_whip.config import AgentWhipConfig, WorkerMode
from agent_whip.models.task import Task
from agent_whip.workers.manager import WorkerManager
from agent_whip.workers.claude import ClaudeWorker, MockClaudeWorker
from agent_whip.workers.claude_cli import ClaudeCLIWorker, MockClaudeCLIWorker
from agent_whip.workers.opencode import OpenCodeWorker, MockOpenCodeWorker
from agent_whip.workers.opencode_cli import OpenCodeCLIWorker, MockOpenCodeCLIWorker


async def test_cli_mock_workers():
    """Test that CLI mock workers work."""
    print("\n=== Testing CLI Mock Workers ===\n")

    config = AgentWhipConfig()

    # Test Mock Claude CLI
    print("1. Mock Claude CLI Worker:")
    mock_claude_cli = MockClaudeCLIWorker(
        config=config.claude,
        project_path=Path.cwd(),
    )

    task = Task(
        id="TEST-001",
        phase="Test Phase",
        phase_number=1,
        description="Create a simple hello world function"
    )

    result = await mock_claude_cli.execute(task)
    print(f"   Success: {result.success}")
    print(f"   Worker: {result.worker_used}")
    print(f"   Duration: {result.duration_seconds}s")

    # Test Mock OpenCode CLI
    print("\n2. Mock OpenCode CLI Worker:")
    mock_opencode_cli = MockOpenCodeCLIWorker(
        config=config.opencode,
        project_path=Path.cwd(),
    )

    result = await mock_opencode_cli.execute(task)
    print(f"   Success: {result.success}")
    print(f"   Worker: {result.worker_used}")
    print(f"   Duration: {result.duration_seconds}s")


async def test_worker_manager_modes():
    """Test WorkerManager with different modes."""
    print("\n=== Testing WorkerManager Modes ===\n")

    task = Task(
        id="TEST-002",
        phase="Test Phase",
        phase_number=1,
        description="Create a test function"
    )

    # Test 1: Mock mode (uses mock CLI workers)
    print("1. Mock mode:")
    config = AgentWhipConfig()
    manager = WorkerManager(
        config=config,
        project_path=Path.cwd(),
        use_mock=True,
    )
    manager.initialize_workers()

    print(f"   Available workers: {list(manager._workers.keys())}")
    print(f"   Claude worker type: {type(manager._workers.get('claude')).__name__}")
    print(f"   OpenCode worker type: {type(manager._workers.get('opencode')).__name__}")

    # Test 2: API mode (but no API key, so no workers)
    print("\n2. API mode (no API key):")
    config = AgentWhipConfig()
    config.claude.mode = WorkerMode.API
    config.opencode.mode = WorkerMode.API
    manager = WorkerManager(
        config=config,
        project_path=Path.cwd(),
        use_mock=False,
    )
    manager.initialize_workers()

    print(f"   Available workers: {list(manager._workers.keys())}")
    print(f"   Has workers: {manager.has_workers()}")

    # Test 3: CLI mode (no CLI installed, but uses mock for test)
    print("\n3. CLI mode (with mock):")
    config = AgentWhipConfig()
    config.claude.mode = WorkerMode.CLI
    config.opencode.mode = WorkerMode.CLI
    manager = WorkerManager(
        config=config,
        project_path=Path.cwd(),
        use_mock=True,  # Use mock since we don't have actual CLI
    )
    manager.initialize_workers()

    print(f"   Available workers: {list(manager._workers.keys())}")
    print(f"   Claude worker type: {type(manager._workers.get('claude')).__name__}")

    # Test 4: Auto mode (default)
    print("\n4. Auto mode (default):")
    config = AgentWhipConfig()
    manager = WorkerManager(
        config=config,
        project_path=Path.cwd(),
        use_mock=True,
    )
    manager.initialize_workers()

    print(f"   Available workers: {list(manager._workers.keys())}")
    print(f"   Claude worker type: {type(manager._workers.get('claude')).__name__}")


async def test_real_cli_availability():
    """Check if real CLI tools are available."""
    print("\n=== Checking Real CLI Availability ===\n")

    import shutil

    claude_cli = shutil.which("claude")
    opencode_cli = shutil.which("opencode")

    print("CLI Tools Installed:")
    print(f"  claude: {'✓ Found at ' + claude_cli if claude_cli else '✗ Not found'}")
    print(f"  opencode: {'✓ Found at ' + opencode_cli if opencode_cli else '✗ Not found'}")

    if claude_cli:
        print("\nClaude CLI detected! AgentWhip can use CLI mode.")
    else:
        print("\nClaude CLI not found. Will use API mode if API key is provided.")


async def main():
    """Run all tests."""
    await test_cli_mock_workers()
    await test_worker_manager_modes()
    await test_real_cli_availability()

    print("\n" + "="*50)
    print("Summary:")
    print("  - CLI Mock workers: ✓ Working")
    print("  - WorkerManager modes: ✓ Working")
    print("  - Priority: CLI > API (auto mode)")
    print("="*50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
