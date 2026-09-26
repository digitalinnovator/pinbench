.PHONY: dev check test docker-test demo clean

# One-command setup: the canary's env plus the isolated, hash-locked Harbor env (ADR-0002).
dev:
	uv sync --frozen
	uv sync --frozen --project tools/harbor

check:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy
	uv run pytest -m "not docker"

test:
	uv run pytest -m "not docker"

# Real Harbor trials in Docker with the zero-cost oracle and nop agents.
docker-test:
	uv run pytest -m docker -v

# Simulated compare: no Docker, no API keys, no spend.
demo:
	uv run canary compare stable regressed -c examples/simulated

# Sealed bundles are read-only; restore write permission before deleting local state.
clean:
	find . -path ./tools/harbor/.venv -prune -o -type d -name .canary -print0 \
		| xargs -0 -I{} sh -c 'chmod -R u+w "{}" && rm -rf "{}"'
