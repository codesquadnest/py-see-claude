# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

py-see-claude is a zero-dependency Python web dashboard that monitors running Claude Code sessions. It detects processes via `pgrep`/`ps`/`lsof`, reads session JSONL files from `~/.claude/projects/`, and serves a live-updating SPA over SSE. Terminal integration (focus, send, launch) uses AppleScript on macOS.

## Commands

```bash
# Install dev dependencies
uv sync --group dev

# Run the dashboard
uv run py-see-claude

# Linting & formatting
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Type checking
uv run mypy src/

# Pylint
uv run pylint src/py_see_claude/

# Tests
uv run pytest                        # all tests
uv run pytest tests/test_server.py   # single file
uv run pytest -k test_name           # single test

# All checks at once via tox
uv run tox
```

## Architecture

Four backend modules, each with a single responsibility:

- **process.py** — Finds Claude PIDs and reads process stats (CPU, memory, TTY, cwd). Uses `pgrep`/`ps` on both platforms, `lsof` on macOS, `/proc` on Linux.
- **sessions.py** — Dataclasses (`LiveSession`, `RecentSession`, `ProjectRoster`, `Message`) and functions that combine process info with JSONL session files from `~/.claude/projects/`. Status is derived from last message role + CPU usage.
- **terminal.py** — macOS-only AppleScript integration. Detects terminal emulator (Ghostty, iTerm2, Terminal.app) by walking the process tree, then dispatches to terminal-specific implementations for focus/send/launch.
- **server.py** — `ThreadedHTTPServer` with `DashboardHandler`. REST API (`/api/sessions`, `/api/ls`, `/api/focus`, `/api/send`, `/api/new`, `/api/launch`) plus SSE streaming (`/api/stream`) via a background broadcaster thread every 2 seconds. Serves static files from `static/`.

The frontend is a single-page app (`static/index.html`, `app.js`, `style.css`) that connects via SSE for live updates. Two view modes: terminal cards and pixel art office scene.

## Key Conventions

- **Zero runtime dependencies** — stdlib only (`http.server`, `json`, `subprocess`, `pathlib`, `threading`). Dev tools are in the `dev` dependency group.
- **Dataclass serialization** — All data structures use `@dataclass` with a `_serialize()` helper that converts snake_case to camelCase for the JSON API.
- **Graceful degradation** — All subprocess calls are wrapped in try/except and return empty/None on failure. Nothing crashes the server.
- **Strict typing** — `from __future__ import annotations` everywhere, strict mypy, `TYPE_CHECKING` guards.
- **Security** — Optional HTTP Basic Auth via `SEE_CLAUDE_AUTH` env var with HMAC comparison. Path traversal prevention via resolve + prefix checks. Shell args escaped with `shlex.quote()`.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `3456` | Server listen port |
| `CLAUDE_HOME` | `~/.claude` | Claude data directory |
| `SEE_CLAUDE_AUTH` | *(none)* | HTTP Basic Auth (`user:pass`) |
| `SEE_CLAUDE_REMOTES` | *(none)* | Multi-machine remotes (`name=host:port,...`) |
