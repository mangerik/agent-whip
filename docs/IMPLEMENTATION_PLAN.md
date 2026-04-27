# AgentWhip - Implementation Plan

**Version:** 1.1
**Date:** 2026-04-23

---

## Overview

This document outlines the step-by-step implementation plan for AgentWhip.

> Catatan: dokumen ini awalnya adalah rencana awal implementasi.  
> Status implementasi terkini dirangkum di bagian "Current Progress Snapshot" di bawah.

---

## Current Progress Snapshot (2026-04-23)

### Sudah jalan
- [x] Parsing `plan.md` (strict parser) + mode fleksibel (`--flexible`)
- [x] Task queue + dependency resolution dasar
- [x] Worker manager + Claude worker + mock worker
- [x] Progress tracker (retry/skip/abort decision)
- [x] QA engine + bug ticket creator
- [x] State persistence JSON (`.agent-whip/state.json`) + backup + checkpoint
- [x] Command `status`, `resume`, `report` load state tersimpan yang sama
- [x] Perbaikan critical flow: retry queue, fail counting, resume accuracy
- [x] Test regresi critical flow (lihat `tests/test_critical_fixes.py`)

### Belum/parsial
- [ ] SQLite state backend penuh (saat ini runtime masih JSON)
- [ ] Suite test menyeluruh (baru fokus critical flow)
- [ ] Report generator multi-format (HTML/JSON) penuh

---

## Phase 1: Foundation (Week 1)

### 1.1 Project Setup
- [ ] Create Python project structure
- [ ] Setup pyproject.toml with dependencies
- [ ] Configure pre-commit hooks (black, ruff, mypy)
- [ ] Setup pytest with test structure
- [ ] Create basic CLI entry point

### 1.2 Core Data Models
- [ ] Implement `Task` dataclass
- [ ] Implement `TaskResult` dataclass
- [ ] Implement `ExecutionState` dataclass
- [ ] Implement `ExecutionPlan` dataclass
- [ ] Add pydantic validation

**Files:**
```
src/agent_whip/
  models/
    __init__.py
    task.py
    state.py
    plan.py
```

### 1.3 Plan Parser
- [ ] Implement markdown parser
- [ ] Extract phases from H2 headings
- [ ] Extract tasks from checklists
- [ ] Parse dependency syntax
- [ ] Build dependency graph
- [ ] Validate DAG (no cycles)

**Files:**
```
src/agent_whip/
  parser/
    __init__.py
    markdown_parser.py
    dependency_graph.py
    validator.py
```

**Tests:**
```python
tests/parser/
  test_markdown_parser.py
  test_dependency_graph.py
  test_validator.py
```

### 1.4 Configuration System
- [ ] Implement config loader
- [ ] Support YAML config
- [ ] Environment variable expansion
- [ ] Schema validation

**Files:**
```
src/agent_whip/
  config/
    __init__.py
    settings.py
    loader.py
```

---

## Phase 2: Task Execution (Week 2)

### 2.1 Task Queue
- [ ] Implement priority queue
- [ ] Dependency resolution
- [ ] Task status tracking
- [ ] Ready task calculation

**Files:**
```
src/agent_whip/
  queue/
    __init__.py
    task_queue.py
    dependency_resolver.py
```

### 2.2 Worker Interface
- [ ] Define Worker abstract class
- [ ] Implement worker manager
- [ ] Worker selection logic

**Files:**
```
src/agent_whip/
  workers/
    __init__.py
    base.py
    manager.py
```

### 2.3 Claude Code Integration
- [ ] Implement ClaudeWorker
- [ ] API client wrapper
- [ ] Task execution logic
- [ ] Response parsing

**Files:**
```
src/agent_whip/
  workers/
    claude.py
    client.py
```

### 2.4 OpenCode Integration (Optional)
- [ ] Implement OpenCodeWorker
- [ ] API client wrapper
- [ ] Task execution logic

**Files:**
```
src/agent_whip/
  workers/
    opencode.py
```

---

## Phase 3: Progress Tracking (Week 3)

### 3.1 State Store
- [ ] Implement JSON state store
- [ ] Implement SQLite state store
- [ ] State persistence logic
- [ ] Checkpoint system
- [ ] Backup/restore functionality

**Files:**
```
src/agent_whip/
  store/
    __init__.py
    base.py
    json_store.py
    sqlite_store.py
```

### 3.2 Progress Tracker (Tukang Cambuk)
- [ ] Implement evaluation logic
- [ ] Next action decision
- [ ] Phase completion detection
- [ ] Retry logic
- [ ] Abort conditions

**Files:**
```
src/agent_whip/
  tracker/
    __init__.py
    evaluator.py
    decision.py
    retry.py
```

### 3.3 Event System
- [ ] Event emitter for state changes
- [ ] Event handlers for logging
- [ ] Progress callbacks

**Files:**
```
src/agent_whip/
  events/
    __init__.py
    emitter.py
    handlers.py
```

---

## Phase 4: QA Integration (Week 4)

### 4.1 QA Engine
- [ ] Playwright integration
- [ ] Test discovery
- [ ] Test execution
- [ ] Result parsing
- [ ] Screenshot capture on failure

