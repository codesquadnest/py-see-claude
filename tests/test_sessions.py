"""Tests for session detection and management."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from py_see_claude.sessions import (
    format_time_ago,
    get_project_roster,
    get_recent_sessions,
    get_session_messages,
    parse_project_name,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestFormatTimeAgo:
    def test_just_now(self) -> None:
        assert format_time_ago(time.time()) == "just now"

    def test_minutes_ago(self) -> None:
        assert format_time_ago(time.time() - 120) == "2m ago"

    def test_hours_ago(self) -> None:
        assert format_time_ago(time.time() - 7200) == "2h ago"

    def test_days_ago(self) -> None:
        assert format_time_ago(time.time() - 172800) == "2d ago"


class TestParseProjectName:
    def test_documents_path(self) -> None:
        assert parse_project_name("-Users-alice-Documents-myapp") == "myapp"

    def test_downloads_path(self) -> None:
        result = parse_project_name("-Users-alice-Downloads-stuff")
        assert result == "~/Downloads/stuff"

    def test_generic_path(self) -> None:
        result = parse_project_name("-Users-alice-Projects-myapp")
        assert result == "~/Projects-myapp"

    def test_home_only(self) -> None:
        assert parse_project_name("-Users-alice") == "~"


class TestGetSessionMessages:
    def test_reads_messages(self, sample_session_file: Path) -> None:
        cwd = "/Users/testuser/Projects/myapp"
        msgs = get_session_messages(cwd)
        assert len(msgs) > 0
        assert msgs[0].role == "user"
        assert msgs[0].text == "fix the failing tests"

    def test_handles_tool_use(self, sample_session_file: Path) -> None:
        cwd = "/Users/testuser/Projects/myapp"
        msgs = get_session_messages(cwd)
        tool_msgs = [m for m in msgs if m.has_tool_use]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].text == "(using tools...)"

    def test_handles_tool_result(self, sample_session_file: Path) -> None:
        cwd = "/Users/testuser/Projects/myapp"
        msgs = get_session_messages(cwd)
        result_msgs = [m for m in msgs if m.has_tool_result]
        assert len(result_msgs) == 1
        assert result_msgs[0].text == "(tool result)"

    def test_empty_cwd(self, tmp_claude_dir: Path) -> None:
        assert get_session_messages("") == []

    def test_nonexistent_project(self, tmp_claude_dir: Path) -> None:
        assert get_session_messages("/nonexistent/path") == []

    def test_limits_message_count(self, sample_session_file: Path) -> None:
        cwd = "/Users/testuser/Projects/myapp"
        msgs = get_session_messages(cwd, count=2)
        assert len(msgs) == 2

    def test_skips_subagent_files(self, tmp_claude_dir: Path) -> None:
        projects_dir = tmp_claude_dir / "projects"
        proj_dir = projects_dir / "-Users-testuser-Projects-myapp"
        proj_dir.mkdir(parents=True, exist_ok=True)
        subagent = proj_dir / "subagent-abc.jsonl"
        subagent.write_text(
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": "subagent message"},
                }
            )
            + "\n"
        )
        msgs = get_session_messages("/Users/testuser/Projects/myapp")
        assert len(msgs) == 0


class TestGetRecentSessions:
    def test_returns_sessions(self, sample_session_file: Path) -> None:
        sessions = get_recent_sessions()
        assert len(sessions) == 1
        assert sessions[0].session_id == "abc123"
        assert sessions[0].first_message == "fix the failing tests"

    def test_empty_projects_dir(self, tmp_claude_dir: Path) -> None:
        sessions = get_recent_sessions()
        assert sessions == []

    def test_respects_limit(self, tmp_claude_dir: Path) -> None:
        projects_dir = tmp_claude_dir / "projects"
        proj_dir = projects_dir / "-Users-testuser-Projects-myapp"
        proj_dir.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            f = proj_dir / f"session-{i}.jsonl"
            f.write_text(
                json.dumps(
                    {
                        "type": "user",
                        "message": {"role": "user", "content": f"msg {i}"},
                    }
                )
                + "\n"
            )
        sessions = get_recent_sessions(limit=3)
        assert len(sessions) == 3


class TestGetProjectRoster:
    def test_returns_projects(self, sample_session_file: Path) -> None:
        roster = get_project_roster()
        assert len(roster) == 1
        assert roster[0].latest_session == "abc123"
        assert roster[0].session_count == 1

    def test_empty(self, tmp_claude_dir: Path) -> None:
        assert get_project_roster() == []

    def test_multiple_sessions_counted(self, tmp_claude_dir: Path) -> None:
        projects_dir = tmp_claude_dir / "projects"
        proj_dir = projects_dir / "-Users-testuser-Projects-myapp"
        proj_dir.mkdir(parents=True, exist_ok=True)
        for i in range(3):
            f = proj_dir / f"session-{i}.jsonl"
            f.write_text(
                json.dumps(
                    {
                        "type": "user",
                        "message": {"role": "user", "content": f"msg {i}"},
                    }
                )
                + "\n"
            )
        roster = get_project_roster()
        assert len(roster) == 1
        assert roster[0].session_count == 3
