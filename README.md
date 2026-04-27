# AgentWhip

**AI Agent Orchestration for Autonomous Development**

AgentWhip is an AI orchestrator that coordinates Claude Code/OpenCode to execute development plans automatically. Think of it as your "tukang cambuk" (whip-cracking overseer) that keeps development tasks moving until completion.

---

## Overview

AgentWhip reads your `plan.md` and orchestrates AI workers to execute tasks, track progress, run QA tests, and continue until all phases are complete—fully autonomous, no human intervention required.

```
plan.md → AgentWhip → Claude Code → Code
              ↑         ↓
              └─────────┘ (progress tracking, QA, retry)
```

---

## Features

- **Dual-Mode Parsing**:
  - **Strict mode**: Fast regex-based markdown parser for standard format
  - **Flexible mode**: AI-powered parser that interprets ANY plan format
  - **Auto-fallback**: Automatically switches to flexible mode if strict parsing fails
- **Claude Settings Integration**: Automatically reads configuration from `~/.claude/settings.json`
- **Provider Support**: Works with Anthropic API, z.ai, and other compatible providers
- **Task Orchestration**: Delegate tasks to Claude Code/OpenCode workers
- **Progress Tracking**: "Tukang Cambuk" evaluates completion and decides next actions
- **Auto-Retry**: Handle failures with configurable retry logic
- **QA Integration**: Run Playwright tests after phase completion
- **State Persistence**: Save execution state and recover accurately after interruption
- **Auto Handover**: When worker reaches 85% token limit, automatically creates summary and delegates to new worker with preserved context
- **Context Document**: Persistent log of all work, decisions, and handovers for full traceability
- **CLI Interface**: Commands for run, validate, status, resume, and report

---

## Quick Start

### Installation

**Via pipx (recommended for global installation):**

```bash
# Install pipx first (if not already installed)
sudo apt install pipx  # Debian/Ubuntu
brew install pipx      # macOS

# Install agent-whip globally
pipx install agent-whip
```

**Via pip:**

```bash
pip install agent-whip
```

**From source:**

```bash
git clone https://github.com/yourusername/agent-whip.git
cd agent-whip
pip install -e .
```

### Create a Plan

```bash
# In your project directory
cat > plan.md << 'EOF'
# Project Plan: My App

## Phases

### Phase 1: Setup

- [ ] SETUP-001 Initialize project
- [ ] SETUP-002 Install dependencies
  - Depends on: SETUP-001

### Phase 2: Development

- [ ] DEV-001 Create main component
  - Depends on: SETUP-002
- [ ] DEV-002 Add styling
  - Depends on: DEV-001

## Success Criteria
- [ ] All tasks complete
- [ ] Tests passing
EOF
```

### Run AgentWhip

```bash
# Start execution
agent-whip run --path .

# Check status
agent-whip status --path .

# Resume if interrupted
agent-whip resume --path .
```

---

## Configuration

### Claude Settings Integration

AgentWhip automatically reads your Claude settings from `~/.claude/settings.json`. If you're using a custom provider like z.ai, it will use the `base_url` from your settings.

Example `~/.claude/settings.json`:
```json
{
  "apiKey": "sk-your-api-key",
  "baseUrl": "https://open.bigmodel.cn/api/paas/v4",
  "model": "claude-opus-4-6"
}
```

### Worker Connection Modes

AgentWhip supports multiple worker connection modes:

| Mode | Description |
|------|-------------|
| `api` (default) | Direct API connection (recommended, most reliable) |
| `auto` | Try CLI first, fallback to API |
| `cli` | CLI tools only (experimental, has limitations) |

**Note:** API mode is recommended for production. CLI mode has limitations:
- Claude CLI: Cannot run from within Claude Code session (nested session block)
- OpenCode CLI: Interactive TUI, not suitable for programmatic use

### Project Configuration

Create `agent-whip.yml` in your project for additional settings:

```yaml
default_worker: claude

claude:
  mode: api  # api | auto | cli (default: api)
  api_key: "${ANTHROPIC_API_KEY}"  # Optional: reads from ~/.claude/settings.json
  base_url: "https://api.anthropic.com"  # Optional: reads from ~/.claude/settings.json
  model: claude-opus-4-6
  max_concurrent: 3

opencode:
  mode: api  # api | auto | cli (default: api)
  api_key: "${OPENCODE_API_KEY}"
  model: default
  max_concurrent: 2

execution:
  max_retries: 3
  retry_delay: 1.0
  task_timeout: 600

qa:
  enabled: true
  run_after_phase: true
  framework: playwright
  test_command: "npm test"
  create_tickets_on_failure: true

state:
  store: json
  path: .agent-whip/state.json
  backup_path: .agent-whip/backup
  checkpoint_interval: 60

handover:
  enabled: true
  token_threshold: 0.85  # Trigger at 85% of token limit

  claude:
    max_tokens_per_session: 200000
    enable_auto_summarize: true

  context_document_enabled: true
  context_document_path: ".agent-whip/context.json"
  max_context_entries: 1000

  max_summary_length: 10000
  include_artifacts: true
  include_decisions: true
```

