# nx01-tui — Developer Guide for Claude

## Versioning

Bump `nx01_tui/__about__.py` after every merge. Use semantic versioning:

| Change type | Example | When |
|---|---|---|
| Patch (bug fix, test, docs) | `1.3.0 → 1.3.1` | Single fix, test-only PR |
| Minor (new feature, perf, UX) | `1.3.1 → 1.4.0` | New capability, visible behaviour change |
| Major (epic, breaking redesign) | `1.4.0 → 2.0.0` | Full redesign, breaking API |

**Always create a separate version-bump PR after the feature PR merges.** Never bundle the bump inside a feature commit — it makes rollbacks harder.

---

## Development Workflow

### Running the TUI

```bash
make dev          # run with live CSS hot-reload (requires console in another terminal)
make console      # Textual debug console — start FIRST, then make dev
```

### Lint + format

```bash
make fmt          # auto-fix formatting and fixable lint errors
make lint         # check only (what CI runs)
```

Linter: `ruff` (line length 100, rules E/F/I/UP/B/W). Config in `pyproject.toml`.

### Tests

```bash
make test         # full suite + coverage report
make test-fast    # fast inner-loop (no coverage)
make check        # lint + test — same as CI
```

Tests live in `tests/`. Runner: `pytest` with `asyncio_mode = auto`.

**Every PR must include tests.** No exceptions:
- Bug fix → regression test that fails before the fix
- New feature → integration test covering the happy path + at least one edge case
- State/persistence change → test the full lifecycle (write → read → verify)

---

## Testing Rules

### Integration tests (Textual apps)

Use `app.run_test()` as an async context manager. Always call `_settle()` after boot to let workers finish:

```python
async def _settle(app, pilot, secs: float = 1.0) -> None:
    await pilot.pause(secs)
    for w in list(app.workers):
        w.cancel()
    await pilot.pause(0.2)
```

Mock all network calls on `app.client` before the context manager opens:

```python
app.client.get_flavors = fake_get_flavors
app.client.list_commands = fake_list_commands
```

Use `tmp_path` + `monkeypatch` to isolate file-system state (e.g. `_STATE_FILE`):

```python
monkeypatch.setattr(app_module, "_STATE_FILE", tmp_path / "state.json")
```

### Unit tests (widgets)

Run with `PYTHONPATH` pointing at the worktree so the editable install doesn't shadow local changes:

```bash
PYTHONPATH=/path/to/worktree .venv/bin/pytest tests/widgets/
```

### Snapshot tests

```bash
make snapshot           # run existing baselines
make snapshot-update    # regenerate baselines after intentional visual changes
```

Snapshots are SVG-based and platform-dependent — they are skipped in CI.

---

## UI / TUI Development

### Always use Textual devtools when making UI changes

1. Open the debug console in a separate terminal first:
   ```bash
   make console          # default
   make console-verbose  # includes EVENT stream
   make console-quiet    # WARNING+ only
   ```

2. Run the app in dev mode (live CSS reload):
   ```bash
   make dev
   ```

3. Check the console for:
   - `WARNING` log lines (unexpected state)
   - DOM events to trace click/key handling
   - CSS layout issues

### CSS changes

All app CSS is in `nx01_tui/tui/app.tcss`. Widget-local CSS goes in `DEFAULT_CSS` on the widget class. Prefer `DEFAULT_CSS` for widget-scoped styles; `app.tcss` for layout and theming.

### Widget lifecycle

Textual widgets: compose → mount → (reactive updates) → unmount. Never read DOM in `__init__`; use `on_mount`. Call `self.call_after_refresh(fn)` when you need to act after a layout pass.

---

## Performance

### Measuring

**Always measure before and after.** Never claim a performance improvement without numbers.

Preferred measurement approach for streaming/rendering:

```python
import time

start = time.perf_counter()
# ... operation ...
elapsed = time.perf_counter() - start
print(f"elapsed: {elapsed*1000:.1f}ms")
```

For DOM writes, count `mount()` / `update()` calls and log the delta.

For memory, use `tracemalloc`:

```python
import tracemalloc
tracemalloc.start()
# ... operation ...
current, peak = tracemalloc.get_traced_memory()
print(f"peak: {peak/1024:.1f}KB")
```

### What to measure

| Concern | Metric |
|---|---|
| Streaming latency | Time from SSE event to widget update (ms) |
| DOM write count | Number of `mount`/`update` calls per turn |
| Memory per message | `tracemalloc` peak during replay |
| Startup time | Time to first interactive frame |

### Key performance rules

- **Batch DOM writes.** Never call `update()` in a tight loop; accumulate and flush once.
- **Scroll sparingly.** `scroll_end(animate=False)` is fine; `scroll_to_widget` with `animate=True` is expensive.
- **Avoid `query()` in hot paths.** Cache widget references; `query()` walks the DOM.
- **`RichLog` over `Markdown` for streaming.** `Markdown` re-renders the full AST on every append; `RichLog.write()` is O(1).

---

## Project Structure

```
nx01_tui/
  __about__.py          ← version string (bump here)
  cli.py                ← entry point
  tui/
    app.py              ← Nx01App (main app, event routing, session state)
    app.tcss            ← global CSS
    client.py           ← httpx SSE client
    events.py           ← SSE event dataclasses + parser
    state.py            ← FlavorState, AgentState, route_event()
    widgets/            ← all Textual widget classes
    modals/             ← modal screens
tests/
  integration/          ← full-app integration tests
  widgets/              ← unit tests per widget
  snapshots/            ← SVG visual regression tests
scripts/
  v11_smoke.py          ← visual smoke test (run manually, generates PNGs)
  v1_visual_smoke.py    ← V1 visual smoke test
  qa_probes/            ← targeted widget behaviour probes
```

---

## CI

CI runs on every PR: `ruff check` → `ruff format --check` → `pytest`.

Pre-merge checklist:
- [ ] `make check` passes locally
- [ ] New tests added for changed behaviour
- [ ] Version bumped (separate PR after merge)
- [ ] No `# noqa` added without a comment explaining why
