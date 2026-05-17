# nx01-tui v1.0 — QA Audit Report

_Adversarial verification of the design pass merged in 615e28a (PR #30 / branch
`feat/v1-design-pass`). Each of the 34 audit items in DESIGN-REVIEW.md is
re-verified by inspecting source, grepping fresh smoke SVGs, and running
9 dedicated probe scripts under `scripts/qa_probes/`. Probes save fresh
screenshots to `artifacts/v1-smoke/qa/`._

## 1. Executive summary

**Stats**
- ✅ PASS: 19 / 34
- ⚠️ PARTIAL: 8 / 34
- ❌ MISSING: 0 / 34
- 🐛 BROKEN: 7 / 34

The design pass is **not ready to ship** as a v1.0 milestone. Of the 4 Critical
items, 2 functionally landed (#1, #4) and 2 are broken (#2 SearchBar, #3 mostly
PASS but dead CSS leftover). Of the 8 High items, 5 PASS, 2 BROKEN (#5
OptionList rail, #12 slash badge), 1 PARTIAL (#10 backdrop). A separate cluster
of bugs surfaced beyond the 34 — most importantly three App-level shortcuts
(`ctrl+f`, `ctrl+k`, `ctrl+c`) are unreachable from `ChatInput` because they're
not declared `priority=True` and TextArea's defaults swallow them.

**Top-3 most-impactful issues**

1. 🐛 **Item 24 (BROKEN)** — `AssistantMessage` renders the literal text
   `[bold $primary]── assistant ──[/]` on screen, every assistant turn.
   `AssistantMessage` extends `Markdown` which does NOT interpret Rich tags. A
   visible markup leak in the most-rendered widget in the app.
2. 🐛 **NEW — keybinding conflicts** — `ctrl+f` (Search), `ctrl+k` (Skills),
   `ctrl+c` (Stop) all bound at App-level without `priority=True`. TextArea
   binds the same keys to its editor defaults. Steady-state focus is the chat
   input, so these documented shortcuts simply don't fire.
3. 🐛 **Item 2 (BROKEN)** — `SearchBar { height: 1 }` survives in
   `app.tcss:60` and overrides the widget's own DEFAULT_CSS (`height: 3`).
   Rendered as a 0-cell-tall invisible shell. `ctrl+f` (even if reachable)
   shows nothing.

**Verdict.** The design pass is a clear visual improvement (StatusBar visible,
Footer gone, V2 rows hidden, Permission risk variants distinct, ConfirmModal
danger styling, header `┃` separators, MemoryModal copy, CostModal columns),
but several Rich-markup choices and CSS override conflicts mean the user-facing
result has at least 5 visible regressions on the happy path. Two further
findings — `q quit` lying in the conversation empty-state copy, and the
`Quit` row in the command palette still showing keybind `q` — are 1-line
cleanups missed in the same PR. Recommend a follow-up "polish" PR addressing
the Critical/High broken items before tagging v1.0.

> **Note on stale evidence.** REPORT.md still references S40, S41, S46–S50,
> S55 — those SVGs in `artifacts/v1-smoke/` are timestamped 13:11 (pre design
> pass). The current smoke runner only produces S01–S15. Items the original
> audit pinned to those captures (e.g. C1's "5 state captures all identical")
> had to be re-checked against fresh probe screenshots in `qa/`.

---

## 2. Item-by-item verification

Column legend: ✅ PASS / ⚠️ PARTIAL / ❌ MISSING / 🐛 BROKEN.
"Implementation" points to the file:lines that landed the change.
"Fix" is set when not PASS.

| # | Title | Expected | Verdict | Implementation | Fix location |
|---|---|---|---|---|---|
| 1 | StatusBar visibility | Bottom bar shows `Ready/Thinking…` etc. | ✅ PASS | `widgets/status_bar.py:28-78`, `app.py:151` | — |
| 2 | SearchBar height + border | `height: 3` so round border + caret render | 🐛 BROKEN | `widgets/search_bar.py:19` sets `height:3` but `app.tcss:60` overrides to `height:1`; final rendered size = 0×N | `app.tcss:60` — delete the `height:1` line OR raise to `height:3` |
| 3 | Sidebar hides below 130 | No empty icon-strip; hidden entirely | ⚠️ PARTIAL | `widgets/sidebar.py:354-365` — correct logic; probe_05 confirms all breakpoints | Dead leftover: `app.tcss:72` + `sidebar.py:303` still declare `MonitorSidebar.icon-strip { width: 3 }` — class never applied. Remove. |
| 4 | PermissionModal risk variants | Border + button order + focus per risk | ✅ PASS | `modals/permission_modal.py:25-101`; probe_04 confirms low→`│` round / med→`█` thick / high→`┃` heavy + Always button hidden on high | — |
| 5 | OptionList rail (`▊`) gone | Flat highlighted row, no per-row rail | 🐛 BROKEN | `app.tcss:26-31` added `option-list--option-highlighted { background: $boost }`. But `▊` is OptionList's own `border: tall $border-blurred` (Textual default), drawn on EVERY row, not just highlighted. CSS targets the wrong selector. SVG count: 37 `▊` glyphs in `s06_command_modal.svg` | `app.tcss` add `OptionList { border: none; padding: 0 1 }` (or compact-class) — kills the rail. Re-introduce a single-cell highlighted indicator if desired. |
| 6 | Memory bar overflow surface | `+over · /compact` when used>limit | ✅ PASS | `widgets/sidebar.py:120-129` — `_label()` appends `+{over:,} over · /compact` | — |
| 7 | Emoji dropped | One monochrome glyph family | ⚠️ PARTIAL | Removed all named offenders (`📄🔧⚡§`). `widgets/file_picker.py:107` uses `▣`; `simple_modals.py:35,65` use `◆ ▸`; `skill_block.py:51` uses `◆`. Only **leftover**: `permission_modal.py:73` still emits `⚠` (Unicode warning sign, 2-cell on many terminals). UserMessage divider `── you ──` still shows `▊` rail (item 7 sub-goal: soften it) — see notes below. | `modals/permission_modal.py:73` drop the `⚠` glyph |
| 7b | UserMessage soft rail | `tall` not `thick`; dim body | ⚠️ PARTIAL | `widgets/messages.py:10-16` switched to `border-left: tall $primary` + `color: $text-muted`. Rendered as `▊` glyph — narrower than `thick` but still a vertical block. Body dimmed: PASS. Visually the user turn still reads as heavy when stacked next to a broken AssistantMessage (item 24). | Consider `border-left: none` + `padding-left: 2`, or use a left-text-bar via Static for full softness. |
| 8 | (renamed 9 in numbering) — see #9 | | | | |
| 9 | SearchBar Enter/Shift+Enter | No more ctrl+n / ctrl+p collision | ✅ PASS | `widgets/search_bar.py:30-31` binds `enter` and `shift+enter`; `modals/help_modal.py:33-34` advertises them; ctrl+n/ctrl+p removed | — |
| 10 | Modal backdrop dim | Stacked modals reveal previous | ⚠️ PARTIAL | `modals/base.py:18` sets `background: $background 70%`. Probe_04 stacked SessionsModal under ConfirmModal: SVG contains no `Sessions` or session entry text — the previous modal is hidden under a near-opaque backdrop. Mechanism exists but doesn't achieve the audit's goal of "still hint at the layer beneath". | `modals/base.py:18` lower to `$background 50%` or render the previous modal explicitly at reduced opacity (e.g. via `Screen.layers` + per-layer opacity). |
| 11 | Thinking single indicator | Spinner only while streaming, chevron only after `done()` | ✅ PASS | `widgets/thinking_block.py:63-78` — chevron created with `display=False`; `done()` swaps; `set_collapsed(True)` while `thinking=True` is no-op (line 127-128). Probe_01 confirms. | — |
| 12 | Slash dropdown badge colors | `cmd→$primary · skill→$accent · tool→$success`, badge in `[ cat ]` | 🐛 BROKEN | `widgets/slash_dropdown.py:158-161` — nested-tag string `[{cat_color}][[/]...` produces literal artefacts. probe_09 SVG shows `[[/] cmd  ]` rendered as literal characters. Categories DO carry the right tuple, but the rendered output is `▶ [[/] cmd  ]` instead of `[ cmd ]`. | Replace with: `f"[{cat_color}]\[ {cat_label:<5}\][/]"` (escape brackets with `\[` and `\]`) OR build with `rich.text.Text` and append colored segments. |
| 13 | CostModal columns + ratio | Session vs Lifetime columns; in/out bar | ✅ PASS | `modals/simple_modals.py:90-148` — verified via probe_07 (`probe_07_cost_populated.svg`). Empty state: ratio_bar() returns `""` cleanly (no crash). | — |
| 14 | Command palette no V2 + no Filter | V2 rows hidden; no filter Input | ✅ PASS | `modals/command_modal.py:109-145` — no Input widget; `if not cmd.enabled: continue`; smoke S06 verifies `emoji_free=True · no_filter=True · no_v2=True` | — |
| 15 | Memory empty store-specific copy | Different hint per Agent/User tab | ✅ PASS | `modals/memory_modal.py:46-73` — store-specific dict; probe_07 SVG shows agent hint copy. | — |
| 16 | DebugModal footer row | Buttons separated from filter input | ✅ PASS | `modals/debug_modal.py:28-63` — three Buttons inside `#footer-row` Horizontal; probe_07 SVG confirms `Pause (p) Clear (ctrl+l) Copy (ctrl+y)` row. | — |
| 17 | HelpModal scrollable + row cursor | `cursor_type="row"`, `height: 1fr` | ✅ PASS | `modals/help_modal.py:53-64`; probe_07 confirms cursor_type==row. New `Ctrl+Q`, `Ctrl+1..9`, `Enter`/`Shift+Enter` rows present (lines 23, 33, 34). | — |
| 18 | Header model auto-pick + dim fallback | Empty → `[dim italic]no model[/]`; otherwise picked from /flavors | ✅ PASS | `widgets/header.py:33,71`; `app.py:174-178,214-229` `_pick_first_model` extracts first `.model` from snapshot. s01 SVG shows `claude-opus-4-7` correctly picked. | — |
| 19 | Auth-failed → short `AUTH` tag + toast | Long suffix in toast not header | ✅ PASS | `widgets/header.py:62-63` outputs `[bold $error]AUTH[/]`; `app.py:184-189` notifies. Renders via Static (Rich-aware) so no markup leak (contrast with item 24). | — |
| 20 | ConfirmModal dangerous chrome | $error border, No focused, "cannot be undone" | ✅ PASS | `modals/confirm_modal.py:14-71`; probe_04 SVG: `│ No (n)  Yes (y) │` order + `This cannot be undone.` + focus on `#no` | — |
| 21 | FlavorPane state ribbon | Top-of-pane redundant state cue | ✅ PASS | `widgets/flavor_pane.py:22-91` — ribbon Static + per-state CSS. probe_07 `probe_07_pane_thinking.svg` shows `Thinking…` label. | — |
| 22 | ToolCallBlock chevron watcher | `watch_collapsed` reactive drives chevron | ✅ PASS | `widgets/tool_call_block.py:177-190`; probe_01 toggles `collapsed` reactive directly and verifies chevron + class. | — |
| 23 | Slash insertion column max-width | Stable column rhythm | ✅ PASS | `widgets/slash_dropdown.py:152-157` — pads to `max_w` capped at 32. Visible in s02 SVG (`/help          ` etc.). | — |
| 24 | AssistantMessage divider | Symmetric `── assistant ──` divider | 🐛 BROKEN | `widgets/messages.py:35-36` — uses `[bold $primary]── assistant ──[/]\n` injected into a **`Markdown`** widget. Markdown does not parse Rich tags. probe_08 + s15 SVG show literal `[bold $primary]── assistant ──[/]` on screen. | `widgets/messages.py:23-44` — either (a) emit divider as separate `Static` mounted above the Markdown widget, or (b) use Markdown syntax (`**── assistant ──**` doesn't accept color but at least it's bold). Recommended (a). |
| 25 | Footer overflow indicator gone | No `▏^p Commands` artefact | ✅ PASS | `app.py:148-151` — Footer removed entirely; smoke S01 SVG bottom row shows only StatusBar. | — |
| 26 | TabbedContent underline restyle | Solid coloured underline | ⚠️ PARTIAL | `app.tcss:17-20` overrides `color/background` on `.underline--bar`. Color likely applied, but the **glyph shape** is still Textual's default `╸━━━━━╺` rounded pill (visible in s01 SVG). | Glyph shape can't be changed via CSS; the pill is Textual's render. Either accept (color does fix the worst of it) or subclass `Underline` for a custom render. |
| 27 | ChatInput placeholder | `Type to chat · /help · @file` | ✅ PASS | `widgets/chat_input.py:60` `placeholder=`; s01 SVG shows it. | — |
| 28 | Skills modal hint enriched | `enter toggle · / filter · ESC close` | ✅ PASS | `modals/simple_modals.py:42`. | — |
| 29 | Tools modal V2 callout | Static row above the list | ✅ PASS | `modals/simple_modals.py:55-60` `.dialog-callout` Static. probe_07 confirms one `.dialog-callout` Static present. | — |
| 30 | Spinner unified + REDUCE_MOTION | One braille frame, env-var fallback | ✅ PASS | `widgets/spinner.py:17-80` — both `SpinnerWidget` and `StarSpinner` route through the same braille set or `[*]` ASCII fallback. | — |
| 31 | Snapshot `&#x27;` decoded | Apostrophes plain in SVGs | ⚠️ PARTIAL | `scripts/v1_visual_smoke.py:109-114` replaces `&#x27;` → `&apos;`. **But other widgets emit `&apos;` already** (e.g. `s15` text shows `I&apos;ll write` in raw SVG). The decode swaps one entity for another, neither is the plain `'` glyph. | `scripts/v1_visual_smoke.py:112` change `"&apos;"` → `"'"` (or decode both `&#x27;` and `&apos;` to literal `'`). |
| 32 | SkillBlock placeholder copy | `Loading skill manifest…` not `_(skill content not yet streamed)_` | ✅ PASS | `widgets/skill_block.py:45` `"_Loading skill manifest…_"`. Still wrapped in Markdown underscore italic — could be cleaner via Static. | — |
| 33 | `q` → `ctrl+q` quit | Plain `q` no longer quits | ⚠️ PARTIAL | `app.py:102` rebinds. **But two follow-up leftovers**: (1) `widgets/conversation.py:31` empty hint still says `[bold]q[/] quit`; (2) `modals/command_modal.py:73` `CommandEntry("quit", ..., keybind="q", ...)` so the command palette row labels the shortcut as `q`. Both visible to user. | (1) `widgets/conversation.py:31` change `q quit` → `ctrl+q quit`. (2) `modals/command_modal.py:73` change `keybind="q"` → `keybind="ctrl+q"`. |
| 34 | Header `┃` separators | Identity / state / model segments | ✅ PASS | `widgets/header.py:61` declares `sep = "[dim]┃[/]"`. s01 SVG: `NX01 ┃ mock reconnecting ┃ claude-opus-4-7`. | — |

---

## 3. Detailed findings (non-PASS items)

### 🐛 Item 24 — AssistantMessage divider renders Rich markup as text — **Critical**

**Where**: `nx01_tui/tui/widgets/messages.py:23-44`

**Repro**: stream any assistant message; alternately run
`scripts/qa_probes/probe_08_assistant_divider_bug.py`. SVG at
`artifacts/v1-smoke/qa/probe_08_assistant_divider.svg` shows the literal text:
```
[bold $primary]── assistant ──[/] Hi there, the answer is **forty-two**.
```

**Root cause**: `AssistantMessage` extends `textual.widgets.Markdown`. The
`_role_label = "[bold $primary]── assistant ──[/]\n"` is **prepended to the
markdown source string**. `Markdown` does not interpret Rich tags — it only
parses CommonMark. So the `[bold ...]` opens are passed through as literal
characters (escaped in HTML, but rendered as text in the terminal).

**Severity**: Critical — visible on every assistant turn.

**Proposed fix** (≤10 lines, replace the `AssistantMessage` class):

```python
class AssistantMessage(Vertical):
    DEFAULT_CSS = "AssistantMessage { height: auto; margin: 0 0 1 0; }"
    def __init__(self, initial: str = "", **kwargs):
        super().__init__(**kwargs)
        self._buffer = initial
        self._md: Markdown | None = None
    def compose(self):
        yield Static("[bold $primary]── assistant ──[/]")
        self._md = Markdown(self._buffer); yield self._md
    def append(self, text: str):
        self._buffer += text
        if self._md: self._md.update(self._buffer)
    def finalise(self): pass
```

---

### 🐛 Item 5 — OptionList `▊` rail on every row — **High**

**Where**: All modals using `OptionList` (Command, Sessions, Skills, Tools,
ModelPicker). CSS: `app.tcss:26-31`.

**Repro**: open the command palette (ctrl+p) — observe a `▊` vertical block
on the left of every row, even non-highlighted ones. SVG count: 37
instances of `▊` in `s06_command_modal.svg`.

**Root cause**: The `▊` is **Textual's `OptionList` default border-left**
(`border: tall $border-blurred` in OptionList's own DEFAULT_CSS). The
audit blamed it on `option-list--option-highlighted` and the design pass
overrode that selector — but the highlighted-row chrome is the row
background, not the rail. The rail is a border.

**Severity**: High — dominant visual element across 5 modals.

**Proposed fix** in `app.tcss`:

```css
OptionList {
    border: none;
    background: $surface;
    padding: 0 1;
}
OptionList:focus { border: none; background-tint: $foreground 5%; }
```

If a focused-row indicator is still wanted, render a one-cell `▶` glyph on
the highlighted Option's prompt instead.

---

### 🐛 Item 12 — Slash dropdown badge artefact `[[/]` — **High**

**Where**: `nx01_tui/tui/widgets/slash_dropdown.py:154-161`

**Repro**: type `/` in chat input. Each completion row ends with literal
`[[/] cmd  ]` instead of `[ cmd ]`. Probe_09 confirms.

**Root cause**: nested Rich tags around literal brackets:

```python
f"[{cat_color}][[/][{cat_color}] {cat_label:<5}[/][{cat_color}]][/]"
```

Rich's parser leaves stray `[` and `]` because the escape pattern is
malformed (opens `[$primary]` then immediately attempts another `[/]`).

**Severity**: High — visible whenever user types `/`.

**Proposed fix** (one-line replacement):

```python
label = (
    f"[bold]{padded}[/]  [dim]{desc}[/]  "
    rf"[{cat_color}]\[ {cat_label:<5}\][/]"
)
```

The raw-string `\[` and `\]` are Rich's literal-bracket escapes inside a
markup span.

---

### 🐛 Item 2 — SearchBar `height: 1` shadow — **Critical**

**Where**: `nx01_tui/tui/app.tcss:60`

**Repro**: probe instrumentation shows `bar.styles.height == 1` and
`bar.size == Size(width=142, height=0)` after `bar.show()`. SVG at
`artifacts/v1-smoke/qa/probe_searchbar_height.svg` has no placeholder
text rendered.

**Root cause**: app-level stylesheet override beats the widget's own
DEFAULT_CSS. The line `SearchBar { ... height: 1; border: round $primary }`
in `app.tcss:60` overrides the widget's `height: 3` rule. With a round
border at height=1, content row is squeezed to 0.

**Severity**: Critical — ctrl+f shows nothing.

**Proposed fix**: delete `app.tcss:60-61` lines (the widget's DEFAULT_CSS
already provides display/dock/border/height correctly).

---

### ⚠️ Item 33 — `q quit` lingers in two places — **Medium**

**Where**:
1. `nx01_tui/tui/widgets/conversation.py:31` — empty-conversation hint
   reads: `ctrl+p command palette · ? help · q quit`.
2. `nx01_tui/tui/modals/command_modal.py:73` — `CommandEntry("quit", "Quit",
   "Exit the application", "q", "System")` — keybind labelled `q` in palette.

**Repro**: fresh app boot (S01 SVG line: `ctrl+p command palette · ? help ·
q quit`); open command palette (S06 SVG: `Quit  Exit the application q`).

**Severity**: Medium — UI lies about the actual binding.

**Proposed fix**: change both literals to `ctrl+q`.

---

### ⚠️ Item 10 — Modal backdrop dim too opaque — **Medium**

**Where**: `nx01_tui/tui/modals/base.py:18` `background: $background 70%`.

**Repro**: probe_04 stacked ConfirmModal over SessionsModal. The SVG
contains no Session entry text — the underlying modal is fully obscured.

**Severity**: Medium — feature exists, doesn't achieve the audit's stated
goal ("still hint at the layer beneath").

**Proposed fix**:

```css
BaseModal { background: $background 40%; }  /* 60% transparent */
```

Or compose the previous screen explicitly at low opacity (Textual
`screen_stack` + `compose` override on `BaseModal`).

---

### ⚠️ Item 3 — Dead `icon-strip` CSS — **Low**

`MonitorSidebar.icon-strip { width: 3 }` survives in both
`app.tcss:72` and `widgets/sidebar.py:303`. The class is never applied
(item 3 removed icon-strip mode in favour of full-hide below 130 cols).
Just dead code. Remove for clarity.

---

### ⚠️ Item 26 — TabbedContent underline pill shape unchanged — **Low**

`app.tcss:17-20` overrides `.underline--bar` color but the pill glyph
`╸━━━━╺` is Textual's default render. Color presumably tinted, glyph
unchanged. Low priority — accept or subclass `Underline`.

---

### ⚠️ Item 31 — `&apos;` artefact still in SVGs — **Low**

The decode in `v1_visual_smoke.py:112` swaps `&#x27;` for `&apos;` — both
are HTML entities. Plain `'` is what the original audit suggested. Other
widget content already emits `&apos;` directly (e.g. s15 contains
`I&apos;ll write`).

**Fix**: `cleaned = raw.replace("&#x27;", "'").replace("&apos;", "'")`.

---

### ⚠️ Item 7 — `⚠` emoji in PermissionModal title — **Low**

`modals/permission_modal.py:73`: `Static("[bold red]⚠ Tool Permission
Required[/]")`. Inconsistent with the item 7 "no emoji" commit. `⚠`
(U+26A0) renders as 1- or 2-cell depending on terminal — exactly the
column-alignment issue the audit warned about.

**Fix**: drop the `⚠`, lean on the red title + thick border.

---

## 4. New issues beyond the 34

### 🐛 N1 — App-level keybindings unreachable from ChatInput — **Critical**

**Where**: `nx01_tui/tui/app.py:91-119` + `textual.widgets.TextArea.BINDINGS`

**Repro**: `uv run python scripts/qa_probes/probe_03_input_keybinding_conflicts.py`

```
CONFLICTS (TextArea defaults will swallow these when input is focused):
  ctrl+k           → action_open_skills
  ctrl+f           → action_search
  ctrl+c           → action_stop_generation
```

**Root cause**: App BINDINGS for `ctrl+f`, `ctrl+k`, `ctrl+c` lack
`priority=True`. TextArea (`ChatInput`'s parent) binds the same keys to
`delete_word_right`, `delete_to_end_of_line`, `copy`. Focused widget wins.

**Severity**: Critical — three documented shortcuts (Search, Skills, Stop)
silently do nothing for the user (steady-state focus is the chat input).

**Proposed fix**: add `priority=True` (matching the Tab + Ctrl+1..9 pattern
that already does this for flavor switching):

```python
Binding("ctrl+f", "search", "Search", show=True, priority=True),
Binding("ctrl+k", "open_skills", "Skills", show=False, priority=True),
Binding("ctrl+c", "stop_generation", "Stop", show=True, priority=True),
```

Additionally consider `ctrl+y` (yank_last_code) and `ctrl+u/d/w/a/e` if any
get used.

---

### 🐛 N2 — `y` / `Y` (yank) bindings unreachable from input — **High**

**Where**: `app.py:105-106` plain `y` and `Y` bound as app-level Bindings
without priority. Normal keystrokes in TextArea — pressed `y`, the
character is typed; the action never fires. The Help modal advertises
`y` and `Y`.

**Fix**: either remove the bindings + delete the Help rows, or move to
`ctrl+y` (taken by TextArea redo — needs priority) / `alt+y`.

---

### 🐛 N3 — `e` in SessionsModal → silent no-op — **Medium**

**Where**: `modals/sessions_modal.py:135-138` dismisses with
`SessionAction("rename", …)`. **No `rename` branch** in
`app.py:_handle_session_action` (lines 561-578). Pressing `e` returns
control to the App which silently ignores the action.

The Sessions modal hint advertises `e rename`; the Help modal advertises
`f / e / d` for `Fork / Edit / Delete`.

**Fix**: implement a rename flow (e.g. push a small Input modal, call
`client.rename_session`), or remove the binding + Help row.

---

### ⚠️ N4 — Smoke runner asserts state, not pixels — **Medium**

The original audit's C1 was missed for the same reason — `S29` claimed
"passed=True" because `bar.state == THINKING` even though the StatusBar
was not visible. The current smoke does not verify visual output (no
snapshot assert on `qa/` SVGs). A regression in `app.tcss` (like the
SearchBar override) would not fail the smoke.

**Fix**: pin a small SVG-snapshot test for the bottom 3 rows of each
state capture, asserting `Ready / Thinking…` text presence.

---

### ⚠️ N5 — `&#x27;` decoder runs only for s01-s15 — **Low**

`scripts/v1_visual_smoke.py:108-117` calls `_screenshot` which decodes.
Probe scripts (`scripts/qa_probes/*`) call `app.save_screenshot` directly
and skip the post-process. SVGs in `qa/` are full of raw `&#x27;`.

**Fix**: factor the decode into a tiny helper module both can import,
e.g. `nx01_tui/tui/test_utils.py: save_clean_screenshot(app, path)`.

---

### ⚠️ N6 — `[bold $color]` inside Markdown is a class of bug — **Medium**

Items 19, 24 used the same `[bold $primary]X[/]` recipe. Item 19 passes
(Static), item 24 fails (Markdown). There's no lint or convention
preventing the next contributor from doing the same.

**Recommended**: introduce `widgets/labels.py: RichStatic(...)` helper
that wraps Rich-aware text rendering, and forbid inlining markup inside
`Markdown` source via a small `tests/test_no_markup_in_markdown.py` grep.

---

### ⚠️ N7 — `q` is still in CommandModal `BINDINGS`? — **Low (confirm only)**

`app.BINDINGS` has no `q` anymore, but the `_handle_command_action`
mapping (`app.py:525`) still routes the `quit` action through
`action_request_quit`. The mapping is correct; only the displayed
keybind in the row is stale. (Covered by Item 33 finding.)

---

### ⚠️ N8 — ConfirmModal `border: round $error` but not `width: 50` — **Low**

`modals/confirm_modal.py:17-18` sets `width: 50` always. When dangerous,
the border becomes `round $error` (good) — but width stays the same so
on a wide terminal the dialog is small. Probably fine for v1, but the
audit "swap button order, prepend cannot-be-undone" expectations all
pass; the only nit is the modal looks slightly cramped at 50 cells with
a long prompt.

---

### ⚠️ N9 — `ChatInput` empty enter no-op silent — **Low**

`widgets/chat_input.py:72-73` returns early on empty text. Good behaviour
— but there's no notify/toast. Pressing Enter on an empty input does
nothing visible. A subtle `notify("Type a message first", timeout=1)`
would help discoverability. Tier Low; not on the audit list.

---

## 5. Improvement proposals beyond the 34

1. **RichStatic helper + Markdown lint** — see N6 above. One module + one
   test prevents item 24 class of regressions.
2. **Single declarative keybinding table** — items L9, H5 + N1 + N2 + N3
   all stem from three sources of truth (`Nx01App.BINDINGS`,
   per-widget `BINDINGS`, `help_modal._KEYBINDINGS`). A
   `keybindings.py` module that exposes all three programmatically would
   end the drift. Test: assert no binding advertised in Help is missing
   in App.
3. **Visual snapshot tests for state captures** — pytest-textual-snapshot
   or a simple SVG text-content assertion. The smoke runner currently
   green-lights regressions silently (see N4).
4. **Rename flow** — implement N3 (`e rename`) instead of removing it. A
   1-line inline `Input` modal that calls `client.rename_session` would
   complete the documented session-action set.
5. **Permission modal: keep `y/n/a` keystrokes always-on** — the
   bindings are not `priority=True`. The modal grabs focus so they
   *should* fire, but verify under Pilot — would be a horrible edge
   case if focus drifts to a Button (`y`/`n` would type into… nothing,
   since Button isn't a text input, but worth a probe).
6. **CostModal: live tick** — currently shows static snapshot. Add a
   `set_interval(2, refresh)` that re-renders from app state, so users
   can keep the modal open during streaming.
7. **MemoryModal: per-tab progress bar** — currently only a text label
   `0 / 2,200 chars (0%)` per tab. A small `ProgressBar` would match
   sidebar.
8. **OptionList alternative**: switch to `ListView` of `ListItem(Static)`
   in the modal list slots. ListView's chrome is simpler and easier to
   customise. Side benefit: kills #5 entirely.
9. **`finalise()` deserves a no-op note** — `AssistantMessage.finalise()`
   currently calls `self.update(self._role_label + self._buffer)` —
   superfluous. After my proposed N1 fix, it becomes a no-op. Worth
   removing.
10. **State ribbon: hide when IDLE/DONE** — `widgets/flavor_pane.py:22-27`
    `_STATE_RIBBON` dict has no entries for IDLE/DONE, but DONE pane
    still has the `.done` CSS class. Inspect: when state transitions
    through DONE → IDLE the ribbon may flash empty. Verify in a probe.

---

## 6. Single ordered plan (paste into GitHub)

```
1.  [Critical] [widgets/messages.py:23-44]        Fix AssistantMessage to mount the role divider as a Static above the Markdown widget; current `[bold $primary]── assistant ──[/]` leaks as literal text. (#24)
2.  [Critical] [app.py:91-119]                    Add priority=True to ctrl+f, ctrl+k, ctrl+c bindings; TextArea defaults swallow them, so Search/Skills/Stop are unreachable from chat input. (NEW N1)
3.  [Critical] [app.tcss:60-61]                   Delete `SearchBar { height: 1 … }` override that shadows the widget's height:3 DEFAULT_CSS — SearchBar currently renders at 0 cells. (#2)
4.  [High]     [app.tcss + OptionList chrome]     Replace the `option-list--option-highlighted` override with `OptionList { border: none; background: $surface; padding: 0 1 }` to kill the `▊` rail; the rail is OptionList's `tall` border, not a row indicator. (#5)
5.  [High]     [widgets/slash_dropdown.py:158-161] Replace nested Rich-tag bracket hack with `[{cat_color}]\[ {cat_label:<5}\][/]` raw-string escape; current pattern leaks literal `[[/]` glyphs. (#12)
6.  [High]     [app.py:105-106]                   y / Y plain bindings are swallowed by TextArea (typed as characters); either move to ctrl+y/alt+y with priority=True, or drop + remove the Help rows. (NEW N2)
7.  [High]     [modals/sessions_modal.py:135 ↔ app.py:561] Implement `rename` action or drop the `e` binding — Help advertises it but pressing `e` is a silent no-op. (NEW N3)
8.  [Medium]   [widgets/conversation.py:31]       Empty-conversation hint reads `q quit` — change to `ctrl+q` to match the actual binding. (#33 leftover)
9.  [Medium]   [modals/command_modal.py:73]       CommandEntry quit keybind label is `"q"` — change to `"ctrl+q"`. (#33 leftover)
10. [Medium]   [modals/base.py:18]                Backdrop alpha 70% hides previous modal entirely; lower to 40% (or render previous screen with reduced opacity) per audit goal "still hint at the layer beneath". (#10)
11. [Medium]   [modals/permission_modal.py:73]    Drop the `⚠` glyph from the title — last remaining emoji-class character; inconsistent with the item-7 commit. (#7)
12. [Medium]   [scripts/v1_visual_smoke.py:112]   Decode `&apos;` → `'` (not `&#x27;` → `&apos;`); plain apostrophe was the audit's stated goal. (#31)
13. [Medium]   [tests/]                           Add a visual-content snapshot for state captures so future CSS regressions (à la #2 SearchBar) don't pass green smoke. (NEW N4)
14. [Low]      [app.tcss:72 + widgets/sidebar.py:303] Remove dead `MonitorSidebar.icon-strip { width: 3 }` rule — never applied since item 3 collapsed to hide-below-130. (#3 hygiene)
15. [Low]      [v1_visual_smoke.py + qa_probes/]  Factor the SVG decode into a shared helper; probe screenshots currently bypass it. (NEW N5)
16. [Low]      [widgets/messages.py:10-16]        Soften UserMessage rail further if desired — `tall` still renders as `▊` block. Consider `border-left: none` + 2-cell padding. (#7b)
17. [Low]      [docs/internal]                    Introduce RichStatic + lint to prevent inlining Rich markup inside Markdown sources (root cause of #24). (NEW N6)
18. [Low]      [widgets/flavor_pane.py:22-27]     Verify the state ribbon disappears cleanly on DONE → IDLE transitions; the `_STATE_RIBBON` dict omits both, but the class may still be present. (NEW N10)
19. [Low]      [widgets/chat_input.py:72-73]      Optionally notify on empty Enter so users get feedback. (NEW N9)
20. [Low]      [docs]                             Regenerate stale `s16-s55` SVGs or remove them from `artifacts/v1-smoke/` so REPORT.md doesn't reference pre-design-pass evidence. (audit hygiene)
```

---

## Probe scripts written

All under `scripts/qa_probes/`. Run via `uv run python <path>` from repo root.

| Probe | Purpose | Verdict |
|---|---|---|
| `probe_01_thinking_chevron.py` | Item 11 + 22 — single-indicator, watcher | PASS |
| `probe_02_keybindings.py` | App bindings + flavor switching | FAIL — ctrl+f does not show SearchBar from input focus |
| `probe_03_input_keybinding_conflicts.py` | Static check: App vs TextArea collisions | FAIL — ctrl+f, ctrl+k, ctrl+c unreachable |
| `probe_04_modals_focus_and_risk.py` | Permission low/med/high + Confirm + stack | PASS |
| `probe_05_sidebar_breakpoints.py` | 7 width breakpoints, hide vs clamp | PASS |
| `probe_06_dropdown_delegation.py` | Up/Down/Enter/Tab/Escape delegation | PASS |
| `probe_07_remaining_modals.py` | Cost, Memory, Help, Debug, Tools, Skills, StatusBar, FlavorPane | PASS |
| `probe_08_assistant_divider_bug.py` | Item 24 — Rich tags in Markdown | FAIL (confirms bug) |
| `probe_09_slash_badge_bug.py` | Item 12 — `[[/]` literal artefact | FAIL (confirms bug) |

---

_End of report._