**Files:**
```
src/agent_whip/
  qa/
    __init__.py
    engine.py
    playwright_runner.py
    result.py
```

### 4.2 Bug Ticket Creation
- [ ] Implement bug ticket creator
- [ ] GitHub Issues integration
- [ ] Jira integration (optional)

**Files:**
```
src/agent_whip/
  qa/
    tickets.py
    integrations/
      github.py
      jira.py
```

### 4.3 QA Orchestration
- [ ] Run QA after phase
- [ ] Handle QA failures
- [ ] Decide continue/abort on failure

---

## Phase 5: CLI & User Experience (Week 5)

### 5.1 CLI Commands
- [ ] `agent-whip run` - Start execution
- [ ] `agent-whip resume` - Resume execution
- [ ] `agent-whip status` - Show status
- [ ] `agent-whip report` - Generate report
- [ ] `agent-whip validate` - Validate plan

**Files:**
```
src/agent_whip/
  cli/
    __init__.py
    main.py
    commands/
      __init__.py
      run.py
      resume.py
      status.py
      report.py
      validate.py
```

### 5.2 Progress Display
- [ ] Real-time progress bar
- [ ] Task status table
- [ ] Phase completion indicator
- [ ] ETA calculation

**Files:**
```
src/agent_whip/
  ui/
    __init__.py
    progress.py
    display.py
```

### 5.3 Reporting
- [ ] HTML report generation
- [ ] Markdown report
- [ ] JSON report
- [ ] Test coverage report

**Files:**
```
src/agent_whip/
  reporting/
    __init__.py
    generator.py
    templates/
      report.html
      report.md
```

---

## Phase 6: Testing & Refinement (Week 6)

### 6.1 Unit Tests
- [ ] Test coverage > 80%
- [ ] All core components tested
- [ ] Edge cases covered

### 6.2 Integration Tests
- [ ] End-to-end execution test
- [ ] Resume test
- [ ] Error recovery test
- [ ] QA integration test

**Files:**
```
tests/integration/
  test_e2e.py
  test_resume.py
  test_recovery.py
  test_qa.py
```

### 6.3 Example Projects
- [ ] Simple project example
- [ ] Multi-phase project
- [ ] Project with dependencies
- [ ] Project with QA

**Files:**
```
examples/
  simple-project/
    plan.md
  multi-phase/
    plan.md
  with-qa/
    plan.md
    tests/
```

---

## Development Order

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: Foundation                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Setup    │─▶│ Models   │─▶│ Parser   │─▶│ Config   │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: Task Execution                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Queue    │─▶│ Worker   │─▶│ Claude   │─▶│ OpenCode │        │
│  │          │  │ Manager  │  │ Worker   │  │ Worker   │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: Progress Tracking                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ State    │─▶│ Tracker  │─▶│ Events   │─▶│ Retry    │        │
│  │ Store    │  │ (Whip)   │  │          │  │ Logic    │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 4: QA Integration                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ QA       │─▶│ Playwright│─▶│ Tickets  │─▶│ Orchestr  │        │
│  │ Engine   │  │ Runner   │  │ Creator  │  │ ation    │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 5: CLI & UX                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ CLI      │─▶│ Progress │─▶│ Report   │─▶│ Display  │        │
│  │ Commands │  │ Display  │  │ Generator│  │          │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 6: Testing                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Unit     │─▶│ Integrat │─▶│ Examples │─▶│ Docs     │        │
│  │ Tests    │  │ ion Tests│  │          │  │          │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
agent-whip/
├── src/
│   └── agent_whip/
│       ├── __init__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── task.py
│       │   ├── state.py
│       │   └── plan.py
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── markdown_parser.py
│       │   └── validator.py
│       ├── queue/
│       │   ├── __init__.py
│       │   └── task_queue.py
│       ├── workers/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── manager.py
│       │   ├── claude.py
│       │   └── opencode.py
│       ├── tracker/
│       │   ├── __init__.py
│       │   └── evaluator.py
│       ├── store/
│       │   ├── __init__.py
│       │   └── state_store.py
│       ├── qa/
│       │   ├── __init__.py
│       │   └── engine.py
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py
│       └── events/
│           ├── __init__.py
│           └── emitter.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── examples/
│   ├── simple-project/
│   └── with-qa/
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── PLAN_SPEC.md
├── pyproject.toml
├── README.md
└── .agent-whip.yml
```

---

## Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"
anthropic = "^0.18.0"
typer = "^0.12.0"
pydantic = "^2.0.0"
pyyaml = "^6.0"
rich = "^13.0.0"
playwright = "^1.40.0"
aiofiles = "^23.0.0"
httpx = "^0.25.0"

[tool.poetry.dev-dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
black = "^23.0.0"
ruff = "^0.1.0"
mypy = "^1.5.0"
pytest-cov = "^4.1.0"
```

---

## Milestones

| Milestone | Criteria | Target |
|-----------|----------|--------|
| M1: Foundation | Parse plan.md, validate DAG | Week 1 |
| M2: Execution | Execute single task | Week 2 |
| M3: Orchestration | Execute full plan with retry | Week 3 |
| M4: QA | Run tests after phase | Week 4 |
| M5: CLI | Usable command-line interface | Week 5 |
| M6: Production | >80% test coverage, examples | Week 6 |
