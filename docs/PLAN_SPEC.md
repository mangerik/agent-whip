# AgentWhip - Plan Specification

**Version:** 1.1
**Date:** 2026-04-23

---

## Overview

This document defines the specification for `plan.md` files that AgentWhip uses to orchestrate development tasks.

---

## File Format

`plan.md` is a **Markdown** file with structured sections. AgentWhip parses this file to extract phases, tasks, and dependencies.

### Parsing Modes

AgentWhip supports three parsing approaches:

1. **Strict mode (default):** Fast regex-based markdown parser with the format defined in this document.
2. **Flexible mode (`--flexible`):** AI-powered parser that interprets ANY plan format.
3. **Automatic fallback:** When strict mode fails, AgentWhip automatically falls back to flexible parsing.

### When to Use Each Mode

| Mode | Best For | Speed |
|------|----------|-------|
| **Strict** | Standard markdown plans with phases | ⚡ Fast |
| **Flexible** | Free-form lists, Notion exports, any format | 🐌 Slower (AI) |
| **Auto-Fallback** | When you're unsure about format | ⚡→🐌 Adapts |

### Flexible Mode Examples

Flexible mode can handle ANY format:

**Simple todo list:**
```markdown
Things to do:
1. Fix the navigation menu bug
2. Add user authentication
3. Implement password reset
```

**Notion-style export:**
```markdown
## Project Tasks
- [ ] Setup database
- [ ] Create API endpoints
- [ ] Build frontend UI
```

**Free-form text:**
```
We need to:
- setup the project
- add auth
- build the dashboard
```

All of these will work with `--flexible` flag!

---

## Structure Template

```markdown
# Project Plan: [Project Name]

## Overview
[Brief description of the project]

## Goals
- [Goal 1]
- [Goal 2]

## Phases

### Phase 1: [Phase Name]
[Optional phase description]

- [ ] [Task ID] Task description
  - Optional: Additional context
  - Depends on: [Task ID]

- [ ] [Task ID] Task description

### Phase 2: [Phase Name]
...

## Dependencies
- External dependencies if any

## Success Criteria
- [ ] Criteria 1
- [ ] Criteria 2

## Notes
[Any additional notes]
```

---

## Section Specifications

### 1. Project Title

**Format:** `# Project Plan: {name}`

**Example:**
```markdown
# Project Plan: E-Commerce Website
```

**Rules:**
- Must be the first H1 heading
- Project name is extracted after "Project Plan:"
- Only one project title per file

### 2. Overview (Optional)

**Format:** Free text under `## Overview`

**Example:**
```markdown
## Overview
Build a modern e-commerce platform with React and Node.js.
```

### 3. Goals (Optional)

**Format:** Bullet list under `## Goals`

**Example:**
```markdown
## Goals
- Launch within 4 weeks
- Support 1000 concurrent users
- 99.9% uptime
```

### 4. Phases

**Format:** H3 headings `### Phase {N}: {Name}`

**Example:**
```markdown
### Phase 1: Setup
### Phase 2: Backend
### Phase 3: Frontend
```

**Rules:**
- Must start with "Phase" followed by number
- Phase numbers must be sequential
- At least one phase required

### 5. Tasks

**Format:** Checklists under phases

**Syntax:**
```markdown
- [ ] TASK-001 Task description here
- [ ] TASK-002 Another task
  - Depends on: TASK-001
```

**Components:**
- `- [ ]` indicates pending task
- Task ID (optional, auto-generated if missing)
- Task description (required)
- `Depends on:` (optional)

**Task ID Format:**
- Alphanumeric with hyphens/underscores
- Examples: `TASK-001`, `setup-db`, `create_auth_model`

**Dependency Syntax:**
```markdown
- [ ] TASK-003 This task depends on others
  - Depends on: TASK-001, TASK-002
```

**Rules:**
- Multiple dependencies separated by comma
- Circular dependencies will cause error
- Non-existent dependency will cause error

### 6. Task Context (Optional)

**Format:** Indented lines under task

**Example:**
```markdown
- [ ] TASK-001 Setup database
  - Use PostgreSQL 14
  - Run migrations after setup
  - Depends on: TASK-000
```

### 7. Dependencies Section (Optional)

**Format:** List under `## Dependencies`

**Example:**
```markdown
## Dependencies
- PostgreSQL 14+
- Node.js 18+
- Redis for caching
```

### 8. Success Criteria (Optional)

**Format:** Checklist under `## Success Criteria`

**Example:**
```markdown
## Success Criteria
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Deployed to staging
```

---

## Complete Example

