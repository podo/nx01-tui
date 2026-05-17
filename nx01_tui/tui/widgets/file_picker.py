"""FilePickerDropdown — @ file reference autocomplete.

When the user types `@filename` in `ChatInput`, this dropdown floats
above the input showing fuzzy matches from the current working
directory. Selecting completes the path inline.
"""

from __future__ import annotations

import os
from pathlib import Path

from textual import on
from textual.binding import Binding
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

_IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".pytest_cache",
    "dist",
    "build",
}
_MAX_CANDIDATES = 200


class FilePickerDropdown(OptionList):
    """Floating list of project files; shown only while target text has `@`."""

    DEFAULT_CSS = """
    FilePickerDropdown {
        display: none;
        dock: top;
        height: auto;
        max-height: 8;
        border: round $accent;
        background: $surface;
    }
    FilePickerDropdown.visible { display: block; }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("tab", "complete", "Complete", show=False),
        Binding("enter", "complete", "Complete", show=False),
    ]

    class Completed(Message):
        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    def __init__(self, root: Path | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._root = Path(root) if root else Path.cwd()
        # Lazy-scan on first `@` keystroke — keeps app boot cheap (matters on
        # slow CI; os.walk on a large repo can add 100ms+).
        self._candidates: list[str] | None = None

    def _ensure_scanned(self) -> list[str]:
        if self._candidates is None:
            self._candidates = self._scan()
        return self._candidates

    def _scan(self) -> list[str]:
        results: list[str] = []
        try:
            for dirpath, dirnames, filenames in os.walk(self._root):
                # Mutate dirnames in-place to prune ignored dirs.
                dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
                rel_dir = Path(dirpath).relative_to(self._root)
                for name in filenames:
                    if name.startswith("."):
                        continue
                    rel = (rel_dir / name).as_posix() if str(rel_dir) != "." else name
                    results.append(rel)
                    if len(results) >= _MAX_CANDIDATES:
                        return results
        except OSError:
            pass
        return sorted(results)

    def update_for_text(self, text: str) -> None:
        """Show / hide based on whether the buffer contains `@<token>`."""
        token = _extract_at_token(text)
        if token is None:
            self.remove_class("visible")
            return
        self._populate(token)
        if self.option_count > 0:
            self.add_class("visible")
            if self.highlighted is None:
                self.highlighted = 0
        else:
            self.remove_class("visible")

    def _populate(self, query: str) -> None:
        self.clear_options()
        q = query.lower()
        for path in self._ensure_scanned():
            if q and q not in path.lower():
                continue
            self.add_option(Option(f"📄  {path}", id=path))

    def action_dismiss(self) -> None:
        self.remove_class("visible")

    def action_complete(self) -> None:
        if self.highlighted is None or self.option_count == 0:
            return
        opt = self.get_option_at_index(self.highlighted)
        if opt and opt.id:
            self.post_message(self.Completed(opt.id))
            self.remove_class("visible")

    @on(OptionList.OptionSelected)
    def _on_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.post_message(self.Completed(event.option.id))
            self.remove_class("visible")


def _extract_at_token(text: str) -> str | None:
    """Return the trailing `@token` substring (after the @, no whitespace), or None."""
    # Find the last `@` in the buffer; require it's at start of buffer OR
    # preceded by whitespace; and that no whitespace appears after.
    i = text.rfind("@")
    if i < 0:
        return None
    if i > 0 and not text[i - 1].isspace():
        return None
    candidate = text[i + 1 :]
    if any(ch.isspace() for ch in candidate):
        return None
    return candidate
