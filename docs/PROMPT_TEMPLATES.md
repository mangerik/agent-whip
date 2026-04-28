# AgentWhip - Prompt Templates untuk User

**Version:** 1.0
**Date:** 2026-04-28

---

## Overview

Dokumen ini berisi **prompt-template** yang bisa kamu gunakan dengan AI apapun (Claude, ChatGPT, Gemini, dll) untuk menghasilkan dokumen-dokumen yang dibutuhkan AgentWhip:

1. **PRD (Product Requirements Document)** - Fondasi proyek
2. **plan.md (Strict Mode)** - Format terstruktur dengan phases & dependencies
3. **plan.md (Flexible Mode)** - Format bebas, AI-powered
4. **agent-whip.yml** - Konfigurasi opsional

---

## Cara Pakai

1. Copy prompt sesuai kebutuhan
2. Paste ke AI pilihanmu (Claude, ChatGPT, dll)
3. Isi variabel dalam kurung siku `[...]` dengan detail proyekmu
4. Simpan output di folder proyekmu
5. Jalankan `agent-whip run --path .`

---

## Template 1: Membuat PRD

**Gunakan prompt ini untuk membuat PRD yang komprehensif.**

```
Act as a Senior Product Manager. Create a comprehensive Product Requirements Document (PRD) for the following project:

## Project Context
- Project Name: [NAMA PROYEK]
- Description: [DESKRIPSI SINGKAT]
- Target Users: [PENGGUNA UTAMA]
- Timeline: [TARGET WAKTU, e.g., 4 weeks]

## Requirements
Create a PRD with the following sections:

1. **Executive Summary**
   - Problem statement
   - Proposed solution
   - Key objectives

2. **User Personas**
   - Primary users with pain points
   - Secondary users
   - User journey overview

3. **Functional Requirements**
   - Core features (must-have)
   - Secondary features (nice-to-have)
   - Future features (out of scope)

4. **Technical Requirements**
   - Tech stack preferences: [TECH STACK, e.g., React + Node.js, Python + FastAPI]
   - Database: [DATABASE, e.g., PostgreSQL, MongoDB]
   - Hosting: [HOSTING, e.g., Vercel, AWS]
   - External APIs: [APIs if any]

5. **Non-Functional Requirements**
   - Performance targets
   - Security requirements
   - Scalability considerations

6. **Success Metrics**
   - Key performance indicators (KPIs)
   - Definition of done

7. **Risks & Mitigation**
   - Technical risks
   - Timeline risks
   - Resource risks

Format the output in Markdown with clear headers and bullet points.
```

---

## Template 2: Membuat plan.md (Strict Mode)

**Gunakan prompt ini untuk membuat plan.md dengan format terstruktur yang sesuai PLAN_SPEC.md AgentWhip.**

```
Act as a Senior Technical Project Manager. Create a plan.md file for AgentWhip orchestration based on this project:

## Project Information
- Project Name: [NAMA PROYEK]
- Description: [DESKRIPSI PROYEK]
- Tech Stack: [TECH STACK]
- Total Timeline: [ESTIMASI WAKTU]

## Output Requirements
Create a Markdown file named plan.md with the EXACT following structure:

```markdown
# Project Plan: [Project Name]

## Overview
[2-3 sentences describing the project]

## Goals
- [Goal 1: SMART goal]
- [Goal 2: SMART goal]
- [Goal 3: SMART goal]

## Phases

### Phase 1: [Phase Name]
[Optional: Brief description of this phase]

- [ ] [PHASE]-001 [Task description]
  - Optional: Additional context or technical details
  - Depends on: [Previous task ID if applicable]

- [ ] [PHASE]-002 [Task description]

### Phase 2: [Phase Name]
- [ ] [PHASE]-001 [Task description]
  - Depends on: [Previous phase task ID]

## Success Criteria
- [ ] All features implemented and tested
- [ ] [Specific acceptance criterion]
- [ ] [Another acceptance criterion]

