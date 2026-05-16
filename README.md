# nx01-tui

Operator cockpit for the [NX01](https://github.com/podo/nx01) fleet agent system — a full-screen Textual TUI and a lightweight chat/watch CLI.

## Install

```bash
# Recommended (uv — isolates the tool from your project venv)
uv tool install git+https://github.com/podo/nx01-tui

# Or with plain pip
pip install git+https://github.com/podo/nx01-tui
```

Requires Python 3.11+.

## Usage

```bash
# Full-screen TUI (both flavors as live tabs)
nx01-tui tui --url https://<your-domain> --api-key <NX01_API_KEY>

# Single-flavor chat (readline REPL)
nx01-tui chat --url https://<your-domain> --api-key <NX01_API_KEY> --flavor assistant
nx01-tui chat --url https://<your-domain> --api-key <NX01_API_KEY> --flavor operator

# Stream live agent events
nx01-tui watch --url https://<your-domain> --api-key <NX01_API_KEY>
```

`NX01_API_KEY` is the bearer token set in the server's `.env`.

### Keybindings (TUI)

| Key | Action |
|-----|--------|
| `ctrl+1`–`4` | Switch flavor tab |
| `Esc` | Clear input |
| `Esc` × 2 | Send `/stop` to active flavor |
| `q` | Quit (when input empty) |
| `@flavor msg` | Route message to specific flavor |
| `/command` | Open command palette |

## Development

```bash
git clone https://github.com/podo/nx01-tui.git
cd nx01-tui
uv sync --extra dev
```

### Devtools

Install [textual-dev](https://github.com/Textualize/textual) (included in dev deps):

```bash
uv sync --extra dev
```

**Live CSS editing + console debugger:**

```bash
# Terminal 1 — open event console
textual console -v

# Terminal 2 — run with hot reload
textual run --dev nx01_tui/tui/app.py -- --url https://<your-domain> --api-key <key>
```

Any CSS change in `app.py` reflects instantly. `self.log(...)` calls appear in the console without corrupting the TUI.

**Browser preview (no terminal needed):**

```bash
textual serve nx01_tui/tui/app.py -- --url https://<your-domain> --api-key <key>
```

Opens the TUI at `http://localhost:8000` — useful for layout review and screenshots.

**Make shortcuts:**

```bash
make dev      # run with --dev + console
make serve    # open in browser
make test     # run test suite
make lint     # ruff check + format
```

Set `NX01_URL` and `NX01_API_KEY` env vars to skip typing them each time:

```bash
export NX01_URL=https://77.42.71.240.nip.io
export NX01_API_KEY=your-key
make dev
```

## Update

From any nx01 installation:

```bash
nx01 tui update
```
