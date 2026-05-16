NX01_URL ?= http://localhost:8000
NX01_API_KEY ?=
APP = nx01_tui/tui/app.py
ARGS = -- --url $(NX01_URL) $(if $(NX01_API_KEY),--api-key $(NX01_API_KEY),)

.PHONY: dev serve test lint fmt check

dev:
	textual console -v &
	textual run --dev $(APP) $(ARGS)

serve:
	textual serve $(APP) $(ARGS)

test:
	pytest --cov=nx01_tui --cov-report=term-missing

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff format .
	ruff check --fix .

check: lint test