## Notes
[Any additional notes for the AI workers]
```

## Guidelines

1. **Phase Creation**: Break down the project into 3-6 logical phases:
   - Phase 1: Setup & Infrastructure (git, dependencies, config)
   - Phase 2: Core Backend/API (if applicable)
   - Phase 3: Core Frontend/UI (if applicable)
   - Phase 4: Testing & QA
   - Phase 5: Deployment & Documentation

2. **Task Creation**:
   - Each task should be completable in 1-3 hours
   - Use clear, action-oriented descriptions
   - Include technical context when needed
   - Add dependencies using "Depends on:" format

3. **Task ID Format**:
   - Use prefix like: SETUP, DB, API, FE, TEST, DEPLOY
   - Example: SETUP-001, API-001, FE-001, TEST-001

4. **Dependencies**:
   - Only add dependencies when truly necessary
   - Reference tasks from earlier phases or earlier in same phase
   - No circular dependencies allowed

5. **Estimated Task Count**: 10-30 tasks total depending on project complexity

Please generate the complete plan.md file now.
```

---

## Template 3: Membuat plan.md (Flexible Mode)

**Gunakan prompt ini untuk membuat plan dalam format apa saja - AgentWhip akan memahaminya dengan flexible mode.**

```
I need to create a project plan for AgentWhip. AgentWhip supports "flexible mode" which can understand ANY plan format.

## Project: [NAMA PROYEK]

Description: [DESKRIPSI PROYEK - be as detailed as possible]

Tech Stack: [TECH STACK YANG DIINGINKAN]

Please create a comprehensive todo list / task list for this project. Format it in ANY way you think is best - it could be:
- A simple numbered list
- A bullet list with categories
- A markdown checklist
- Any other format you prefer

Just make sure to include ALL necessary tasks to complete this project from zero to deployment.

Break down tasks into logical categories (setup, development, testing, deployment).
Include dependencies where one task must finish before another starts.
```

---

## Template 4: Quick Plan (Untuk Proyek Sederhana)

**Gunakan untuk proyek kecil/sederhana.**

```
Create a simple project plan for AgentWhip.

Project: [NAMA PROYEK]
Description: [DESKRIPSI SINGKAT]

Create a task list following this simple format:

1. [ ] Initialize project with [tech stack]
2. [ ] Setup basic configuration
3. [ ] Build core feature: [fitur utama]
4. [ ] Build core feature: [fitur utama 2]
5. [ ] Add styling
6. [ ] Write tests
7. [ ] Deploy to [platform]

Add more specific tasks based on my project description above.
Each task should be specific and actionable.
```

---

## Template 5: Membuat agent-whip.yml

**Prompt untuk membuat konfigurasi opsional.**

```
Create an agent-whip.yml configuration file for AgentWhip with the following specifications:

## Project Context
- Project: [NAMA PROYEK]
- AI Worker: [claude | opencode]
- API Provider: [anthropic | z.ai | openai | custom]

## Requirements
Create a YAML file with these sections:

1. Project metadata
2. Worker configuration (Claude or OpenCode)
3. Execution settings (retries, timeouts)
4. QA settings (enabled/disabled, test framework)
5. State management settings
6. Handover settings (if applicable)

Use this template and fill in appropriate values:

```yaml
# agent-whip.yml
project:
  name: "[PROJECT_NAME]"

default_worker: claude

claude:
  mode: api  # api | auto | cli
  model: claude-opus-4-6
  max_concurrent: 3
  timeout: 600

execution:
  max_retries: 3
  retry_delay: 2.0
  task_timeout: 300
  continue_on_error: false

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

Adjust values based on my project context above.
```

---

## Template 6: Refine Existing Plan

**Gunakan untuk memperbaiki plan yang sudah ada.**

```
I have an existing plan.md for AgentWhip. Please review and refine it.

## Current Plan
[PASTE YOUR CURRENT PLAN HERE]

## Review Criteria
Please analyze and improve:
1. Task granularity - are tasks too big or too small?
2. Dependencies - are dependencies correct? Any missing?
3. Phase organization - are phases logical?
4. Completeness - are any critical tasks missing?
5. Clarity - are task descriptions clear for AI workers?

