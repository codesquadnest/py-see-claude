"""Tests for terminal detection and multi-terminal integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from py_see_claude.terminal import (
    _detect_running_terminal,
    _generic_focus,
    _generic_send,
    _iterm2_focus,
    _iterm2_run,
    _iterm2_send,
    _normalize_tty,
    _terminal_app_focus,
    _terminal_app_send,
    detect_terminal_for_tty,
    focus_terminal,
    launch_session,
    new_session,
    send_message,
)


class TestNormalizeTty:
    def test_full_form(self) -> None:
        assert _normalize_tty("ttys003") == "ttys003"

    def test_dev_path(self) -> None:
        assert _normalize_tty("/dev/ttys003") == "ttys003"

    def test_short_form(self) -> None:
        assert _normalize_tty("s003") == "ttys003"

    def test_whitespace(self) -> None:
        assert _normalize_tty("  ttys003  ") == "ttys003"


class TestDetectTerminalForTty:
    @patch("py_see_claude.terminal.is_macos", return_value=False)
    def test_non_macos(self, _mock: object) -> None:
        assert detect_terminal_for_tty("ttys003") == "unknown"

    @patch("py_see_claude.terminal._detect_running_terminal", return_value="terminal")
    @patch("py_see_claude.terminal._get_comm")
    @patch("py_see_claude.terminal._get_ppid")
    @patch("py_see_claude.terminal.subprocess.run")
    @patch("py_see_claude.terminal.is_macos", return_value=True)
    def test_detects_ghostty_from_process_tree(
        self,
        _mac: object,
        mock_run: MagicMock,
        mock_ppid: MagicMock,
        mock_comm: MagicMock,
        _fallback: object,
    ) -> None:
        # ps -t ttys003 returns PPIDs
        mock_run.return_value = MagicMock(stdout="100\n100\n")
        # Walking up: PID 100 is login, PID 99 is ghostty
        mock_comm.side_effect = lambda pid: {
            "100": "/usr/bin/login",
            "99": "/Applications/Ghostty.app/Contents/MacOS/ghostty",
        }.get(pid, "")
        mock_ppid.side_effect = lambda pid: {"100": "99", "99": "1"}.get(pid, "")
        assert detect_terminal_for_tty("ttys003") == "ghostty"

    @patch("py_see_claude.terminal._detect_running_terminal", return_value="terminal")
    @patch("py_see_claude.terminal._get_comm")
    @patch("py_see_claude.terminal._get_ppid")
    @patch("py_see_claude.terminal.subprocess.run")
    @patch("py_see_claude.terminal.is_macos", return_value=True)
    def test_detects_iterm2_from_process_tree(
        self,
        _mac: object,
        mock_run: MagicMock,
        mock_ppid: MagicMock,
        mock_comm: MagicMock,
        _fallback: object,
    ) -> None:
        mock_run.return_value = MagicMock(stdout="200\n")
        mock_comm.side_effect = lambda pid: {
            "200": "/usr/bin/login",
            "199": "iTerm2",
        }.get(pid, "")
        mock_ppid.side_effect = lambda pid: {"200": "199", "199": "1"}.get(pid, "")
        assert detect_terminal_for_tty("ttys005") == "iterm2"

    @patch("py_see_claude.terminal._detect_running_terminal", return_value="terminal")
    @patch("py_see_claude.terminal.subprocess.run")
    @patch("py_see_claude.terminal.is_macos", return_value=True)
    def test_falls_back_on_error(
        self, _mac: object, mock_run: MagicMock, _fallback: object
    ) -> None:
        mock_run.side_effect = OSError("ps failed")
        assert detect_terminal_for_tty("ttys003") == "terminal"


class TestDetectRunningTerminal:
    @patch("py_see_claude.terminal.subprocess.run")
    def test_detects_ghostty(self, mock_run: MagicMock) -> None:
        def side_effect(cmd: list[str], **_: object) -> MagicMock:
            result = MagicMock()
            result.stdout = "12345\n" if cmd == ["pgrep", "-x", "ghostty"] else ""
            return result

        mock_run.side_effect = side_effect
        assert _detect_running_terminal() == "ghostty"

    @patch("py_see_claude.terminal.subprocess.run")
    def test_detects_iterm2(self, mock_run: MagicMock) -> None:
        def side_effect(cmd: list[str], **_: object) -> MagicMock:
            result = MagicMock()
            if cmd == ["pgrep", "-x", "ghostty"]:
                result.stdout = ""
            elif cmd == ["pgrep", "-x", "iTerm2"]:
                result.stdout = "67890\n"
            else:
                result.stdout = ""
            return result

        mock_run.side_effect = side_effect
        assert _detect_running_terminal() == "iterm2"

    @patch("py_see_claude.terminal.subprocess.run")
    def test_defaults_to_terminal(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="")
        assert _detect_running_terminal() == "terminal"


class TestITerm2:
    @patch("py_see_claude.terminal.subprocess.run")
    def test_focus_uses_select_w(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock()
        _iterm2_focus("ttys001")
        script = mock_run.call_args[0][0][2]
        assert "select w" in script
        assert "select t" in script
        assert "activate" in script

    @patch("py_see_claude.terminal.subprocess.run")
    def test_send_uses_write_text(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="sent")
        result = _iterm2_send("ttys001", "hello world")
        script = mock_run.call_args[0][0][2]
        assert "write text" in script
        assert "ttys001" in script
        assert result is True

    @patch("py_see_claude.terminal.subprocess.run")
    def test_send_returns_false_when_session_not_found(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="")
        result = _iterm2_send("ttys999", "hello")
        assert result is False

    @patch("py_see_claude.terminal.subprocess.run")
    def test_run_creates_tab(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock()
        _iterm2_run("echo hello")
        script = mock_run.call_args[0][0][2]
        assert "create tab" in script

    @patch("py_see_claude.terminal.subprocess.run", side_effect=OSError)
    def test_focus_handles_error(self, _mock: object) -> None:
        assert _iterm2_focus("ttys001") is False

    @patch("py_see_claude.terminal.subprocess.run", side_effect=OSError)
    def test_send_handles_error(self, _mock: object) -> None:
        assert _iterm2_send("ttys001", "hello") is False


class TestTerminalApp:
    @patch("py_see_claude.terminal.subprocess.run")
    def test_focus_matches_full_tty(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock()
        _terminal_app_focus("ttys001")
        script = mock_run.call_args[0][0][2]
        assert "ttys001" in script

    @patch("py_see_claude.terminal.subprocess.run")
    def test_send_writes_message(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock()
        _terminal_app_send("ttys001", "hello")
        assert mock_run.called

    @patch("py_see_claude.terminal.subprocess.run", side_effect=OSError)
    def test_focus_handles_error(self, _mock: object) -> None:
        assert _terminal_app_focus("ttys001") is False

    @patch("py_see_claude.terminal.subprocess.run", side_effect=OSError("test error"))
    def test_send_handles_error(self, _mock: object) -> None:
        result = _terminal_app_send("ttys001", "hello")
        assert result is not True


class TestGenericTerminal:
    @patch("py_see_claude.terminal.subprocess.run")
    def test_focus_activates_app(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock()
        _generic_focus("ghostty", cwd="/Users/test/myproject")
        # First call activates the app (uses display name from _KNOWN_TERMINALS)
        first_script = mock_run.call_args_list[0][0][0][2]
        assert "ghostty" in first_script.lower()
        assert "activate" in first_script

    @patch("py_see_claude.terminal.subprocess.run")
    def test_focus_matches_cwd_in_title(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock()
        _generic_focus("ghostty", cwd="/Users/test/myproject")
        # Second call tries to match window by title
        assert mock_run.call_count == 2
        second_script = mock_run.call_args_list[1][0][0][2]
        assert "myproject" in second_script

    @patch("py_see_claude.terminal.subprocess.run", side_effect=OSError)
    def test_focus_handles_error(self, _mock: object) -> None:
        assert _generic_focus("ghostty") is False

    @patch("py_see_claude.terminal.time.sleep")
    @patch("py_see_claude.terminal.subprocess.run")
    def test_send_types_message(self, mock_run: MagicMock, _sleep: object) -> None:
        mock_run.return_value = MagicMock()
        _generic_send("ghostty", "test message", cwd="/test/proj")
        # Should have multiple calls: activate, window match, then keystroke
        assert mock_run.call_count >= 2


class TestPublicAPI:
    @patch("py_see_claude.terminal.is_macos", return_value=False)
    def test_send_non_macos(self, _mock: object) -> None:
        result = send_message("ttys001", "hello")
        assert result is not True
        assert isinstance(result, str)

    @patch("py_see_claude.terminal.is_macos", return_value=False)
    def test_focus_non_macos(self, _mock: object) -> None:
        assert focus_terminal("ttys001") is False

    @patch("py_see_claude.terminal.is_macos", return_value=False)
    def test_launch_non_macos(self, _mock: object) -> None:
        assert launch_session("abc123", "/test") is False

    @patch("py_see_claude.terminal.is_macos", return_value=False)
    def test_new_session_non_macos(self, _mock: object) -> None:
        assert new_session("/test", "hello") is False

    @patch("py_see_claude.terminal._iterm2_send", return_value=True)
    @patch("py_see_claude.terminal.detect_terminal_for_tty", return_value="iterm2")
    @patch("py_see_claude.terminal.is_macos", return_value=True)
    def test_send_dispatches_to_iterm2(
        self, _mac: object, _det: object, mock_send: MagicMock
    ) -> None:
        assert send_message("ttys001", "hello") is True
        mock_send.assert_called_once_with("ttys001", "hello")

    @patch("py_see_claude.terminal._ghostty_send", return_value=True)
    @patch("py_see_claude.terminal.detect_terminal_for_tty", return_value="ghostty")
    @patch("py_see_claude.terminal.is_macos", return_value=True)
    def test_send_dispatches_to_ghostty(
        self, _mac: object, _det: object, mock_send: MagicMock
    ) -> None:
        assert send_message("ttys001", "hello", cwd="/test/proj") is True
        mock_send.assert_called_once_with("hello", cwd="/test/proj", focus=True)

    @patch("py_see_claude.terminal._iterm2_focus", return_value=True)
    @patch("py_see_claude.terminal.detect_terminal_for_tty", return_value="iterm2")
    @patch("py_see_claude.terminal.is_macos", return_value=True)
    def test_focus_dispatches_to_iterm2(
        self, _mac: object, _det: object, mock_focus: MagicMock
    ) -> None:
        assert focus_terminal("ttys001") is True
        mock_focus.assert_called_once_with("ttys001")

    @patch("py_see_claude.terminal._ghostty_focus", return_value=True)
    @patch("py_see_claude.terminal.detect_terminal_for_tty", return_value="ghostty")
    @patch("py_see_claude.terminal.is_macos", return_value=True)
    def test_focus_dispatches_to_ghostty(
        self, _mac: object, _det: object, mock_focus: MagicMock
    ) -> None:
        assert focus_terminal("ttys001", cwd="/test/proj") is True
        mock_focus.assert_called_once_with(cwd="/test/proj")