```markdown
# Project Plan: Blog Platform

## Overview
Build a simple blog platform with user authentication and post management.

## Goals
- Support Markdown posts
- User authentication
- Comment system

## Phases

### Phase 1: Infrastructure

- [ ] INFRA-001 Initialize repository
  - Create git repository
  - Setup .gitignore

- [ ] INFRA-002 Setup database schema
  - Create users table
  - Create posts table
  - Create comments table
  - Depends on: INFRA-001

### Phase 2: Backend API

- [ ] API-001 Create authentication endpoint
  - POST /auth/login
  - POST /auth/register
  - Depends on: INFRA-002

- [ ] API-002 Create posts endpoints
  - GET /posts
  - POST /posts
  - PUT /posts/:id
  - DELETE /posts/:id
  - Depends on: API-001

- [ ] API-003 Create comments endpoint
  - GET /posts/:id/comments
  - POST /posts/:id/comments
  - Depends on: API-002

### Phase 3: Frontend

- [ ] FE-001 Setup React project
  - Use Vite
  - Install dependencies

- [ ] FE-002 Create authentication UI
  - Login form
  - Register form
  - Depends on: FE-001

- [ ] FE-003 Create posts UI
  - Post list
  - Post detail
  - Create/edit form
  - Depends on: FE-002, API-002

### Phase 4: Testing

- [ ] TEST-001 Write unit tests
  - Cover all API endpoints
  - Depends on: API-003

- [ ] TEST-002 Write E2E tests
  - Use Playwright
  - Cover critical user flows
  - Depends on: FE-003

## Success Criteria
- [ ] All tests passing
- [ ] No critical bugs
- [ ] Documentation complete

## Notes
- Use TypeScript for type safety
- Follow Airbnb style guide
```

---

## Parsing Rules

### 1. Task Extraction

```python
# Pseudo-code
for phase in document.find_all("### Phase"):
    phase_number = extract_number(phase.heading)
    phase_name = extract_name(phase.heading)

    for item in phase.find_all("- [ ]"):
        task_id = extract_task_id(item) or generate_id()
        description = extract_description(item)
        dependencies = extract_dependencies(item)
        context = extract_context(item)

        tasks.append(Task(
            id=task_id,
            phase=phase_number,
            description=description,
            dependencies=dependencies,
            context=context
        ))
```

### 2. Dependency Resolution

```python
# Build dependency graph
graph = {}
for task in tasks:
    graph[task.id] = task.dependencies

# Validate DAG (no cycles)
if has_cycle(graph):
    raise ValidationError("Circular dependency detected")

# Build execution order
ready_tasks = find_tasks_with_no_dependencies(graph)
```

### 3. Auto-Generated Task IDs

If task ID is not provided, AgentWhip will generate:

```
Phase 1, Task 1 → P1-T001
Phase 1, Task 2 → P1-T002
Phase 2, Task 1 → P2-T001
...
```

---

## Error Handling

| Error | Description | Solution |
|-------|-------------|----------|
| No phases found | No `### Phase` headings | Add at least one phase |
| No tasks in phase | Empty phase | Add tasks or remove phase |
| Circular dependency | A → B → A | Break the cycle |
| Invalid task ID | Special characters | Use alphanumeric only |
| Missing dependency | Depends on non-existent | Fix dependency reference |

---

## Best Practices

1. **Sequential Phases**: Number phases sequentially
2. **Clear Task Names**: Use descriptive task names
3. **Granular Tasks**: Break down large tasks
4. **Explicit Dependencies**: Always specify dependencies
5. **Context Information**: Add context for complex tasks
6. **Review Before Run**: Validate plan before execution
7. **Choose Right Parser**: Use strict for standard format, flexible for anything else
8. **Trust Auto-Fallback**: Let AgentWhip choose the right parser automatically

---

## Validation

AgentWhip provides a validation command:

```bash
# Strict mode validation
agent-whip validate --plan plan.md

# Flexible mode validation (for any format)
agent-whip validate --plan plan.md --flexible
```

**Output:**
```
✓ Plan structure valid
✓ 4 phases found
✓ 12 tasks found
✓ Dependency graph valid (DAG)
✓ All task IDs unique
✓ All dependencies valid

Plan is ready to execute!
```

**Auto-Fallback Behavior:**
If you run `agent-whip run` without `--flexible` and the strict parser fails, AgentWhip will automatically:
1. Display a warning: "Strict parsing failed, falling back to flexible mode..."
2. Re-parse using AI-powered flexible parser
3. Continue execution normally

This ensures your plan is always interpretable, regardless of format!

---

## Advanced Features (Future)

### 1. Task Priority

```markdown
- [ ] TASK-001 High priority task
  - Priority: high
```

### 2. Estimated Time

```markdown
- [ ] TASK-001 Setup database
  - Estimate: 2h
```

### 3. Tags

```markdown
- [ ] TASK-001 Create auth model
  - Tags: backend, security
```

### 4. Assignee

```markdown
- [ ] TASK-001 Write documentation
  - Assignee: john
```

### 5. Conditions

```markdown
- [ ] TASK-001 Deploy to production
  - Condition: all_tests_passing
```
