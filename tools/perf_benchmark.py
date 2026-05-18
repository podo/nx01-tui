"""
tools/perf_benchmark.py — streaming render performance: old vs new.

Simulates two scenarios:
  A) Short thread:  20 turns × 200 chunks  = 4 000 chunks
  B) Long thread:   80 turns × 500 chunks  = 40 000 chunks

Chunk rate: 8 ms/chunk (typical LLM streaming throughput).

Run with:  uv run python tools/perf_benchmark.py
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


# ── Model ─────────────────────────────────────────────────────────────

@dataclass
class SimResult:
    scenario: str
    turns: int
    chunks_total: int
    chunk_ms: float
    # streaming
    md_updates_old: int = 0
    md_updates_new: int = 0
    scroll_old: int = 0
    scroll_new: int = 0
    # timers  (fires across entire session, all active blocks)
    thinking_timer_old: int = 0
    thinking_timer_new: int = 0
    tool_timer_old: int = 0
    tool_timer_new: int = 0


# ── Simulation helpers ────────────────────────────────────────────────

def sim_streaming(
    turns: int,
    chunks_per_turn: int,
    chunk_ms: float,
    md_flush_ms: float = 50.0,
    scroll_flush_ms: float = 100.0,
) -> tuple[int, int, int, int]:
    """Return (md_old, md_new, scroll_old, scroll_new) for N turns."""
    md_old = 0
    md_new = 0
    scroll_old = 0
    scroll_new = 0

    for _ in range(turns):
        turn_ms = chunks_per_turn * chunk_ms
        # old: 1 md.update() per chunk; 1 scroll_end per chunk
        md_old += chunks_per_turn
        scroll_old += chunks_per_turn
        # new: 1 flush per interval (+ 1 for finalise at end-of-turn)
        md_new += int(turn_ms / md_flush_ms) + 1
        scroll_new += int(turn_ms / scroll_flush_ms) + 1

    return md_old, md_new, scroll_old, scroll_new


def sim_timers(
    session_seconds: float,
    thinking_seconds_per_turn: float = 3.0,
    tool_active_seconds_per_turn: float = 2.0,
    turns: int = 1,
    thinking_old_hz: float = 10.0,
    thinking_new_hz: float = 2.0,
    tool_old_hz: float = 5.0,
    tool_new_hz: float = 2.0,
) -> tuple[int, int, int, int]:
    """Return (thinking_old, thinking_new, tool_old, tool_new) timer fires."""
    thinking_total_s = thinking_seconds_per_turn * turns
    tool_total_s = tool_active_seconds_per_turn * turns

    thinking_old = int(thinking_total_s * thinking_old_hz)
    thinking_new = int(thinking_total_s * thinking_new_hz)
    tool_old = int(tool_total_s * tool_old_hz)
    tool_new = int(tool_total_s * tool_new_hz)

    return thinking_old, thinking_new, tool_old, tool_new


# ── Scenarios ─────────────────────────────────────────────────────────

CHUNK_MS = 8.0  # 8 ms between tokens ≈ ~125 tokens/sec

SCENARIOS = [
    ("short thread", 20, 200),
    ("long thread",  80, 500),
]


def run() -> list[SimResult]:
    results = []
    for label, turns, chunks in SCENARIOS:
        chunks_total = turns * chunks
        session_seconds = chunks_total * CHUNK_MS / 1000

        md_old, md_new, scroll_old, scroll_new = sim_streaming(
            turns, chunks, CHUNK_MS
        )
        t_old, t_new, tool_old, tool_new = sim_timers(
            session_seconds,
            thinking_seconds_per_turn=3.0,
            tool_active_seconds_per_turn=2.0,
            turns=turns,
        )

        r = SimResult(
            scenario=label,
            turns=turns,
            chunks_total=chunks_total,
            chunk_ms=CHUNK_MS,
            md_updates_old=md_old,
            md_updates_new=md_new,
            scroll_old=scroll_old,
            scroll_new=scroll_new,
            thinking_timer_old=t_old,
            thinking_timer_new=t_new,
            tool_timer_old=tool_old,
            tool_timer_new=tool_new,
        )
        results.append(r)
    return results


# ── Also measure actual Python overhead ───────────────────────────────

def measure_append_overhead() -> tuple[float, float]:
    """Wall-time for 10 000 string appends: old (no dirty flag) vs new."""
    N = 10_000
    buf = ""
    update_count = 0

    # Old: append + call update every time
    t0 = time.perf_counter()
    for i in range(N):
        buf += "x"
        # simulate work done by Markdown.update (just counting here)
        update_count += 1
    old_ms = (time.perf_counter() - t0) * 1000

    # New: append + set dirty flag (update called 50ms/8ms ≈ 6x less often)
    buf = ""
    dirty = False
    flush_every = 6  # ~50ms / 8ms
    actual_updates = 0
    t0 = time.perf_counter()
    for i in range(N):
        buf += "x"
        dirty = True
        if i % flush_every == 0 and dirty:
            actual_updates += 1
            dirty = False
    if dirty:
        actual_updates += 1
    new_ms = (time.perf_counter() - t0) * 1000

    return old_ms, new_ms


# ── Report ────────────────────────────────────────────────────────────

def fmt_ratio(old: int, new: int) -> str:
    r = old / max(new, 1)
    return f"{r:.1f}x"


def report(results: list[SimResult]) -> None:
    SEP = "─" * 72
    print()
    print("nx01-tui streaming render benchmark")
    print(f"Chunk rate: {CHUNK_MS:.0f} ms/chunk  │  Markdown flush: 50 ms  │  Scroll flush: 100 ms")
    print()

    for r in results:
        session_s = r.chunks_total * r.chunk_ms / 1000
        print(SEP)
        print(f"Scenario: {r.scenario.upper()}  ({r.turns} turns × {r.chunks_total // r.turns} chunks = {r.chunks_total:,} chunks, {session_s:.0f}s stream)")
        print()
        print(f"  {'Metric':<30} {'Old':>8}  {'New':>8}  {'Savings':>8}")
        print(f"  {'─'*30}  {'─'*8}  {'─'*8}  {'─'*8}")
        print(f"  {'Markdown.update() calls':<30} {r.md_updates_old:>8,}  {r.md_updates_new:>8,}  {fmt_ratio(r.md_updates_old, r.md_updates_new):>8}")
        print(f"  {'scroll_end() calls':<30} {r.scroll_old:>8,}  {r.scroll_new:>8,}  {fmt_ratio(r.scroll_old, r.scroll_new):>8}")
        print(f"  {'ThinkingBlock timer fires':<30} {r.thinking_timer_old:>8,}  {r.thinking_timer_new:>8,}  {fmt_ratio(r.thinking_timer_old, r.thinking_timer_new):>8}")
        print(f"  {'ToolCallBlock timer fires':<30} {r.tool_timer_old:>8,}  {r.tool_timer_new:>8,}  {fmt_ratio(r.tool_timer_old, r.tool_timer_new):>8}")
        total_old = r.md_updates_old + r.scroll_old + r.thinking_timer_old + r.tool_timer_old
        total_new = r.md_updates_new + r.scroll_new + r.thinking_timer_new + r.tool_timer_new
        print(f"  {'─'*30}  {'─'*8}  {'─'*8}  {'─'*8}")
        print(f"  {'TOTAL DOM writes':<30} {total_old:>8,}  {total_new:>8,}  {fmt_ratio(total_old, total_new):>8}")
        print()

    print(SEP)
    old_ms, new_ms = measure_append_overhead()
    print(f"Python-side append overhead (10 000 chunks):")
    print(f"  Old (update every chunk): {old_ms:.2f} ms")
    print(f"  New (dirty flag only):    {new_ms:.2f} ms")
    print()


if __name__ == "__main__":
    report(run())
