# nx01-tui 10x Performance Design

**Date**: 2026-05-18  
**Goal**: 10x improvement across streaming latency, long-thread stability, and session restore speed.

---

## Baseline

Current main (v1.2.0) has these known hot-path issues:

- `AssistantMessage.append()` calls `Markdown.update(full_buffer)` on every chunk — O(n²) parse cost over a long response.
- `scroll_end(animate=False)` called on every `append_thinking`, `append_assistant`, `start_tool` — triggers layout recalc per event.
- Session replay mounts widgets sequentially; each mount triggers layout.
- Bootstrap makes sequential API calls per flavor (list_skills → get_tools × N flavors).

Branch `worktree-perf-fixes` (v1.3.0) fixes the first two via Batch 1+2 but is not yet merged.

---

## Approach: Incremental Batches

### Step 0 — Merge worktree-perf-fixes

Already coded and CI-green. Delivers:

- Two-phase streaming: buffer chunks in a `Static` (no Markdown parse during stream), finalize to `Markdown` once at turn end, freeze back to `Static`.
- Single `RichLog.write()` per chunk (was: one write per character).
- Widget freezing during bulk operations to skip layout recalc.
- DOM paging: archive oldest message groups when widget count exceeds threshold.

**Expected**: 8x fewer DOM writes, 17.9x hot-path ops reduction, 500x Markdown parse reduction.

---

### Batch 3 — SSE Event Micro-batching

**Problem**: Each SSE token fires `post_message → on_sse_message → widget.update() → scroll_end()`. At 50 tokens/sec that is 50 layout passes against a 16ms frame budget.

**Solution**: AsyncIO queue + frame-synchronized drain at 30fps.

```python
# __init__
self._event_queue: asyncio.Queue[SseEvent] = asyncio.Queue()

# _sse_loop: replace post_message with queue put
await self._event_queue.put(payload)

# New method, called via set_interval(1/30, ...)
async def _drain_events(self) -> None:
    if self._event_queue.empty():
        return
    with self.batch_update():
        while not self._event_queue.empty():
            event = self._event_queue.get_nowait()
            self._dispatch_event(event)
    self._active_conv().scroll_end(animate=False)
```

**Key decisions**:
- 30fps drain cadence: fast enough to feel real-time, slow enough to batch 2–3 tokens per frame at typical streaming rate.
- Debug modal (`DebugModal.push`) still receives events — drain loop must feed it.
- Connection status messages (`ConnectionStatusMessage`) bypass the queue (they're rare and need immediate UI response).
- `batch_update()` groups all DOM mutations; single `scroll_end` per drain cycle.

**Expected**: Max 30 layout passes/sec regardless of token rate. Streaming feels smooth because text accumulates between drains.

---

### Batch 4 — Replay / Session Restore Batching

**Problem**: `_replay_messages()` mounts widgets one-by-one sequentially. Each `mount()` triggers a layout recalc. For a 50-message history: 50 layout passes just to restore.

**Solution**: Wrap replay in `batch_update()`, use `Static` for historical messages (no Markdown parse), single `scroll_end` after all mounts.

```python
async def _replay_messages(self, messages: list[dict]) -> None:
    conv = self._active_conv()
    with self.batch_update():
        for msg in messages:
            role = msg.get("role", "user")
            text = msg.get("content", "")
            if role == "user":
                conv.mount(UserMessage(text))
            else:
                # Historical messages: Static only, no live Markdown widget.
                conv.mount(StaticAssistantMessage(text))
    conv.scroll_end(animate=False)
```

`StaticAssistantMessage` renders pre-formatted text as a `Static` with Rich markup — zero Markdown parse cost. Only the current (live) turn gets a real `AssistantMessage` with Markdown.

**Expected**: 10–50x faster restore for large sessions. No layout stutter during replay.

---

### Batch 5 — Bootstrap Parallelization

**Problem**: For each flavor, bootstrap does:
```python
skills = await client.list_skills(flavor)   # sequential
tools  = await client.get_tools(flavor)     # sequential
```
For 3 flavors: 6 sequential HTTP round-trips before the UI is ready.

**Solution**: Gather all flavor data in parallel.

```python
async def _bootstrap_slash_dropdowns(self, flavors: list[str]) -> None:
    results = await asyncio.gather(
        *[self._fetch_flavor_data(fl) for fl in flavors],
        return_exceptions=True,
    )
    for fl, result in zip(flavors, results):
        if isinstance(result, Exception):
            logger.warning("bootstrap %s failed: %s", fl, result)
            continue
        skills, tools = result
        self.query_one(f"#slash-{fl}", SlashDropdown).set_sources(
            commands=commands, skills=skills, tools=tools
        )
```

**Expected**: 3x faster bootstrap for 3 flavors (network-bound, fully parallel).

---

## Success Criteria

| Metric | Current (v1.2.0) | Target |
|--------|-----------------|--------|
| Layout passes/sec at 50 tok/s | ~50 | ≤30 |
| Markdown parses per 1000-char response | ~50 | 1 |
| Session restore time (50 msgs) | >1s visible stutter | <100ms |
| Bootstrap time (3 flavors) | ~3× RTT | ~1× RTT |
| DOM widget count after 100 turns | unbounded | ≤200 (paged) |

---

## Implementation Order

1. Merge `worktree-perf-fixes` → baseline 8x (Step 0)
2. Batch 3: SSE micro-batching (app.py — ~50 lines changed)
3. Batch 4: Replay batching + StaticAssistantMessage (app.py + messages.py — ~70 lines)
4. Batch 5: Bootstrap gather (app.py — ~30 lines)

Each batch ships independently and has measurable before/after via the existing benchmark script.

---

## Non-Goals

- Worker threads for Markdown parsing (Textual widgets are not thread-safe)
- True virtual scrolling (DOM paging from Batch 2 is sufficient)
- Network-level SSE compression (backend concern, not TUI)
