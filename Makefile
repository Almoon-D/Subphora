# Developer commands. Everything runs inside the uv-managed environment, against the locked
# dependency set (uv.lock).

UV_RUN := uv run --locked

.PHONY: setup check test fmt lint types imports format-check coverage prompt

setup:  ## Update uv and Python, install the locked environment
	@# An old uv does not know the newest Python. `self update` works for the standalone
	@# installer; cloud sessions ship uv another way, where `tool install` replaces it.
	uv self update 2>/dev/null || uv tool install --force uv
	@# Newest patch of every installed Python (3.15.2 → 3.15.3); the environment follows it.
	uv python upgrade
	uv sync --locked

check: format-check lint types imports coverage  ## Everything CI runs

test:  ## pytest only
	$(UV_RUN) pytest

fmt:  ## Format the code
	$(UV_RUN) ruff format

lint:
	$(UV_RUN) ruff check

types:
	$(UV_RUN) mypy

imports:
	$(UV_RUN) lint-imports

format-check:
	$(UV_RUN) ruff format --check

coverage:  ## pytest with the coverage floor from pyproject.toml
	$(UV_RUN) pytest --cov --cov-report=term-missing

prompt:  ## The common header and one session's prompt: make prompt S=01 (or S=maintenance)
	@test -n "$(S)" || { echo "usage: make prompt S=<session id, e.g. 01, 01a, maintenance>" >&2; exit 2; }
	@f=$$(ls docs/sessions/$(S)-*.md docs/sessions/$(S).md 2>/dev/null | head -1); \
	 test -n "$$f" || { echo "no docs/sessions/$(S)-*.md" >&2; exit 2; }; \
	 cat docs/sessions/_header.md; echo; cat "$$f"