Output the refined plan.md with improvements.
```

---

## Workflow: Dari Ide ke Eksekusi

Berikut alur kerja recommended untuk memaksimalkan AgentWhip:

```
┌─────────────────┐
│  1. IDE AWAL    │  Kamu punya ide proyek
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. BUAT PRD    │  Gunakan Template 1 → PRD.md
│  (AI apa saja)  │  Mendefinisikan requirement jelas
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. BUAT PLAN   │  Gunakan Template 2 → plan.md
│  (AI apa saja)  │  Breakdown jadi tasks + dependencies
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. VALIDATE    │  agent-whip validate --plan plan.md
│  (AgentWhip)    │  Cek format & dependency validity
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  5. RUN!        │  agent-whip run --path .
│  (AgentWhip)    │  AI workers eksekusi otomatis
└─────────────────┘
```

---

## Tips untuk Hasil Maksimal

### 1. Prompt Engineering untuk plan.md

**Lebih Spesifik = Lebih Baik**
```
❌ "Create authentication"
✅ "Implement JWT authentication with login/register endpoints,
   including password hashing with bcrypt, token refresh mechanism,
   and middleware for protected routes"
```

**Tambahkan Tech Stack di Prompt**
```
Include specific tech details:
- React with Vite for frontend
- Tailwind CSS for styling
- Node.js + Express for backend
- PostgreSQL with Prisma ORM
```

**Definisikan Acceptance Criteria**
```
For each task, specify what "done" looks like:
- TEST-001 Write unit tests
  - Cover all API endpoints
  - Minimum 80% code coverage
  - All tests passing
```

### 2. Timing & Dependencies

**Serial vs Parallel Tasks**
```
❌ Semua tasks depends on task sebelumnya (slow)
✅ Hanya add dependencies jika truly necessary (fast)
```

**Phase Organization**
```
Phase 1: Setup (git, deps, config)
Phase 2: Backend/Database (schema, migrations, API)
Phase 3: Frontend (components, pages, state)
Phase 4: Integration (connect FE + BE)
Phase 5: Testing (unit, E2E)
Phase 6: Deploy (CI/CD, hosting)
```

### 3. Testing di AgentWhip

**Test dulu dengan --mock**
```bash
agent-whip run --path . --mock
```
Tidak memakan API quota, untuk cek apakah plan valid.

**Validate sebelum run**
```bash
agent-whip validate --plan plan.md
```
Pastikan tidak ada dependency cycle atau error.

---

## Contoh: End-to-End Flow

### Step 1: Buat PRD (dengan ChatGPT/Claude/Gemini)

```
[Copy Template 1, isi variabel, paste ke AI]

Output: PRD.md
```

### Step 2: Buat plan.md (dengan AI apapun)

```
[Copy Template 2, isi variabel dari PRD.md, paste ke AI]

Output: plan.md
```

### Step 3: Setup proyek

```bash
mkdir my-project
cd my-project
# Copy PRD.md and plan.md here
```

### Step 4: Validate

```bash
agent-whip validate --plan plan.md
```

### Step 5: Run (mock dulu untuk test)

```bash
agent-whip run --path . --mock
```

### Step 6: Run production

```bash
agent-whip run --path .
```

---

## Troubleshooting Prompt Outputs

### Problem: AI generates wrong format

**Fix:** Be more explicit in your prompt:
```
IMPORTANT: Follow the EXACT structure below. Do not deviate.
The file must start with "# Project Plan:" followed by project name.
Phases must use "### Phase N:" format.
Tasks must use "- [ ]" checkbox format.
```

### Problem: Tasks are too vague

**Fix:** Add this to your prompt:
```
For each task:
- Use action verbs (Create, Implement, Add, Setup)
- Be specific about what needs to be done
- Include technical details when relevant
- Keep tasks granular (1-3 hours per task)
```

### Problem: Too many or too few tasks

**Fix:** Add this constraint:
```
Target 15-25 tasks total across all phases.
Each phase should have 3-6 tasks.
```

---

## Quick Reference: Command AgentWhip

| Command | Description |
|---------|-------------|
| `agent-whip run --path .` | Run with strict parser (default) |
| `agent-whip run --path . --flexible` | Run with AI flexible parser |
| `agent-whip run --path . --mock` | Test run without API calls |
| `agent-whip validate --plan plan.md` | Validate plan format |
| `agent-whip status --path .` | Check execution progress |
| `agent-whip resume --path .` | Resume interrupted execution |
| `agent-whip report --path .` | Generate execution report |

---

## Appendix: Plan Examples

### Example 1: Simple Web App (Strict Format)

```markdown
# Project Plan: Portfolio Website

