# nx01-tui v1.0 — Design Audit

## 1. Executive summary

The app has a clear, principled foundation: round-bordered cards, a three-tier border-color state machine for the FlavorPane, a tabbed cockpit, a unified `/`-aware command surface, and disciplined separation of header/conversation/sidebar/footer chrome. The strongest aspect is the **conversation-block system** (ThinkingBlock / ToolCallBlock / SkillBlock / CodeBlock) — chevron + spinner + icon + elapsed time forms a tight, recognisable grammar that scales from collapsed one-liners to fully expanded logs. The weakest aspect is **state legibility at the screen edges**: the StatusBar widget never actually renders (the Textual `Footer` occupies the same `dock: bottom; height: 1` slot, so the agent state / token count / "Thinking…" label are silently invisible across S29 and S46–S50, despite the tests passing), and the `FlavorPane` border-color state machine is too subtle to be the primary state signal it's documented as. **If you had one hour:** unblock the StatusBar by giving it a distinct dock row above Footer (or remove Footer and merge its hints into the StatusBar) — half of the design's promised state surfacing comes back instantly.

---

## 2. Findings grouped by severity

### Critical

#### C1. StatusBar widget is never visible
- **Where:** S29, S46, S47, S48, S49, S50 — `app.py:148-152`, `widgets/status_bar.py:24-29`, `app.tcss:11-12`
- **Observation:** Both `StatusBar` and `Footer` are yielded with `dock: bottom; height: 1`. Textual's `Footer` wins the slot; the StatusBar (`● Ready` / `⠋ Thinking…` / `✻ Tool call` / token count) never reaches the screen. Every state-bar smoke test still passes because the assertions inspect widget reactive state, not pixel output. In all 5 state captures the bottom row shows only the Footer binding hints — identical text across `IDLE`, `THINKING`, `TOOL_CALL`, `DONE`, `ERROR`.
- **Why it matters:** The bottom-bar agent state is one of the v1 design contract's primary "legibility from anywhere" affordances. Users have no persistent token/state readout; the only state cue left is a 1-cell border-colour change, which is easy to miss at a glance.
- **Proposed fix:** Either (a) drop `Footer()` from `Nx01App.compose` and absorb its binding text into a third StatusBar column, or (b) explicitly stack: give StatusBar `dock: bottom; offset-y: -1` (or wrap StatusBar + Footer in a `Vertical` docked bottom with `height: 2`). Add a visual regression assertion: snapshot the bottom 2 rows and assert StatusBar's `#state` text is present.

#### C2. `SearchBar` overlay is rendered as an unusable empty rectangle
- **Where:** S26 — `widgets/search_bar.py:16-20`, also referenced in `app.tcss:43`
- **Observation:** The bar uses `height: 1` together with `border: round $primary`. A round border requires 3 rows minimum (top edge, content, bottom edge). At height 1 Textual draws only the two horizontal edges and the content row is squeezed out; in S26 the bar appears as a hollow 1-cell-tall box with no placeholder, no caret, no glyph.
- **Why it matters:** Ctrl+F is the primary discoverability surface for in-conversation search; a user pressing it sees nothing happen except a thin line appearing, and there's no input affordance visible.
- **Proposed fix:** `height: 3` (round border) or `height: 1` + `border: none` + a leading `🔍 ` glyph or `[Search]` label. Add a keybinding pill at the right edge (`enter find · n next · esc close`). Same pattern audit applies to `ChatInput.min-height: 2` — at minimum height the border crops the content row.

#### C3. Icon-strip sidebar is empty (no icons)
- **Where:** S13 — `widgets/sidebar.py:296-360`
- **Observation:** `apply_terminal_width` adds the `.icon-strip` class at `width < 130`, which only sets `width: 3` in CSS. There is no alternate render mode that shows compact glyphs per section — the panel becomes a blank 3-column vertical sliver. Each `_Section` still renders its full structure inside, but truncation makes it indistinguishable from "nothing".
- **Why it matters:** A user on a 110-col terminal (very common: VS Code split, tmux, half-screen iTerm) loses the entire monitoring sidebar with zero feedback that it exists.
- **Proposed fix:** Add an `is_icon_strip` reactive on `MonitorSidebar`; each section overrides its compose to yield a 1-cell glyph when icon-strip is active (`◉` Activity, `▦` Memory, `⚡` Skills, `⬢` MCP, `▤` Context, `▭` Session). Hovering / clicking a glyph could expand the section as a popover. Alternatively, hide entirely below 130 cols and surface a `ctrl+b` hint in the StatusBar.

