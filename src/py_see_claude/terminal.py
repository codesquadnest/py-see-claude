"""Terminal integration for macOS — supports Ghostty, iTerm2, Terminal.app, and others."""

from __future__ import annotations

import contextlib
import os
import re
import shlex
import subprocess
import tempfile
import time

# Map of lowercase identifier -> (pgrep name, AppleScript/System Events process name)
_KNOWN_TERMINALS: dict[str, tuple[str, str]] = {
    "ghostty": ("ghostty", "ghostty"),
    "iterm2": ("iTerm2", "iTerm2"),
    "terminal": ("Terminal", "Terminal"),
}


def is_macos() -> bool:
    """Check if running on macOS."""
    return os.uname().sysname == "Darwin"


def _get_ppid(pid: str) -> str:
    """Get parent PID of a process."""
    try:
        result = subprocess.run(
            ["ps", "-o", "ppid=", "-p", pid],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def _get_comm(pid: str) -> str:
    """Get the command name of a process."""
    try:
        result = subprocess.run(
            ["ps", "-o", "comm=", "-p", pid],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        comm = result.stdout.strip()
        # ps -o comm= may return a full path on macOS (e.g.
        # /System/Applications/.../Terminal); extract the basename so
        # callers can match on the process name alone.
        return os.path.basename(comm) if comm else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def _normalize_tty(tty: str) -> str:
    """Normalize TTY to the kernel form (e.g. 'ttys003').

    ps -o tty= returns 'ttys003' on macOS.
    /dev paths are '/dev/ttys003'.
    """
    tty = tty.strip()
    if tty.startswith("/dev/"):
        tty = tty[5:]
    # Already in full form like ttys003
    if tty.startswith("tty"):
        return tty
    # Short form like s003 (shouldn't happen on macOS but just in case)
    if re.match(r"^s\d+$", tty):
        return "tty" + tty
    return tty


def _walk_up_for_terminal(start_pid: str) -> str:
    """Walk up the process tree from a PID to find the terminal emulator.

    Returns 'ghostty', 'iterm2', 'terminal', or empty string if not found.
    """
    current = start_pid
    for _ in range(10):
        if not current or current in ("0", "1"):
            break
        comm = _get_comm(current).lower()
        if "ghostty" in comm:
            return "ghostty"
        if "iterm" in comm:
            return "iterm2"
        if comm == "terminal":
            return "terminal"
        current = _get_ppid(current)
    return ""


def detect_terminal_for_tty(tty: str, pid: str = "") -> str:
    """Determine which terminal emulator owns a TTY by walking the process tree.

    If *pid* is provided, walks up directly from that process (most reliable).
    Otherwise falls back to finding processes on the TTY via ``ps -t``.
    Returns 'ghostty', 'iterm2', 'terminal', or the raw process name.
    """
    if not is_macos():
        return "unknown"

    # Strategy 1: walk up from the known PID (most reliable)
    if pid:
        found = _walk_up_for_terminal(_get_ppid(pid))
        if found:
            return found

    # Strategy 2: find processes on the TTY and walk up from their parents
    norm = _normalize_tty(tty)
    try:
        result = subprocess.run(
            ["ps", "-t", norm, "-o", "ppid="],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        ppids = {p.strip() for p in result.stdout.strip().split() if p.strip()}

        for ppid in ppids:
            found = _walk_up_for_terminal(ppid)
            if found:
                return found
    except (subprocess.SubprocessError, OSError):
        pass

    return _detect_running_terminal()


def _detect_running_terminal() -> str:
    """Fallback: check which terminal apps are running."""
    for key, (pgrep_name, _) in _KNOWN_TERMINALS.items():
        try:
            result = subprocess.run(
                ["pgrep", "-x", pgrep_name],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if result.stdout.strip():
                return key
        except (subprocess.SubprocessError, OSError):
            pass
    return "terminal"


# ---- Terminal.app implementations ----


def _terminal_app_focus(tty: str) -> bool:
    """Focus Terminal.app window by TTY."""
    norm = _normalize_tty(tty)
    script = (
        'tell application "Terminal"\n'
        "  activate\n"
        "  repeat with w from 1 to count of windows\n"
        "    set win to window w\n"
        "    repeat with t from 1 to count of tabs of win\n"
        "      set theTab to tab t of win\n"
        f'      if tty of theTab contains "{norm}" then\n'
        "        set selected tab of win to theTab\n"
        "        set index of win to 1\n"
        '        return "found"\n'
        "      end if\n"
        "    end repeat\n"
        "  end repeat\n"
        "end tell"
    )
    try:
        subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=5, check=False
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def _terminal_app_send(tty: str, message: str, focus: bool = True) -> bool | str:
    """Send a message to a Terminal.app tab via ``do script``.

    Uses Terminal.app's native ``do script`` which writes directly to the
    tab's PTY — no System Events / Accessibility permission needed.
    Returns True on success, or an error string on failure.
    """
    norm = _normalize_tty(tty)
    tmp_path = f"/tmp/see-claude-msg-{int(time.time() * 1000)}.txt"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(message)

        focus_lines = ""
        if focus:
            focus_lines = (
                "        set selected tab of win to theTab\n"
                "        set index of win to 1\n"
                "        activate\n"
            )

        script = (
            f'set msgText to (read POSIX file "{tmp_path}")\n'
            'tell application "Terminal"\n'
            "  repeat with w from 1 to count of windows\n"
            "    set win to window w\n"
            "    repeat with t from 1 to count of tabs of win\n"
            "      set theTab to tab t of win\n"
            f'      if tty of theTab contains "{norm}" then\n'
            + focus_lines
            + "        do script msgText in theTab\n"
            '        return "sent"\n'
            "      end if\n"
            "    end repeat\n"
            "  end repeat\n"
            "end tell"
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if "sent" in result.stdout:
            return True
        # Return osascript error for diagnosis
        err = result.stderr.strip()
        return err if err else False
    except (subprocess.SubprocessError, OSError) as exc:
        return str(exc)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)


def _terminal_app_run(shell_cmd: str) -> bool:
    """Run a command in a new Terminal.app tab."""
    try:
        quoted = shell_cmd.replace("\\", "\\\\").replace('"', '\\"')
        script_content = f'tell application "Terminal"\ndo script "{quoted}"\nend tell'
        fd, script_path = tempfile.mkstemp(prefix="see-claude-script-", suffix=".scpt")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(script_content)
            subprocess.run(
                ["osascript", script_path],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return True
        finally:
            with contextlib.suppress(OSError):
                os.unlink(script_path)
    except (subprocess.SubprocessError, OSError):
        return False


# ---- iTerm2 implementations ----


def _iterm2_focus(tty: str) -> bool:
    """Focus iTerm2 window by TTY."""
    norm = _normalize_tty(tty)
    script = (
        'tell application "iTerm2"\n'
        "  repeat with w in windows\n"
        "    repeat with t in tabs of w\n"
        "      repeat with s in sessions of t\n"
        f'        if tty of s contains "{norm}" then\n'
        "          select t\n"
        "          select w\n"
        "          activate\n"
        '          return "found"\n'
        "        end if\n"
        "      end repeat\n"
        "    end repeat\n"
        "  end repeat\n"
        "end tell"
    )
    try:
        subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=5, check=False
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def _iterm2_send(tty: str, message: str) -> bool:
    """Send a message to an iTerm2 session using its native write text.

    The message and the trailing Return are written as two separate PTY
    writes with a delay in between. Claude Code's TUI batches rapid input
    as a paste and a \\r arriving inside that batch is treated as a
    newline in the prompt rather than a submit — the delay lets paste
    detection finalize so the Return registers as a fresh key press.
    """
    norm = _normalize_tty(tty)
    tmp_path = f"/tmp/see-claude-msg-{int(time.time() * 1000)}.txt"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(message)

        script = (
            f'set msgText to (read POSIX file "{tmp_path}")\n'
            'tell application "iTerm2"\n'
            "  repeat with w in windows\n"
            "    repeat with t in tabs of w\n"
            "      repeat with s in sessions of t\n"
            f'        if tty of s contains "{norm}" then\n'
            "          tell s to write text msgText newline NO\n"
            "          delay 0.5\n"
            '          tell s to write text "" newline YES\n'
            '          return "sent"\n'
            "        end if\n"
            "      end repeat\n"
            "    end repeat\n"
            "  end repeat\n"
            "end tell"
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return "sent" in result.stdout
    except (subprocess.SubprocessError, OSError):
        return False
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)


def _iterm2_run(shell_cmd: str) -> bool:
    """Run a command in a new iTerm2 tab."""
    try:
        escaped = shell_cmd.replace("\\", "\\\\").replace('"', '\\"')
        script = (
            'tell application "iTerm2"\n'
            "  activate\n"
            "  tell current window\n"
            "    set newTab to (create tab with default profile)\n"
            "    tell current session of newTab\n"
            f'      write text "{escaped}"\n'
            "    end tell\n"
            "  end tell\n"
            "end tell"
        )
        subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=10, check=False
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False


# ---- Ghostty implementations ----
# Ghostty has no AppleScript dictionary. We use System Events to find
# the correct tab by matching the cwd in tab titles, then type via keystroke.


def _ghostty_select_tab(cwd: str = "") -> bool:
    """Select the Ghostty tab for a specific Claude Code session.

    Ghostty exposes tabs as radio buttons inside a tab group. Tries matching
    by CWD basename first (most specific), then "Claude Code", then "claude".
    """
    # Build match candidates, most specific first
    candidates: list[str] = []
    if cwd:
        basename = os.path.basename(cwd.rstrip("/"))
        if basename:
            candidates.append(basename)
    candidates.append("Claude Code")
    candidates.append("claude")

    # Build a single script that tries each match string in order
    blocks: list[str] = []
    for match_str in candidates:
        blocks.append(
            "    repeat with w in windows\n"
            "      try\n"
            "        repeat with tg in tab groups of w\n"
            "          repeat with rb in radio buttons of tg\n"
            f'            if title of rb contains "{match_str}" then\n'
            "              click rb\n"
            "              delay 0.3\n"
            '              return "found"\n'
            "            end if\n"
            "          end repeat\n"
            "        end repeat\n"
            "      end try\n"
            "    end repeat\n"
        )

    script = (
        'tell application "System Events"\n'
        '  tell process "ghostty"\n'
        + "".join(blocks)
        + "  end tell\n"
        "end tell"
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return "found" in result.stdout
    except (subprocess.SubprocessError, OSError):
        return False


def _ghostty_focus(cwd: str = "") -> bool:
    """Focus Ghostty and select the correct tab."""
    try:
        subprocess.run(
            ["osascript", "-e", 'tell application "ghostty" to activate'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return False

    _ghostty_select_tab(cwd)
    return True


def _ghostty_send(message: str, cwd: str = "", focus: bool = True) -> bool:
    """Send a message to the correct Ghostty tab.

    When *focus* is False, briefly activates Ghostty to type then immediately
    re-focuses the previously active application.
    """
    if focus:
        _ghostty_focus(cwd)
        time.sleep(0.3)

        tmp_path = f"/tmp/see-claude-msg-{int(time.time() * 1000)}.txt"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(message)

            script = (
                'tell application "System Events"\n'
                '  tell process "ghostty"\n'
                f'    set msgText to (read POSIX file "{tmp_path}")\n'
                "    keystroke msgText\n"
                "    keystroke return\n"
                "  end tell\n"
                "end tell"
            )
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return True
        except (subprocess.SubprocessError, OSError):
            return False
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)

    # No-focus path: remember the active app, activate Ghostty to type,
    # then immediately switch back.
    tmp_path = f"/tmp/see-claude-msg-{int(time.time() * 1000)}.txt"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(message)

        script = (
            'tell application "System Events"\n'
            "  set prevApp to name of first application process "
            "whose frontmost is true\n"
            "end tell\n"
            'tell application "ghostty" to activate\n'
            "delay 0.3\n"
            'tell application "System Events"\n'
            '  tell process "ghostty"\n'
            f'    set msgText to (read POSIX file "{tmp_path}")\n'
            "    keystroke msgText\n"
            "    keystroke return\n"
            "  end tell\n"
            "end tell\n"
            "delay 0.1\n"
            'tell application prevApp to activate\n'
        )
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)


# ---- Generic implementations (fallback for unknown terminals) ----


def _generic_focus(process_name: str, cwd: str = "") -> bool:
    """Focus a terminal window using System Events, matching by title if possible."""
    app_name = process_name
    # Capitalize for `tell application`
    for key, (_, display) in _KNOWN_TERMINALS.items():
        if key == process_name:
            app_name = display
            break

    # Activate the app
    try:
        subprocess.run(
            ["osascript", "-e", f'tell application "{app_name}" to activate'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return False

    if not cwd:
        return True

    # Try to find and raise the right window by matching cwd in the title
    basename = os.path.basename(cwd.rstrip("/"))
    if not basename:
        return True

    # Use System Events to find window by title
    process_id = process_name.lower()
    script = (
        'tell application "System Events"\n'
        f'  tell process "{process_id}"\n'
        "    set frontmost to true\n"
        "    repeat with w in windows\n"
        f'      if name of w contains "{basename}" then\n'
        '        perform action "AXRaise" of w\n'
        '        return "found"\n'
        "      end if\n"
        "    end repeat\n"
        "  end tell\n"
        "end tell"
    )
    with contextlib.suppress(subprocess.SubprocessError, OSError):
        subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=5, check=False
        )
    return True


def _generic_send(process_name: str, message: str, cwd: str = "", focus: bool = True) -> bool:
    """Send a message to any terminal by typing via System Events.

    When *focus* is False, briefly activates the terminal to type then
    immediately re-focuses the previously active application.
    """
    app_name = process_name
    for key, (_, display) in _KNOWN_TERMINALS.items():
        if key == process_name:
            app_name = display
            break

    if focus:
        _generic_focus(process_name, cwd)
        time.sleep(0.3)

    process_id = process_name.lower()
    tmp_path = f"/tmp/see-claude-msg-{int(time.time() * 1000)}.txt"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(message)

        if focus:
            script = (
                'tell application "System Events"\n'
                f'  tell process "{process_id}"\n'
                f'    set msgText to (read POSIX file "{tmp_path}")\n'
                "    keystroke msgText\n"
                "    keystroke return\n"
                "  end tell\n"
                "end tell"
            )
        else:
            script = (
                'tell application "System Events"\n'
                "  set prevApp to name of first application process "
                "whose frontmost is true\n"
                "end tell\n"
                f'tell application "{app_name}" to activate\n'
                "delay 0.3\n"
                'tell application "System Events"\n'
                f'  tell process "{process_id}"\n'
                f'    set msgText to (read POSIX file "{tmp_path}")\n'
                "    keystroke msgText\n"
                "    keystroke return\n"
                "  end tell\n"
                "end tell\n"
                "delay 0.1\n"
                'tell application prevApp to activate\n'
            )
        subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=10, check=False
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)


def _generic_run(process_name: str, shell_cmd: str) -> bool:
    """Launch a command in a new window of any terminal."""
    app_name = process_name
    for key, (_, display) in _KNOWN_TERMINALS.items():
        if key == process_name:
            app_name = display
            break

    try:
        # Open new window: Cmd+N after activating
        subprocess.run(
            ["osascript", "-e", f'tell application "{app_name}" to activate'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        time.sleep(0.3)

        process_id = process_name.lower()
        escaped = shell_cmd.replace("\\", "\\\\").replace('"', '\\"')
        script = (
            'tell application "System Events"\n'
            f'  tell process "{process_id}"\n'
            '    keystroke "n" using command down\n'
            "    delay 0.5\n"
            f'    keystroke "{escaped}"\n'
            "    keystroke return\n"
            "  end tell\n"
            "end tell"
        )
        subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=10, check=False
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False


# ---- Public API ----


def send_message(
    tty: str, message: str, cwd: str = "", focus: bool = True, pid: str = ""
) -> bool | str:
    """Send a message to a terminal session identified by TTY.

    When *focus* is False the terminal window stays in the background.
    Returns True on success, or an error string on failure.
    """
    if not is_macos():
        return "Not supported on this platform"

    terminal = detect_terminal_for_tty(tty, pid=pid)
    if terminal == "iterm2":
        ok = _iterm2_send(tty, message)
        return True if ok else f"iTerm2: session with tty {tty} not found"
    if terminal == "terminal":
        result = _terminal_app_send(tty, message, focus=focus)
        if result is True:
            return True
        detail = result if isinstance(result, str) else ""
        return f"Terminal.app: tab with tty {tty} not found" + (f" ({detail})" if detail else "")
    if terminal == "ghostty":
        ok = _ghostty_send(message, cwd=cwd, focus=focus)
        return True if ok else "Ghostty: failed to send"
    ok = _generic_send(terminal, message, cwd, focus=focus)
    return True if ok else f"Terminal '{terminal}': failed to send"


def focus_terminal(tty: str, cwd: str = "", pid: str = "") -> bool:
    """Focus the terminal window containing a session."""
    if not is_macos():
        return False

    terminal = detect_terminal_for_tty(tty, pid=pid)
    if terminal == "iterm2":
        return _iterm2_focus(tty)
    if terminal == "terminal":
        return _terminal_app_focus(tty)
    if terminal == "ghostty":
        return _ghostty_focus(cwd=cwd)
    return _generic_focus(terminal, cwd)


def launch_session(session_id: str, cwd: str, skip_perms: bool = False) -> bool:
    """Resume a Claude session in a new terminal tab."""
    if not is_macos():
        return False

    cmd = f"claude --resume {session_id}"
    if skip_perms:
        cmd += " --dangerously-skip-permissions"
    dir_path = cwd if cwd.startswith("/") else f"/{cwd}"
    shell_cmd = f"cd {shlex.quote(dir_path)} && {cmd}"

    terminal = _detect_running_terminal()
    if terminal == "iterm2":
        return _iterm2_run(shell_cmd)
    if terminal == "terminal":
        return _terminal_app_run(shell_cmd)
    return _generic_run(terminal, shell_cmd)


def new_session(directory: str, prompt: str = "", skip_perms: bool = False) -> bool:
    """Launch a new Claude session in a new terminal tab."""
    if not is_macos():
        return False

    cmd = "claude"
    if skip_perms:
        cmd += " --dangerously-skip-permissions"
    if prompt:
        cmd += f" {shlex.quote(prompt)}"

    dir_path = (
        directory if directory.startswith("/") else os.path.join(os.path.expanduser("~"), directory)
    )
    shell_cmd = f"cd {shlex.quote(dir_path)} && {cmd}"

    terminal = _detect_running_terminal()
    if terminal == "iterm2":
        return _iterm2_run(shell_cmd)
    if terminal == "terminal":
        return _terminal_app_run(shell_cmd)
    return _generic_run(terminal, shell_cmd)
