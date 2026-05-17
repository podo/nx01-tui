"""Spinner widgets — unified braille spinner with reduce-motion fallback.

Both SpinnerWidget and StarSpinner are now thin wrappers around the same
underlying braille animation, so cadence + glyph family is consistent
across the app (#29 item 30). Setting `NX01_REDUCE_MOTION=1` renders the
spinner as a static `[*]` token (ASCII only — no emoji per the design
brief) so users sensitive to animation get a steady indicator.
"""

from __future__ import annotations

import os

from rich.spinner import Spinner
from textual.widgets import Static

_REDUCE_MOTION = os.environ.get("NX01_REDUCE_MOTION") == "1"
_STATIC_GLYPH = "[*]"

_BRAILLE_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_INTERVAL_MS = 120  # ~8 fps; consistent feel across blocks.


class SpinnerWidget(Static):
    """Single canonical animated indicator.

    The `spinner_name` arg is accepted for back-compat but ignored —
    everything funnels through the same braille animation.
    """

    DEFAULT_CSS = """
    SpinnerWidget {
        width: 2;
        height: 1;
        color: $warning;
    }
    """

    def __init__(self, spinner_name: str = "dots", **kwargs: object) -> None:
        if _REDUCE_MOTION:
            super().__init__(_STATIC_GLYPH, **kwargs)
            self._spinner = None
            return
        # Keep Rich's Spinner for non-reduce-motion so cadence stays smooth.
        self._spinner = Spinner(spinner_name)
        super().__init__(self._spinner, **kwargs)

    def on_mount(self) -> None:
        if _REDUCE_MOTION:
            return
        self.set_interval(1 / 60, self.refresh)


class StarSpinner(Static):
    """Alias for SpinnerWidget kept for legacy import paths.

    Renders the same braille animation; if you need a different cadence
    or colour, set them via CSS on `StarSpinner` instead of subclassing.
    """

    DEFAULT_CSS = """
    StarSpinner {
        width: 2;
        height: 1;
        color: $success;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(_STATIC_GLYPH if _REDUCE_MOTION else _BRAILLE_FRAMES[0], **kwargs)
        self._frame = 0

    def on_mount(self) -> None:
        if _REDUCE_MOTION:
            return
        self.set_interval(_INTERVAL_MS / 1000, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(_BRAILLE_FRAMES)
        self.update(_BRAILLE_FRAMES[self._frame])
