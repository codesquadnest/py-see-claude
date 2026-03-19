"""Shared test fixtures for py-see-claude."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest


@pytest.fixture
def tmp_claude_dir(monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Create a temporary .claude directory structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        claude_dir = Path(tmpdir) / ".claude"
        projects_dir = claude_dir / "projects"
        projects_dir.mkdir(parents=True)
        monkeypatch.setattr("py_see_claude.sessions.CLAUDE_DIR", claude_dir)
        monkeypatch.setattr("py_see_claude.sessions.PROJECTS_DIR", projects_dir)
        yield claude_dir


@pytest.fixture
def sample_session_file(tmp_claude_dir: Path) -> Path:
    """Create a sample session JSONL file."""
    projects_dir = tmp_claude_dir / "projects"
    proj_dir = projects_dir / "-Users-testuser-Projects-myapp"
    proj_dir.mkdir(parents=True, exist_ok=True)

    session_file = proj_dir / "abc123.jsonl"
    lines = [
        json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": "fix the failing tests"},
            }
        ),
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "I'll look at the tests now."}],
                },
            }
        ),
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "read_file", "input": {"path": "test.py"}},
                    ],
                },
            }
        ),
        json.dumps(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "tool_result", "content": "file contents here"}],
                },
            }
        ),
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "I found the issue and fixed it."}],
                },
            }
        ),
    ]
    session_file.write_text("\n".join(lines) + "\n")
    return session_file


@pytest.fixture
def mock_home(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set a predictable HOME for testing."""
    home = "/Users/testuser"
    monkeypatch.setenv("HOME", home)
    return home
