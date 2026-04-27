# AgentWhip - Product Requirement Document

**Version:** 1.1
**Date:** 2026-04-23
**Status:** In Progress

---

## 1. Executive Summary

AgentWhip adalah sistem AI Agent Orchestration yang bertugas mengoordinasikan Claude Code/OpenCode untuk mengeksekusi development plan secara otomatis. Sistem ini bertindak sebagai "tukang cambuk" yang memastikan setiap task dalam plan.md dieksekusi sampai selesai.

## 2. Problem Statement

Developer sering menghabiskan waktu untuk:
- Manually delegasi task ke AI coding assistant
- Memantau progress dan memutuskan next step
- Menjalankan test dan verifikasi hasil
- Mengkoordinasi antara development dan QA

**Goal:** Otomatisasi seluruh lifecycle development dari plan hingga deployment.

## 3. Solution Overview

AgentWhip adalah orchestrator agent yang:
1. Membaca `plan.md` dari project
2. Mendelegasikan task ke Claude Code/OpenCode
3. Memantau progress dan memutuskan next action
4. Menjalankan QA dengan Playwright
5. Menyimpan checkpoint/final state ke `.agent-whip/state.json`
6. Berhenti ketika semua phase selesai

Command `status`, `resume`, dan `report` membaca state yang sama dari `.agent-whip/state.json` agar konsisten dengan eksekusi terakhir.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  plan.md    │────▶│ Orkestrator  │────▶│ Claude Code │
│  (Input)    │     │  (AgentWhip) │     │  (Worker)   │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Tukang Cambuk│
                    │  (Evaluator) │
                    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  QA Agent    │
                    │ (Playwright) │
                    └──────────────┘
```

## 4. Core Features

### 4.1 Plan Parser
- Parse `plan.md` dalam format markdown
- Extract phases, tasks, dependencies
- Build execution graph

### 4.2 Task Delegator
- Delegasi task ke Claude Code API
- Track task status (pending, in_progress, completed, failed)
- Handle retry logic

### 4.3 Progress Evaluator (Tukang Cambuk)
- Evaluate task completion
- Decide next action (continue, retry, skip)
- Track overall progress

### 4.4 QA Orchestrator
- Run Playwright test suite
- Evaluate test results
- Create bug tickets jika gagal

### 4.5 State Management
- Persist progress state
- Support resume after interruption
- Rollback capability

## 5. User Stories

### US1: Plan Execution
**As a** developer
**I want to** menjalankan AgentWhip dengan plan.md
**So that** seluruh development task dieksekusi otomatis

### US2: Progress Tracking
**As a** developer
**I want to** melihat progress real-time
**So that** saya tahu status proyek

### US3: Error Recovery
**As a** developer
**I want to** AgentWhip handle error otomatis
**So that** proses tidak stuck

### US4: QA Automation
**As a** developer
**I want to** test otomatis setelah phase selesai
**So that** kualitas terjaga

## 6. Non-Functional Requirements

### 6.1 Performance
- Task delegation: < 5 seconds
- Progress check interval: 10 seconds
- Full plan execution: sesuai complexity

### 6.2 Reliability
- Auto-retry untuk failed task (max 3x)
- State persistence setiap action
- Graceful shutdown

### 6.3 Extensibility
- Plugin architecture untuk custom worker
- Support multiple AI providers (Claude, OpenCode)
- Custom QA tools

## 7. Technical Stack

| Component | Technology |
|-----------|------------|
| Core | Python 3.11+ |
| AI Provider | Anthropic Claude API, OpenCode API |
| State Store | JSON/SQLite |
| QA | Playwright |
| CLI | Typer/Click |
| Logging | Structlog |

## 8. Success Metrics

- [ ] Plan dapat dieksekusi end-to-end tanpa human intervention
- [ ] 95% task completion rate untuk valid plan
- [ ] < 1% false positive completion (task marked done tapi belum)
- [ ] Support resume after interruption

## 9. Open Questions

| Question | Priority | Owner |
|----------|----------|-------|
| Claude Code API availability? | High | - |
| OpenCode API documentation? | High | - |
| Cost per execution? | Medium | - |
| Multi-project support? | Low | - |

## 10. Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1 | 1 week | Core orchestrator + plan parser |
| Phase 2 | 1 week | Claude Code integration |
| Phase 3 | 1 week | Tukang Cambuk + state management |
| Phase 4 | 1 week | QA Agent integration |
| Phase 5 | 1 week | Testing + refinement |
