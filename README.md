# py-see-claude

A lightweight Python dashboard that shows all your running [Claude Code](https://docs.anthropic.com/en/docs/claude-code) sessions in one place. See which projects they're in, whether they're working or idle, and click to jump straight to that terminal.

> **Based on [see-claude](https://github.com/lukejbyrne/see-claude) by [@lukejbyrne](https://github.com/lukejbyrne)**
> This is a Python rewrite with improved project structure, Docker support, and dev tooling.

## What It Does

- Detects all running Claude Code sessions on your machine
- **Two views**: terminal cards or pixel art characters at desks
- Status indicators: **green** = actively working, **yellow** = thinking, **grey** = idle
- Click any session to expand it with full conversation history
- Send messages to Claude sessions directly from the dashboard
- Click to focus that Terminal tab (macOS only)
- Launch new sessions with a directory browser
- Resume recent sessions with one click
- `--dangerously-skip-permissions` toggle for resume/launch
- Desktop notifications when Claude finishes working
- Auto-refreshes via server-sent events

## Requirements

- **Python** 3.11 or higher (or Docker)
- **macOS** or **Linux** (macOS for full Terminal integration; Linux for Docker/monitoring)
- At least one running Claude Code session

## Quick Start

### With uv (recommended)

```bash
git clone <repo-url>
cd py-see-claude
uv run py-see-claude
```

### With pip

```bash
pip install .
py-see-claude
```

### With Docker

```bash
docker build -t py-see-claude .
docker run --rm -p 3456:3456 \
  --pid=host \
  --user "$(id -u):$(id -g)" \
  -v "$HOME/.claude:/home/app/.claude:ro" \
  py-see-claude
```

Then open **<http://localhost:3456>** in your browser.

## Docker Notes

The Docker setup is designed for **Linux hosts** where Claude Code runs directly:

- `--pid=host` shares the host PID namespace so the dashboard can detect Claude processes
- `-v "$HOME/.claude:/home/app/.claude:ro"` mounts your Claude data **read-only** — the dashboard never writes to your Claude files
- `--user "$(id -u):$(id -g)"` runs the container as your host user, ensuring correct file permission handling without compromising Claude's file ownership

**macOS Docker limitation**: Docker on macOS runs inside a Linux VM, so it cannot see host macOS processes. On macOS, run directly with `uv run py-see-claude` instead.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `PORT` | `3456` | Server listen port |
| `CLAUDE_HOME` | `~/.claude` | Path to Claude data directory |

## How It Works

1. Uses `pgrep` to find running `claude` processes
2. Uses `ps` and `lsof` (or `/proc` on Linux) to get each session's working directory, CPU, memory, and uptime
3. Reads session files from `~/.claude/projects/` for conversation history and status
4. Serves a single-page dashboard with live updates via SSE
5. On macOS, uses AppleScript to find and focus the matching Terminal tab

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run linting
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Run type checking
uv run mypy src/

# Run pylint
uv run pylint src/py_see_claude/

# Run tests
uv run pytest

# Run all checks
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/ && uv run pytest
```

## Project Structure

```bash
py-see-claude/
├── pyproject.toml              # Project config (uv, ruff, mypy, pylint, pytest)
├── Dockerfile                  # Container support
├── src/
│   └── py_see_claude/
│       ├── __init__.py         # Package metadata
│       ├── __main__.py         # Entry point
│       ├── server.py           # HTTP server, routing, SSE
│       ├── sessions.py         # Session detection, messages, roster
│       ├── process.py          # Process inspection (pgrep, ps, lsof, /proc)
│       ├── terminal.py         # macOS Terminal integration (AppleScript)
│       └── static/
│           ├── index.html      # Dashboard HTML
│           ├── style.css       # Styles
│           └── app.js          # Frontend logic + pixel art renderer
└── tests/
    ├── conftest.py             # Test fixtures
    ├── test_sessions.py        # Session logic tests
    ├── test_process.py         # Process inspection tests
    └── test_server.py          # HTTP server tests
```

## Zero Runtime Dependencies

Like the original, this project uses only Python standard library modules for runtime (`http.server`, `json`, `subprocess`, `pathlib`, `threading`). No pip install needed beyond the package itself. Dev tools (ruff, mypy, pylint, pytest) are development-only dependencies.

## Credits

- Original [see-claude](https://github.com/lukejbyrne/see-claude) by [Luke Byrne](https://github.com/lukejbyrne) — the Node.js dashboard that inspired this Python rewrite
- Pixel art view, character design, and office scene from the original project

## License

MIT
