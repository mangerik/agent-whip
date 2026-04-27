# API vs CLI Integration

## Current Implementation: API-based

AgentWhip saat ini menggunakan **API-based integration**:

```
AgentWhip → HTTP API → Anthropic/OpenCode
```

### Kelebihan:
- ✓ Kontrol penuh atas token tracking
- ✓ Bisa berjalan tanpa instalasi CLI
- ✓ Retry logic lebih robust
- ✓ Bisa di-deploy sebagai service terpisah

### Kekurangan:
- ✗ Perlu setup API key terpisah
- ✗ Tidak memanfaatkan config CLI yang sudah ada

---

## Alternative: CLI-based Integration

Alternatif adalah menggunakan **CLI-based integration**:

```
AgentWhip → Subprocess → claude/opencode CLI
```

### Contoh implementasi:

```python
class ClaudeCLIWorker(Worker):
    """Worker that uses Claude Code CLI via subprocess."""

    async def execute(self, task: Task) -> TaskResult:
        prompt = self.get_prompt_for_task(task)

        # Call claude CLI
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "prompt",
            prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        # Parse output...
```

### Kelebihan:
- ✓ Pakai auth dari CLI yang sudah ter-configure
- ✓ Tidak perlu API key terpisah
- ✓ Lebih simpel dari sisi user

### Kekurangan:
- ✗ Token tracking sulit (perlu parse CLI output)
- ✗ Tergantung instalasi CLI
- ✗ Error handling lebih kompleks
- ✗ Output format bisa berubah antar versi CLI

---

## Recommendation

**Saat ini: API-based lebih direkomendasikan** karena:
1. Token tracking penting untuk handover feature
2. Bisa berjalan di environment tanpa CLI
3. Lebih testable dan maintainable

**Future enhancement:** Tambah opsi CLI mode untuk user yang sudah punya CLI ter-install.

---

## Configuration

### API-based (current)
```yaml
# agent-whip.yml
claude:
  api_key: "${ANTHROPIC_API_KEY}"
  model: claude-opus-4-6

opencode:
  api_key: "${OPENCODE_API_KEY}"
```

### CLI-based (future)
```yaml
# agent-whip.yml
workers:
  claude:
    mode: cli  # or "api"
    path: /usr/bin/claude  # optional, default to PATH

  opencode:
    mode: cli
    path: /usr/bin/opencode
```
