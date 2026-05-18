# nx01-tui 10x Performance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Achieve ≥60fps average frame rate during active streaming, session restore from >1s to <100ms, and bootstrap from N×RTT to 1×RTT across all flavors.

**Architecture:** Three independent batches on top of the existing v1.2.0 codebase (main). Batch 3 adds a 60fps event drain loop to coalesce SSE events. Batch 4 wraps session replay in `batch_update()` + scroll suppression. Batch 5 parallelizes per-flavor bootstrap HTTP calls with `asyncio.gather()`.

**Tech Stack:** Python 3.11+, Textual (TUI framework), asyncio, httpx (SSE client). Run tests with `pytest -x -q tests/`.

---

## IMPORTANT: Baseline Check

Before starting, verify you're on the right branch and tests pass:

```bash
git status                    # should be on worktree-perf-plan or main
pytest -x -q tests/ --timeout=30
```

Expected: all tests pass. If tests are failing, stop and fix them before touching code.

---

## Task 1: Add scroll suppression to ConversationView

**Why:** The drain loop (Task 2) must process many events without triggering `scroll_end` per-event. ConversationView currently calls `scroll_end` in `append_assistant`, `append_thinking`, and `start_tool`. We need a way to suppress that during batch drain.

**Files:**
- Modify: `nx01_tui/tui/widgets/conversation.py`
- Test: `tests/widgets/test_conversation.py` (create if absent)

**Step 1: Write the failing test**

Check if `tests/widgets/` exists:
```bash
ls tests/widgets/
```

Create `tests/widgets/test_conversation.py` if needed (add `tests/widgets/__init__.py` too if absent):

```python
"""Tests for ConversationView scroll suppression."""
from __future__ import annotations

import pytest
from nx01_tui.tui.app import Nx01App


@pytest.mark.asyncio
async def test_suppress_scroll_prevents_intermediate_scrolls():
    """With suppress_scroll active, scroll_end is not called per-event."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    scroll_calls: list[str] = []

    async with app.run_test() as pilot:
        await pilot.pause(0.3)

        pane = app._panes.get("assistant")
        if pane is None:
            pytest.skip("no assistant pane")

        conv = pane.conversation
        original_scroll = conv.scroll_end

        def track_scroll(**kwargs):
            scroll_calls.append("scroll")
            return original_scroll(**kwargs)

        conv.scroll_end = track_scroll  # type: ignore[method-assign]

        with conv.suppress_scroll():
            conv.append_assistant("hello ")
            conv.append_assistant("world")

        before_explicit = len(scroll_calls)
        conv.scroll_end(animate=False)
        assert len(scroll_calls) == before_explicit + 1  # exactly one scroll at end
        assert before_explicit == 0  # none during suppression
```

**Step 2: Run to verify it fails**

```bash
pytest tests/widgets/test_conversation.py -v
```

Expected: `AttributeError: 'ConversationView' object has no attribute 'suppress_scroll'`

**Step 3: Implement suppress_scroll in ConversationView**

Open `nx01_tui/tui/widgets/conversation.py`. In `__init__` (line 68), add flag:

```python
def __init__(self, **kwargs: object) -> None:
    super().__init__(**kwargs)
    self._active_thinking: ThinkingBlock | None = None
    self._active_assistant: AssistantMessage | None = None
    self._active_tools: dict[str, ToolCallBlock] = {}
    self._empty_state: _EmptyState | None = None
    self._unread_divider: UnreadDivider | None = None
    self._scroll_suppressed: bool = False          # ← add this
```

Add the context manager (after `__init__`, before `on_mount`):

```python
from contextlib import contextmanager

@contextmanager
def suppress_scroll(self):
    """Suppress scroll_end calls during batch operations."""
    self._scroll_suppressed = True
    try:
        yield
    finally:
        self._scroll_suppressed = False
```

Add `_maybe_scroll` helper:

```python
def _maybe_scroll(self) -> None:
    if not self._scroll_suppressed:
        self.scroll_end(animate=False)
```

Replace every bare `self.scroll_end(animate=False)` **inside the widget methods** (not in external callers) with `self._maybe_scroll()`. The methods to update are `add_user_message` (line 103), `append_thinking` (line 120), `start_tool` (line 146), `append_assistant` (line 167), `end_assistant` (line 183). Do NOT replace the explicit `scroll_end` call in `scroll_to_unread_after_refresh` (line 136) — that one is intentional.

**Step 4: Run the test**

```bash
pytest tests/widgets/test_conversation.py -v
```

Expected: PASS

**Step 5: Run full suite**

```bash
pytest -x -q tests/ --timeout=30
```

