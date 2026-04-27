# Cara Pakai AgentWhip

**Update terbaru:** 2026-04-23

Lihat juga: [FLOW_TERBARU.md](FLOW_TERBARU.md) untuk ringkasan flow runtime paling baru.

Panduan lengkap menggunakan AgentWhip di proyek nyata.

---

## Persiapan

### 1. Install AgentWhip

**Via pipx (recommended untuk global installation):**

```bash
# Install pipx dulu (kalau belum)
sudo apt install pipx  # Debian/Ubuntu
brew install pipx      # macOS

# Install agent-whip secara global
pipx install agent-whip
```

**Via pip:**

```bash
pip install agent-whip
```

**Dari source:**

```bash
cd /path/to/agent-whip
pip install -e .
```

### 2. Setup API Key (Untuk Claude)

**Opsional** - AgentWhip otomatis baca dari `~/.claude/settings.json`

Kalau mau setup manual:

```bash
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
```

Atau simpan di `.env`:

```bash
echo "ANTHROPIC_API_KEY=sk-ant-xxxxx" > .env
```

**Menggunakan Provider Lain (z.ai, dll):**

AgentWhip otomatis deteksi dari `~/.claude/settings.json`:

```json
{
  "apiKey": "your-api-key",
  "baseUrl": "https://open.bigmodel.cn/api/paas/v4",
  "model": "claude-opus-4-6"
}
```

Tidak perlu konfigurasi tambahan!

---

## Contoh Proyek: Todo App

Misal proyekmu di `~/projects/my-todo-app`

### Langkah 1: Buat `plan.md`

```bash
cd ~/projects/my-todo-app
```

Buat file `plan.md`:

```markdown
# Project Plan: My Todo App

## Overview
Build a simple todo application with React + Node.js

## Goals
- User can add todos
- User can mark todos as complete
- Data persists in localStorage

## Phases

### Phase 1: Project Setup

- [ ] SETUP-001 Initialize Git repository
- [ ] SETUP-002 Create package.json
  - Depends on: SETUP-001
- [ ] SETUP-003 Setup React with Vite
  - Depends on: SETUP-002

### Phase 2: Core Features

- [ ] CORE-001 Create Todo component
  - Depends on: SETUP-003
- [ ] CORE-002 Implement add todo
  - Depends on: CORE-001
- [ ] CORE-003 Implement toggle complete
  - Depends on: CORE-001
- [ ] CORE-004 Implement delete todo
  - Depends on: CORE-001

### Phase 3: Styling

- [ ] STYLE-001 Add Tailwind CSS
  - Depends on: CORE-004
- [ ] STYLE-002 Create responsive layout
  - Depends on: STYLE-001

### Phase 4: Testing

- [ ] TEST-001 Write unit tests
  - Depends on: STYLE-002
- [ ] TEST-002 Setup Playwright
  - Depends on: TEST-001
- [ ] TEST-003 Write E2E tests
  - Depends on: TEST-002

## Success Criteria
- [ ] All features working
- [ ] Tests passing
- [ ] Deployed to Vercel
```

### Langkah 2: Validasi Plan

```bash
agent-whip validate --plan plan.md
```

Output:

```
AgentWhip v0.1.0 - Plan Validator

✓ Plan structure valid
  Phases: 4
  Tasks: 11
✓ Dependency graph valid (no cycles)
✓ All task IDs unique

Plan is ready to execute!
```

### Langkah 3: Jalankan (Mock Mode untuk Test)

```bash
agent-whip run --path . --mock
```

Output:

```
AgentWhip v0.1.0

Validating plan...
  ✓ Project: My Todo App
  ✓ Phases: 4
  ✓ Tasks: 11

┌─────────────────────────────────┐
│         Plan Summary            │
├─────────────────────────────────┤
│ Phase                    Tasks   │
├─────────────────────────────────┤
│ Phase 1: Project Setup      3       │
│ Phase 2: Core Features       4       │
│ Phase 3: Styling            2       │
│ Phase 4: Testing            2       │
└─────────────────────────────────┘

Initializing AgentWhip...
  ✓ Workers: mock-claude

Starting execution...

🚀 Execution started: My Todo App
⏳ [SETUP-001] Initialize Git repository...
✅ [SETUP-001] completed in 0.1s

⏳ [SETUP-002] Create package.json...
✅ [SETUP-002] completed in 0.1s

... (lanjut sampai selesai)

✅ Execution completed!
   Total: 11
   Completed: 11
   Failed: 0
```

### Langkah 4: Jalankan dengan Claude API (Production)

```bash
# Set API key
export ANTHROPIC_API_KEY="sk-ant-xxxxx"

# Run (tanpa --mock)
agent-whip run --path .
```

Claude akan:
1. Baca task
2. Eksekusi (tulis code, run command, dll)
3. Report hasil
4. Lanjut ke task berikutnya

---

## Flexible Mode - Format Plan Apapun!

### Apa itu Flexible Mode?

Flexible mode menggunakan AI untuk membaca format plan apapun - tidak perlu format markdown yang rigid.

### Contoh Format Sederhana

Buat file `plan-simple.md`:

```markdown
Todo List untuk Project Jatelindo:

1. Fix the navigation menu bug
2. Add user authentication
3. Implement password reset
4. Update the homepage design
5. Optimize database queries
```

Jalankan dengan flexible mode:

```bash
agent-whip run --path . --flexible
```

AgentWhip akan:
1. Gunakan Claude AI untuk interpretasi plan
2. Extract tasks, phases, dan dependencies secara otomatis
3. Jalankan eksekusi seperti biasa

### Format yang Didukung

