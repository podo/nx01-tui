# NX01-TUI — Design Specification

> Operator cockpit for the [NX01](https://github.com/podo/nx01) fleet — a tabbed multi-flavor Textual TUI with real-time activity monitoring, full Hermes CLI feature parity, and a discoverable command-modal hub.

**Status:** Design locked, ready for implementation.
**Phase:** V1 (22 features) → V2 (~15 features).

---

## Table of contents

1. [Vision](#vision)
2. [Layout](#layout)
3. [Agent state machine](#agent-state-machine)
4. [Conversation widgets](#conversation-widgets)
5. [Right sidebar](#right-sidebar)
6. [Modal system](#modal-system)
7. [Input system](#input-system)
8. [Animations](#animations)
9. [Keybindings](#keybindings)
10. [Hermes CLI → TUI feature mapping](#hermes-cli--tui-feature-mapping)
11. [Widget hierarchy](#widget-hierarchy)
12. [TCSS outline](#tcss-outline)
13. [SSE event handling](#sse-event-handling)
14. [Error & disconnection](#error--disconnection)
15. [V1 / V2 scope](#v1--v2-scope)

---

## Vision

A single full-screen Textual TUI that talks to the nx01 API server via SSE and gives the operator one cockpit for every flavor. Influences:

- **Crush** (charmbracelet) — 5-zone layout, collapsible thinking, nested tool spinners, rounded borders.
- **OpenCode** (sst) — right sidebar that auto-hides on narrow terminals, agent color cycling.
- **Claude Code** (Anthropic) — star spinners, rotating verbs, per-tool specialized renderers, permission dialogs.
- **Factory.ai** — approval workflow modal, `?` help overlay.

Design principles:

1. **Conversation = detail.** Tool calls, thinking, diffs all live inline as collapsible blocks. Default-collapsed; expand on demand.
2. **Sidebar = at-a-glance.** Activity list, memory bars, context %, skills — always visible, never hidden behind clicks.
3. **Modals = actions.** CommandModal (ctrl+p) is the central hub; sub-modals for sessions, memory, skills, tools, config.
4. **Rounded borders everywhere.** Soft, modern, distinguishes from legacy box-drawing TUIs.
5. **State transitions are animated.** TCSS `transition: border 300ms in_out_cubic` handles state-class flips automatically.

---

## Layout

```
┌─ AppHeader ──────────────────────────────────────────────────────┐
│ NX01 ⬤ nx01.example.com   claude-opus-4-7    ctrl+p ctrl+s ?    │
├─ TabbedContent ──────────────────────────────────────────────────┤
│ ⠋ assistant │ ○ operator │ ○ analyst │ + …                       │
├─ FlavorPane (Horizontal) ────────────────────────────────────────┤
│                                                │                 │
│  ConversationContainer (1fr)                   │  MonitorSidebar │
│  ┌────────────────────────────────────────┐    │  (width: 28)    │
│  │ ConversationView (VerticalScroll)      │    │                 │
│  │                                        │    │  ── Activity ── │
│  │  UserMessage                           │    │  ✓ read_file    │
│  │  ▸ 💭 3s                                │    │  ✻ bash         │
│  │  ▸ ✓ read_file  .github/                │    │  ○ grep ×3      │
│  │  ▸ ⚡ skill:ci-setup                    │    │                 │
│  │  ▾ ✻ write_file .github/workflows/ci.. │    │  ── Memory ──   │
│  │    + name: CI                          │    │  ███▓░ 2100/2200│
│  │    + on: [push, pull_request]          │    │                 │
│  │  AssistantMessage (streaming…▌)        │    │  ── Skills ──   │
│  │                                        │    │  ⚡ ci-setup    │
│  ├────────────────────────────────────────┤    │                 │
│  │ InputArea (TextArea)                   │    │  ── Context ──  │
│  │ Type a message…                        │    │  ████░ 48k/200k │
│  └────────────────────────────────────────┘    │                 │
├─ StatusBar ──────────────────────────────────────────────────────┤
│ ⠋ Thinking… · assistant    24% ctx · y copy · ctrl+f search    │
└──────────────────────────────────────────────────────────────────┘
```

### Layout primitives

| Region | Widget | Sizing |
|---|---|---|
| Header | `Static` | `dock: top; height: 1` |
| Tabs | `TabbedContent` | `height: auto` |
| Flavor pane | `Horizontal` container | `height: 1fr` |
| Conversation | `Vertical` container | `width: 1fr` (takes remaining) |
| Sidebar | `Vertical` container | `width: 28` (or `auto-hide`) |
| Status bar | `Static` | `dock: bottom; height: 1` |
| Footer | `Footer` (Textual built-in) | `dock: bottom` |

---

## Agent state machine

Each flavor pane has six possible states. State drives tab indicator, pane border color, and status bar text.

| State | Tab indicator | Pane border | Status bar | CSS class |
|---|---|---|---|---|
| Idle | `○ flavor` | dim panel | `● Ready` | _(no class)_ |
| Thinking | `⠋ flavor` (yellow, braille spin) | yellow pulse 2s | `⠋ Thinking…` | `.thinking` |
| Writing | `▌ flavor` (blue, blink) | blue solid | `▌ Writing…` | `.streaming` |
| Tool call | `✻ flavor` (green, star spin) | green pulse 1.5s | `✻ {tool_name}` | `.tool_call` |
| Done | `○ flavor` | → idle (300ms transition) | `✓ Done` | _(no class)_ |
| Error | `✗ flavor` | red solid | `✗ Error: …` | `.error` |

Implementation:

```python
class AgentState(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    STREAMING = "streaming"
    TOOL_CALL = "tool_call"
    DONE = "done"
    ERROR = "error"

def set_state(self, state: AgentState) -> None:
    pane = self.query_one(FlavorPane)
    pane.remove_class(*[s.value for s in AgentState])
    pane.add_class(state.value)
    # TCSS handles border color transition automatically
```

---

## Conversation widgets

All conversation blocks extend `Collapsible` and follow the same expand/collapse pattern:

- **Chevron** at the leftmost position: `▸` collapsed, `▾` expanded.
- Chevron rotates 90° over 200ms via `styles.animate("transform")`.
- Toggle via `x` key, `space` key, or click on chevron.
- Collapsed state shows compact summary; expanded shows full content.

### ThinkingBlock

Yellow border, `💭` icon. Streams live during thinking; collapses automatically when turn completes.

```
▾ 💭 3s   thinking
  The user wants CI/CD. Let me check the project
  structure first to see what we have…▌

▸ 💭 3s   thinking   ← collapsed (default after done)
```

| State | Border | Behaviour |
|---|---|---|
| Streaming | yellow pulse 2s | `collapsed=False`, RichLog appends chunks |
| Done | dim yellow | `collapsed=True`, title shows `💭 {seconds}s` |

### ToolCallBlock

Green border, status icon. Five states:

```
▸ ○ bash      git log --oneline -5            queued (opacity 0.45)
▾ ✻ write_file .github/workflows/ci.yml  1.4s active (green pulse)
  + name: CI
  + on: [push, pull_request]
  ▌
▸ ✓ read_file .github/   not found       0.1s done (collapsed)
▸ ✓ read_file ×5  api/server.py, config.py… 1.2s grouped (same tool)
▾ ✗ bash      docker build .                  error (red border)
  COPY failed: file not found in build context
```

| State | Border | Icon | Opacity | Collapsed? |
|---|---|---|---|---|
| Queued | dim gray | `○` | 0.45 | yes |
| Active | green pulse 1.5s | star spinner | 1.0 | no (open) |
| Done | dim green | `✓` | 0.7 | yes |
| Done ×N (same tool) | dim green | `✓` | 0.7 | yes |
| Error | red solid | `✗` | 1.0 | no (open) |

### SkillBlock

Purple border, `⚡` icon. Appears when Hermes loads a skill into the session.

```
▾ ⚡ skill:ci-setup    loading…
▸ ⚡ skill:ci-setup    loaded · 4.2kb
```

Same Collapsible pattern as ToolCallBlock. Expand reveals skill markdown content.

### Diff display (inline)

Diffs render inside expanded ToolCallBlocks for `write_file` / `edit_file` operations. No separate diff pane.

```
▾ ✓ write_file .github/workflows/ci.yml (created)
  @@ -0,0 +1,18 @@
  + name: CI
  + on: [push, pull_request]
  + jobs:
  +   test:
  …12 more lines (expand for full)
```

Implementation: `rich.Text` with per-line ANSI coloring (`+` green, `-` red, `@@` cyan), written to a `RichLog` inside the ToolCallBlock. Truncate to 20 lines with "… N more" expander.

---

## Right sidebar

`MonitorSidebar` is a right-docked panel (~28 cells wide) showing real-time monitoring. Per-flavor state; switches with tabs.

### Sections

| Section | Content | Per-flavor? |
|---|---|---|
| **Activity** | Compact tool call list (icon + name + elapsed). Active row highlighted. | yes |
| **Memory** | Two progress bars: agent (`MEMORY.md`, 2200 chars), user (`USER.md`, 1375 chars). 3-line preview. Color: green <75%, orange 75–90%, red >90%. | no (shared) |
| **Skills** | Session-loaded skills list (⚡ name + size). Active skill purple, others dim. | yes |
| **Context** | Token usage bar (green <60%, orange 60–80%, red >80%). Format: `48,231 / 200,000 · 24%`. | yes |
| **Session** | Title, message count, age, model. Read-only — `ctrl+s` for actions. | yes |

### Responsive behaviour

| Terminal width | Sidebar |
|---|---|
| ≥ 140 cols | Full sidebar (28 cells wide) |
| 120–139 cols | Icon strip (3 cells: ✻📝⚡%◎) |
| < 120 cols | Hidden — `ctrl+b` to force-show as overlay |

Implementation: `App.on_resize()` adds/removes CSS classes (`.hidden`, `.icon-strip`).

### Interactions

| Action | Behaviour |
|---|---|
| `ctrl+b` | Toggle sidebar shown/hidden |
| Click Activity row | Scroll conversation to that ToolCallBlock + expand it |
| Click Memory section | Open MemoryModal (ctrl+m) |
| Click Skills entry | Expand skill content as tooltip overlay |
| Click Context bar | Send `/context` to display breakdown |
| Click Session info | Open SessionsModal (ctrl+s) |

---

## Modal system

All modals are `ModalScreen` subclasses pushed onto a stack. ESC pops one level. Modal stack example: `[CommandModal, SessionsModal]` — selecting "Sessions" from CommandModal pushes SessionsModal on top; ESC returns to CommandModal; ESC again returns to main app.

### CommandModal (`ctrl+p`) — central hub

Categorized list of all actions with fuzzy search at top. Direct keybinding shown on the right of each row.

```
╭─ Commands ──────────────────────────────────╮
│ 🔍 Filter…                                   │
├──────────────────────────────────────────────┤
│ Quick Actions                                │
│   💬 Sessions                       ctrl+s   │
│   📝 Memory                         ctrl+m   │
│   + New Session                     ctrl+n   │
│   ⚡ Skills                         ctrl+k   │
│   🔧 Tools & MCP                    ctrl+t   │
│                                              │
│ Flavor                                       │
│   🤖 Switch Flavor                   Tab     │
│   ⚙ Switch Model                    /model   │
│                                              │
│ View                                         │
│   ▸ Toggle Sidebar                  ctrl+b   │
│   🎨 Toggle Theme                    d       │
│   🔍 Search in Conversation         ctrl+f   │
│                                              │
│ System                                       │
│   📊 Cost & Tokens                  /cost    │
│   ⚙ Configuration                   /config  │
│   ❓ Help                            ?        │
│   🚪 Quit                             q       │
╰──────────────────────────────────────────────╯
```

### Sub-modals

| Modal | Trigger | Content |
|---|---|---|
| `CommandModal` | `ctrl+p` | Central hub of all actions |
| `SessionsModal` | `ctrl+s` or via CommandModal | Sessions grouped by flavor, search, resume/fork/rename/delete |
| `MemoryModal` | `ctrl+m` or via CommandModal | Two tabs (Agent / User Profile), char usage bars |
| `SkillsModal` | `ctrl+k` or via CommandModal | All available skills, load/unload |
| `ToolsModal` | `ctrl+t` or via CommandModal | Tools + MCP servers + Toolsets tabs |
| `ConfigModal` | via CommandModal | Settings key/value editor |
| `CostModal` | via CommandModal | Cost breakdown per session/model |
| `ModelPickerModal` | via CommandModal | Switch active model |
| `HelpModal` | `?` | Keybinding table |
| `PermissionModal` | SSE `permission_required` | Tool name + args + risk + y/n/a buttons |
| `ConfirmModal` | Destructive actions | Generic y/n confirmation |

### SessionsModal detail

```
╭─ Sessions ──────────────────────────────────╮
│ 🔍 Filter sessions…                          │
├──────────────────────────────────────────────┤
│ ── assistant ─────────────────────────────── │
│  ▸ Deploy CI/CD pipeline    2m ago · 14 msgs │
│      How do I set up CI/CD for this proj…    │
│      r resume  f fork  e rename  d delete    │
│                                              │
│  ▸ Refactor auth module     yesterday · 8    │
│                                              │
│ ── operator ──────────────────────────────── │
│  ▸ Production deploy        3d ago · 22 msgs │
├──────────────────────────────────────────────┤
│ n new · r resume · f fork · e rename · d del │
╰──────────────────────────────────────────────╯
```

Grouped by flavor. Sorted by `last_active` desc. Selection navigable with `↑↓`. Delete requires ConfirmModal.

### PermissionModal detail

```
╭─ ⚠ Tool Permission Required ────────────────╮
│ Tool: bash                                   │
│ Args: rm -rf ./dist/ && docker build .       │
│ Risk: medium — deletes build artifacts       │
│                                              │
│ ┌─────────┐  ┌─────────┐  ┌──────────────┐ │
│ │ y Allow │  │ n Deny  │  │ a Always Allow│ │
│ └─────────┘  └─────────┘  └──────────────┘ │
╰──────────────────────────────────────────────╯
```

Pushed via `push_screen_wait()` inside the SSE worker coroutine. Blocks the stream until y/n/a.

---

## Input system

### ChatInput (TextArea subclass)

```python
class ChatInput(TextArea):
    BINDINGS = [
        Binding("ctrl+j", "submit", "Submit", show=False),
    ]

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def action_submit(self) -> None:
        text = self.text.strip()
        if text:
            self.post_message(self.Submitted(text))
            self.clear()
```

CSS: `height: auto; min-height: 2; max-height: 8;` — expands as user types, scrolls internally past 8 lines.

| Key | Action |
|---|---|
| `ctrl+j` | Submit (universal) |
| `Shift+Enter` | Newline (Kitty/WezTerm/Ghostty only — uses CSI u escape) |
| `Enter` | Newline (TextArea default) |
| `/` | Trigger slash command autocomplete |
| `@` | Trigger file/agent reference autocomplete (V2) |
| `ESC` | Clear input |

### Slash command autocomplete

When the input starts with `/`, a `SelectionList` overlay appears above the input showing fuzzy-matched commands.

Implementation: `textual-autocomplete` library wraps the TextArea with a dropdown.

```python
class SlashAutocomplete(AutoComplete):
    def get_search_string(self) -> str:
        value = self.target.text
        return value[1:] if value.startswith("/") else ""

    def apply_completion(self, completion: str) -> None:
        self.target.text = "/" + completion + " "
```

Commands come from the active flavor's `/help` output, cached per-flavor.

---

## Animations

All animations target 60fps where possible (braille spinners) and 200–300ms for state transitions.

### Spinners

| Name | Frames | FPS | Use |
|---|---|---|---|
| MiniDot (braille) | `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` | 12 | Thinking state, tab indicator |
| Star (Claude Code) | `· ✻ ✽ ✶ ✳ ✢` | 8 | Tool call header |
| Cursor blink | `▌` | 1Hz | Streaming text cursor |
| Pulse | `█▓▒░` | 8 | Reconnecting indicator |

Spinner widget pattern (Rich-based):

```python
from rich.spinner import Spinner
from textual.widgets import Static

class SpinnerWidget(Static):
    def __init__(self, name: str = "dots"):
        super().__init__(Spinner(name))

    def on_mount(self) -> None:
        self.set_interval(1/60, self.refresh)
```

### Border state transitions

TCSS handles automatically:

```css
FlavorPane {
    border: round $panel;
    transition: border 300ms in_out_cubic;
}
FlavorPane.thinking  { border: round $warning; }
FlavorPane.streaming { border: round $primary; }
FlavorPane.tool_call { border: round $success; }
FlavorPane.error     { border: round $error; }
```

Python only needs to flip the class — Textual animates the rest.

### Pulse animations

Active ToolCallBlocks and ThinkingBlocks pulse via `@keyframes` on box-shadow (where supported) or border color cycling via `set_interval`:

```python
class PulseBorder(Widget):
    def on_mount(self):
        self._pulse = 0
        self.set_interval(0.05, self._animate)

    def _animate(self):
        self._pulse = (self._pulse + 0.05) % 1.0
        intensity = abs(math.sin(self._pulse * math.pi))
        # Color interpolation between dim and bright
        self.styles.border = ("round", color_at(intensity))
```

### Chevron rotation

```python
class ExpandChevron(Static):
    expanded = reactive(False)

    def watch_expanded(self, val: bool) -> None:
        # Approach A: character swap (no animation, instant)
        self.update("▾" if val else "▸")
        # Approach B: Textual transform animation
        # self.styles.animate("transform",
        #                     value="rotate(90deg)" if val else "rotate(0)",
        #                     duration=0.2, easing="out_cubic")
```

---

## Keybindings

### Global

| Key | Action |
|---|---|
| `ctrl+p` | Command Modal (central hub) |
| `ctrl+s` | Sessions modal (direct) |
| `ctrl+m` | Memory modal (direct) |
| `ctrl+k` | Skills modal (direct) |
| `ctrl+t` | Tools/MCP modal (direct) |
| `ctrl+n` | New session in active flavor |
| `ctrl+b` | Toggle sidebar |
| `ctrl+f` | Search in conversation |
| `ctrl+c` | Stop generation |
| `Tab` / `Shift+Tab` | Switch flavor |
| `?` | Help overlay |
| `q` | Quit (when input empty) |
| `d` | Toggle theme |
| `ESC` | Pop modal / dismiss overlay |

### Conversation

| Key | Action |
|---|---|
| `↑↓ PgUp PgDn` | Scroll conversation |
| `x` or `space` | Toggle chevron on focused block |
| `y` | Yank focused block to clipboard |
| `Y` | Yank last assistant code block |
| `n` / `N` | Next / previous search match |

### Input

| Key | Action |
|---|---|
| `ctrl+j` | Submit message |
| `Shift+Enter` | Newline (modern terminals only) |
| `Enter` | Newline (TextArea default) |
| `/` | Slash command autocomplete |
| `@` | File/agent reference (V2) |

### Modal-specific

| Modal | Keys |
|---|---|
| SessionsModal | `r` resume, `f` fork, `e` rename, `d` delete, `n` new |
| MemoryModal | `Tab` switch agent/user, `a` add, `e` edit (V2), `d` delete entry (V2) |
| PermissionModal | `y` allow, `n`/`ESC` deny, `a` always allow |
| HelpModal | `ESC` / `?` close |

### Copy keys explained

| Key | Action | Mechanism |
|---|---|---|
| `cmd+c` (macOS) / `ctrl+shift+c` (Linux/Windows) | Copy selected text | Terminal-native — drag-select first |
| `y` | Yank focused block | Textual `App.copy_to_clipboard()` → OSC52 |
| `Y` | Yank last assistant code block | Same |
| `ctrl+c` | Stop generation | Cancel SSE worker |

---

## Hermes CLI → TUI feature mapping

Legend: `v1` shipped in v1 · `v2` planned · `auto` automatic · `modal` opens modal · `inline` in chat · `sidebar` in sidebar

### Session management

| Hermes CLI | TUI surface | Trigger | Scope |
|---|---|---|---|
| `/help` | HelpModal | `?` · ctrl+p → Help | v1 |
| `/new` | New session in active flavor | `ctrl+n` · ctrl+p → New | v1 |
| `/resume [id]` | SessionsModal — Resume | `ctrl+s` → `r` | v1 |
| `/fork [id]` | SessionsModal — Fork | ctrl+s → `f` | v1 |
| `/sessions` | SessionsModal | `ctrl+s` · ctrl+p → Sessions | v1 |
| `/title [text]` | SessionsModal — Rename | ctrl+s → `e` | v1 |
| `/history` | ConversationView scrollback | `PgUp` / `↑` | v1 (auto) |
| `/context` | Sidebar Context section | always visible · click for breakdown | v1 (sidebar) |
| `/compact` | Auto-trigger near limit | `/compact` in input | v1 (auto) |
| `/delete [id]` | SessionsModal — Delete + ConfirmModal | ctrl+s → `d` → `y` | v1 |

### Memory

| Hermes CLI | TUI surface | Trigger | Scope |
|---|---|---|---|
| `/memory read` | Sidebar Memory + MemoryModal | always visible · `ctrl+m` | v1 |
| `/memory add <text>` | Slash command in input | type `/memory add …` | v1 (inline) |
| `/memory remove <n>` | Slash command in input | type `/memory remove N` | v1 (inline) |
| `/memory replace <n> <text>` | Slash command in input | type `/memory replace N "…"` | v1 (inline) |
| `/user read` | MemoryModal — User Profile tab | ctrl+m → `Tab` | v1 |
| `/user add/remove/replace` | Slash command in input | same as `/memory` but for user | v1 (inline) |

### Tools, skills, MCP

| Hermes CLI | TUI surface | Trigger | Scope |
|---|---|---|---|
| (tool call) | ToolCallBlock + sidebar Activity row | auto on SSE `tool_call` event | v1 |
| `/tools` | ToolsModal | `ctrl+t` · ctrl+p → Tools | v1 |
| `/skills` | SkillsModal + sidebar active skills | `ctrl+k` · ctrl+p → Skills | v1 |
| `/skill load <name>` | Slash command + sidebar update | type `/skill load name` | v1 |
| (skill invocation) | SkillBlock (purple, ⚡) | auto on SSE `skill_loaded` event | v1 |
| `/mcp` | ToolsModal — MCP tab + sidebar status | ctrl+t → MCP | v2 |
| `/toolset` | ToolsModal — Toolsets tab | ctrl+t → Toolsets | v2 |
| (permission required) | PermissionModal — y/n/a | auto on SSE event | v1 |

### Model, cost, config

| Hermes CLI | TUI surface | Trigger | Scope |
|---|---|---|---|
| `/model` | Header (display) + ModelPickerModal | ctrl+p → Switch Model | v1 |
| `/cost` | CostModal — usage breakdown | ctrl+p → Cost | v1 |
| `/tokens` | Sidebar Context + status bar | always visible | v1 (sidebar) |
| `/status` | Status bar (always visible) | always visible | v1 (auto) |
| `/config` | ConfigModal | ctrl+p → Configuration | v1 |
| `/set`, `/get`, `/unset` | Slash command in input | type `/set key value` | v1 (inline) |
| `/export`, `/import` | ConfigModal — buttons | ctrl+p → Configuration | v2 |
| `/version` | HelpModal footer | `?` | v1 |
| `/whoami` | Header (right side) | always visible | v1 |

### Conversation actions

| Hermes CLI | TUI surface | Trigger | Scope |
|---|---|---|---|
| (send message) | InputArea | `ctrl+j` | v1 |
| (cancel generation) | Stop SSE worker | `ctrl+c` | v1 |
| (search history) | SearchBar (floats top) | `ctrl+f` | v1 |
| (copy code) | Yank to clipboard | `y` / `Y` | v1 |
| (expand/collapse block) | Chevron toggle | `x` · `space` · click | v1 |
| (paste image) | Drag-drop / `/paste` | drag · `/paste` | v2 |

### Flavor / multi-agent

| Hermes CLI | TUI surface | Trigger | Scope |
|---|---|---|---|
| (switch flavor) | TabbedContent | `Tab` / `Shift+Tab` · click | v1 |
| (new flavor) | Auto-discovered + manual `/flavor` | backend discovery · `/flavor` | v2 |
| `@subagent` reference | @mention chip in input | type `@` · autocomplete | v2 |

### Advanced (V2)

| Hermes CLI | TUI surface | Trigger | Scope |
|---|---|---|---|
| `/cron` | CronModal — DataTable of jobs | ctrl+p → Cron | v2 |
| `/kanban` | KanbanModal — board with columns | ctrl+p → Kanban | v2 |
| `/browser` | BrowserModal — screenshot preview | ctrl+p → Browser | v2 |
| `/debug` | DebugModal — raw SSE event log | ctrl+p → Debug · `/debug` | v2 |
| `/plugins` | PluginsModal — enable/disable list | ctrl+p → Plugins | v2 |
| `/restart` | Backend restart trigger | ctrl+p → Restart (with confirm) | v2 |
| `/update` | UpdateModal — version check | ctrl+p → Update | v2 |
| (image input) | Drag-drop / `/paste` | drag · `/paste` | v2 |

---

## Widget hierarchy

```
Nx01App (App)
├── AppHeader (Static, docked=top)
├── TabbedContent
│   └── TabPane (id="flavor-{name}", per flavor)
│       └── FlavorPane (Horizontal, CSS class = state)
│           ├── ConversationContainer (Vertical, width=1fr)
│           │   ├── ConversationView (VerticalScroll)
│           │   │   ├── SearchBar (Input, hidden by default)
│           │   │   ├── UserMessage (Markdown)
│           │   │   ├── ThinkingBlock (Collapsible)
│           │   │   │   └── RichLog (streaming thought chunks)
│           │   │   ├── ToolCallBlock (Collapsible)
│           │   │   │   ├── Static (header row)
│           │   │   │   └── RichLog (streaming output + diff)
│           │   │   ├── SkillBlock (Collapsible)
│           │   │   │   └── Markdown (skill content)
│           │   │   └── AssistantMessage (Markdown, streaming)
│           │   └── InputArea (Horizontal, fixed)
│           │       ├── ChatInput (TextArea, auto-expand)
│           │       └── SlashDropdown (SelectionList, floats above)
│           └── MonitorSidebar (Vertical, width=28)
│               ├── ActivitySection (VerticalScroll)
│               ├── MemorySection (Static + progress bars)
│               ├── SkillsSection (Static + labels)
│               ├── ContextSection (Static + progress bar)
│               └── SessionSection (Static)
├── StatusBar (Static, docked=bottom)
├── Footer (Footer, docked=bottom)
└── ModalScreen stack
    ├── CommandModal (ctrl+p) — CENTRAL HUB
    ├── SessionsModal (ctrl+s)
    ├── MemoryModal (ctrl+m)
    ├── SkillsModal (ctrl+k)
    ├── ToolsModal (ctrl+t)
    ├── ConfigModal
    ├── CostModal
    ├── ModelPickerModal
    ├── HelpModal (?)
    ├── PermissionModal (on SSE permission_required)
    └── ConfirmModal (destructive actions)
```

---

## TCSS outline

```css
/* nx01_tui/tui/app.tcss */

/* ── Layout ──────────────────────────────────────────────── */
Screen { layers: base modals; }
AppHeader { dock: top; height: 1; background: $surface; }
StatusBar { dock: bottom; height: 1; background: $surface; }
Footer { dock: bottom; }
TabbedContent { height: 1fr; }

FlavorPane { layout: horizontal; border: round $panel; transition: border 300ms in_out_cubic; }
ConversationContainer { width: 1fr; height: 1fr; }
ConversationView { height: 1fr; padding: 1 2; }
InputArea { height: auto; min-height: 3; max-height: 10; border-top: solid $panel; }

/* ── Sidebar ─────────────────────────────────────────────── */
MonitorSidebar { width: 28; height: 1fr; border-left: solid $panel;
                 background: $background-darken-1; }
MonitorSidebar.hidden     { display: none; }
MonitorSidebar.icon-strip { width: 3; }

/* ── State machine (animated borders) ────────────────────── */
FlavorPane.thinking  { border: round $warning; }
FlavorPane.streaming { border: round $primary; }
FlavorPane.tool_call { border: round $success; }
FlavorPane.error     { border: round $error; }

/* ── Conversation blocks ─────────────────────────────────── */
ThinkingBlock         { border: round $warning; margin: 0 0 1 0; }
ThinkingBlock.done    { border: round $warning 30%; opacity: 0.7; }

ToolCallBlock         { border: round $panel; margin: 0 0 1 0; }
ToolCallBlock.queued  { opacity: 0.45; }
ToolCallBlock.active  { border: round $success; }
ToolCallBlock.done    { border: round $success 30%; opacity: 0.7; }
ToolCallBlock.error   { border: round $error; }

SkillBlock            { border: round $accent; margin: 0 0 1 0; opacity: 0.7; }

UserMessage           { margin-right: 8; padding: 0 1; }
AssistantMessage      { margin-left: 0; }

/* ── Input ───────────────────────────────────────────────── */
ChatInput        { height: auto; min-height: 1; max-height: 8;
                   border: round $panel; padding: 0 1; }
ChatInput:focus  { border: round $primary; }

/* ── Modals ──────────────────────────────────────────────── */
ModalScreen { align: center middle; }
CommandModal > .dialog    { width: 60; height: auto; border: round $primary; }
SessionsModal > .dialog   { width: 70; height: 80%; border: round $primary; }
MemoryModal > .dialog     { width: 60; height: 70%; border: round $accent; }
PermissionModal > .dialog { width: 60; height: auto; border: thick $error; }
HelpModal > .dialog       { width: 60; height: auto; border: round $primary; }

/* ── Floating overlays ───────────────────────────────────── */
SearchBar      { display: none; dock: top; height: 1; border: round $primary; }
SearchBar.visible { display: block; }
SlashDropdown  { display: none; dock: top; max-height: 8; border: round $panel; }
SlashDropdown.visible { display: block; }

/* ── Sidebar sections ────────────────────────────────────── */
SidebarSection .section-title { color: $text-muted; text-style: upper; }
ActivityRow.active            { background: $success 10%; }
ActivityRow.error             { color: $error; }
SidebarProgress.low    Bar    { color: $success; }
SidebarProgress.medium Bar    { color: $warning; }
SidebarProgress.high   Bar    { color: $error; }
```

---

## SSE event handling

The TUI subscribes to the nx01 API's `/events` stream and dispatches messages to widgets based on event type.

| SSE event | Handler |
|---|---|
| `agent_thought_chunk` | Append to active `ThinkingBlock`'s RichLog |
| `agent_thought_done` | `ThinkingBlock.done()` — collapse with duration |
| `agent_message_chunk` | Append to active `AssistantMessage`'s Markdown |
| `tool_call_start` | Create new `ToolCallBlock(state="active")` |
| `tool_call_output` | Append to ToolCallBlock's RichLog |
| `tool_call_done` | `ToolCallBlock.mark_done(summary)` |
| `tool_call_error` | `ToolCallBlock.mark_error(msg)` |
| `skill_loaded` | Create new `SkillBlock` + add to sidebar Skills section |
| `permission_required` | `await app.push_screen_wait(PermissionModal(...))` |
| `agent_turn_done` | Set state to `done`, finalize blocks |
| `token_usage` | Update sidebar Context section + status bar |
| `flavor_status` | Update tab indicator |
| `error` | Set state to `error`, show error in conversation |

Implementation:

```python
@work(exclusive=True, group="sse")
async def sse_worker(self) -> None:
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", f"{self.api_url}/events",
                                  headers={"Authorization": f"Bearer {self.api_key}"}) as r:
            async for line in r.aiter_lines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    self.post_message(SseEvent(event))

def on_sse_event(self, message: SseEvent) -> None:
    event = message.event
    handler = self.EVENT_HANDLERS.get(event["type"])
    if handler:
        handler(self, event)
```

---

## Error & disconnection

### Connection states

| State | Indicator | Behaviour |
|---|---|---|
| Connected | `⬤` green in header | Normal operation |
| Disconnected | `✗ Disconnected` in status bar (red) + retry button | All tabs disabled until reconnected |
| Reconnecting | `⠋ Reconnecting…` (yellow, braille spin) + attempt counter | Show in status bar |
| Per-flavor error | `✗ flavor` tab indicator (red) | That tab shows error in conversation |

### Reconnection logic

Exponential backoff: 1s, 2s, 4s, 8s, 16s (capped). Auto-retry indefinitely; manual retry via `r` key in disconnected state.

```python
async def reconnect_with_backoff(self):
    delay = 1.0
    while not self._connected:
        try:
            await self._connect()
            return
        except Exception as e:
            await asyncio.sleep(min(delay, 16.0))
            delay *= 2
```

---

## V1 / V2 scope

### V1 (22 features)

- Tabbed cockpit (TabbedContent per flavor)
- AppHeader (domain + model)
- SSE streaming infrastructure
- ThinkingBlock (collapsible, duration)
- ToolCallBlock (inline, 5 states)
- SkillBlock (purple, ⚡)
- Diff display (inline in tool block)
- Agent state animations (4 states + transitions)
- MonitorSidebar (Activity / Memory / Skills / Context / Session)
- Sidebar responsive auto-hide
- ChatInput (TextArea, multi-line, ctrl+j submit)
- Slash command autocomplete (textual-autocomplete)
- CommandModal (ctrl+p) — central hub
- SessionsModal (ctrl+s)
- MemoryModal (ctrl+m)
- SkillsModal (ctrl+k)
- ToolsModal (ctrl+t)
- ConfigModal
- CostModal
- ModelPickerModal
- HelpModal (?)
- PermissionModal
- ConfirmModal (destructive actions)
- StatusBar
- In-conversation search (ctrl+f)
- Copy code (y/Y, OSC52)
- Error / disconnection states + reconnect
- Stop generation (ctrl+c)
- Chevron expand/collapse with rotation
- Token / context usage meter

### V2 (~15 features)

- `@file` reference chips in input (OpenCode extmarks)
- Click-to-copy per code block (widget-per-block)
- Memory editing in modal
- Rotating verb text on spinner (Claude Code style)
- Rainbow shimmer gradient (opt-in, high CPU)
- Cron job manager modal
- Kanban board modal
- Browser integration (screenshot preview)
- Plugin manager modal
- Debug panel (raw SSE event log)
- Agent color cycling (multi-agent threads)
- Image input (drag-drop, `/paste`, clipboard)
- MCP server integration UI
- Toolsets manager
- Update checker / restart server

### Out of scope

- Subprocess REPL (Hermes interactive prompts not relevant to TUI)
- Direct shell escape (use `bash` tool instead)
- File browser sidebar (use `@file` chips in V2 instead)

---

## References

- [Crush](https://github.com/charmbracelet/crush) — Bubble Tea AI TUI
- [OpenCode](https://github.com/sst/opencode) — SolidJS / OpenTUI AI assistant
- [Claude Code](https://docs.anthropic.com/claude/docs/claude-code) — Ink-based AI TUI
- [Textual docs](https://textual.textualize.io/)
- [Rich docs](https://rich.readthedocs.io/)
- [textual-autocomplete](https://github.com/darrenburns/textual-autocomplete)
- [Hermes CLI](https://github.com/openai/hermes) — backing agent runtime
- [nx01 main repo](https://github.com/podo/nx01)