Expected: all pass.

**Step 6: Commit**

```bash
git add nx01_tui/tui/widgets/conversation.py tests/widgets/
git commit -m "feat(perf): add suppress_scroll context manager to ConversationView"
```

---

## Task 2: Batch 3 — SSE event micro-batching

**Why:** Currently every SSE event triggers `post_message → on_sse_message → _dispatch_event → widget.update() → scroll_end`. At 50 tok/sec that's 50 full layout passes per second. We drain the queue 60 times/sec instead — ≤60 layout passes/sec (matching display refresh).

**Files:**
- Modify: `nx01_tui/tui/app.py`
- Test: `tests/integration/test_sse_batching.py` (create)

**Step 1: Write the failing test**

Create `tests/integration/test_sse_batching.py`:

```python
"""SSE micro-batching — events accumulate in queue, not immediate dispatch."""
from __future__ import annotations

import asyncio
import pytest
from nx01_tui.tui.app import Nx01App
from nx01_tui.tui.events import AgentChunkEvent


@pytest.mark.asyncio
async def test_sse_events_go_into_queue_not_immediate(monkeypatch):
    """SSE 'event' payloads are put in _event_queue, not dispatched immediately."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])

    async with app.run_test() as pilot:
        await pilot.pause(0.2)

        # _event_queue must exist
        assert hasattr(app, "_event_queue"), "_event_queue not found on app"

        # Put a fake chunk event into the queue manually
        fake_event = AgentChunkEvent(flavor="assistant", text="hi", at=0)
        app._event_queue.put_nowait(fake_event)

        # Immediately after put, it should still be in the queue (not drained yet)
        assert not app._event_queue.empty()

        # After one drain cycle (≥1/60s), queue should be empty
        await pilot.pause(0.1)
        assert app._event_queue.empty()


@pytest.mark.asyncio
async def test_connection_status_bypasses_queue(monkeypatch):
    """ConnectionStatusMessage must still dispatch immediately (not queued)."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    dispatched: list[str] = []

    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        original = app.on_connection_status_message

        def track(msg):
            dispatched.append(msg.kind)
            return original(msg)

        monkeypatch.setattr(app, "on_connection_status_message", track)

        from nx01_tui.tui.app import ConnectionStatusMessage
        app.post_message(ConnectionStatusMessage("connected"))
        await pilot.pause(0.05)

        assert "connected" in dispatched
```

**Step 2: Run to verify it fails**

```bash
pytest tests/integration/test_sse_batching.py -v
```

Expected: `AssertionError: _event_queue not found on app`

**Step 3: Implement the queue and drain loop**

In `nx01_tui/tui/app.py`, apply these changes in order:

**3a. Add queue to `__init__`** (after line 154, inside `__init__`):

```python
self._event_queue: asyncio.Queue[SseEvent] = asyncio.Queue()
```

**3b. Register drain interval in `on_mount`** (line 164, add after `self.run_worker(self._bootstrap(), ...)`):

```python
async def on_mount(self) -> None:
    domain = urlparse(self.base_url).netloc or self.base_url
    self.query_one(AppHeader).domain = domain
    self.run_worker(self._bootstrap(), exclusive=True, name="bootstrap")
    self.set_interval(1 / 30, self._drain_events)   # ← add this line
```

**3c. Change `_sse_loop` to queue instead of post_message** (line 321-322):

Replace:
```python
if kind == "event":
    self.post_message(SseMessage(payload))
```
With:
```python
if kind == "event":
    self._event_queue.put_nowait(payload)
```

Keep the `ConnectionStatusMessage` lines unchanged — they still use `post_message`.

**3d. Add `_drain_events` method** (add after `on_connection_status_message`, around line 361):

```python
async def _drain_events(self) -> None:
    """Drain the SSE event queue in one batch per 60fps interval."""
    if self._event_queue.empty():
        return
    flavor = self._active_flavor()
    pane = self._panes.get(flavor)
    conv = pane.conversation if pane else None

    with self.batch_update():
        ctx = conv.suppress_scroll() if conv else _null_ctx()
        with ctx:
            while not self._event_queue.empty():
                event = self._event_queue.get_nowait()
                self._debug_buffer.append(event)
                if self._debug_modal is not None:
                    self._debug_modal.push(event)
                self._dispatch_event(event)

    if conv is not None:
        conv.scroll_end(animate=False)
```

Add a tiny helper at module level (near the top of app.py, after imports):

```python
from contextlib import contextmanager, nullcontext as _null_ctx
```

Note: `nullcontext` is in `contextlib` since Python 3.7. Import it as `_null_ctx` for clarity.