Flexible mode bisa handle:
- ✅ Todo list sederhana
- ✅ Notion exports
- ✅ GitHub Issues
- ✅ Text notes
- ✅ Markdown non-standar
- ✅ Format apapun yang bisa dibaca manusia!

### Auto-Fallback

Kalau strict mode gagal parse plan, AgentWhip otomatis fallback ke flexible mode:

```bash
agent-whip run --path .  # Auto-fallback kalau perlu
```

---

## Folder Structure Setelah Eksekusi

```
my-todo-app/
├── plan.md                  ← Plan file
├── src/                     ← Generated by Claude
│   ├── components/
│   │   └── Todo.jsx
│   ├── App.jsx
│   └── main.jsx
├── package.json             ← Generated
├── vite.config.js           ← Generated
├── .agent-whip/             ← AgentWhip data
│   ├── state.json           ← Execution state
│   ├── backup/              ← State backups
│   ├── tickets/             ← Bug tickets (if any)
│   └── reports/             ← QA reports
└── .env                     ← API keys
```

---

## Commands Lengkap

### `agent-whip run`

Jalankan eksekusi dari awal.

```bash
# Opsi:
--path, -p      Path ke proyek (default: current dir)
--mock, -m      Gunakan mock worker (tanpa API)
--flexible, -F  Parsing fleksibel (AI-powered) untuk format plan apapun
```

Contoh:
```bash
agent-whip run --path .                     # Current dir, strict parser
agent-whip run --path ~/projects/todo      # Proyek lain
agent-whip run --path . --mock              # Mode test
agent-whip run --path . --flexible          # Flexible parser (format apapun!)
```

**Auto-Fallback:**
Kalau strict parser gagal, AgentWhip otomatis gunakan flexible parser.

### `agent-whip resume`

Lanjutkan eksekusi yang terinterrupt.

```bash
agent-whip resume --path .
```

Kapan dipakai:
- Program crash/stop
- Tekan Ctrl+C
- System restart

### `agent-whip status`

Cek progress eksekusi.

```bash
agent-whip status --path .
```

Output:
```
┌─────────────────────────────┐
│      Execution Status        │
├─────────────────────────────┤
│ Field         Value          │
├─────────────────────────────┤
│ Status        running        │
│ Project       My Todo App    │
│ Current Phase Phase 2        │
│ Current Task  CORE-002       │
│ Progress      45.5%          │
│ Completed     5/11           │
│ Failed        0              │
└─────────────────────────────┘
```

### `agent-whip validate`

Validasi plan.md tanpa jalanin.

```bash
agent-whip validate --plan plan.md
agent-whip validate --plan plan.md --flexible
```

### `agent-whip report`

Generate laporan eksekusi.

```bash
agent-whip report --path .
```

---

## Flow Baru (2026-04-23)

### Saat `run`
1. Parse `plan.md` (strict, atau `--flexible` jika diminta).
2. **Auto-fallback**: Kalau strict gagal, otomatis coba flexible mode.
3. Bangun task queue berdasarkan dependency.
4. Eksekusi task siap jalan.
5. Evaluasi hasil: lanjut, retry, skip, atau abort.
6. Jalankan QA saat phase selesai.
7. Simpan checkpoint dan final state ke `.agent-whip/state.json`.

### Saat `status`, `resume`, dan `report`
1. Load state tersimpan dari `.agent-whip/state.json`.
2. Rebuild queue berdasarkan status task tersimpan (completed/failed/skipped/pending).
3. Tampilkan status, lanjutkan eksekusi, atau buat report dari state yang sama.

---

## Contoh Config (`agent-whip.yml`)

**Opsional** - AgentWhip otomatis baca dari `~/.claude/settings.json`

Kalau perlu override, buat file di root proyek:

```yaml
# agent-whip.yml
project:
  name: "My Todo App"

default_worker: claude

claude:
  api_key: "${ANTHROPIC_API_KEY}"  # Opsional: dibaca dari ~/.claude/settings.json
  base_url: "https://api.anthropic.com"  # Opsional: dibaca dari ~/.claude/settings.json
  model: claude-opus-4-6
  max_concurrent: 3
  timeout: 600

opencode:
  api_key: "${OPENCODE_API_KEY}"
  model: default
  max_concurrent: 2
  timeout: 600

execution:
  max_retries: 3
  retry_delay: 2.0
  task_timeout: 300
  continue_on_error: false  # Stop kalau ada error

qa:
  enabled: true
  run_after_phase: true
  framework: playwright
  test_command: "npm test"
  create_tickets_on_failure: true

state:
  store: json
  path: ".agent-whip/state.json"
  backup_path: ".agent-whip/backup/"
  checkpoint_interval: 60

logging:
  level: INFO
  file: ".agent-whip/agent-whip.log"
```

---

## Troubleshooting

### Plan tidak ditemukan

```bash
[red]✗ Plan file not found: plan.md
```

**Solusi:** Pastikan `plan.md` ada di root proyek.

### API Key tidak set

```bash
[red]✗ No worker available
```

**Solusi:**
```bash
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
```

### Dependency cycle

```bash
[red]✗ Dependency errors:
  Circular dependency detected: TASK-A -> TASK-B -> TASK-A
```

**Solusi:** Fix dependency di plan.md

### Resume tidak bekerja

```bash
[yellow]No execution state found.
```

**Solusi:** Jalankan `agent-whip run` dulu untuk membuat state.

---

## Tips

1. **Mulai dengan `--mock`** untuk test plan
2. **Pecah phase kecil** untuk task kompleks
3. **Gunakan `depends on`** untuk urutan yang penting
4. **Cek status** periodic untuk monitoring
5. **Review plan.md** sebelum run production
6. **Flexible mode** untuk format plan non-standar atau cepat
7. **Auto-fallback** - biarkan AgentWhip pilih parser yang tepat
