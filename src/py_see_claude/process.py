"""Process inspection utilities for finding Claude Code sessions."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProcessInfo:
    pid: str
    tty: str
    cpu: str
    mem: str
    elapsed: str
    state: str


def find_claude_pids() -> list[str]:
    """Find all running claude process PIDs."""
    try:
        result = subprocess.run(
            ["pgrep", "-x", "claude"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        pids = result.stdout.strip()
        if not pids:
            return []
        return [p for p in pids.split("\n") if p]
    except (subprocess.SubprocessError, OSError):
        return []


def get_process_info(pid: str) -> ProcessInfo | None:
    """Get detailed process information for a PID."""
    try:
        result = subprocess.run(
            ["ps", "-o", "pid=,tty=,%cpu=,%mem=,etime=,state=", "-p", pid],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        info = result.stdout.strip()
        if not info:
            return None
        parts = info.split()
        if len(parts) < 6:
            return None
        return ProcessInfo(
            pid=parts[0],
            tty=parts[1],
            cpu=parts[2],
            mem=parts[3],
            elapsed=parts[4],
            state=parts[5],
        )
    except (subprocess.SubprocessError, OSError):
        return None


def get_process_cwd(pid: str) -> str:
    """Get the working directory of a process.

    Uses /proc on Linux, lsof on macOS.
    """
    # Linux: use /proc (fast, no subprocess needed)
    proc_cwd = Path(f"/proc/{pid}/cwd")
    if proc_cwd.exists():
        try:
            return str(proc_cwd.resolve())
        except OSError:
            pass

    # macOS: use lsof
    try:
        result = subprocess.run(
            ["lsof", "-p", pid],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        for line in result.stdout.split("\n"):
            if "cwd" in line:
                parts = line.split()
                if parts:
                    return parts[-1]
    except (subprocess.SubprocessError, OSError):
        pass

    # Fallback: lsof -Fn
    try:
        result = subprocess.run(
            ["lsof", "-p", pid, "-Fn"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("n/"):
                return line[1:]
    except (subprocess.SubprocessError, OSError):
        pass

    return ""