## Overview
Build a personal portfolio website with project showcase and contact form.

## Goals
- Display projects with images and descriptions
- Contact form with email notification
- Responsive design for mobile
- Deploy to Vercel

## Phases

### Phase 1: Project Setup

- [ ] SETUP-001 Initialize git repository
  - Create .gitignore for Node.js

- [ ] SETUP-002 Setup Next.js project
  - Use TypeScript
  - Install Tailwind CSS
  - Depends on: SETUP-001

- [ ] SETUP-003 Setup project structure
  - Create /components folder
  - Create /pages folder
  - Depends on: SETUP-002

### Phase 2: Core Components

- [ ] FE-001 Create Layout component
  - Header with navigation
  - Footer with social links
  - Depends on: SETUP-003

- [ ] FE-002 Create Hero section
  - Name and title
  - Call-to-action button
  - Depends on: SETUP-003

- [ ] FE-003 Create Projects section
  - Grid layout for project cards
  - Project card component with image, title, description
  - Depends on: FE-001

### Phase 3: Contact Form

- [ ] FE-004 Create contact form UI
  - Name, email, message fields
  - Form validation
  - Depends on: FE-001

- [ ] API-001 Create contact API endpoint
  - POST /api/contact
  - Send email using Resend
  - Depends on: SETUP-002

- [ ] FE-005 Connect form to API
  - Handle form submission
  - Show success/error messages
  - Depends on: FE-004, API-001

### Phase 4: Styling & Polish

- [ ] STYLE-001 Apply responsive design
  - Mobile-first approach
  - Breakpoints for tablet/desktop
  - Depends on: FE-003

- [ ] STYLE-002 Add animations
  - Fade-in effects on scroll
  - Hover effects on cards
  - Depends on: STYLE-001

### Phase 5: Testing & Deploy

- [ ] TEST-001 Test all functionality
  - Form submission
  - Responsive breakpoints
  - Cross-browser testing
  - Depends on: STYLE-002

- [ ] DEPLOY-001 Deploy to Vercel
  - Connect GitHub repository
  - Configure environment variables
  - Depends on: TEST-001

## Success Criteria
- [ ] All sections rendering correctly
- [ ] Contact form working end-to-end
- [ ] Mobile responsive
- [ ] Deployed and accessible via Vercel URL
```

### Example 2: Same Project (Flexible Format)

```markdown
My Portfolio Website - TODO List

Project: Build a personal portfolio website with Next.js

Tech Stack: Next.js 14, TypeScript, Tailwind CSS, Vercel, Resend (email)

Tasks:

1. Setup Phase
   - Initialize git repo with proper .gitignore
   - Create Next.js project with TypeScript and Tailwind
   - Set up folder structure (components, pages, styles)

2. Build Components
   - Make Layout component with header/footer
   - Create Hero section with name and CTA
   - Build Projects grid with card components
   - Each card shows: image, title, description, links

3. Contact Form
   - Design contact form UI (name, email, message)
   - Add client-side validation
   - Create /api/contact endpoint
   - Integrate Resend for email sending
   - Connect form to API with loading/error states

4. Styling
   - Make it mobile-responsive
   - Add smooth animations
   - Ensure good contrast and accessibility

5. Launch
   - Test everything locally
   - Deploy to Vercel
   - Verify contact form works in production
```

Both examples work! Use strict for consistency, flexible for speed.
```
