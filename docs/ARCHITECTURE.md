# AgentWhip - Architecture Document

**Version:** 1.1
**Date:** 2026-04-23

Referensi flow ringkas: [FLOW_TERBARU.md](FLOW_TERBARU.md)

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          AgentWhip Core                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Plan Parser  │─▶│ Task Queue   │─▶│   Execution Engine       │  │
│  └──────────────┘  └──────────────┘  │  ┌────────────────────┐  │  │
│                                       │  │  Worker Manager    │  │  │
│  ┌──────────────┐  ┌──────────────┐  │  │  - Claude Worker   │  │  │
│  │ State Store  │◀─│ Progress     │  │  │  - OpenCode Worker │  │  │
│  │              │  │   Tracker    │  │  └────────────────────┘  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│                                       │                              │
│  ┌──────────────┐  ┌──────────────┐  │                              │
│  │   QA Engine  │◀─│   Evaluator  │──┘                              │
│  │  (Playwright)│  │(Tukang Cambuk)│                              │
│  └──────────────┘  └──────────────┘                                  │
└─────────────────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ plan.md     │    │ Claude API  │    │ Playwright  │
│ (Input)     │    │ OpenCode API│    │ (QA)        │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 1.2 Component Overview

| Component | Responsibility |
|-----------|----------------|
| **Plan Parser** | Dual-mode parser: strict (markdown) or flexible (AI-powered) |
| **Task Queue** | Manage task queue, handle dependencies |
| **Worker Manager** | Manage AI workers (Claude, OpenCode) |
| **Progress Tracker** | Track execution status, emit events |
| **Evaluator** | Evaluate completion, decide next action |
| **QA Engine** | Run tests, evaluate results |
| **State Store** | Persist state, support resume |
| **Config Loader** | Load config from project + `~/.claude/settings.json` |

---

## 2. Data Models

### 2.1 Plan Structure (plan.md)

```markdown
# Project Plan: [Project Name]

## Overview
[Brief description]

## Phases

### Phase 1: [Phase Name]
- [ ] Task 1.1: [Description]
- [ ] Task 1.2: [Description]
  - Depends on: Task 1.1

### Phase 2: [Phase Name]
- [ ] Task 2.1: [Description]
  - Depends on: Task 1.2, Task 1.3

## Dependencies
- External: [list external dependencies]

## Success Criteria
- [ ] [Criteria 1]
- [ ] [Criteria 2]
```

### 2.2 Internal State Model

```python
@dataclass
class Task:
    id: str
    phase: str
    description: str
    status: TaskStatus  # pending, in_progress, completed, failed, skipped
    dependencies: list[str]
    attempts: int
    result: Optional[TaskResult]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

@dataclass
class TaskResult:
    success: bool
    output: str
    error: Optional[str]
    artifacts: list[str]

@dataclass
class ExecutionState:
    project_name: str
    plan_path: str
    phases: list[Phase]
    current_phase: Optional[str]
    current_task: Optional[str]
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    started_at: datetime
    last_updated: datetime
```

---

## 3. Component Details

### 3.1 Plan Parser

**Responsibility:** Parse plan.md dan build execution graph

AgentWhip uses a **dual-mode parser**:

#### Strict Mode (Default)
Fast regex-based markdown parser for standard format.

```python
class MarkdownParser:
    def parse(self, plan_path: Path) -> ExecutionPlan:
        # Parse markdown with regex
        # Extract phases and tasks
        # Build dependency graph
        # Validate DAG (no cycles)
        return ExecutionPlan(...)
```

**Key Functions:**
- `parse_phase()`: Extract phase dari markdown heading
- `parse_task()`: Extract task dari checklist
- `parse_dependencies()`: Parse task dependencies
- `validate_dag()`: Ensure no circular dependencies

#### Flexible Mode (AI-Powered)
Uses Claude AI to interpret ANY plan format.

```python
class FlexibleParser:
    async def parse(self, plan_path: Path) -> ExecutionPlan:
        # Read plan content
        # Send to Claude AI for interpretation
        # Extract structured plan from AI response
        # Build execution plan
        return ExecutionPlan(...)
```

**Supported Formats:**
- Free-form todo lists
- Notion exports
- GitHub Issues
- Simple text notes
- Any human-readable format!

#### Auto-Fallback
When strict mode fails, automatically falls back to flexible mode:

```python
async def parse_plan_with_fallback(plan_path: Path) -> ExecutionPlan:
    try:
        return await strict_parser.parse(plan_path)
    except Exception:
        return await flexible_parser.parse(plan_path)
```

### 3.2 Task Queue

