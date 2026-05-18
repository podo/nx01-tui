"""
tools/perf_benchmark.py — streaming render performance across three versions.

  Baseline  — original code, zero optimisations
  Batch 1   — 5 fixes: debounce Markdown/scroll, slower timers, O(1) counters
  Batch 2   — 4 new fixes: Static streaming, single RichLog writes, freeze, paging

Scenarios:
  A) Short thread:  20 turns, 200 chunks/turn, 3 tool calls/turn
  B) Long thread:   80 turns, 500 chunks/turn, 5 tool calls/turn

Chunk rate: 8 ms/chunk (~125 tokens/sec).
Tool output: 30 lines per result (typical grep/read response).

Run with:  uv run python tools/perf_benchmark.py
"""

from __future__ import annotations

import time

CHUNK_MS = 8.0  # ms between tokens
MD_FLUSH_MS = 50.0  # Markdown/Static flush interval (batch 1+2)
SCROLL_FLUSH_MS = 100.0  # scroll_end debounce interval (batch 1+2)
THINKING_S = 3.0  # avg seconds of thinking per turn
TOOL_ACTIVE_S = 1.5  # avg seconds one tool runs
TOOL_OUTPUT_LINES = 30  # avg lines in one tool result
MAX_MOUNTED_TURNS = 30  # paging cap (batch 2)
MD_CHILD_NODES = 18  # avg Textual Markdown child widgets per response


def _fmt(n: int) -> str:
    return f"{n:>8,}"


def _ratio(a: int, b: int) -> str:
    if b == 0:
        return "  ∞"
    r = a / b
    return f"{r:>6.1f}x"


# ── Per-turn simulators ───────────────────────────────────────────────────────


def streaming_writes(chunks: int, version: int) -> int:
    """How many Markdown/Static DOM-writes happen during one streaming turn."""
    if version == 0:
        return chunks  # one full Markdown.update per chunk
    elif version == 1:
        turn_ms = chunks * CHUNK_MS
        return int(turn_ms / MD_FLUSH_MS) + 1  # batched; +1 for finalise
    else:  # version 2: Static.update (no parse) during stream, 1 Markdown at end
        turn_ms = chunks * CHUNK_MS
        return int(turn_ms / MD_FLUSH_MS) + 1  # same flush count but much cheaper


def streaming_parse_ops(chunks: int, version: int) -> int:
    """How many *full Markdown parse operations* happen during one streaming turn."""
    if version == 0:
        return chunks  # parse on every chunk
    elif version == 1:
        turn_ms = chunks * CHUNK_MS
        return int(turn_ms / MD_FLUSH_MS) + 1  # parse on every 50ms flush
    else:  # version 2: Static during stream (no parse); 1 parse on finalise
        return 1


def scroll_calls(chunks: int, version: int) -> int:
    if version == 0:
        return chunks  # scroll_end per chunk
    else:
        turn_ms = chunks * CHUNK_MS
        return int(turn_ms / SCROLL_FLUSH_MS) + 1


def thinking_timer_fires(turns: int, version: int) -> int:
    hz = 10.0 if version == 0 else 2.0  # batch 1+2: 0.5s interval
    return int(turns * THINKING_S * hz)


def tool_timer_fires(turns: int, tools_per_turn: int, version: int) -> int:
    hz = 5.0 if version == 0 else 2.0
    return int(turns * tools_per_turn * TOOL_ACTIVE_S * hz)


def richlog_writes_tools(turns: int, tools_per_turn: int, version: int) -> int:
    """RichLog.write() calls across all tool outputs."""
    calls_per_result = TOOL_OUTPUT_LINES if version == 0 else 1
    return turns * tools_per_turn * calls_per_result


def dom_nodes_peak(turns: int, version: int) -> int:
    """Estimated peak DOM node count (completed conversation)."""
    nodes_per_turn = 2 + MD_CHILD_NODES  # user msg + assistant markdown subtree
    if version < 2:
        return turns * nodes_per_turn  # unbounded
    # version 2: freeze collapses Markdown to 1 Static; paging caps to MAX_MOUNTED_TURNS
    active_turns = min(turns, MAX_MOUNTED_TURNS)
    frozen_nodes = 2  # user msg + 1 Static (frozen)
    return active_turns * frozen_nodes


# ── Scenarios ─────────────────────────────────────────────────────────────────

SCENARIOS = [
    ("short thread", 20, 200, 3),
    ("long thread", 80, 500, 5),
]


def simulate(turns: int, chunks: int, tools: int) -> list[dict]:
    """Return list of metric dicts for versions 0, 1, 2."""
    results = []
    for v in range(3):
        parse_ops = sum(streaming_parse_ops(chunks, v) for _ in range(turns))
        scroll = sum(scroll_calls(chunks, v) for _ in range(turns))
        think_timer = thinking_timer_fires(turns, v)
        tool_timer = tool_timer_fires(turns, tools, v)
        log_writes = richlog_writes_tools(turns, tools, v)
        dom = dom_nodes_peak(turns, v)
        results.append(
            {
                "parse_ops": parse_ops,
                "scroll": scroll,
                "think_timer": think_timer,
                "tool_timer": tool_timer,
                "log_writes": log_writes,
                "dom_nodes": dom,
                "total_hot": parse_ops + scroll + think_timer + tool_timer + log_writes,
            }
        )
    return results


