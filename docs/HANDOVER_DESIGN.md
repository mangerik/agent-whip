# Handover Feature - Design Document

**Version:** 1.0
**Date:** 2026-04-23
**Status:** Draft

---

## 1. Overview

### 1.1 Problem Statement

Dalam eksekusi plan yang panjang dengan multi-agent, context window dan token limit menjadi bottleneck. Ketika satu agent mendekati limit (85%), perlu ada mekanisme untuk:

1. Mendeteksi limit tercapai
2. Membuat summarize pekerjaan yang sudah dilakukan
3. Melaporkan ke orchestrator
4. Delegasi ke agent baru dengan konteks terjaga
5. Menyimpan konteks yang terupdate secara persisten

### 1.2 Goals

- **Seamless Continuity**: Agent baru bisa lanjut tanpa kehilangan konteks
- **Context Preservation**: Semua progress dan keputusan tersimpan
- **Transparent Handover**: Orchestrator tahu persis apa yang terjadi
- **Minimal Disruption**: Handover tidak mengganggu flow eksekusi

---

## 2. Architecture

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     AgentWhip Orchestrator                      │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │Token Tracker │─▶│Handover Mgr  │─▶│  Context Document      │ │
│  │              │  │              │  │  (Persistent State)     │ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
│           │                │                     │               │
│           ▼                ▼                     ▼               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Worker Manager                              │   │
│  │  ┌──────────┐      ┌──────────┐      ┌──────────┐       │   │
│  │  │Worker A  │────▶│Handover  │────▶│Worker B  │       │   │
│  │  │@85%      │      │Summary   │      │(Fresh)   │       │   │
│  │  └──────────┘      └──────────┘      └──────────┘       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Worker A executing task...                                   │
│    - Token usage: 170,000 / 200,000 (85%)                      │
│                                                                 │
│ 2. TokenTracker detects threshold                               │
│    - Emits TOKEN_THRESHOLD_REACHED event                        │
│                                                                 │
│ 3. HandoverManager triggered                                    │
│    a) Calls ContextSummarizer                                   │
│    b) Generates HandoverContext                                 │
│    c) Saves to ContextDocument                                  │
│                                                                 │
│ 4. Orchestrator creates Worker B                                │
│    - Passes HandoverContext as initial context                 │
│    - Updates state with handover record                         │
│                                                                 │
│ 5. Worker B continues execution                                 │
│    - Full context from Worker A preserved                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Components

### 3.1 TokenTracker

**Location:** `src/agent_whip/workers/token_tracker.py`

**Responsibility:**
- Track token usage per worker session
- Detect when threshold is reached
- Emit threshold events

**API:**
```python
class TokenTracker:
    def __init__(self, limit: int, threshold: float = 0.85)
    def record_usage(self, input_tokens: int, output_tokens: int) -> None
    def should_trigger_handover(self) -> bool
    def get_usage_stats(self) -> TokenUsageStats
    def reset(self) -> None
```

**Events Emitted:**
- `TOKEN_THRESHOLD_REACHED` - When usage >= threshold
- `TOKEN_USAGE_UPDATED` - On every usage update

---

### 3.2 ContextSummarizer

**Location:** `src/agent_whip/context/summarizer.py`

**Responsibility:**
- Create compact summary of work done
- Extract critical context for continuation
- Preserve decisions and artifacts

**API:**
```python
class ContextSummarizer:
    async def summarize_handover(
        self,
        state: ExecutionState,
        task: Task,
        work_done: str,
    ) -> HandoverContext

    async def summarize_phase(self, phase: Phase) -> PhaseSummary
    async def summarize_task_history(self, tasks: list[Task]) -> TaskHistorySummary
```

**Output Structure (HandoverContext):**
```python
@dataclass
class HandoverContext:
    handover_id: str
    timestamp: datetime

    # Project context
    project_name: str
    project_path: str

    # Execution context
    current_phase: str
    current_task: str
    phase_progress: float  # 0.0 - 1.0

    # Work summary
    work_summary: str  # AI-generated summary
    tasks_completed: list[str]  # Task IDs
    tasks_pending: list[str]  # Task IDs

    # Artifacts
    files_created: list[str]
    files_modified: list[str]
    decisions_made: list[DecisionRecord]

    # Context snapshot (compact)
    context_snapshot: dict  # Compact state dict

    # Metadata
    from_worker_id: str
    tokens_used: int
    session_duration: float
```

---

### 3.3 HandoverManager

**Location:** `src/agent_whip/workers/handover.py`

**Responsibility:**
- Coordinate handover process
- Create new worker instance
- Pass context to new worker