**Responsibility:** Manage task execution order

```python
class TaskQueue:
    def __init__(self, tasks: list[Task]):
        self.ready_queue = PriorityQueue()
        self.running = set()
        self.completed = set()
        self.failed = set()

    def get_next_task(self) -> Optional[Task]:
        # Return task yang dependencies-nya satisfied
        pass

    def mark_complete(self, task_id: str):
        # Move task to completed, check dependents
        pass
```

### 3.3 Worker Manager

**Responsibility:** Manage AI workers

```python
class WorkerManager:
    def __init__(self):
        self.workers = {
            "claude": ClaudeWorker(),
            "opencode": OpenCodeWorker(),
        }

    async def execute(self, task: Task) -> TaskResult:
        # Select worker based on task/availability
        # Execute task
        # Return result
        pass
```

**Worker Interface:**

```python
class Worker(ABC):
    @abstractmethod
    async def execute(self, task: Task) -> TaskResult:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass
```

### 3.4 Progress Tracker (Tukang Cambuk)

**Responsibility:** Evaluate progress dan decide next action

```python
class ProgressTracker:
    def evaluate(self, task: Task, result: TaskResult) -> NextAction:
        # Decide: continue, retry, skip, abort
        if result.success:
            return NextAction.CONTINUE
        elif task.attempts < MAX_RETRIES:
            return NextAction.RETRY
        else:
            return NextAction.ABORT

    def should_run_qa(self, phase: str) -> bool:
        # Run QA after phase completion
        pass
```

**Decision Logic:**

| Condition | Action |
|-----------|--------|
| Task success | Continue to next task |
| Task failed, retry < max | Retry task |
| Task failed, retry >= max | Abort or skip based on config |
| Phase complete | Run QA if enabled |
| QA failed | Create bug ticket, continue or abort |

### 3.5 QA Engine

**Responsibility:** Run Playwright tests

```python
class QAEngine:
    def __init__(self, project_path: Path):
        self.playwright = PlaywrightProject(project_path)

    async def run_tests(self) -> QAResult:
        # Discover tests
        # Run tests
        # Collect results
        return QAResult(...)

    def create_bug_ticket(self, failure: TestFailure):
        # Create issue in tracker
        pass
```

### 3.6 State Store

**Responsibility:** Persist execution state

```python
class StateStore:
    def save(self, state: ExecutionState):
        # Save to JSON/SQLite
        pass

    def load(self) -> Optional[ExecutionState]:
        # Load previous state
        pass

    def checkpoint(self, state: ExecutionState):
        # Create checkpoint
        pass
```

---

## 4. Execution Flow

### 4.1 Main Execution Loop

```python
async def run(project_path: Path, flexible: bool = False):
    orchestrator = ExecutionOrchestrator.create(
        project_path=project_path,
        use_flexible=flexible,
    )

    while running and not complete:
        task = queue.get_ready()
        if not task:
            wait_or_finish()
            continue

        result = await worker_manager.execute_task(task)
        action = tracker.evaluate_task_result(task, result)

        if action == RETRY:
            queue.requeue(task.id)
        elif action == SKIP:
            queue.mark_skipped(task.id)
        elif action == ABORT:
            queue.mark_failed(task.id)
            state.mark_aborted(...)
            raise RuntimeError(...)
        else:
            queue.mark_completed(task.id)

        if action == RUN_QA:
            qa_result = await qa_engine.run_tests(...)
            maybe_create_tickets(qa_result)

        maybe_checkpoint()

    state_store.save(state, plan)  # .agent-whip/state.json
```

### 4.2 State-Aware Commands

`status`, `resume`, dan `report` menggunakan state yang sama:
1. Inisialisasi orchestrator.
2. Load state + plan dari `.agent-whip/state.json`.
3. Rebuild queue dari status task tersimpan.
4. Tampilkan status / lanjutkan run / generate report dari state tersebut.

### 4.3 State Diagram

```
┌────────┐     ┌─────────────┐     ┌────────────┐
│  START │────▶│  PARSING   │────▶│  QUEUING  │
└────────┘     └─────────────┘     └────────────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │ EXECUTING  │◀────┐
                                    └─────────────┘     │
                                           │            │
                                           ▼            │
                                    ┌─────────────┐     │
                              ┌────│ EVALUATING  │─────┘
                              │    └─────────────┘
                              │           │
                ┌─────────────┴───────────┴─────────────┐
                │                   │                    │
                ▼                   ▼                    ▼
         ┌───────────┐        ┌───────────┐        ┌───────────┐
         │  CONTINUE │        │   RETRY   │        │   ABORT   │
         └───────────┘        └───────────┘        └───────────┘
                │                   │                    │
                └───────────────────┴────────────────────┘
                                    │
                                    ▼
                              ┌───────────┐
                              │    QA     │
                              └───────────┘
                                    │
                                    ▼
                              ┌───────────┐
                              │  COMPLETE │
                              └───────────┘
```

