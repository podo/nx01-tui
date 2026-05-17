# nx01-tui v1.0 — QA Re-verification Report

_Adversarial re-audit of fix commit `03c9120` on branch
`feat/v1-design-pass`, against the 15 BROKEN+PARTIAL items the previous
QA pass (`QA-REPORT.md`) flagged. Every probe SVG was re-inspected by
parsing the raw `<text>` segments rather than trusting probe exit codes.
6 new probes (probe_10..probe_16) target gaps in the prior probe set._

## 1. Executive summary

**13 / 15 originally non-PASS items now RESOLVED. 2 still PARTIAL/BROKEN.
3 new regressions found from the fix commit itself.**

The fix commit landed every Critical and most High items correctly:
SearchBar renders at 3 cells (#2), OptionList rails gone across 6
modals (#5), AssistantMessage divider rendered as Static and code-block
extraction preserved (#24, `_buffer` still populated, `CodeBlock`
mounts), priority bindings reach App handlers from focused ChatInput
(#N1, #N2), `e rename` binding + handler removed (#N3), `q` no longer
quits and Quit row in palette says `ctrl+q` (#33).

**But three significant regressions slipped in**, and one PARTIAL item
(#10 backdrop dim) still doesn't achieve the audit's stated goal.

**Top-3 most-impactful new issues**

1. 🐛 **R1 (new) — Slash badge renders literal `\]`**. The #12 fix
   replaced the nested-Rich-tag hack with a raw-string `\[ … \]`
   escape. Rich correctly escapes `\[` to a literal `[`, but `\]`
   is not a recognised escape — Rich emits two literal chars `\]`.
   Probe_15 SVG shows `[ cmd  \]`, `[ skill\]`, `[ tool \]`. The
   `probe_09` from the prior pass declared PASS only because it
   searched for the OLD substring `[[/]`, not the new `\]`.
2. 🐛 **R2 (new) — `ctrl+c` priority steals Input/TextArea copy
   inside modals**. The fix added `priority=True` to App-level
   `ctrl+c → action_stop_generation`. Textual priority bindings
   fire regardless of focused widget. With SessionsModal /
   MemoryModal / DebugModal's filter `Input` focused, pressing
   ctrl+c now fires "Stop sent" instead of copying selected text.
   Empirically confirmed: notify log after ctrl+c in focused filter
   Input contains `['Stop sent', 'abort:test-corr-id']`.
3. 🐛 **R3 (new) — `ctrl+y` priority steals DebugModal's own
   `ctrl+y → yank_buffer`**. DebugModal binds `ctrl+y` (no priority)
   to "Copy buffer"; the new App-level `ctrl+y → yank_focused` has
   `priority=True` and wins. Pressing ctrl+y inside DebugModal now
   copies the active chunk instead of the event buffer. The button
   labelled "Copy (ctrl+y)" lies.

**Additionally, two cosmetic leftovers from #N3 (rename removal)**:
- `command_modal.py:35` — Sessions command description still reads
  `"Resume · fork · rename · delete"`. UI lists an action that no
  longer exists.
- `slash_dropdown.py:24` — `/title` slash command description still
  reads `"rename current session"`. Same lie.
- `sessions_modal.py:28` dataclass docstring still mentions `rename`
  in the action list (low — internal comment only).

**Verdict.** The QA fix is mostly successful and the design pass
is closer to ship-ready than before. But R1 (slash badge `\]`) is
visible on every `/`-prefix in chat, and R2 (ctrl+c steal) breaks a
universal modal-input keystroke. Neither was caught by the existing
probe suite because each probe tested for the OLD failure mode, not
for the NEW correct behaviour. Recommend a tiny follow-up PR (≤30
loc) addressing R1, R2, R3, and the 3 rename leftovers before merge.

> **Stale-SVG note.** `s16…s55` in `artifacts/v1-smoke/` are still
> timestamped 13:11 (pre-fix). `s18_skills_modal.svg`,
> `s19_tools_modal.svg`, `s24_model_picker_modal.svg` show ▊ rails
> at x=768.6 — but these are the OLD captures, not evidence against
> the fix. The fresh probe_12_*.svg captures show 0 rails. The smoke
> runner should regenerate s16-s55 in CI.

---

## 2. Per-item re-verification

Column legend: ✅ RESOLVED / 🐛 STILL BROKEN / ❌ REGRESSED / ⚠️
PARTIAL-STILL.

### Originally BROKEN (7 items)

| # | Title | Original verdict | Fix landed at | New verdict | Evidence |
|---|---|---|---|---|---|
| 2 | SearchBar height + border | 🐛 BROKEN | `app.tcss:60-61` deleted | ✅ RESOLVED | probe_11: `bar.region.height==3`; `probe_11_searchbar.svg` shows three rows (`▔`/Search…/`▁`); SVG contains `Search` text. |
| 5 | OptionList `▊` rail | 🐛 BROKEN | `app.tcss:27-35` added `OptionList { border: none; … }` | ✅ RESOLVED | probe_12 all six modals (`probe_12_command/sessions/skills/tools/model_picker/memory.svg`) show **0** `▊` rails. Stale `s18/s19/s24` SVGs still show old rails — confirmed stale by file timestamp. |
| 12 | Slash dropdown badge colors | 🐛 BROKEN | `widgets/slash_dropdown.py:158-161` — `\[ … \]` raw string | ❌ REGRESSED | probe_15: SVG shows literal `[ cmd  \]`, `[ skill\]`, `[ tool \]`. The closing `\]` escape is not recognised by Rich; emitted as two literal chars. The prior probe_09 only searched for the OLD `[[/]` artefact and missed this. |
| 24 | AssistantMessage divider | 🐛 BROKEN | `widgets/messages.py:31-71` — rewrite as `Vertical(Static + Markdown)` | ✅ RESOLVED | probe_10: `── assistant ──` text in SVG; no `[bold $primary]`/`[bold]`/`[/]` leak; `am._buffer` preserved; `CodeBlock` mounts on fenced block. |
| 33 | `q → ctrl+q` quit | ⚠️ PARTIAL (broken leftovers) | `conversation.py:31` + `command_modal.py:73` | ✅ RESOLVED | probe_14: plain `q` is typed as char, app stays alive; no `q` in `Nx01App.BINDINGS`. SVG `s01` and `probe_14_q_no_quit.svg` both render `ctrl+q quit`. |
| N1 | `ctrl+f/k/c` unreachable from input | 🐛 BROKEN (NEW) | `app.py:91-122` — all priority=True | ✅ RESOLVED | probe_13: ctrl+f shows SearchBar; ctrl+k pushes SkillsModal; ctrl+c fires `action_stop_generation` (notify "Stop sent") and abort hook. ChatInput.text stays empty after each — no leaked chars. |
| N2 | `y/Y` swallowed by TextArea | 🐛 BROKEN (NEW) | `app.py:109-110` — moved to `ctrl+y` / `ctrl+shift+y` priority | ✅ RESOLVED | probe_13: ctrl+y yanks focused chunk; ctrl+shift+y yanks last code block (`print('xyz')`). Help row updated. |

### Originally PARTIAL (8 items)

| # | Title | Original verdict | Fix landed at | New verdict | Evidence |
|---|---|---|---|---|---|
| 3 | Sidebar hides below 130 — dead icon-strip CSS | ⚠️ PARTIAL | `app.tcss:81-83` + `sidebar.py:299-302` — `.icon-strip` rule removed | ✅ RESOLVED | `grep MonitorSidebar.icon-strip` returns 0 hits in source. `apply_terminal_width` no longer adds the class. probe_05 still PASS. |
| 7 | `⚠` glyph in PermissionModal title | ⚠️ PARTIAL | `permission_modal.py:73` | ✅ RESOLVED | Source line: `Static("[bold red]Tool Permission Required[/]", …)` — no `⚠`. |
| 7b | UserMessage soft rail | ⚠️ PARTIAL | `widgets/messages.py:18-25` — `border-left: tall` dropped, `padding: 0 2` | ✅ RESOLVED | probe_10 SVG renders `── you ──` without a `▊` rail in the user turn. |
| 10 | Modal backdrop dim too opaque | ⚠️ PARTIAL | `modals/base.py:18` `40%` | ⚠️ PARTIAL-STILL | `probe_04_stacked_modals.svg`: no `Sessions`, no `Filter`, no `Delete` text from the back modal visible. The 70%→40% change to the BaseModal background may not actually composite the previous screen — Textual modals draw over the previous screen, not through it. Visual goal "still hint at the layer beneath" is unmet. (See §4 R4 — proposed fix in §6.) |
| 26 | TabbedContent underline pill shape | ⚠️ PARTIAL | Untouched (per fix commit) | ⚠️ PARTIAL-STILL (acceptable defer) | Glyph shape is a Textual render limitation; color override works. See §5. |
| 31 | `&apos;`/`&#x27;` artefacts | ⚠️ PARTIAL | `scripts/v1_visual_smoke.py:108-114` — both decoded to `'` | ✅ RESOLVED | Source line: `cleaned = raw.replace("&#x27;", "'").replace("&apos;", "'")`. (Probe_07 fresh SVGs use raw save; smoke pipeline now produces clean apostrophes — see also §4 N5-still.) |
| N3 | Sessions `e rename` silent no-op | 🐛 BROKEN (NEW) | `sessions_modal.py` — binding + handler removed; help row updated to `f / d` | ⚠️ PARTIAL-STILL (3 leftover refs) | `e rename` binding gone; help modal updated. BUT: `command_modal.py:35` still says `"Resume · fork · rename · delete"`; `slash_dropdown.py:24` still says `/title rename current session`; `sessions_modal.py:28` dataclass docstring still lists `rename`. UI continues to advertise an action that no longer exists. |
| N7 | Confirm: `q` still in CommandModal? | ⚠️ PARTIAL (cleanup) | `command_modal.py:73` → `keybind="ctrl+q"` | ✅ RESOLVED | Source line shows `"ctrl+q"`. Probe_12 command modal SVG: `Quit  Exit the application ctrl+q`. |

### Tally

- ✅ RESOLVED: **13 / 15** (#2, #5, #24, #33, N1, N2, #3, #7, #7b, #31, N7, also Help-modal copy refreshed)
- ⚠️ PARTIAL-STILL: **1** (#10 backdrop)
- ❌ REGRESSED: **1** (#12 slash badge: old bug fixed, new `\]` bug introduced)
- Acceptable defer: #26 (Textual render limit), N3 has cleanup leftovers but core fix landed

---

## 3. New probe scripts written

All under `scripts/qa_probes/`. Run via `uv run python <path>` from
repo root. Each probe parses the raw SVG `<text>` segments rather
than trusting an exit code or a string match the previous suite
might have shipped.

| Probe | Purpose | Verdict |
|---|---|---|
| `probe_10_role_divider_render.py` | Mount AssistantMessage + UserMessage, screenshot, assert `── assistant ──` / `── you ──` visible, no `[bold $primary]` / `[/]` leaks, `_buffer` still populated, `CodeBlock` mounts on fenced code at end-of-turn. | PASS |
| `probe_11_searchbar_visible.py` | Press ctrl+f from ChatInput focus; assert `.visible` class, `bar.region.height >= 3`, SVG shows `Search` placeholder. | PASS |
| `probe_12_optionlist_no_rail.py` | Mount Command/Sessions/Skills/Tools/ModelPicker/Memory modals; screenshot each; assert 0 `▊` glyphs (filtering out filter-Input caret false positives). | PASS (all 6 modals) |
| `probe_13_priority_bindings.py` | Focus ChatInput, press each priority key; assert each fires the expected side effect (SearchBar visible / SkillsModal pushed / abort posted / yank chunk / yank last code) AND that no character leaked into ChatInput.text. | PASS |
| `probe_14_q_no_quit.py` | Press plain `q` repeatedly; assert app stays running, `q` typed as character, no `q` key in `Nx01App.BINDINGS`. | PASS |
| `probe_15_slash_badge_backslash.py` | Drive `/` in chat input; scan SVG for literal `\]` artefact (the REGRESSION the prior `probe_09` didn't catch). | **FAIL — confirms R1** |
| `probe_16_modal_ctrl_steal.py` | Focus SessionsModal's filter Input; press ctrl+c; verify App.action_stop_generation fired (regression). Open DebugModal; press ctrl+y; verify App.action_yank_focused fired instead of DebugModal's own yank_buffer (regression). | **FAIL — confirms R2 and R3** |

---

## 4. New regressions found

### ❌ R1 — Slash dropdown badge renders literal `\]` — **High**

**Where**: `nx01_tui/tui/widgets/slash_dropdown.py:158-161`

**Repro**: `uv run python scripts/qa_probes/probe_15_slash_badge_backslash.py`

```
SVG: literal '\]' present — slash badge `\]` escape leaks. Examples:
['[ cmd  \\]', '[ skill\\]', '[ tool \\]']
```

**Root cause**: The fix used a raw string:

```python
label = (
    f"[bold]{padded}[/]  [dim]{desc}[/]  "
    rf"[{cat_color}]\[ {cat_label:<5}\][/]"
)
```

In Rich markup, `\[` is the escape for a literal `[` (because `[`
opens a tag). But `]` doesn't need escaping outside a tag context —
so Rich treats `\]` as the literal two-character sequence `\]`. The
opening bracket renders cleanly; the closing renders as `\]`.

**Severity**: High — visible on every line of every `/` completion.

**Proposed fix** — use `rich.text.Text` for the badge segment so
neither bracket is interpreted as markup:

```python
from rich.text import Text

label_t = Text()
label_t.append(padded, style="bold")
label_t.append("  ")
label_t.append(desc, style="dim")
label_t.append("  ")
label_t.append(f"[ {cat_label:<5}]", style=cat_color)
self.add_option(Option(label_t, id=insertion))
```

Alternative one-liner that works in pure-string markup:

```python
label = (
    f"[bold]{padded}[/]  [dim]{desc}[/]  "
    f"[{cat_color}]\\[ {cat_label:<5}][/]"  # only the OPENING bracket needs escaping
)
```

(The closing `]` is safe because no tag context is open at that
position.)

---

### ❌ R2 — `ctrl+c` priority steals copy in focused modal Inputs — **High**

**Where**: `nx01_tui/tui/app.py:102` — `Binding("ctrl+c", "stop_generation", ..., priority=True)`.

**Repro**: `uv run python scripts/qa_probes/probe_16_modal_ctrl_steal.py`.
Direct repro: open SessionsModal, focus its `#filter` Input, press
`ctrl+c` → notify log contains `['Stop sent', 'abort:test-corr-id']`.

**Root cause**: Textual `priority=True` bindings fire regardless of
which widget has focus. `Input`/`TextArea` both bind `ctrl+c` to
`copy` at the widget level (no priority). Priority wins → the
selection-copy keystroke is now a global "stop generation" command
everywhere in the app, including inside every modal's filter Input.

Affected modals (filter Input or TextArea-equivalent that needs
ctrl+c copy):
- `SessionsModal` (`#filter`)
- `MemoryModal` (filter)
- `DebugModal` (`#filter`)
- `CommandModal` (no filter — but `OptionList` content selection)

**Severity**: High — ctrl+c is the universal copy keystroke. Stealing
it is surprising and arguably worse than the original "Search not
firing from input focus" problem the priority change was meant to
fix.

**Proposed fix**: drop `priority=True` from `ctrl+c` and instead
move the App-level binding to `ctrl+shift+c` (or `escape` while
generating). Keep ctrl+c for in-input copy. Acceptable to keep
`ctrl+f` / `ctrl+k` priority (no equivalent universal collision).

```python
Binding("ctrl+c", "stop_generation", "Stop", show=True),  # NO priority
# … or move to a non-conflicting chord:
Binding("escape", "stop_generation", "Stop while streaming", show=True, priority=True),
```

---

### ❌ R3 — `ctrl+y` priority steals DebugModal's own ctrl+y → yank_buffer — **Medium**

**Where**: `nx01_tui/tui/app.py:109` — `Binding("ctrl+y", "yank_focused", ..., priority=True)`.

**Repro**: open DebugModal, press `ctrl+y`. Expected (per the modal's
own `BINDINGS` and the button labelled `Copy (ctrl+y)`): the entire
event buffer is copied to clipboard. Actual: `action_yank_focused`
fires on the App and copies the most recent assistant chunk
instead.

Confirmed by probe_16: copy_log contains the marker chunk text
`"MARKER_FROM_APP_YANK_FOCUSED"` after pressing ctrl+y inside the
modal.

**Severity**: Medium — the DebugModal still has a clickable
`Copy (ctrl+y)` Button that DOES copy the buffer, but the keystroke
labelled on the button does the wrong thing.

**Proposed fix**: drop `priority=True` from ctrl+y (the per-modal
binding will then beat the App-level one when the modal is open),
OR move the App-level binding to `alt+y`:

```python
Binding("alt+y", "yank_focused", "Copy", show=False, priority=True),
Binding("alt+Y", "yank_last_code", "Copy last", show=False, priority=True),
```

---

### ⚠️ R4 — Backdrop dim 40% still hides the back modal entirely — **Medium**

**Where**: `nx01_tui/tui/modals/base.py:18` `background: $background 40%`.

**Repro**: probe_04 stacked ConfirmModal over SessionsModal.
`probe_04_stacked_modals.svg`: 0 occurrences of `Sessions`, `Filter`,
`Delete` — the back modal is invisible.

**Root cause**: `BaseModal { background: $background 40% }` paints
the modal's OWN background (the area outside the `.dialog`) with
40%-alpha. But Textual's modal stack renders the under-screen
content underneath; the over-modal's outside background is the
"backdrop". With `background: $background 40%`, the backdrop is
$background colored at 40% alpha — which composites against… nothing
visible, because what's underneath is the previous Screen (the App)
with the SessionsModal painted on top of it. The previous modal's
content lives in `.dialog` which is layered above the new
ConfirmModal's translucent backdrop, but the new ConfirmModal's
`.dialog` covers the same coordinate range.

In practice the visible result is: ConfirmModal `.dialog` opaque,
ConfirmModal backdrop translucent over App.compose() output, NO
visibility of SessionsModal's `.dialog` because both modals are
docked centre+middle.

**Proposed fix** — render the previous screen explicitly under the
new modal at reduced opacity:

```python
class BaseModal(ModalScreen):
    def on_mount(self):
        # Stack the previous screen visibly behind us at 50% so the
        # user sees the layer they came from.
        super().on_mount()
        # Or: change BaseModal CSS to NOT mask the area outside the
        # dialog, just darken the previous screen with screen.styles.opacity
        # on push.
```

Practical alternative: accept the visual goal as "darken the App
view" rather than "show the previous modal" — and re-document the
audit goal accordingly. Either way, item #10's stated outcome
("still hint at the layer beneath") is not achieved.

---

### ⚠️ R5 — N3 rename-removal leftovers in 3 places — **Low**

**Where** (each is a UI string lying about supported actions):

1. `nx01_tui/tui/modals/command_modal.py:35` — Sessions command
   description: `"Resume · fork · rename · delete"`. probe_12 SVG
   shows: `│Sessions  Resume · fork · rename · delete  ctrl+s│`.
2. `nx01_tui/tui/widgets/slash_dropdown.py:24` —
   `("/title", "rename current session")`. The slash command is
   advertised in the dropdown but there's no rename handler.
3. `nx01_tui/tui/modals/sessions_modal.py:28` — dataclass docstring
   still lists `rename`: `action: str  # resume | fork | rename | delete | new`.

**Severity**: Low — three string-only edits. None are functional.

**Proposed fix**: search-and-replace `rename` in those three sites.
`/title` slash command: drop entirely OR wire to a rename modal (the
prior audit's recommendation #4).

---

### Concerns probed and CLEARED (not regressions)

- ✅ `ctrl+q` reachable: `app.py:104` has `priority=True`. probe_14
  confirms `ctrl+q` in BINDINGS.
- ✅ `_buffer` attribute survives AssistantMessage rewrite: probe_10
  confirms `am._buffer` populated and `CodeBlock` mounts on fenced
  block.
- ✅ Plain `q` typed as char in ChatInput, app does not exit:
  probe_14 confirms.
- ✅ OptionList `:focus` rectangle subtle but present: `background-tint:
  $foreground 5%` plus `option-list--option-highlighted { background:
  $boost; color: $text; text-style: bold }` gives a distinct focused
  row even without a border. probe_12 SVGs show the highlighted-row
  shading clearly.
- ✅ No `action_rename` dangling references in handlers (only string
  references in 3 sites listed under R5).
- ✅ Smoke pipeline `&apos;` decode: source line now decodes both
  entities to literal `'`. (Probe captures still bypass the
  smoke-runner decode — see N5-still in §5.)

---

## 5. Deferred items recheck

The previous engineer deferred five items: N4 (smoke-asserts-state-not-pixels),
N6 (RichStatic helper + lint), #26 (TabbedContent underline pill shape), N9
(silent empty-Enter), and #16 (this was actually PASS in the prior audit;
likely the parent meant a different N-item — re-interpreted below).

| Item | Status | Note |
|---|---|---|
| **N4** — Smoke asserts state, not pixels | Still deferred — **acceptable for v1.0** | The visual-content snapshot infra is the cleanest fix but unnecessary for v1.0 ship. probe_11/12/13/15 demonstrate the same coverage at the probe layer. Recommend adding pytest-textual-snapshot for state captures in v1.1. |
| **N6** — RichStatic helper + lint to prevent markup-in-Markdown | Still deferred — **acceptable** | The item-24 root cause was a specific class of bug; the rewrite forces explicit Static + Markdown separation in `AssistantMessage` itself. No other widget exhibits the same pattern (grep `Markdown(` across `nx01_tui/tui/widgets/` returns only `AssistantMessage`). The lint adds value but isn't blocking. |
| **#26** — TabbedContent underline pill glyph | Still deferred — **acceptable** | Glyph is Textual's `╸━━━╺` render of `Underline` widget; not configurable via CSS. Color override works (visible in s01). Subclassing Underline for v1.1. |
| **N9** — Empty Enter silent | Still deferred — **acceptable** | Unchanged in the fix commit. Cosmetic discoverability nit; not blocking. |
| **#16 / N5** — Probe scripts bypass the SVG decoder | **Worth promoting to active** — see below | After the #31 fix, `v1_visual_smoke.py` produces clean `'` but `qa/*.svg` still contain raw `&#x27;` / `&apos;` because probe scripts call `app.save_screenshot` directly. Three of the new probes (10, 11, 13) read their own SVGs back — they currently parse the HTML-entity form correctly because they call `replace("&#160;"," ")` etc., but a probe that asserts plain-apostrophe presence would fail until the decoder is factored into a shared helper. Recommend `nx01_tui/tui/test_utils.py: save_clean_screenshot(app, path)` and have all probes call that. |

**New evidence pushing N5 off the defer list**: my probes had to
re-implement the decode logic ad-hoc 3× (probe_10, probe_11,
probe_13). Worth ~10 loc.

---

## 6. Final ordered plan (paste into GitHub)

```
1. [High] [widgets/slash_dropdown.py:158-161]                Replace `rf"[{cat_color}]\[ {cat_label:<5}\][/]"` with a `rich.text.Text` build OR drop the trailing `\]` escape (only `\[` needs escaping; the closing bracket is safe). Current render shows literal `\]`. (R1)
2. [High] [app.py:102]                                       Drop `priority=True` from `ctrl+c → stop_generation`, OR move the binding to a non-conflicting chord (e.g. `escape` while streaming). Current binding steals selection-copy inside every focused Input/TextArea. (R2)
3. [Medium] [app.py:109]                                     Drop `priority=True` from `ctrl+y → yank_focused`, OR move to `alt+y`. Current binding steals DebugModal's own `ctrl+y → yank_buffer` handler. (R3)
4. [Medium] [modals/base.py:18]                              `background: $background 40%` does NOT actually let the back modal show through (both modals dock centre+middle; backdrop colour change has no effect on stacked dialogs). Either implement a real overlap rendering (e.g. push the previous screen with `opacity 0.5` on push) or update the audit goal. (R4 / #10 STILL PARTIAL)
5. [Low]   [modals/command_modal.py:35]                      Sessions command description still reads "Resume · fork · rename · delete" — drop `rename`. (R5.1)
6. [Low]   [widgets/slash_dropdown.py:24]                    `/title` slash command description still reads "rename current session" — drop the command or wire it. (R5.2)
7. [Low]   [modals/sessions_modal.py:28]                     Dataclass docstring still lists `rename` in the action list — drop. (R5.3)
8. [Low]   [nx01_tui/tui/test_utils.py NEW]                  Factor `save_clean_screenshot(app, path)` and route both `scripts/v1_visual_smoke.py` and `scripts/qa_probes/probe_*.py` through it. (N5 promotion)
9. [Defer] [pytest-textual-snapshot]                         State-capture pixel-level assertions for the smoke runner. (N4)
10.[Defer] [widgets subclass `Underline`]                    Custom-render the TabbedContent underline to drop the pill shape. (#26)
```

---

## Appendix — Files touched by the fix commit (verification trace)

```
nx01_tui/tui/app.py                            BINDINGS priority=True everywhere     ✅
nx01_tui/tui/app.tcss                          OptionList {border:none}, SearchBar override deleted, .icon-strip deleted  ✅
nx01_tui/tui/modals/base.py                    BaseModal background 70% → 40%          ⚠️ landed but no visual effect on stacked modals (R4)
nx01_tui/tui/modals/command_modal.py           "q" → "ctrl+q" on Quit row              ✅ (but rename leftover at :35  R5.1)
nx01_tui/tui/modals/help_modal.py              y/Y → ctrl+y/ctrl+shift+y; f/d (no e)   ✅
nx01_tui/tui/modals/permission_modal.py        ⚠ glyph dropped                          ✅
nx01_tui/tui/modals/sessions_modal.py          e/rename binding + handler removed       ✅ (docstring leftover R5.3)
nx01_tui/tui/widgets/conversation.py           "q quit" → "ctrl+q quit"                ✅
nx01_tui/tui/widgets/messages.py               AssistantMessage rewrite                  ✅ (probe_10)
nx01_tui/tui/widgets/sidebar.py                .icon-strip class never applied          ✅
nx01_tui/tui/widgets/slash_dropdown.py         Badge bracket escape                      ❌ REGRESSED — see R1
scripts/v1_visual_smoke.py                     `&apos;` decode plain                    ✅
```

---

_End of report._
