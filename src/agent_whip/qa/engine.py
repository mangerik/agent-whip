"""
QA Engine for AgentWhip.

Runs Playwright tests and evaluates results.
"""

import asyncio
import json
import re
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from agent_whip.config import AgentWhipConfig, QAConfig
from agent_whip.models.state import PhaseState


class TestStatus(str, Enum):
    """Status of a test."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    ERROR = "error"


class TestResult(BaseModel):
    """Result of a single test."""

    name: str = Field(description="Test name")
    status: TestStatus = Field(description="Test status")
    duration: float = Field(default=0.0, description="Test duration in seconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    file: Optional[str] = Field(default=None, description="Test file path")
    line: Optional[int] = Field(default=None, description="Line number")


class QAResult(BaseModel):
    """Result of QA execution."""

    success: bool = Field(description="Overall success")
    total_tests: int = Field(default=0, description="Total number of tests")
    passed: int = Field(default=0, description="Number of passed tests")
    failed: int = Field(default=0, description="Number of failed tests")
    skipped: int = Field(default=0, description="Number of skipped tests")
    duration: float = Field(default=0.0, description="Total duration in seconds")
    tests: list[TestResult] = Field(default_factory=list, description="Individual test results")
    screenshots: list[str] = Field(default_factory=list, description="Screenshot paths")

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_tests == 0:
            return 0.0
        return (self.failed / self.total_tests) * 100

    @property
    def has_failures(self) -> bool:
        """Check if there are any failures."""
        return self.failed > 0

    def get_failed_tests(self) -> list[TestResult]:
        """Get list of failed tests."""
        return [t for t in self.tests if t.status == TestStatus.FAILED]


class QAEngine(BaseModel):
    """
    QA Engine for running tests.

    Supports Playwright and other test frameworks.
    """

    config: QAConfig
    project_path: Path

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def run_tests(
        self,
        phase: Optional[PhaseState] = None,
    ) -> QAResult:
        """
        Run QA tests.

        Args:
            phase: Phase being tested (for context)

        Returns:
            QAResult with test results
        """
        if not self.config.enabled:
            return QAResult(
                success=True,
                total_tests=0,
                passed=0,
                duration=0.0,
            )

        # Determine test command
        test_command = self._get_test_command()

        # Run tests
        return await self._run_command(test_command)

    def _get_test_command(self) -> str:
        """Get test command based on framework."""
        framework = self.config.framework.lower()

        if framework == "playwright":
            # Check for package.json
            package_json = self.project_path / "package.json"
            if package_json.exists():
                # Use npm test if it has playwright config
                return "npm test"
            # Direct playwright command
            return "npx playwright test"
        elif framework == "jest":
            return "npm test"
        elif framework == "pytest":
            return "pytest"
        else:
            return self.config.test_command

    async def _run_command(self, command: str) -> QAResult:
        """
        Run test command and parse results.

        Args:
            command: Command to run

        Returns:
            Parsed QAResult
        """
        import subprocess

        try:
            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.timeout if hasattr(self.config, "timeout") else 300,
            )

            output = stdout.decode("utf-8")
            error_output = stderr.decode("utf-8")

            # Parse results
            return self._parse_output(output, error_output, process.returncode)

        except asyncio.TimeoutError:
            return QAResult(
                success=False,
                total_tests=0,
                failed=1,
                duration=300.0,
                tests=[TestResult(
                    name="timeout",
                    status=TestStatus.TIMEOUT,
                    error="Test execution timed out",
                )],
            )
        except Exception as e:
            return QAResult(
                success=False,
                total_tests=0,
                failed=1,
                duration=0.0,
                tests=[TestResult(
                    name="error",
                    status=TestStatus.ERROR,
                    error=str(e),
                )],
            )

    def _parse_output(self, stdout: str, stderr: str, return_code: int) -> QAResult:
        """Parse test output into QAResult."""
        # Try to detect framework and parse accordingly
        if "playwright" in stdout.lower() or "playwright" in stderr.lower():
            return self._parse_playwright(stdout, stderr, return_code)
        elif "jest" in stdout.lower():
            return self._parse_jest(stdout, stderr, return_code)
        elif "pytest" in stdout.lower():
            return self._parse_pytest(stdout, stderr, return_code)
        else:
            # Generic parsing
            return self._parse_generic(stdout, stderr, return_code)

    def _parse_playwright(self, stdout: str, stderr: str, return_code: int) -> QAResult:
        """Parse Playwright test output."""
        tests = []
        passed = 0
        failed = 0
        skipped = 0

        # Parse Playwright JSON output if available
        # Look for test results in output
        lines = stdout.split("\n")

        current_test = None

        for line in lines:
            # Try to find test results
            # Playwright format: ✓ test name or ✗ test name
            if line.startswith("  ✓") or line.startswith("  ✔"):
                name = line[3:].strip()
                tests.append(TestResult(name=name, status=TestStatus.PASSED))
                passed += 1
            elif line.startswith("  ✗") or line.startswith("  ✖"):
                name = line[3:].strip()
                tests.append(TestResult(name=name, status=TestStatus.FAILED))
                failed += 1
            elif line.startswith("  -") or "skipped" in line.lower():
                name = line[3:].strip()
                tests.append(TestResult(name=name, status=TestStatus.SKIPPED))
                skipped += 1

        # If no tests found in output, try summary line
        if not tests:
            # Look for summary like "3 passed, 1 failed"
            summary_match = re.search(r"(\d+) passed", stdout)
            if summary_match:
                passed = int(summary_match.group(1))

            failed_match = re.search(r"(\d+) failed", stdout)
            if failed_match:
                failed = int(failed_match.group(1))

        # Check for screenshots
        screenshots = []
        screenshot_dir = self.project_path / "test-results"
        if screenshot_dir.exists():
            screenshots = [
                str(p) for p in screenshot_dir.glob("**/*.png")
                if p.is_file()
            ]

        return QAResult(
            success=(return_code == 0 and failed == 0),
            total_tests=len(tests) or passed + failed + skipped,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration=self._extract_duration(stdout),
            tests=tests,
            screenshots=screenshots,
        )

    def _parse_jest(self, stdout: str, stderr: str, return_code: int) -> QAResult:
        """Parse Jest test output."""
        tests = []
        passed = 0
        failed = 0

        # Parse Jest output
        lines = stdout.split("\n")

        for line in lines:
            # ✓ test name
            if "✓" in line:
                name = line.split("✓")[1].strip() if "✓" in line else line
                tests.append(TestResult(name=name, status=TestStatus.PASSED))
                passed += 1
            elif "✕" in line:
                name = line.split("✕")[1].strip() if "✕" in line else line
                tests.append(TestResult(name=name, status=TestStatus.FAILED))
                failed += 1

        # Look for summary
        summary_match = re.search(r"Tests:\s+(\d+) passed, (\d+) failed", stdout)
        if summary_match:
            passed = int(summary_match.group(1))
            failed = int(summary_match.group(2))

        return QAResult(
            success=(return_code == 0 and failed == 0),
            total_tests=passed + failed,
            passed=passed,
            failed=failed,
            skipped=0,
            duration=self._extract_duration(stdout),
            tests=tests,
        )

    def _parse_pytest(self, stdout: str, stderr: str, return_code: int) -> QAResult:
        """Parse pytest output."""
        tests = []
        passed = 0
        failed = 0
        skipped = 0

        # Parse pytest output
        lines = stdout.split("\n")

        for line in lines:
            # PASSED test_name.py::test_func
            if "PASSED" in line:
                name = line.split("PASSED")[1].strip()
                tests.append(TestResult(name=name, status=TestStatus.PASSED))
                passed += 1
            elif "FAILED" in line:
                name = line.split("FAILED")[1].strip()
                tests.append(TestResult(name=name, status=TestStatus.FAILED))
                failed += 1
            elif "SKIPPED" in line:
                name = line.split("SKIPPED")[1].strip()
                tests.append(TestResult(name=name, status=TestStatus.SKIPPED))
                skipped += 1

        # Look for summary
        summary_match = re.search(r"(\d+) passed, (\d+) failed", stdout)
        if summary_match:
            passed = int(summary_match.group(1))
            failed = int(summary_match.group(2))

        return QAResult(
            success=(return_code == 0 and failed == 0),
            total_tests=passed + failed + skipped,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration=self._extract_duration(stdout),
            tests=tests,
        )

    def _parse_generic(self, stdout: str, stderr: str, return_code: int) -> QAResult:
        """Generic test output parser."""
        # Try to extract basic info
        passed_match = re.search(r"(\d+) pass", stdout, re.IGNORECASE)
        failed_match = re.search(r"(\d+) fail", stdout, re.IGNORECASE)

        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else (1 if return_code != 0 else 0)

        return QAResult(
            success=(return_code == 0),
            total_tests=passed + failed,
            passed=passed,
            failed=failed,
            skipped=0,
            duration=self._extract_duration(stdout),
            tests=[],
        )

    def _extract_duration(self, output: str) -> float:
        """Extract test duration from output."""
        # Look for patterns like "in 5.2s" or "Time: 5.2s"
        match = re.search(r"(?:in|time:)\s+(\d+\.?\d*)s?", output, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return 0.0

    def get_test_files(self) -> list[Path]:
        """Get list of test files in project."""
        test_patterns = [
            "**/*.test.js",
            "**/*.test.ts",
            "**/*.spec.js",
            "**/*.spec.ts",
            "**/test_*.py",
            "**/*_test.py",
        ]

        test_files = []
        for pattern in test_patterns:
            test_files.extend(self.project_path.glob(pattern))

        return test_files

    def has_tests(self) -> bool:
        """Check if project has any tests."""
        return len(self.get_test_files()) > 0


class MockQAEngine(BaseModel):
    """
    Mock QA Engine for testing.

    Simulates test execution without running actual tests.
    """

    config: QAConfig
    project_path: Path

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def run_tests(
        self,
        phase: Optional[PhaseState] = None,
    ) -> QAResult:
        """Simulate running tests."""
        await asyncio.sleep(0.1)

        # Simulate successful test run
        return QAResult(
            success=True,
            total_tests=5,
            passed=5,
            failed=0,
            skipped=0,
            duration=0.5,
            tests=[
                TestResult(name=f"Test {i}", status=TestStatus.PASSED)
                for i in range(5)
            ],
        )

    def has_tests(self) -> bool:
        """Mock always has tests."""
        return True