Current runtime note:
- Orchestrator persists execution state to `.agent-whip/state.json`
- Context and handover history saved to `.agent-whip/context.json`

---

## Plan Format

### Dual-Mode Parsing

AgentWhip supports two parsing modes:

**1. Strict Mode (Default)**
- Fast, regex-based markdown parser
- Requires structured format with phases and task checkboxes
- See [PLAN_SPEC.md](docs/PLAN_SPEC.md) for full specification

**2. Flexible Mode (`--flexible`)**
- AI-powered parser using Claude
- Works with ANY plan format:
  - Free-form todo lists
  - Notion exports
  - GitHub Issues
  - Simple text notes
  - Non-standard markdown
- Use `--flexible` flag or auto-fallback on parse failure

**3. Auto-Fallback**
- If strict mode fails, AgentWhip automatically falls back to flexible mode
- Ensures your plan is always interpretable

### Example: Strict Format

```markdown
# Project Plan: Project Name

## Phases

### Phase 1: Phase Name

- [ ] TASK-001 Task description
- [ ] TASK-002 Another task
  - Depends on: TASK-001

### Phase 2: Another Phase
...
```

### Example: Flexible Format (Any Format!)

```markdown
Things to do for my project:

1. Fix the navigation menu bug
2. Add user authentication
3. Implement password reset
4. Update the homepage design
5. Optimize database queries
```

With `--flexible` mode, AgentWhip will use Claude AI to interpret ANY format and extract tasks, phases, and dependencies automatically.

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `agent-whip run --path <dir> [--mock] [--flexible]` | Start execution. `--flexible` uses AI parser for any format |
| `agent-whip resume --path <dir> [--mock]` | Resume from saved state |
| `agent-whip status --path <dir>` | Show status from saved state |
| `agent-whip report --path <dir>` | Generate report from saved state |
| `agent-whip validate --plan <plan.md> [--flexible]` | Validate plan syntax. `--flexible` for any format |

### Options

| Option | Description |
|--------|-------------|
| `--path, -p` | Path to project directory (default: current) |
| `--mock, -m` | Use mock worker for testing (no API calls) |
| `--flexible, -F` | Use AI-powered flexible parser for any plan format |
| `--plan` | Path to plan file (for validate command) |

---

## Runtime Flow (Updated 2026-04-23)

```text
run:
1) Parse plan.md (strict parser, or --flexible for AI parsing)
2) On parse failure, auto-fallback to flexible mode
3) Build queue from plan
4) Execute ready task
5) Evaluate result: continue / retry / skip / abort
6) Run QA when phase complete
7) Save checkpoints + final state to .agent-whip/state.json

status/resume/report:
1) Load saved state + saved plan from .agent-whip/state.json
2) Load context from .agent-whip/context.json
3) Rebuild queue based on stored task statuses
4) Show status / continue execution / render report
```

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  plan.md    │────▶│ Orkestrator  │────▶│ AI Workers  │
│  (Input)    │     │  (AgentWhip) │     │ (API/CLI)   │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ WorkerManager│
                    │ - Claude     │
                    │ - OpenCode   │
                    └──────────────┘
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

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

---

## Documentation

- [PRD](docs/PRD.md) - Product Requirements Document
- [ARCHITECTURE](docs/ARCHITECTURE.md) - System Architecture
- [IMPLEMENTATION_PLAN](docs/IMPLEMENTATION_PLAN.md) - Development Plan
- [PLAN_SPEC](docs/PLAN_SPEC.md) - Plan File Specification
- [FLOW_TERBARU](docs/FLOW_TERBARU.md) - Runtime flow terbaru (run/status/resume/report)
- [CLI_VS_API](docs/CLI_VS_API.md) - Worker connection modes comparison

---

## Development

```bash
# Clone repository
git clone https://github.com/yourusername/agent-whip.git
cd agent-whip

# Install in editable mode for development
pip install -e .

# Or install globally with pipx
pipx install --editable .

# Run tests
pytest

# Run with coverage
pytest --cov=agent_whip
```

---

## Status

🚧 **Under Active Development**

This is currently in planning/development phase. See [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for progress.

---

## License

MIT

---

## Contributing

Contributions welcome! Please read our contributing guidelines before submitting PRs.
