"""Probe: keybinding conflicts between App-level and TextArea defaults.

TextArea's default BINDINGS swallow these keys when focused:
    ctrl+f -> delete_word_right
    ctrl+k -> delete_to_end_of_line_or_delete_line
    ctrl+c -> copy
    ctrl+y -> redo
    ctrl+u -> delete_to_start_of_line
    ctrl+d -> delete_right
    ctrl+w -> delete_word_left
    ctrl+a -> cursor_line_start
    ctrl+e -> cursor_line_end

Any App-level Binding bound to these without priority=True will be invisible to the
user when the chat input has focus — which is the steady-state focus.

This probe ENUMERATES the conflicts and reports each.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from textual.widgets import TextArea  # noqa: E402

from nx01_tui.tui.app import Nx01App  # noqa: E402


def main() -> int:
    text_area_keys = set()
    for b in TextArea.BINDINGS:
        for k in b.key.split(","):
            text_area_keys.add(k.strip())

    app_bindings = Nx01App.BINDINGS
    conflicts = []
    for b in app_bindings:
        for k in b.key.split(","):
            k = k.strip()
            if k in text_area_keys:
                if not b.priority:
                    conflicts.append((k, b.action))

    if conflicts:
        print("CONFLICTS (TextArea defaults will swallow these when input is focused):")
        for k, a in conflicts:
            print(f"  {k:15}  → action_{a}")
        return 1
    print("OK: no unresolved App vs TextArea keybinding conflicts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
