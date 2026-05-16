"""Spinner widgets — wraps Rich spinners + custom star sequence."""

from __future__ import annotations

from rich.spinner import Spinner
from textual.widgets import Static


class SpinnerWidget(Static):
    """60fps refresh wrapping a Rich Spinner.

    Default: braille `dots` for thinking. Pass spinner_name to switch.
    """

    DEFAULT_CSS = """
    SpinnerWidget {
        width: 2;
        height: 1;
        color: $warning;
    }
    """

    def __init__(self, spinner_name: str = "dots", **kwargs: object) -> None:
        self._spinner = Spinner(spinner_name)
        super().__init__(self._spinner, **kwargs)

    def on_mount(self) -> None:
        self.set_interval(1 / 60, self.refresh)


class StarSpinner(Static):
    """Claude Code style star spinner: · ✻ ✽ ✶ ✳ ✢ at 8fps."""

    FRAMES = ("·", "✻", "✽", "✶", "✳", "✢")
    INTERVAL = 1 / 8

    DEFAULT_CSS = """
    StarSpinner {
        width: 2;
        height: 1;
        color: $success;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(self.FRAMES[0], **kwargs)
        self._frame = 0

    def on_mount(self) -> None:
        self.set_interval(self.INTERVAL, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(self.FRAMES)
        self.update(self.FRAMES[self._frame])