---

## 5. API Design

### 5.1 CLI Interface

```bash
# Start execution
agent-whip run --path <project-dir> [--mock] [--flexible]

# Resume execution
agent-whip resume --path <project-dir> [--mock]

# Check status
agent-whip status --path <project-dir>

# Generate report
agent-whip report --path <project-dir>

# Validate plan
agent-whip validate --plan <plan-path> [--flexible]
```

### 5.2 Python API

```python
from pathlib import Path
from agent_whip.orchestrator import ExecutionOrchestrator

# fresh run
orchestrator = ExecutionOrchestrator.create(
    project_path=Path("/path/to/project"),
    use_flexible=False,
)
state = await orchestrator.run()

# resume flow
orchestrator = ExecutionOrchestrator.create(project_path=Path("/path/to/project"))
if orchestrator.load_saved_state():
    resumed_state = await orchestrator.run()
status = orchestrator.get_status()
```

---

## 6. Error Handling

### 6.1 Error Categories

| Category | Handling |
|----------|----------|
| Parse Error | Abort, show error location |
| Dependency Cycle | Abort, show cycle |
| Worker Unavailable | Retry with exponential backoff |
| Task Execution Failed | Retry up to MAX_RETRIES |
| QA Failure | Create bug, continue or abort |
| State Corruption | Recovery from backup |

### 6.2 Retry Strategy

```python
@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0
    exponential_base: float = 2.0

def calculate_delay(attempt: int, config: RetryConfig) -> float:
    return min(
        config.base_delay * (config.exponential_base ** attempt),
        config.max_delay
    )
```

---

## 7. Configuration

### 7.1 Config Hierarchy

AgentWhip loads configuration in this order (later overrides earlier):

1. **Default values** from code
2. **`~/.claude/settings.json`** - Auto-detected Claude settings
3. **`agent-whip.yml`** - Project-specific config
4. **Environment variables** - Runtime overrides

### 7.2 Claude Settings Integration

AgentWhip automatically reads from `~/.claude/settings.json`:

```json
{
  "apiKey": "sk-your-api-key",
  "baseUrl": "https://open.bigmodel.cn/api/paas/v4",
  "model": "claude-opus-4-6"
}
```

This enables seamless integration with:
- Anthropic API (default)
- z.ai (Zhipu AI)
- Other compatible providers

### 7.3 Config File (agent-whip.yml)

Optional project-specific config:

```yaml
# agent-whip.yml
project:
  name: "My Project"

default_worker: "claude"

claude:
  api_key: "${ANTHROPIC_API_KEY}"  # Optional: reads from ~/.claude/settings.json
  base_url: "https://api.anthropic.com"  # Optional: reads from ~/.claude/settings.json
  model: "claude-opus-4-6"
  max_concurrent: 3
  timeout: 600

opencode:
  api_key: "${OPENCODE_API_KEY}"
  model: "default"
  max_concurrent: 2
  timeout: 600

execution:
  max_retries: 3
  retry_delay: 1.0
  task_timeout: 600  # seconds

qa:
  enabled: true
  run_after_phase: true
  test_command: "npm test"
  framework: "playwright"

state:
  store: "json"
  path: ".agent-whip/state.json"
  backup_path: ".agent-whip/backup/"

logging:
  level: "INFO"
  file: ".agent-whip/agent-whip.log"
```

Current implementation note:
- Runtime orchestration currently persists/resumes from `.agent-whip/state.json`.

---

## 8. Security Considerations

1. **API Key Management**: Use environment variables, never hardcode
2. **State File Security**: Encrypt sensitive state data
3. **Code Execution**: Validate task before execution
4. **Dependency Validation**: Ensure no malicious dependencies

---

## 9. Scalability Considerations

1. **Horizontal Scaling**: Support multiple orchestrator instances
2. **Distributed Lock**: For shared state store
3. **Worker Pool**: Dynamic scaling based on load
4. **Circuit Breaker**: Prevent cascade failures

---

## 10. Future Enhancements

| Feature | Priority |
|---------|----------|
| Multi-project support | Low |
| Web dashboard | Medium |
| Slack/Discord integration | Low |
| Custom worker plugins | High |
| Cost estimation | Medium |
| A/B testing strategies | Low |
