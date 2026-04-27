# Simple Todo List - Flexible Mode Example

This is a simple todo list that demonstrates AgentWhip's **flexible parsing mode**.

Unlike the strict format required by the standard parser, this can be ANY format - AgentWhip uses Claude AI to interpret it and extract tasks, phases, and dependencies automatically.

---

## How to Use

```bash
# Validate with flexible mode
agent-whip validate --plan examples/plan-simple.md --flexible

# Run with flexible mode
agent-whip run --path . --flexible
```

---

## Example 1: Simple Numbered List

```
Project: E-Commerce Website

1. Setup project structure
2. Configure database
3. Create user authentication
4. Build product catalog
5. Implement shopping cart
6. Add payment integration
7. Deploy to production
```

---

## Example 2: Bullet Points

```markdown
Things to do for my app:

- Fix the navigation menu bug
- Add user authentication
- Implement password reset
- Update the homepage design
- Optimize database queries
```

---

## Example 3: Notion-Style Export

```markdown
## Project Tasks

### Backend
- [ ] Setup Express server
- [ ] Configure PostgreSQL
- [ ] Create API endpoints
- [ ] Add authentication middleware

### Frontend
- [ ] Initialize React app
- [ ] Setup routing
- [ ] Create components
- [ ] Connect to API
```

---

## Example 4: Free-Form Text

```
We need to build a todo app. Here's what needs to be done:

First, setup the project with React and Node.js
Then create the database schema for users and todos
After that, build the REST API endpoints
Finally, create the frontend UI

Don't forget to add tests!
```

---

## Why Flexible Mode?

**Strict Mode** requires:
- Exact markdown format with `### Phase N:` headings
- Checklist syntax `- [ ] TASK-ID Description`
- Explicit dependency declarations

**Flexible Mode** accepts:
- ✅ Any text format
- ✅ Numbered lists, bullet points, or free text
- ✅ Notion exports, GitHub issues, text notes
- ✅ Implicit phases and dependencies (detected by AI)

---

## Auto-Fallback

If you don't specify `--flexible` and strict parsing fails, AgentWhip will **automatically** fall back to flexible mode:

```bash
# This will auto-fallback if strict parsing fails
agent-whip run --path .
```

You'll see:
```
[AgentWhip] Strict parsing failed, falling back to flexible mode...
[Flexible Parser] Using Claude AI to interpret plan...
✓ Parsed 7 tasks from plan
```

---

## Tips for Flexible Mode

1. **Be descriptive** - More context helps AI understand your plan
2. **Group related tasks** - Put related tasks together for better phase detection
3. **Mention dependencies** - Use words like "after", "depends on", "once X is done"
4. **Use natural language** - Write like you're explaining to a human

---

## Comparison

| Feature | Strict Mode | Flexible Mode |
|---------|-------------|---------------|
| Format required | Structured markdown | Any format |
| Speed | Fast (regex) | Slower (AI) |
| Error tolerance | Low (must match format) | High (AI interprets) |
| Best for | Standard projects | Quick prototypes, non-standard formats |
