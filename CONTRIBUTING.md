# Contributing to RTM MCP

Thank you for your interest in contributing!

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/lukasz/rtm-mcp.git
cd rtm-mcp
```

2. Install with dev dependencies:
```bash
make dev
```

3. Set up RTM credentials:
```bash
make setup
```

## Development Workflow

### Running the Server

```bash
make run
```

### Testing

```bash
# Run all tests
make test

# Run with coverage
make test/coverage
```

### Linting

```bash
# Check code
make lint

# Fix formatting
make format
```

## Code Style

- Python 3.11+ with type hints
- Ruff for formatting and linting
- Pyright for type checking
- Async/await for all I/O operations

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`make test && make lint`)
5. Commit with a clear message
6. Push to your fork
7. Open a Pull Request

## Adding New Tools

See [CLAUDE.md](CLAUDE.md) for architecture details and examples.

1. Identify the RTM API method
2. Add tool to appropriate file in `src/rtm_mcp/tools/`
3. Use consistent patterns (see existing tools)
4. Add tests
5. Update README if user-facing

## Questions?

Open an issue for discussion before making major changes.
