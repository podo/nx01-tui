# nx01-tui

TUI client for the NX01 fleet agent system.

## Install

```bash
pip install nx01-tui
```

Or for development:

```bash
git clone https://github.com/podo/nx01-tui.git
cd nx01-tui
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Usage

```bash
# Interactive chat
nx01-tui chat --url https://your-server.example.com --api-key YOUR_API_KEY

# Interactive TUI (rich terminal UI)
nx01-tui tui --url https://your-server.example.com --api-key YOUR_API_KEY
```

Get your API key from the NX01 server's `/profile` endpoint.