#### C4. Permission modal does not visually differentiate risk levels
- **Where:** S20 (medium) vs S40 (high) — `modals/permission_modal.py:18-32`
- **Observation:** REPORT.md S40 claims "stronger visual emphasis when risk=high", but the CSS is constant (`border: thick $error` + `#risk { color: $warning }`) for every risk value. Only the `Risk: {value}` text changes. The medium and high screenshots are pixel-identical except for that word.
- **Why it matters:** This is a destructive-action gate. `rm -rf /` (high) and a cache rebuild (medium) read with the same urgency. Users will habituate to "always Allow" if there's no escalating cue.
- **Proposed fix:** Drive the border + button styling from `self.risk`: `low` → `border: round $warning`; `medium` → `border: thick $warning`; `high` → `border: heavy $error` + flashing/pulsing risk row + reorder buttons so `Deny` is first/highlighted; also re-label `Always (a)` → `Always allow this tool (a)` only when risk in {low, medium}, hide entirely on high.

---

### High

#### H1. OptionList rows are dominated by a left focus-rail (`▊`) on every row
- **Where:** S06, S07, S08, S18, S19, S22, S37, S38 — `modals/command_modal.py:93-98`, `modals/sessions_modal.py:37-42`, `modals/simple_modals.py:17/41`, `modals/debug_modal.py:28-35`
- **Observation:** Every row of every OptionList in the app is prefixed with `▊` (Textual's default option-highlighted indicator drawn at full height because no override exists). It looks like a forced bookmark bar on every line — not a focus cue.
- **Why it matters:** The modals look noisy and over-engineered; the actual highlighted row is not distinguishable from siblings.
- **Proposed fix:** In a shared modal stylesheet, override `OptionList > .option-list--option { padding: 0 1; }` and `OptionList > .option-list--option-highlighted { background: $boost; color: $text; }` — flat highlighted row, no left bar. Reserve `▊` (or `▶`) for the current selection only, not the highlighted bookmark.

#### H2. Memory progress bar does not surface overflow
- **Where:** S51 (`agent 22,500 / 2,200`, `user 8,800 / 1,375`) — `widgets/sidebar.py:120-141`, `widgets/sidebar.py:107-118`
- **Observation:** When `used > limit`, the ProgressBar caps at 100% (it has no over-cap visualisation) and the label colour rule (`$success` < 75%, `$warning` < 90%, else `$error`) does fire `$error`, but the bar itself remains a uniform solid line — no overflow stripe, no `>>` indicator, no compaction-required suggestion.
- **Why it matters:** Memory exhaustion is a state the user must respond to. The bar implying "everything fits" while values are 10× over limit is misleading.
- **Proposed fix:** When `used > limit`: render the bar in `$error`, append `+X over` to the label, and add a one-line `[$warning]/compact to free X chars[/]` hint below the row. Cap the bar at 100% width but switch its glyph to `▓▓▓▓▓` to visually distinguish overflow.

#### H3. Iconography is inconsistent across "same-concept" surfaces
- **Where:** S05 vs S06; S18 vs S19; S17; S52
- **Observation:** REPORT S06 explicitly verifies "emoji_free=True" for the Command palette — yet the surrounding app uses emoji freely: file picker rows have `📄` (`widgets/file_picker.py:107`), Tools modal rows have `🔧` (`modals/simple_modals.py:54`), Skills modal rows have `⚡` (`modals/simple_modals.py:33`, `widgets/sidebar.py:171`, `widgets/skill_block.py:51`), Memory modal uses `§` (`modals/memory_modal.py:54`). The app simultaneously promises "no emoji" and ships emoji.
- **Why it matters:** Emoji width is inconsistent across terminals (`🔧` is often 2-cell, `⚡` sometimes 1, sometimes 2) — column alignment breaks. The mix of glyph styles (Unicode emoji vs box-drawing vs Nerd-Font-style) makes the app feel assembled, not designed.
- **Proposed fix:** Commit to one glyph family. Recommended: monochrome box-drawing / geometric (e.g. `⬢` MCP, `◆` skill, `▸` tool, `▣` file, `❡` memory). Drop every emoji. Define a `glyphs.py` module that maps `tool/skill/file/cmd/memory` → one Unicode char and import from there everywhere.

#### H4. UserMessage indent / `── you ──` divider is shown as a solid `█` rail
- **Where:** S11, S27, S28, S42–S45, S51, S52 — `widgets/messages.py:9-19`
- **Observation:** `UserMessage` uses `border-left: thick $primary`, which renders as a stacked column of `█` glyphs against the user text. Combined with the `── you ──` label, the user turn reads as a heavy, dominant block — visually more prominent than the assistant reply that follows.
- **Why it matters:** Reverses the natural reading hierarchy. The assistant's content should be the dominant element; user turns are context.
- **Proposed fix:** Replace `border-left: thick $primary` with `border-left: tall $primary` (single-cell line) or remove the border and rely on the `── you ──` label + 1-cell left padding. Apply `color: $text-muted` to the user content so the assistant reply dominates.

#### H5. SearchBar keybindings collide with global priority bindings
- **Where:** `widgets/search_bar.py:27-30` vs `app.py:91-119`, plus `modals/help_modal.py:32`
- **Observation:** SearchBar declares `ctrl+n` → next match and `ctrl+p` → prev match. But the App declares `ctrl+p` (Command Modal) and `ctrl+n` (new_session) as global bindings, and the Help modal advertises `n / N` for next/prev match. None of the three sources agree.
- **Why it matters:** Pressing ctrl+p inside SearchBar will either open the command palette or change focus, depending on event order. Documented `n / N` is the third behaviour, undocumented in code.
- **Proposed fix:** Use `enter` → next match, `shift+enter` → prev match (already idiomatic for search). Update `HelpModal._KEYBINDINGS` and rename `Conversation` keys `n / N` to `Search` group keys `Enter / Shift+Enter`. Remove the ctrl+n / ctrl+p bindings from SearchBar.

#### H6. Modal stack has no backdrop / dim
- **Where:** S55 — `modals/base.py:12-34`
- **Observation:** When `ConfirmModal` is pushed on top of `SessionsModal`, the underlying modal vanishes from view (the whole frame is black). There is no scrim, no dim layer, no peek of the modal underneath. The user loses context — were they working in Sessions or did the dialog come from elsewhere?
- **Why it matters:** Modal-over-modal is a documented v1 capability. Stacking should preserve mental model.
- **Proposed fix:** In `Screen` (or `BaseModal`) set `background: $background 80%` on the screen itself (Textual supports alpha). Optionally render the previous modal at 40% opacity behind the current one. At minimum, add a 1-cell `╮ Sessions › Confirm` breadcrumb above the active modal title.

#### H7. ThinkingBlock collapsed label is two parallel glyphs (`▼ ⠼`)
- **Where:** S11, S13, S14, S27 (header line) — `widgets/thinking_block.py:64-75`
- **Observation:** The header is `▼  ⠼  Thinking…  0s  …  x to toggle`. The ExpandChevron (`▶/▼`) and the SpinnerWidget (`⠼ braille`) sit side-by-side. After `done()`, the label rewrites to `💭 {s}s — thought` but the chevron stays `▶` and the spinner is hidden — fine. But during streaming, two animated indicators compete (chevron's "expand" semantics is binary, spinner is "in-progress"). Cognitive load.
- **Why it matters:** Two icons say the same thing — "active, expand to view".
- **Proposed fix:** Replace ExpandChevron during the active phase with the spinner; swap to chevron only after `done()`. Or merge them: an animated `⠁ ⠂ ⠄ ⠂` rotating chevron when active, static `▶/▼` when finished.

#### H8. Dropdown completion menu has no category color encoding
- **Where:** S02, S03, S34, S35 — `widgets/slash_dropdown.py:140-145`
- **Observation:** Each row ends with `cmd` / `skill` / `tool` rendered as `[$accent]{cat_label}[/]` — same colour for all three. Users can't pre-attentively scan for "just skills".
- **Why it matters:** Categories carry meaning (a slash command is instant; a tool consumes turns; a skill changes context). Same colour means scanning all rows.
- **Proposed fix:** `cmd` → `$primary`, `skill` → `$accent`, `tool` → `$success`. Right-align the category badge inside a fixed 7-cell column with brackets: `[ cmd ]`. Same encoding in Command Modal so it transfers.

---

### Medium

#### M1. CostModal is bare and floats high
- **Where:** S23 — `modals/simple_modals.py:81-100`
- **Observation:** Three labelled `Static` rows, no separators, no per-flavor breakdown, no spark, no rate ($/min, tokens/sec), no session vs total split. The dialog (`height: auto`) is so short it sits near the top centre, dwarfed by empty space.
- **Why it matters:** Cost is a primary trust signal for paid users. The empty dialog reads "this feature isn't real".
- **Proposed fix:** Reserve `height: 18`. Two columns: left = current session totals (in / out / cached / $), right = lifetime + last-hour rate. Add a faint 24-cell horizontal bar showing input vs output ratio. `min-width: 70`.

#### M2. CommandModal "── V2 ──" group with disabled rows is dead weight
- **Where:** S06, S07 — `modals/command_modal.py:74-83`
- **Observation:** Four disabled entries (`Cron Jobs`, `Kanban`, `Browser`, `Plugins`) live below `── V2 ──`. They occupy ~20% of the visible options list and aren't actionable.
- **Why it matters:** Visual clutter, scroll cost, and discoverability of real actions suffers.
- **Proposed fix:** Hide the V2 group by default; surface only when the user has typed `v2` in the filter or pressed `?` for "show coming-soon". Or move them to the Help modal's "Roadmap" footer.

#### M3. Memory modal Agent vs User tabs show identical empty state
- **Where:** S17, S39 — `modals/memory_modal.py:46-55`
- **Observation:** Empty state is `[dim]empty[/]`. No guidance, no `Press /memory add to seed`, no link to docs. The same word is shown for two semantically distinct stores (agent ≠ user).
- **Why it matters:** First-run users see "empty" twice and learn nothing about what should go there.
- **Proposed fix:** Per-tab empty hint: `Agent memory captures facts the agent remembers across sessions. Type /memory add "fact" in chat to seed.` and same for user.

#### M4. DebugModal filter input + 3 buttons on one row crowds and crops button labels
- **Where:** S22 — `modals/debug_modal.py:28-35`, `:52-61`
- **Observation:** With `filter: width 1fr` and three buttons (`Pause (p)`, `Clear (ctrl+l)`, `Copy (ctrl+y)`) all on the same Horizontal row, the buttons render their floating `▔` shadow above and `▁` below, eating two extra rows of vertical space. At 90% width the buttons look tacked on.
- **Why it matters:** Looks rushed; the visual rhythm clashes with the calm RichLog below.
- **Proposed fix:** Move the buttons to a dialog footer (right-aligned). Filter input gets the full top row. Buttons row: `─────  Pause  Clear  Copy  ESC` as a single horizontal.

#### M5. Help modal table has no scroll affordance and `cursor_type="none"`
- **Where:** S16 — `modals/help_modal.py:43-57`
- **Observation:** `DataTable(zebra_stripes=True, cursor_type="none")` and `DataTable { height: auto }`. With 27 rows and `height: 90%`, on small terminals the table will exceed the modal — but `cursor_type="none"` removes the focused-row indicator, and there's no scrollbar style or "↑↓ to scroll" hint.
- **Why it matters:** Users won't realise there's more content below the fold; help becomes truncated silently.
- **Proposed fix:** `cursor_type="row"` + `cursor_foreground_priority: renderable` so an arrow-keyed row tinge is visible. Add `↑↓ scroll · / filter` to the dialog-hint. Consider replacing the table with two columns of Static rows grouped under `[bold]Global[/] / [bold]Conversation[/] / [bold]Input[/] / [bold]Sessions[/]` so scrolling is per-group.

#### M6. Header model field shows `—` (em-dash) as a hardcoded placeholder
- **Where:** S01, S30, S31, S32, S33 — `widgets/header.py:31`, `:66`
- **Observation:** `model = reactive("—")`; until a model is selected the header reads `mock · — · …`. The em-dash reads as content, not "unset", and never updates if no model is ever picked.
- **Why it matters:** The header always looks half-loaded.
- **Proposed fix:** Default `model = ""` and render `dim grey "no model selected"` when empty. After `Switch Model` modal dismiss, persist. On every connect, hit `/v1/models` and auto-pick the first available so steady state is never blank.

#### M7. AppHeader auth-failed text length pushes against the right-edge hints
- **Where:** S31 — `widgets/header.py:58-66`
- **Observation:** `[$error]{self.domain} (auth failed — check API key)[/]` is a long inline; at 110 cols it visually butts up against the right-hand `ctrl+p cmd · …` hints, with `#spacer` shrinking close to zero.
- **Why it matters:** Header looks cramped exactly when something has gone wrong — bad first impression.
- **Proposed fix:** Move the parenthetical detail to a one-line `notify` toast and keep the header tight: `[$error]{domain}[/] [dim]·[/] [bold]AUTH[/]`. Or hide the right-hand hints when an error suffix is present.

#### M8. ConfirmModal uses red title for "dangerous" but the same body styling
- **Where:** S21 (dangerous) vs S41 (benign) — `modals/confirm_modal.py:31-43`
- **Observation:** Dangerous variant only changes title colour (`bold red`) and "Yes" button variant. The dialog border, prompt text colour, and dimensions are identical. The destructive nature of `Delete this session?` is conveyed entirely by one red word.
- **Why it matters:** Easy to miss the danger if the user is scanning fast.
- **Proposed fix:** Dangerous → `border: round $error`. Swap button order: `No (n)` first, default-focused. Add an `[error]This cannot be undone[/]` row above the buttons regardless of the prompt text.

#### M9. FlavorPane border-color state machine is the single state cue (and a subtle one)
- **Where:** S42–S45 — `app.tcss:19-24`, `widgets/flavor_pane.py:23-34`
- **Observation:** The state is encoded only as a single-pixel-thick border colour change around the entire pane (~190 cells tall on a 50-row terminal). With the StatusBar broken (C1), the only state signal is the border colour at the screen edge. Easily missed; bad for colour-vision-deficient users (red/green tool/error indistinguishable to some).
- **Why it matters:** State surfacing is supposed to be glanceable.
- **Proposed fix:** Add a thicker top edge (`border-top: heavy $primary`) that always carries the state colour, plus a 1-cell state ribbon at the top of the conversation pane showing `⠋ Thinking…` text, with the colour matching the border. This restores legibility independent of any dock state.

#### M10. ThinkingBlock and ToolCallBlock chevrons can drift out of sync with body visibility
- **Where:** S28 (error case) — `widgets/tool_call_block.py:117-123`
- **Observation:** On `ERROR`, `set_collapsed(False)` is called, which sets `ExpandChevron.expanded = True` (→ `▼`). But S28 shows `▶ ✗ curl bad-url`. The block enters with `add_class("queued")`, then transitions; if the test fires `set_status(ERROR)` synchronously the chevron should be `▼`, but the snapshot shows `▶`. Either the watcher is racing the snapshot or the test never expanded the block.
- **Why it matters:** Inconsistency between the chevron's promise and the body's reality breaks the user's mental model.
- **Proposed fix:** Derive `ExpandChevron.expanded` from a single source of truth (the `collapsed` reactive) via a watcher, not a manual call. Add a watcher on ToolCallBlock.collapsed that re-renders the chevron, eliminating drift.

#### M11. Slash dropdown completion shows description as `[dim]` text right next to the bold command — no column rhythm
- **Where:** S02–S04, S34, S35 — `widgets/slash_dropdown.py:144`
- **Observation:** Each row is `[bold]{insertion}[/]  [dim]{desc}[/]  [$accent]{cat}[/]` — variable-width insertion means descriptions start at varying columns: `/help · show help` vs `/skill ci-setup · available`. The eye can't lock onto a column.
- **Why it matters:** Density without rhythm; scanning is slow.
- **Proposed fix:** Compute a max-width across visible insertions (`max(len(i) for i, _, _ in candidates)`), left-pad each insertion. Render description in column 2 starting at fixed offset. Category badge right-aligned in fixed col 3.

#### M12. UserMessage label `── you ──` is dim and small while the body is bright
- **Where:** S11, S15 — `widgets/messages.py:18-19`
- **Observation:** `[dim]── you ──[/]\n{text}` — the role attribution is whispered while the content is loud. There's no parallel `── assistant ──` label on AssistantMessage. Asymmetric.
- **Why it matters:** Conversation reads as a half-narrated transcript.
- **Proposed fix:** Either drop both role dividers (lean on the colour + indent treatment) or add a matching `[bold $primary]── assistant ──[/]` to AssistantMessage. Pick one.

---

### Low

#### L1. Footer hint bar is duplicated near the right edge
- **Where:** S01 + most screens — Textual `Footer` default
- **Observation:** The Footer shows `^p Commands ^s Sessions ^m Memory ^b Sidebar … ▏^p Commands` — the trailing `▏^p Commands` is Textual's "more bindings" indicator with an overlap of the first binding.
- **Proposed fix:** Either set `show_command_palette=False` on the Footer or supply a `Footer(compact=True)` styled to hide the overflow indicator. Or use a custom footer (already what StatusBar is meant for).

#### L2. Tab strip uses `╸━━━╺` underline glyphs — non-standard, looks like a 2D bar chart
- **Where:** All screens with TabbedContent — Textual default TabbedContent underline
- **Observation:** Active tab shows `╸━━━━━━━━━╺` (rounded ends); inactive tabs show plain `━━`. The transition is abrupt and the active "pill" is short relative to the tab labels.
- **Proposed fix:** Override `Tabs > Underline > .underline--bar` colour to `$primary` and make the rounded ends optional. Alternatively replace the underline with a left-bar approach (`▎`) that aligns with the FlavorPane border colour.

#### L3. ChatInput shows no submit hint when empty
- **Where:** S01, S54 — `widgets/chat_input.py:25-37`
- **Observation:** Empty bordered TextArea with no internal placeholder. The empty-state hint in the conversation suggests Enter to send, but the input itself is silent.
- **Proposed fix:** Add `placeholder="Type to chat · /help · @file"` (Textual TextArea supports placeholder via theme override) or render an internal Static `placeholder` overlay that disappears on focus.

#### L4. Skills modal hint says only "ESC close" — no load/unload hint
- **Where:** S18 — `modals/simple_modals.py:37`
- **Observation:** REPORT calls out "clicking would load/unload" but the modal hint shows `ESC close` only. No `enter toggle · / filter` cue.
- **Proposed fix:** Hint line: `enter toggle · / filter · ESC close`.

#### L5. Tools modal advertises V2 deferral in its hint line
- **Where:** S19 — `modals/simple_modals.py:58-60`
- **Observation:** Hint reads `MCP and Toolsets tabs land in V2 · ESC close`. Mixing roadmap copy with action hints reads like a stuck "we know it's incomplete" sticker.
- **Proposed fix:** Move "MCP / Toolsets coming in V2" to a one-line `Static` above the OptionList, styled as a soft callout. Keep the hint line for actions only.

#### L6. Spinner braille frames may flash on slow terminals
- **Where:** S11, S13, S14, S27, S47 — `widgets/spinner.py`, `widgets/thinking_block.py:67-70`
- **Observation:** Two spinner classes are used (`SpinnerWidget("dots")` and `StarSpinner`). Different speeds, different glyph sets. Accessibility-wise it's also worth a "reduce motion" affordance.
- **Proposed fix:** Single `Spinner(style="dots", interval_ms=120)` shared. Honour an env var `NX01_REDUCE_MOTION=1` that renders the spinner as a static `⏳` glyph.

#### L7. Sessions modal preview uses `&#x27;` (literal HTML entity) for apostrophes
- **Where:** S08, S15, S27 (snapshot artefact) — SVG snapshot extraction shows `&#x27;` for `'`
- **Observation:** This is a snapshot/export artefact (SVG encoding), not a runtime bug, but worth pinning a test that asserts plain apostrophes in copied content.
- **Proposed fix:** Add a snapshot post-processing step to decode `&#x27;` → `'`, or change `app.copy_to_clipboard` callsites to assert escapes don't leak.

#### L8. SkillBlock content default is the literal string `_(skill content not yet streamed)_`
- **Where:** Not directly screenshot — `widgets/skill_block.py:45`
- **Observation:** Underscore italic markdown placeholder appears in the body until streamed content arrives.
- **Proposed fix:** Default to `[dim italic]Loading skill manifest…[/]` rendered via Static, not Markdown — looks more native to the rest of the UI.

#### L9. `q` to quit is unmodified — easy to fire mid-chat
- **Where:** S01 + global binding — `app.py:102`
- **Observation:** Plain `q` quits the app. The TextArea steals most key presses, but `q` is bound app-level (`show=True`). In some focus states (modal closed but input not yet focused) a `q` exits.
- **Proposed fix:** Bind to `ctrl+q` instead, or require a confirm modal when there's an unsent message in the input. Update Help modal accordingly.

#### L10. Header brand `[bold]NX01[/]` is followed by domain in the same line — no visual separation between identity and connection state
- **Where:** S01, S30–S33 — `widgets/header.py:56-66`
- **Observation:** `NX01  mock (reconnecting)  ·  —` reads as one continuous phrase. The brand and connection state are conceptually different but visually fused.
- **Proposed fix:** Use a glyph divider: `[bold]NX01[/]  [dim]┃[/]  [$warning]mock · reconnecting[/]  [dim]┃[/]  [dim]gpt-4o[/]`. Vertical bar separators improve scannability.

---

## 3. Cross-cutting themes

1. **Bottom-of-screen state is broken or unused.** StatusBar widget is silently invisible (C1); FlavorPane border state is too thin (M9); Footer carries only static binding hints. Three pieces meant to carry state, none of them do their job well.
2. **Iconography lacks a system.** Emoji (`📄 🔧 ⚡`), Unicode geometric (`✓ ✗ ○ ●`), box-drawing (`█ ▊ ▔ ▁`), and brand-style ASCII (`──`) coexist with no rule. REPORT.md explicitly verifies "emoji_free" for the command palette while shipping emoji everywhere else (H3).
3. **Risk / danger styling is inconsistent and too quiet.** Permission modal uses `thick` border for all risks (C4); Confirm modal uses red title only (M8); FlavorPane error uses subtle border-only (M9). No coherent "this is destructive" treatment.
4. **Modal chrome variants are ad-hoc.** Width values are sprinkled per modal (`width: 50`, `width: 60`, `width: 64`, `width: 70`, `width: 80`, `width: 90%`); some have `border: round $primary`, MemoryModal uses `$accent`, PermissionModal uses `thick $error`; title colours and bold treatment differ. Each modal looks like it was authored independently (M4, M8, H3, H6).
5. **OptionList visual default is wrong.** Six modals all render with a heavy `▊` left rail. This is the dominant visual element across the modal layer (H1).
6. **Empty / over-limit / loading states are afterthoughts.** Cost modal at zero is bare (M1); memory modal empty shows `empty` (M3); memory bar at 1000% overflow looks identical to 50% (H2). The design budget went into the happy path.
7. **Keybinding source-of-truth is split three ways:** app.py priority bindings, per-widget BINDINGS, and the Help modal's hardcoded list. They disagree (H5, L9). A single declarative table that both populates `BINDINGS` and `_KEYBINDINGS` would prevent drift.

---

## 4. Comparison vs reference TUIs

- **vs `opencode` (sst):** opencode has a persistent bottom row showing model + cost + token rate + state — always there, always live. nx01-tui designs the same affordance but it's offscreen (C1). opencode commits to a single accent colour for active state; nx01 spreads across border colour, title colour, and button variant.
- **vs Claude Code CLI:** Claude Code's `/`-completion menu is dense, single-column, monochrome category-tagged — nx01's slash dropdown is structurally identical and very close in quality. Claude Code's tool-call rendering is a single line with status emoji + title + elapsed; nx01's `ToolCallBlock` is a full bordered card, which is more elaborate (per-block border, chevron, body) — heavier but more discoverable.
- **vs `lazygit`:** lazygit has rock-solid responsive layouts: panels recompose, never disappear, every panel has an icon-strip mode that's actually iconic. nx01's icon-strip mode is empty (C3). lazygit also commits to a unified glyph family (single Unicode set) — nx01 is mixed (H3). lazygit's status bar at the bottom is the constant anchor; nx01's is invisible.
- **vs `gh dash`:** gh dash has explicit empty-state designs ("No notifications. Press R to refresh.") with copy + keybinding; nx01's empty states just say "empty" or "no activity" (M3). gh dash uses a single muted teal accent across the entire app — easy to scan; nx01 uses 4–5 accent colours.

What nx01-tui does well that the reference apps don't: the `FlavorPane.thinking/streaming/tool_call/done/error` border colour transition is a nice ambient signal that opencode/Claude Code/lazygit don't have. The `@file` and `/`-completion priority-binding delegation pattern through ChatInput is elegant and copy-worthy.

---

## 5. Quick wins (≤30 min each)

1. Remove `Footer()` from `Nx01App.compose` (app.py:152). StatusBar becomes visible immediately (fixes C1).
2. Bump SearchBar `height: 1` → `height: 3` (search_bar.py:18). One-line fix for C2.
3. Add `OptionList > .option-list--option-highlighted { background: $boost; }` to `app.tcss` and (in shared modal CSS) remove the default focus-rail by setting `OptionList { scrollbar-gutter: stable; }` and overriding the cursor styling. Kills the `▊` rail across all six modals (H1).
4. In `_render_store` (memory_modal.py:46-55), branch empty: `if not entries: yield Static("[dim italic]Agent memory captures facts the agent remembers across sessions. Type [bold]/memory add \"fact\"[/] in chat to seed.[/]")`. (M3)
5. Strip the `── V2 ──` block from `default_commands()` (command_modal.py:74-83); render only when filter contains `v2`. (M2)
6. Set `MemorySection._label` to append `[$error] (+{used-limit} over)[/]` when over-cap (sidebar.py:120-141). (H2 partial.)
7. In `_brand_text` (header.py:56-66), replace `[dim]·[/]` with `[dim]┃[/]` and dim/wrap a `model = ""` to `[dim italic]no model[/]`. (L10, M6)
8. Move `[dim]MCP and Toolsets tabs land in V2[/]` from the hint line to a `Static` callout above the list in `ToolsModal` (simple_modals.py:58-60). (L5)
9. Rebind `q` → `ctrl+q` in `app.py:102`. One-line safety fix. (L9)
10. In `ConfirmModal.compose`, when `self.dangerous`, set `self.styles.border = ("round", "$error")` on the `.dialog` and prepend an `[$error]This cannot be undone[/]` row. (M8)

---

## 6. Numbered improvement list

1. **[Critical] [S29, S46-S50]** Restore StatusBar visibility — Footer occupies the same `dock: bottom` slot so `app.py:148-152` silently hides the agent-state / token / flavor row that the design relies on.
2. **[Critical] [S26]** Fix SearchBar `height: 1` + round border in `search_bar.py:18-20` — the bar currently renders as a hollow line with no caret or placeholder when activated by ctrl+f.
3. **[Critical] [S13]** Implement icon-strip rendering for `MonitorSidebar` — `sidebar.py:296-360` only sets `width: 3` so the responsive collapse produces an empty 3-column sliver instead of section icons.
4. **[Critical] [S20, S40]** Drive `PermissionModal` chrome from `self.risk` in `permission_modal.py:18-32` — high and medium variants are pixel-identical, defeating the destructive-action gate.
5. **[High] [S06-S08, S18-S19, S22, S37-S38]** Override Textual's default OptionList highlighted-row chrome — the `▊` left rail on every list row dominates six modals (`modals/*.py` + a shared CSS rule).
6. **[High] [S51]** Render memory overflow visually — `sidebar.py:107-141` lets `agent 22,500 / 2,200` show as a benign solid bar; add `+over` label, `$error` bar colour, and a `/compact` suggestion when used > limit.
7. **[High] [S05, S18-S19, S52]** Replace mixed emoji (`📄 🔧 ⚡`) with one monochrome glyph family in `widgets/file_picker.py:107`, `modals/simple_modals.py:33/54`, `widgets/sidebar.py:171`, `widgets/skill_block.py:51` — REPORT.md verifies "emoji_free" for the command palette while shipping emoji elsewhere.
7. **[High] [S11, S27, S28, S42-S45, S51, S52]** Soften `UserMessage` from `border-left: thick $primary` (`messages.py:9-19`) — the heavy `█` rail makes user turns visually dominate the assistant response.
9. **[High] [S26]** Resolve SearchBar keybinding conflict — `search_bar.py:27-30` ctrl+n/ctrl+p collide with global app bindings and Help modal's documented `n/N`; switch to `Enter` / `Shift+Enter` and update `help_modal.py:32`.
10. **[High] [S55]** Add modal-stack backdrop dim in `modals/base.py:12-34` — pushing ConfirmModal over SessionsModal hides the underlying modal entirely; users lose context.
11. **[High] [S11, S13, S14, S27]** Consolidate ThinkingBlock chevron + spinner into one indicator in `thinking_block.py:64-75` — two parallel animated glyphs (`▼ ⠼`) say the same thing.
12. **[High] [S02-S04, S34-S35]** Color-code slash-dropdown category badges (cmd/skill/tool) in `slash_dropdown.py:140-145` so users can scan by category at a glance.
13. **[Medium] [S23]** Flesh out CostModal in `simple_modals.py:81-100` — three bare rows feel like a stub; add session vs lifetime split, rate, and visual ratio.
14. **[Medium] [S06]** Hide the "── V2 ──" disabled group by default in `command_modal.py:74-83`; surface only when the user filters for "v2".
15. **[Medium] [S17, S39]** Replace generic `[dim]empty[/]` in `memory_modal.py:54` with store-specific guidance copy that teaches the seeding command.
16. **[Medium] [S22]** Move DebugModal buttons to a dialog footer in `debug_modal.py:28-61` — the filter input + three buttons on one Horizontal row crops labels and adds shadow noise.
17. **[Medium] [S16]** Add scroll affordance + group headers to HelpModal in `help_modal.py:43-57` — `cursor_type="none"` + auto-height truncates silently on small terminals.
18. **[Medium] [S01, S30-S33]** Replace hardcoded `model = "—"` placeholder in `header.py:31` with a dim "no model selected" treatment, and auto-pick the first available model on connect.
19. **[Medium] [S31]** Move auth-failed long suffix to a toast and keep the header tight in `header.py:58-66` — at 110 cols the failure message crowds the right-edge hints.
20. **[Medium] [S21, S41]** Differentiate ConfirmModal dangerous variant beyond title colour in `confirm_modal.py:31-43` — add `$error` border, swap button focus order, prepend "cannot be undone" line.
21. **[Medium] [S42-S45]** Add a redundant top-of-pane state ribbon to FlavorPane so the state cue isn't only a single-cell border colour at the screen edge (`flavor_pane.py:23-34`).
22. **[Medium] [S28]** Sync ToolCallBlock chevron to `collapsed` reactive via a watcher in `tool_call_block.py:177-186` to eliminate drift between chevron and body visibility.
23. **[Medium] [S02-S04, S34-S35]** Compute a max-width for the slash-dropdown insertion column in `slash_dropdown.py:135-145` so descriptions align in a fixed column.
24. **[Medium] [S11, S15, S52]** Decide on role-divider symmetry in `messages.py:9-30` — either add `── assistant ──` to AssistantMessage or drop the divider on UserMessage; current asymmetric treatment reads inconsistent.
25. **[Low] [most screens]** Suppress Textual Footer's "more bindings" overflow indicator (or replace with a custom footer) to remove the duplicated `^p Commands` at the right edge.
26. **[Low] [all tabbed screens]** Restyle TabbedContent underline (`╸━━━╺`) to a left-bar or solid coloured underline aligned with the FlavorPane state colour.
27. **[Low] [S01, S54]** Add a placeholder hint inside the empty ChatInput in `chat_input.py:25-37`: `Type to chat · /help · @file`.
28. **[Low] [S18]** Add `enter toggle · / filter` to SkillsModal hint line in `simple_modals.py:37`.
29. **[Low] [S19]** Move "MCP and Toolsets tabs land in V2" from the hint line to a soft callout above the list in `simple_modals.py:58-60`.
30. **[Low] [S11, S27, S47]** Unify spinner widgets — `SpinnerWidget("dots")` and `StarSpinner` use different glyph sets and intervals; consolidate to one in `widgets/spinner.py` and honour `NX01_REDUCE_MOTION`.
31. **[Low] [S08, S15]** Decode SVG snapshot `&#x27;` artefacts in the captured fixtures or assert plain apostrophes in copied content.
32. **[Low]** Replace `_(skill content not yet streamed)_` placeholder string in `skill_block.py:45` with a dim Static loading line.
33. **[Low] [global]** Rebind `q` → `ctrl+q` in `app.py:102` to avoid accidental quit during chat.
34. **[Low] [S01, S30-S33]** Replace `·` separators in the header with `┃` vertical bars and group identity/connection/model into three visually distinct segments in `header.py:56-66`.