**3e. Remove the now-unused `on_sse_message` handler** (lines 337–341):

Delete:
```python
def on_sse_message(self, message: SseMessage) -> None:
    self._debug_buffer.append(message.event)
    if self._debug_modal is not None:
        self._debug_modal.push(message.event)
    self._dispatch_event(message.event)
```

Also remove the `SseMessage` class (lines 78–82) and its import usage if nothing else references it.

**Step 4: Run the test**

```bash
pytest tests/integration/test_sse_batching.py -v
```

Expected: PASS

**Step 5: Run full suite**

```bash
pytest -x -q tests/ --timeout=30
```

Expected: all pass. If any test directly posts `SseMessage`, update it to put to `_event_queue` instead.

**Step 6: Commit**

```bash
git add nx01_tui/tui/app.py tests/integration/test_sse_batching.py
git commit -m "perf(batch3): SSE event micro-batching — max 60fps target"
```

---

## Task 3: Batch 4 — Replay/restore batching

**Why:** `_replay_messages` (app.py:669) mounts widgets one-by-one. Each `mount()` call triggers a layout recalc. For 50 historical messages, that's 50+ layout passes during session restore — visible as a "loading stutter."

**Fix:** Wrap the entire replay in `batch_update()` + `conv.suppress_scroll()`. Call `scroll_end` exactly once after all mounts.

**Files:**
- Modify: `nx01_tui/tui/app.py` (lines 669–728 and 920–938)
- Test: `tests/integration/test_replay_batching.py` (create)

**Step 1: Write the failing test**

Create `tests/integration/test_replay_batching.py`:

```python
"""Replay batching — session restore wraps all mounts in batch_update."""
from __future__ import annotations

import pytest
from nx01_tui.tui.app import Nx01App
from nx01_tui.tui.modals.sessions_modal import SessionAction
from nx01_tui.tui.widgets import AssistantMessage, UserMessage


def _big_session(n: int = 20) -> list[dict]:
    """n user+assistant pairs."""
    rows = []
    for i in range(n):
        rows.append({"role": "user", "content": f"msg {i}", "timestamp": i * 2})
        rows.append({"role": "assistant", "content": f"reply {i}", "timestamp": i * 2 + 1})
    return rows


@pytest.mark.asyncio
async def test_replay_scroll_called_once(monkeypatch):
    """scroll_end called exactly once after replaying 20 messages."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    scroll_calls: list[int] = []

    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        pane = app._panes.get("assistant")
        if pane is None:
            pytest.skip("no assistant pane")
        conv = pane.conversation
        original = conv.scroll_end

        def track(**kw):
            scroll_calls.append(1)
            return original(**kw)

        conv.scroll_end = track  # type: ignore[method-assign]
        scroll_calls.clear()

        rows = _big_session(20)
        app._replay_messages("assistant", rows)

        # Allow one settle tick
        await pilot.pause(0.1)

        # The replay itself should produce at most 1 scroll_end call.
        # (It could be 0 if _auto_resume_flavor calls it afterwards, or 1 if
        # _replay_messages ends with an explicit scroll.)
        assert len(scroll_calls) <= 1, f"Expected ≤1 scroll, got {len(scroll_calls)}"


@pytest.mark.asyncio
async def test_replay_content_correct_after_batching(monkeypatch):
    """All messages render correctly even with batch_update wrapping."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])

    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        pane = app._panes.get("assistant")
        if pane is None:
            pytest.skip("no assistant pane")
        conv = pane.conversation

        rows = [
            {"role": "user", "content": "hello", "timestamp": 1},
            {"role": "assistant", "content": "world", "timestamp": 2},
        ]
        app._replay_messages("assistant", rows)
        await pilot.pause(0.2)

        user_msgs = conv.query(UserMessage)
        asst_msgs = conv.query(AssistantMessage)
        assert len(list(user_msgs)) >= 1
        assert len(list(asst_msgs)) >= 1
```

**Step 2: Run to verify it fails**

```bash
pytest tests/integration/test_replay_batching.py::test_replay_scroll_called_once -v
```

Expected: FAIL — scroll_calls will be > 1 (one per message).

**Step 3: Wrap _replay_messages in batch_update + suppress_scroll**

In `nx01_tui/tui/app.py`, update `_replay_messages` (starting at line 669):

Replace the body so the loop is wrapped:

