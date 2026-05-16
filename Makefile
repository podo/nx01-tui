NX01_URL     ?= http://localhost:8000
NX01_API_KEY ?=
APP           = nx01_tui/tui/app.py
ARGS          = -- --url $(NX01_URL) $(if $(NX01_API_KEY),--api-key $(NX01_API_KEY),)

.PHONY: help dev console console-verbose console-quiet serve \
        test test-fast test-cov snapshot snapshot-update lint fmt check install

help:
	@echo "nx01-tui — developer targets"
	@echo ""
	@echo "  make dev               — run with live CSS reload (start console in another terminal first)"
	@echo "  make console           — start the Textual debug console (run in a separate terminal)"
	@echo "  make console-verbose   — console with EVENT logging"
	@echo "  make console-quiet     — console with only WARNING+ messages"
	@echo "  make serve             — serve the TUI over HTTP via textual-serve"
	@echo "  make test              — run full pytest suite with coverage"
	@echo "  make test-fast         — run pytest without coverage (inner-loop dev)"
	@echo "  make snapshot          — run snapshot tests"
	@echo "  make snapshot-update   — regenerate snapshot baselines"
	@echo "  make lint              — ruff check + ruff format check"
	@echo "  make fmt               — ruff format + ruff check --fix"
	@echo "  make check             — lint + test (CI gate)"
	@echo "  make install           — uv sync with dev extras"

# ── Devtools (per Textual devtools guide) ─────────────────────────────

dev:
	textual run --dev $(APP) $(ARGS)

console:
	textual console

console-verbose:
	textual console -v

console-quiet:
	textual console -x EVENT -x DEBUG

serve:
	textual serve $(APP) $(ARGS)

# ── Test ──────────────────────────────────────────────────────────────

test:
	uv run pytest --cov=nx01_tui --cov-report=term-missing

test-fast:
	uv run pytest

snapshot:
	uv run pytest tests/snapshots/

snapshot-update:
	uv run pytest --snapshot-update

# ── Lint / format ─────────────────────────────────────────────────────

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

check: lint test

install:
	uv sync --extra dev