**API:**
```python
class HandoverManager:
    def __init__(
        self,
        summarizer: ContextSummarizer,
        state_store: StateStore,
        event_emitter: EventEmitter,
    )

    async def trigger_handover(
        self,
        from_worker: Worker,
        task: Task,
        token_tracker: TokenTracker,
    ) -> HandoverResult

    async def create_continuation_worker(
        self,
        handover_context: HandoverContext,
        worker_type: str,
    ) -> Worker

    def get_handover_history(self) -> list[HandoverRecord]
```

**Output Structure (HandoverResult):**
```python
@dataclass
class HandoverResult:
    success: bool
    handover_id: str

    from_worker_id: str
    to_worker_id: str

    context_summary: str
    tokens_preserved: int  # Estimated tokens in summary

    timestamp: datetime
    duration_ms: float

    error: Optional[str] = None
```

---

### 3.4 ContextDocument

**Location:** `src/agent_whip/context/document.py`

**Responsibility:**
- Maintain persistent context log
- Track all handovers
- Provide current context snapshot

**API:**
```python
class ContextDocument:
    def __init__(self, project_path: Path, state_store: StateStore)

    def save_context_update(self, event: ContextEvent) -> None
    def get_current_context(self) -> dict
    def get_handover_history(self) -> list[HandoverRecord]

    def append_handover(self, handover: HandoverRecord) -> None
    def append_task_completion(self, task_id: str, result: TaskResult) -> None
    def append_decision(self, decision: DecisionRecord) -> None

    def _persist(self) -> None
    def _load(self) -> None
```

**Storage:**
- File: `.agent-whip/context.json`
- Format: JSON with append-only log

**Structure:**
```json
{
  "project_name": "MyProject",
  "created_at": "2026-04-23T10:00:00Z",
  "updated_at": "2026-04-23T12:30:00Z",
  "current_phase": "Phase 2: Development",
  "current_task": "DEV-002",

  "handovers": [
    {
      "handover_id": "ho_20260423_001",
      "timestamp": "2026-04-23T11:30:00Z",
      "from_worker": "worker_A",
      "to_worker": "worker_B",
      "reason": "token_limit_85%",
      "context_summary": "..."
    }
  ],

  "context_log": [
    {
      "timestamp": "2026-04-23T10:00:00Z",
      "event": "execution_started",
      "data": {...}
    },
    {
      "timestamp": "2026-04-23T10:30:00Z",
      "event": "task_completed",
      "task_id": "DEV-001",
      "data": {...}
    }
  ],

  "decisions": [
    {
      "timestamp": "2026-04-23T10:15:00Z",
      "topic": "architecture_choice",
      "decision": "Use FastAPI instead of Flask",
      "rationale": "..."
    }
  ]
}
```

---

### 3.5 Updated Worker Base

**Modifications to:** `src/agent_whip/workers/base.py`

**New Methods:**
```python
class Worker(ABC):
    def __init__(self, ...):
        self.token_tracker: TokenTracker = ...
        self.handover_manager: Optional[HandoverManager] = None

    async def execute_with_handover(
        self,
        task: Task,
    ) -> TaskResult:
        """Execute with auto-handover when limit reached."""

    def _check_handover_needed(self) -> bool:
        """Check if handover should be triggered."""

    async def _do_handover(self, task: Task) -> HandoverResult:
        """Perform handover to new worker."""
```

---

### 3.6 Updated Orchestrator

**Modifications to:** `src/agent_whip/orchestrator.py`

**New Components:**
```python
class ExecutionOrchestrator:
    def __init__(self, ...):
        # New components
        self._context_document: ContextDocument = ...
        self._handover_manager: HandoverManager = ...

    async def _execute_task(self, task: Task) -> None:
        """Updated to handle handover events."""

    def _handle_handover_event(self, event: HandoverEvent) -> None:
        """Handle handover triggered event."""

    def get_handover_history(self) -> list[HandoverRecord]:
        """Get all handovers for this execution."""
```

---

## 4. Event System

### 4.1 New Events

| Event Name | Payload | Triggered When |
|------------|---------|----------------|
| `TOKEN_THRESHOLD_REACHED` | `{worker_id, usage, limit, percentage}` | Token usage >= threshold |
| `HANDOVER_TRIGGERED` | `{handover_id, from_worker, to_worker, context_summary}` | Handover initiated |
| `HANDOVER_COMPLETED` | `{handover_id, success, duration_ms}` | Handover complete |
| `HANDOVER_FAILED` | `{handover_id, error}` | Handover failed |
| `CONTEXT_UPDATED` | `{event_type, data}` | Context document updated |