```python
def _replay_messages(
    self,
    flavor: str,
    rows: list[dict],
    unread_from_row: int | None = None,
) -> None:
    from .state import ToolStatus

    conv = self._panes[flavor].conversation

    with self.batch_update(), conv.suppress_scroll():
        for i, row in enumerate(rows):
            if unread_from_row is not None and i == unread_from_row:
                new_count = len(rows) - unread_from_row
                conv.insert_unread_divider(new_count)

            role = row.get("role", "")
            reasoning = row.get("reasoning") or row.get("reasoning_content") or ""
            if reasoning:
                t = conv.start_thinking()
                t.append_chunk(reasoning)
                conv.end_thinking(auto_collapse=True)

            if role == "user":
                content = row.get("content") or ""
                if content:
                    conv.add_user_message(str(content))
            elif role == "assistant":
                content = row.get("content") or ""
                if content:
                    conv.start_assistant(str(content))
                    conv.end_assistant()
                for tc in row.get("tool_calls") or []:
                    name = tc.get("name") or tc.get("function", {}).get("name", "tool")
                    args = tc.get("arguments") or tc.get("function", {}).get("arguments", "")
                    call_id = tc.get("id", "")
                    block = conv.start_tool(tool=str(name), args=str(args), call_id=call_id)
                    block.set_status(ToolStatus.DONE)
            elif role == "tool":
                call_id = row.get("tool_call_id", "")
                tool_name = row.get("tool_name") or "tool"
                output = row.get("content") or ""
                block = conv.get_tool(call_id) if call_id else None
                if block is None:
                    block = conv.start_tool(tool=str(tool_name), args="", call_id=call_id)
                if output:
                    block.append_output(str(output))
                block.set_status(ToolStatus.DONE)
    # Single scroll after all mounts — suppress_scroll is now released.
    # Caller (_auto_resume_flavor) may scroll to unread divider instead;
    # this scroll is a safe fallback for the manual-resume path.
    conv.scroll_end(animate=False)
```

**Step 4: Run the tests**

```bash
pytest tests/integration/test_replay_batching.py -v
```

Expected: PASS

**Step 5: Run full suite**

```bash
pytest -x -q tests/ --timeout=30
```

Expected: all pass. The existing `test_session_resume.py` tests must still pass.

**Step 6: Commit**

```bash
git add nx01_tui/tui/app.py tests/integration/test_replay_batching.py
git commit -m "perf(batch4): wrap _replay_messages in batch_update + suppress_scroll"
```

---

## Task 4: Batch 5 — Bootstrap parallelization

**Why:** `_bootstrap_slash_dropdowns` (app.py:247) fetches `list_skills` and `get_tools` for each flavor sequentially. For 3 flavors: 6 sequential HTTP round-trips. With `asyncio.gather()` these become concurrent — ~3x faster bootstrap.

**Files:**
- Modify: `nx01_tui/tui/app.py` (lines 247–296)
- Test: `tests/integration/test_bootstrap_parallel.py` (create)

**Step 1: Write the failing test**

Create `tests/integration/test_bootstrap_parallel.py`:

```python
"""Bootstrap parallelization — per-flavor API calls run concurrently."""
from __future__ import annotations

import asyncio
import pytest
from nx01_tui.tui.app import Nx01App


@pytest.mark.asyncio
async def test_bootstrap_fetches_flavors_concurrently(monkeypatch):
    """list_skills for flavor A and B are called concurrently, not sequentially."""
    app = Nx01App("http://localhost:9999", flavors=["alpha", "beta"])

    call_log: list[tuple[str, float]] = []

    async def fake_list_skills(flavor: str):
        call_log.append((f"skills:{flavor}", asyncio.get_event_loop().time()))
        await asyncio.sleep(0.05)  # simulate network latency
        return []

    async def fake_get_tools(flavor: str):
        call_log.append((f"tools:{flavor}", asyncio.get_event_loop().time()))
        await asyncio.sleep(0.05)
        return {}

    async def fake_list_commands():
        return []

    monkeypatch.setattr(app.client, "list_skills", fake_list_skills)
    monkeypatch.setattr(app.client, "get_tools", fake_get_tools)
    monkeypatch.setattr(app.client, "list_commands", fake_list_commands)

    async with app.run_test() as pilot:
        await pilot.pause(1.5)  # let bootstrap complete

    # Both flavors' skills should have been fetched.
    fetched_flavors = {name.split(":")[1] for name, _ in call_log if name.startswith("skills:")}
    assert "alpha" in fetched_flavors
    assert "beta" in fetched_flavors

    # Concurrent: the two skills calls should start within 0.03s of each other.
    alpha_t = next((t for n, t in call_log if n == "skills:alpha"), None)
    beta_t = next((t for n, t in call_log if n == "skills:beta"), None)
    if alpha_t and beta_t:
        assert abs(alpha_t - beta_t) < 0.03, (
            f"Skills fetches not concurrent: alpha={alpha_t:.3f} beta={beta_t:.3f}"
        )
```

