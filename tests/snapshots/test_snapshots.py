"""SVG snapshot tests — visual regression for key UI states.

Run `make snapshot-update` after intentional visual changes to regenerate
the SVG baselines. First-time runs always fail until baselines exist.

Live-animation states (thinking spinner, active tool pulse) are excluded —
they're inherently non-deterministic and would create flaky comparisons.
We snapshot stable states only: idle, post-turn, modals, error.

`snap_compare` is sync — these tests are not async.
"""

from __future__ import annotations

from nx01_tui.tui.app import Nx01App
from nx01_tui.tui.events import parse_event
from tests.fixtures.sample_events import chunk, skill_loaded, turn_done

_SIZE = (160, 40)


def test_snapshot_idle(snap_compare):
    """Fresh app, two flavor tabs, empty sidebar — base reference."""
    app = Nx01App("http://localhost:9999", api_key=None, flavors=["assistant", "operator"])
    assert snap_compare(app, terminal_size=_SIZE)


def test_snapshot_done_with_skill(snap_compare):
    """Post-turn: assistant reply visible, skill block, sidebar populated."""
    app = Nx01App("http://localhost:9999", api_key=None, flavors=["assistant"])

    async def run_before(pilot):
        await pilot.pause(0.3)
        app._dispatch_event(parse_event(skill_loaded(name="ci-setup", size=4096)))
        app._dispatch_event(parse_event(chunk(text="Done. CI workflow ready.")))
        app._dispatch_event(parse_event(turn_done()))
        await pilot.pause(0.2)

    assert snap_compare(app, terminal_size=_SIZE, run_before=run_before)


def test_snapshot_help_modal(snap_compare):
    """`?` reveals keybinding table over the cockpit."""
    app = Nx01App("http://localhost:9999", api_key=None, flavors=["assistant"])
    assert snap_compare(app, terminal_size=_SIZE, press=["question_mark"])


def test_snapshot_command_modal(snap_compare):
    """`ctrl+p` opens the central command hub."""
    app = Nx01App("http://localhost:9999", api_key=None, flavors=["assistant"])
    assert snap_compare(app, terminal_size=_SIZE, press=["ctrl+p"])
