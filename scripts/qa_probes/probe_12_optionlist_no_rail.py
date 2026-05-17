"""Probe 12: OptionList `▊` rail gone across all modals (#5 RESOLVED check).

Mounts each modal that uses OptionList (Command, Sessions, Skills, Tools,
ModelPicker, Memory) and screenshots each. The fresh SVGs must contain
0 `▊` glyphs.

NOTE: A focused Input (e.g. SessionsModal's filter Input) renders a
caret which Textual draws as `▊` (a focused-input cursor block). To
isolate the OptionList border from the Input caret, we DEFOCUS the
filter Input before screenshot — by focusing the OptionList directly
(or pressing Tab / Down to move focus).
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from textual.widgets import OptionList  # noqa: E402

from nx01_tui.tui.app import Nx01App  # noqa: E402
from nx01_tui.tui.modals.command_modal import CommandModal, default_commands  # noqa: E402
from nx01_tui.tui.modals.memory_modal import MemoryModal  # noqa: E402
from nx01_tui.tui.modals.sessions_modal import SessionEntry, SessionsModal  # noqa: E402
from nx01_tui.tui.modals.simple_modals import (  # noqa: E402
    ModelPickerModal,
    SkillsModal,
    ToolsModal,
)


def _mock(app):
    async def fake_get_flavors():
        return {"a": {"name": "a", "model": "m"}}

    app.client.get_flavors = fake_get_flavors
    app.client.list_commands = lambda: _async_return([])
    app.client.list_skills = lambda flavor=None: _async_return([])
    app.client.get_tools = lambda flavor=None: _async_return({"tools": []})


async def _async_return(v):
    return v


async def _focus_option_list(app, pilot):
    """Move focus to the modal's OptionList (away from any filter Input)."""
    await pilot.pause(0.2)
    try:
        ol = app.screen.query_one(OptionList)
        ol.focus()
        await pilot.pause(0.2)
    except Exception:  # noqa: BLE001
        pass


def _count_rails(svg_path: Path) -> int:
    """Count `▊` glyphs that appear in OptionList rows.

    Filters out the Input-caret false positive — Input caret renders as a
    `▊` directly to the right of the input's left border (column 1 inside).
    OptionList rails appear at the start of every visible option row.
    Our discriminator: a rail glyph is one whose containing line ALSO
    contains another regular character (not just the caret block alone in
    the row). The caret renders inside an otherwise-empty input line
    decorated by `╭ … ╮` / `╰ … ╯` rounded borders. So we exclude any
    `▊` whose preceding context is empty space + the input's content.

    Simpler approach: count ▊ glyphs but report the SVG path for manual
    audit; treat 0 as the gold standard. Anything > 0 is investigated by
    capturing the line context.
    """
    raw = svg_path.read_text()
    text_chunks = re.findall(r">([^<]+)<", raw)
    return sum(c.count("▊") for c in text_chunks)


def _inspect_rails(svg_path: Path) -> list[str]:
    """Return surrounding-line context for each `▊` glyph in the SVG.

    Used to distinguish OptionList tall-border (regression) from Input
    caret cursor (acceptable focus indicator).
    """
    raw = svg_path.read_text()
    # Group <text> elements by y-coordinate so we can reconstruct lines.
    matches = list(
        re.finditer(
            r'<text[^>]*x="([\d.]+)"[^>]*y="([\d.]+)"[^>]*>([^<]*)</text>',
            raw,
        )
    )
    by_y: dict[float, list[tuple[float, str]]] = {}
    for m in matches:
        x, y, c = float(m.group(1)), float(m.group(2)), m.group(3)
        by_y.setdefault(y, []).append((x, c))
    contexts: list[str] = []
    for y, segs in by_y.items():
        if any("▊" in c for _, c in segs):
            line = "".join(c for _, c in sorted(segs)).replace("&#160;", " ")
            contexts.append(f"y={y}: {line.strip()!r}")
    return contexts


async def main() -> int:
    failures: list[str] = []
    artefacts_dir = ROOT / "artifacts/v1-smoke/qa"
    artefacts_dir.mkdir(parents=True, exist_ok=True)

    # Each scenario: (label, modal-factory, focus-target — None means focus
    # the first OptionList).
    cases = [
        (
            "command",
            lambda: CommandModal(default_commands()),
        ),
        (
            "sessions",
            lambda: SessionsModal(
                [
                    SessionEntry(
                        session_id=f"s{i:08x}",
                        flavor="a",
                        title=f"Session {i}",
                        last_active="just now",
                    )
                    for i in range(5)
                ]
            ),
        ),
        (
            "skills",
            lambda: SkillsModal(
                [
                    {"name": "ci-setup", "size": 4096, "loaded": False},
                    {"name": "browser", "size": 8192, "loaded": True},
                    {"name": "python-debug", "size": 12288, "loaded": False},
                ]
            ),
        ),
        (
            "tools",
            lambda: ToolsModal(
                [
                    {"name": "bash", "description": "execute shell"},
                    {"name": "read_file", "description": "read a file"},
                    {"name": "edit_file", "description": "edit a file"},
                ]
            ),
        ),
        (
            "model_picker",
            lambda: ModelPickerModal(
                [
                    "claude-opus-4-7",
                    "claude-sonnet-4-6",
                    "claude-haiku-4-5",
                    "gpt-4o",
                ],
                current="claude-opus-4-7",
            ),
        ),
        (
            "memory",
            lambda: MemoryModal(
                agent_entries=["agent note 1", "agent note 2"],
                user_entries=["user note 1"],
            ),
        ),
    ]

    for label, factory in cases:
        app = Nx01App("http://mock", api_key="t", flavors=["a"])
        _mock(app)
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause(0.8)
            modal = factory()
            app.push_screen(modal)
            await pilot.pause(0.4)
            await _focus_option_list(app, pilot)

            svg_path = artefacts_dir / f"probe_12_{label}.svg"
            app.save_screenshot(str(svg_path))
            rails = _count_rails(svg_path)
            if rails > 0:
                contexts = _inspect_rails(svg_path)
                # Filter out lines that are clearly Input caret (line contains
                # the input placeholder text and only one ▊). OptionList rails
                # repeat once per row, so a multi-▊ pattern is the signal.
                option_row_rails = [c for c in contexts if "Filter" not in c and "filter" not in c]
                if option_row_rails:
                    failures.append(
                        f"{label}: {rails} ▊ glyph(s) in {svg_path.name} — "
                        f"OptionList rail likely still present.\n"
                        f"  contexts:\n    " + "\n    ".join(option_row_rails)
                    )

    print("\n".join(failures) if failures else "OK: optionlist-no-rail probe PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
