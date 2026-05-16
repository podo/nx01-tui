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

For development:

```bash
git clone https://github.com/podo/nx01-tui.git
cd nx01-tui
pip install -e ".[dev]"
```

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

`NX01_API_KEY` is the bearer token set in the server's `.env` (`NX01_API_KEY`).

## Update

From any nx01 installation:

```bash
nx01 tui update
```