**Step 2: Run to verify it fails**

```bash
pytest tests/integration/test_bootstrap_parallel.py -v
```

Expected: FAIL — `alpha_t` and `beta_t` are ~0.05s apart (sequential).

**Step 3: Refactor `_bootstrap_slash_dropdowns` to use asyncio.gather**

Replace `_bootstrap_slash_dropdowns` in `nx01_tui/tui/app.py` (lines 247–296):

```python
async def _bootstrap_slash_dropdowns(self, flavors: list[str]) -> None:
    # Wait for FlavorPane mounts to settle in the DOM.
    for _ in range(20):
        await asyncio.sleep(0.05)
        try:
            if all(self.query_one(f"#slash-{fl}", SlashDropdown) for fl in flavors):
                break
        except Exception:  # noqa: BLE001
            continue

    try:
        commands = await self.client.list_commands()
    except Exception as exc:  # noqa: BLE001
        logger.warning("slash dropdown: list_commands failed: %s", exc)
        commands = []

    # Fetch skills + tools for all flavors concurrently.
    results = await asyncio.gather(
        *[self._fetch_flavor_dropdown_data(fl) for fl in flavors],
        return_exceptions=True,
    )

    for fl, result in zip(flavors, results):
        if isinstance(result, Exception):
            logger.warning("slash dropdown: fetch failed for %s: %s", fl, result)
            skills, tools = [], []
        else:
            skills, tools = result

        try:
            self.query_one(f"#slash-{fl}", SlashDropdown).set_sources(
                commands=commands, skills=skills, tools=tools
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("slash dropdown: set_sources(%s) failed: %s", fl, exc)

        state = self._states.get(fl)
        pane = self._panes.get(fl)
        if state and pane and skills:
            state.preload_skills(skills)
            pane.sync_sidebar(state)

async def _fetch_flavor_dropdown_data(
    self, flavor: str
) -> tuple[list, list]:
    """Fetch skills + tools for one flavor. Returns (skills, tools)."""
    try:
        skills = await self.client.list_skills(flavor)
    except Exception as exc:  # noqa: BLE001
        logger.warning("slash dropdown: list_skills(%s) failed: %s", flavor, exc)
        skills = []
    try:
        tools_resp = await self.client.get_tools(flavor)
        tools = (
            tools_resp.get("tools", [])
            if isinstance(tools_resp, dict)
            else (tools_resp or [])
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("slash dropdown: get_tools(%s) failed: %s", flavor, exc)
        tools = []
    return skills, tools
```

**Step 4: Run the test**

```bash
pytest tests/integration/test_bootstrap_parallel.py -v
```

Expected: PASS

**Step 5: Run full suite**

```bash
pytest -x -q tests/ --timeout=30
```

Expected: all pass.

**Step 6: Commit**

```bash
git add nx01_tui/tui/app.py tests/integration/test_bootstrap_parallel.py
git commit -m "perf(batch5): parallelize per-flavor bootstrap with asyncio.gather"
```

---

## Task 5: Verify and measure

**Step 1: Run the full test suite one final time**

```bash
pytest -x -q tests/ --timeout=30
```

Expected: all pass, no regressions.

**Step 2: Sanity check the drain interval is registered**

```bash
python -c "
import asyncio
from nx01_tui.tui.app import Nx01App
app = Nx01App('http://localhost:9999', flavors=['assistant'])
print('_event_queue:', hasattr(app, '_event_queue'))
print('_drain_events:', hasattr(app, '_drain_events'))
"
```

Expected: both `True`.

**Step 3: Manual smoke test** (if server available)

Start the TUI and:
1. Send a message — streaming should feel smooth (no jank between tokens)
2. Quit and reopen — session should restore without visible stutter
3. Switch flavors — tabs should populate instantly

**Step 4: Commit any final tweaks, then create a PR**

```bash
git log --oneline main..HEAD
```

Expected: 4 commits (Tasks 1–4). Then push and open PR targeting `main`.

---

## Rollback

Each task is an independent commit. To revert any single batch:

```bash
git revert <commit-sha>   # creates a revert commit, no force push needed
```

---

## Success Criteria

| Metric | Before | After |
|--------|--------|-------|
| scroll_end calls per 10 streamed tokens | 10 | 1 |
| Layout passes/sec at 50 tok/s | ~50 | ≤60 (one per frame) |
| scroll_end calls during 50-msg replay | ~100 | 1 |
| Bootstrap HTTP calls serialized | N×2 sequential | N parallel |
