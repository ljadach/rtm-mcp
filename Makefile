.PHONY: install dev lint format test test/coverage run clean help

help:
	@echo "RTM MCP Server - Development Commands"
	@echo ""
	@echo "  make install      Install dependencies"
	@echo "  make dev          Install with dev dependencies"
	@echo "  make lint         Run linting (ruff + pyright)"
	@echo "  make format       Format code with ruff"
	@echo "  make test         Run tests"
	@echo "  make test/coverage Run tests with coverage"
	@echo "  make run          Run the MCP server"
	@echo "  make setup        Run auth setup script"
	@echo "  make inspect      Run MCP Inspector"
	@echo "  make clean        Clean build artifacts"

install:
	uv sync

dev:
	uv sync --all-extras

lint:
	uv run ruff check src tests
	uv run pyright src

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

test:
	uv run pytest

test/coverage:
	uv run pytest --cov=src/rtm_mcp --cov-report=term-missing --cov-report=html

run:
	uv run rtm-mcp

setup:
	uv run rtm-setup

inspect:
	npx @modelcontextprotocol/inspector uv run rtm-mcp

clean:
	rm -rf .ruff_cache .pytest_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