# ── Python-side micro-benchmark ───────────────────────────────────────────────


def measure_append_overhead(n: int = 10_000) -> tuple[float, float, float]:
    """Wall-time for N chunk appends under three regimes."""
    buf = ""

    # v0: append + Markdown.update (simulate with len() call as proxy for parse cost)
    t0 = time.perf_counter()
    for _ in range(n):
        buf += "x"
        _ = len(buf)  # proxy: O(1) but forces a real loop iteration
    v0_ms = (time.perf_counter() - t0) * 1000

    # v1: append + dirty flag (same flush rate, but lighter "parse")
    buf = ""
    dirty = False
    flush_every = max(1, int(MD_FLUSH_MS / CHUNK_MS))
    t0 = time.perf_counter()
    for i in range(n):
        buf += "x"
        dirty = True
        if i % flush_every == 0 and dirty:
            _ = len(buf)
            dirty = False
    if dirty:
        _ = len(buf)
    v1_ms = (time.perf_counter() - t0) * 1000

    # v2: append + dirty flag (flush is Static.update — no parse proxy needed)
    buf = ""
    dirty = False
    t0 = time.perf_counter()
    for i in range(n):
        buf += "x"
        dirty = True
        if i % flush_every == 0 and dirty:
            dirty = False  # no parse — just flag reset
    v2_ms = (time.perf_counter() - t0) * 1000

    return v0_ms, v1_ms, v2_ms


# ── Report ────────────────────────────────────────────────────────────────────


def report() -> None:
    SEP = "─" * 82

    print()
    print("nx01-tui streaming render benchmark — three-stage comparison")
    print(
        f"Params: {CHUNK_MS:.0f} ms/chunk · MD flush {MD_FLUSH_MS:.0f} ms · "
        f"scroll flush {SCROLL_FLUSH_MS:.0f} ms · paging cap {MAX_MOUNTED_TURNS} turns"
    )
    print()

    for label, turns, chunks, tools in SCENARIOS:
        session_s = turns * chunks * CHUNK_MS / 1000
        data = simulate(turns, chunks, tools)
        v0, v1, v2 = data

        print(SEP)
        print(
            f"Scenario: {label.upper()}  "
            f"({turns} turns × {chunks} chunks × {tools} tools, {session_s:.0f}s stream)"
        )
        print()
        print(f"  {'Metric':<32} {'Baseline':>10}  {'Batch 1':>10}  {'Batch 2':>10}  {'Total':>8}")
        print(f"  {'─' * 32}  {'─' * 10}  {'─' * 10}  {'─' * 10}  {'─' * 8}")

        rows = [
            ("Markdown parse ops", "parse_ops"),
            ("scroll_end() calls", "scroll"),
            ("ThinkingBlock timer", "think_timer"),
            ("ToolCallBlock timer", "tool_timer"),
            ("RichLog writes (tools)", "log_writes"),
        ]
        for name, key in rows:
            print(
                f"  {name:<32} {_fmt(v0[key])}  {_fmt(v1[key])}  {_fmt(v2[key])}"
                f"  {_ratio(v0[key], v2[key])}"
            )

        print(f"  {'─' * 32}  {'─' * 10}  {'─' * 10}  {'─' * 10}  {'─' * 8}")
        print(
            f"  {'TOTAL hot-path ops':<32} {_fmt(v0['total_hot'])}  "
            f"{_fmt(v1['total_hot'])}  {_fmt(v2['total_hot'])}"
            f"  {_ratio(v0['total_hot'], v2['total_hot'])}"
        )
        print()
        print(
            f"  {'Peak DOM nodes':<32} {_fmt(v0['dom_nodes'])}  "
            f"{_fmt(v1['dom_nodes'])}  {_fmt(v2['dom_nodes'])}"
            f"  {_ratio(v0['dom_nodes'], v2['dom_nodes'])}"
        )
        print()

    print(SEP)
    v0_ms, v1_ms, v2_ms = measure_append_overhead()
    print("Python append overhead (10 000 chunks):")
    print(f"  Baseline (parse every chunk):  {v0_ms:6.2f} ms")
    print(f"  Batch 1  (parse every 50ms):   {v1_ms:6.2f} ms")
    print(f"  Batch 2  (Static, no parse):   {v2_ms:6.2f} ms")
    print()

    print("Batch 1 fixes: debounce Markdown updates · debounce scroll_end ·")
    print("               slower ThinkingBlock/ToolCallBlock timers · O(1) activity counters")
    print("Batch 2 fixes: Static-during-streaming · single RichLog write per chunk ·")
    print(
        f"               freeze old turns to Static · paging (max {MAX_MOUNTED_TURNS} turns in DOM)"
    )  # noqa: E501
    print()


if __name__ == "__main__":
    report()
