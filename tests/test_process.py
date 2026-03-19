"""Tests for process inspection utilities."""

from __future__ import annotations

from unittest.mock import patch

from py_see_claude.process import (
    find_claude_pids,
    get_process_cwd,
    get_process_info,
)


class TestFindClaudePids:
    @patch("py_see_claude.process.subprocess.run")
    def test_finds_pids(self, mock_run: object) -> None:
        mock_run.return_value.stdout = "12345\n67890\n"  # type: ignore[union-attr]
        pids = find_claude_pids()
        assert pids == ["12345", "67890"]

    @patch("py_see_claude.process.subprocess.run")
    def test_no_pids(self, mock_run: object) -> None:
        mock_run.return_value.stdout = ""  # type: ignore[union-attr]
        pids = find_claude_pids()
        assert pids == []

    @patch("py_see_claude.process.subprocess.run", side_effect=OSError("pgrep not found"))
    def test_handles_error(self, mock_run: object) -> None:
        pids = find_claude_pids()
        assert pids == []


class TestGetProcessInfo:
    @patch("py_see_claude.process.subprocess.run")
    def test_parses_info(self, mock_run: object) -> None:
        mock_run.return_value.stdout = "12345 ttys001 15.2 1.3 01:23:45 S"  # type: ignore[union-attr]
        info = get_process_info("12345")
        assert info is not None
        assert info.pid == "12345"
        assert info.tty == "ttys001"
        assert info.cpu == "15.2"
        assert info.mem == "1.3"
        assert info.elapsed == "01:23:45"
        assert info.state == "S"

    @patch("py_see_claude.process.subprocess.run")
    def test_empty_output(self, mock_run: object) -> None:
        mock_run.return_value.stdout = ""  # type: ignore[union-attr]
        assert get_process_info("12345") is None

    @patch("py_see_claude.process.subprocess.run", side_effect=OSError)
    def test_handles_error(self, mock_run: object) -> None:
        assert get_process_info("12345") is None


class TestGetProcessCwd:
    @patch("py_see_claude.process.subprocess.run")
    @patch("py_see_claude.process.Path.exists", return_value=False)
    def test_lsof_fallback(self, mock_exists: object, mock_run: object) -> None:
        mock_run.return_value.stdout = (  # type: ignore[union-attr]
            "COMMAND   PID USER  FD TYPE DEVICE   SIZE NODE NAME\n"
            "claude  12345 user cwd  DIR 1,18    640  123 /Users/user/project\n"
        )
        cwd = get_process_cwd("12345")
        assert cwd == "/Users/user/project"

    @patch("py_see_claude.process.subprocess.run", side_effect=OSError)
    @patch("py_see_claude.process.Path.exists", return_value=False)
    def test_handles_all_errors(self, mock_exists: object, mock_run: object) -> None:
        cwd = get_process_cwd("12345")
        assert cwd == ""
