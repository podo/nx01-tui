# nx01-tui

Operator cockpit for the [NX01](https://github.com/podo/nx01) fleet — a full-screen Textual TUI plus chat / watch / doctor / install / update CLIs.

## Quick start

```bash
# 1. Install (requires Python 3.11+)
uv tool install git+https://github.com/podo/nx01-tui            # isolated (recommended)
# or:  pip install git+https://github.com/podo/nx01-tui

# 2. Point at your NX01 server
export NX01_URL='https://<your-domain>'
export NX01_API_KEY='<64-char bearer token from the server .env>'

# 3. Verify the install + connection
nx01-tui test          # imports + headless boot + live probe

# 4. Launch
nx01-tui tui
```

Once `NX01_URL` and `NX01_API_KEY` are set, every command picks them up automatically. You never need to retype them.

## Commands

| Command | What it does |
|---------|--------------|
| `nx01-tui tui` | Full-screen cockpit (tabs per flavor, sidebar, modals) |
| `nx01-tui chat --flavor <name>` | Single-turn REPL against one flavor |
| `nx01-tui watch [--flavor <name>]` | Live SSE event stream |
| `nx01-tui doctor` | Probe `/health` + auth-gated endpoints (`/flavors`, `/commands`, `/tools`) |
| `nx01-tui test` | Imports + headless app boot + modal-stack check (no pytest needed) |
| `nx01-tui install` | Reinstall from GitHub HEAD + run the smoke test |
| `nx01-tui update` | Reinstall from GitHub HEAD only |

Each command accepts `--url` and `--api-key` to override the env vars on a one-shot basis.

### Updating

```bash
nx01-tui update     # pulls latest main, reinstalls in place
```

Auto-detects whether you installed via `uv tool`, `uv pip`, or plain `pip` and runs the right upgrade command. Pin to a fork with `NX01_TUI_SOURCE=git+https://github.com/you/nx01-tui` or `nx01-tui update --source git+…`.

### Diagnosing connection issues

```bash
$ nx01-tui doctor
NX01 doctor — https://77.42.71.240.nip.io
  /health                       HTTP 200
  /flavors (auth)               HTTP 401  ← --api-key wrong or missing (must be 64 hex chars)
  /commands (auth)              HTTP 401
  /tools                        HTTP 200
✗ 2 failed
```

`401` means your `NX01_API_KEY` doesn't match the server's. `unreachable` means DNS / TLS / Caddy issue. The header in the TUI also shows the cause: green dot = OK, red dot + `(auth failed)` = 401, red dot + `(offline)` = network.

## Environment variables

| Variable | Default | Used by |
|----------|---------|---------|
| `NX01_URL` | `http://localhost:8000` | `tui`, `chat`, `watch`, `doctor`, `test`, `install` |
| `NX01_API_KEY` | _(none)_ | same |
| `NX01_FLAVOR` | `assistant` | `chat`, `watch` |
| `NX01_TUI_SOURCE` | `git+https://github.com/podo/nx01-tui` | `update`, `install` |

## Keybindings (TUI)

| Key | Action |
|-----|--------|
| `ctrl+p` | Command palette (every action, fuzzy-filtered) |
| `ctrl+s` | Sessions modal — resume / fork / rename / delete |
| `ctrl+m` | Memory modal — agent + user stores |
| `ctrl+k` | Skills modal |
| `ctrl+t` | Tools modal |
| `ctrl+n` | New session in active flavor |
| `ctrl+b` | Toggle sidebar |
| `ctrl+f` | Search in conversation |
| `ctrl+shift+d` | Debug modal — raw SSE event log |
| `ctrl+c` | Stop generation |
| `Enter` | Send message |
| `Shift+Enter` | Newline (modern terminals — Kitty / WezTerm / Ghostty / iTerm2) |
| `Alt+Enter` | Newline (Terminal.app fallback) |
| `ctrl+j` | Send message (universal fallback) |
| `Tab` / `Shift+Tab` | Cycle flavor tabs |
| `?` | Help overlay (auto-generated keybinding table) |
| `q` | Quit |
| `y` / `Y` | Yank focused / last code block |
| `x` or `space` | Expand / collapse focused block |
| `@filename` (in input) | File picker dropdown |
| `/command` (in input) | Slash command autocomplete |

## Development

```bash
git clone https://github.com/podo/nx01-tui.git
cd nx01-tui
uv sync --extra dev
```

### Devtools (Textual)

Two terminals — one for the console, one for the live-reload app:

```bash
# Terminal 1: event console
textual console -v

# Terminal 2: app with hot reload
textual run --dev nx01_tui/tui/app.py -- --url "$NX01_URL" --api-key "$NX01_API_KEY"
```

CSS changes reflect instantly. `self.log(...)` calls land in the console without corrupting the TUI.

### Browser preview

```bash
textual serve nx01_tui/tui/app.py -- --url "$NX01_URL" --api-key "$NX01_API_KEY"
```

Opens the TUI at `http://localhost:8000` — useful for layout review and screenshots.

### Make shortcuts

```bash
make dev               # textual run --dev
make console           # textual console
make serve             # textual serve (browser)
make test              # pytest with coverage
make snapshot          # regenerate SVG snapshot baselines
make snapshot-update   # update + commit baselines
make lint              # ruff check + format check
make fmt               # ruff format + fix
```

## Architecture

The TUI is a single `Nx01App` (Textual `App`) composing:

- **AppHeader** — domain + model + connection state (green / yellow reconnecting / red auth-failed)
- **TabbedContent → FlavorPane** — one per flavor; horizontal layout of conversation + sidebar
- **ConversationView** — scrollable; mounts ThinkingBlock / ToolCallBlock / SkillBlock / CodeBlock / AssistantMessage as SSE events arrive
- **MonitorSidebar** — 6 live sections: Activity (per-turn tools), Memory (progress bars), Skills (loaded), MCP (server status), Context (token meter), Session
- **StatusBar** — agent state + token usage + shortcut hints
- **Modal stack** — CommandModal hub + Sessions / Memory / Skills / Tools / Config / Cost / ModelPicker / Help / Permission / Confirm / Debug

The Hermes backend lives behind `https://<your-domain>` (TLS via Caddy). The client talks to it via:

- `GET /flavors` + SSE `/events` — discovery & live stream
- `POST /message` — submit a turn
- `GET /sessions` / `POST /sessions/{id}/resume|fork` / `PATCH` / `DELETE` — session CRUD
- `GET /memory/{store}?flavor=…` / `POST` — per-flavor memory
- `GET /skills?flavor=…` — per-flavor skill listing
- `GET /commands` — slash command discovery
- `POST /permissions/{id}` — resolve a dangerous-tool prompt
- `POST /abort` — cancel an in-flight turn

See [`DESIGN.md`](./DESIGN.md) for the full spec.