---

## 5. Configuration

### 5.1 New Config Section

```yaml
# agent-whip.yml

handover:
  enabled: true
  token_threshold: 0.85  # 85%

  # Per-worker limits
  workers:
    claude:
      max_tokens_per_session: 200000
      enable_auto_summarize: true

    opencode:
      max_tokens_per_session: 200000
      enable_auto_summarize: true

  # Context preservation
  context_document:
    enabled: true
    path: ".agent-whip/context.json"
    max_entries: 1000
    compact_on_save: true

  # Summarization
  summarizer:
    model: "claude-opus-4-6"  # Model for summarization
    max_summary_length: 10000  # Max tokens in summary
    include_artifacts: true
    include_decisions: true
```

---

## 6. Proof-of-Concept

### 6.1 PoC Test Scenarios

```python
# tests/handover/test_handover_poc.py

class HandoverPOCTest:
    """Proof of concept tests for handover feature."""

    async def test_token_tracker_threshold(self):
        """Test token tracker detects 85% threshold."""
        tracker = TokenTracker(limit=200000, threshold=0.85)

        # Use 170,000 tokens
        tracker.record_usage(input_tokens=85000, output_tokens=85000)

        assert tracker.should_trigger_handover() == True
        assert tracker.get_usage_stats().percentage == 85.0

    async def test_context_summarizer(self):
        """Test context summarizer creates valid summary."""
        summarizer = ContextSummarizer()

        summary = await summarizer.summarize_handover(
            state=mock_state,
            task=mock_task,
            work_done="Created user authentication module",
        )

        assert summary.handover_id is not None
        assert summary.work_summary is not None
        assert len(summary.tasks_completed) > 0

    async def test_handover_flow(self):
        """Test complete handover flow."""
        # 1. Create worker with token tracker
        worker = MockWorkerWithTracker()

        # 2. Simulate work until threshold
        await worker.simulate_work(tokens=170000)

        # 3. Verify handover triggered
        assert worker.handover_triggered == True

        # 4. Verify new worker created with context
        new_worker = worker.continuation_worker
        assert new_worker is not None
        assert new_worker.context_summary is not None

    async def test_context_document_persistence(self):
        """Test context document persists correctly."""
        doc = ContextDocument(project_path=test_project)

        # Add some events
        doc.save_context_update(ContextEvent(
            event_type="task_completed",
            data={"task_id": "DEV-001", "result": "success"}
        ))

        # Reload and verify
        doc2 = ContextDocument(project_path=test_project)
        doc2._load()

        assert len(doc2.get_handover_history()) == 1
```

---

## 7. Implementation Plan

### Phase 1: Core Infrastructure (Day 1-2)
- [ ] TokenTracker implementation
- [ ] Handover data models (HandoverContext, HandoverResult, HandoverRecord)
- [ ] Event system updates

### Phase 2: Context Management (Day 2-3)
- [ ] ContextSummarizer implementation
- [ ] ContextDocument implementation
- [ ] StateStore integration

### Phase 3: Worker Integration (Day 3-4)
- [ ] Worker base class updates
- [ ] ClaudeWorker token tracking
- [ ] HandoverManager implementation

### Phase 4: Orchestrator Integration (Day 4-5)
- [ ] Orchestrator updates
- [ ] Handover event handling
- [ ] Context document lifecycle

### Phase 5: Testing & Documentation (Day 5-6)
- [ ] PoC tests
- [ ] Integration tests
- [ ] Documentation updates
- [ ] Example usage

---

## 8. Success Criteria

- [ ] Token threshold detection working at 85%
- [ ] Context summary captures all critical information
- [ ] New worker can continue without context loss
- [ ] Handover recorded in context document
- [ ] Orchestrator can handle multiple handovers
- [ ] PoC tests passing
- [ ] Documentation complete

---

## 9. Open Questions

| Question | Priority | Proposed Solution |
|----------|----------|-------------------|
| How to handle handover during active task? | High | Pause task, handover, resume with context |
| What if handover fails? | High | Retry with exponential backoff, fallback to continue |
| How to verify context integrity? | Medium | Hash verification of context snapshot |
| Multiple concurrent handovers? | Low | Queue handovers, process sequentially |

---

## 10. Future Enhancements

- **Smart Summarization**: Use AI to identify only critical context
- **Differential Context**: Only send changed context to new worker
- **Handover Optimization**: Predict handover need and prepare in advance
- **Context Compression**: Compress context before storage
- **Multi-Orchestrator Handover**: Handover between orchestrator instances
