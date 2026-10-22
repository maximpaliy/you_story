export UV_CACHE_DIR := $(CURDIR)/work/uv-cache

.PHONY: sync check unit format openapi

sync:
	UV_CACHE_DIR=work/uv-cache uv sync --frozen

check:
	uv run --frozen ruff check .
	uv run --frozen ruff format --check .
	uv run --frozen mypy
	uv run --frozen python -m tools.check_architecture
	uv run --frozen python -m tools.export_openapi --check
	uv run --frozen python -m pytest --junitxml=work/test-results.xml
	uv build --wheel --out-dir dist
	uv run --frozen python -m tools.check_artifact

unit:
	uv run --frozen python -m pytest -m 'not postgres'

format:
	uv run --frozen ruff check --fix .
	uv run --frozen ruff format .

openapi:
	uv run --frozen python -m tools.export_openapi
