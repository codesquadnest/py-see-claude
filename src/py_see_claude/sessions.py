"""Session detection and management for Claude Code."""

from __future__ import annotations

import contextlib
import json
import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from py_see_claude.process import find_claude_pids, get_process_cwd, get_process_info

CLAUDE_DIR = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
PROJECTS_DIR = CLAUDE_DIR / "projects"


@dataclass
class Message:
    role: str
    text: str
    has_tool_use: bool = False
    has_tool_result: bool = False
    timestamp: str = ""


@dataclass
class LiveSession:
    pid: str
    tty: str
    cpu: str
    mem: str
    elapsed: str
    cwd: str
    project_name: str
    status: str
    messages: list[Message] = field(default_factory=list)


@dataclass
class RecentSession:
    session_id: str
    project_name: str
    cwd: str
    last_modified: float
    last_modified_str: str
    first_message: str


@dataclass
class ProjectRoster:
    dir_key: str
    cwd: str
    project_name: str
    latest_session: str
    session_count: int
    last_modified: float
    last_modified_str: str
    first_message: str


def _cwd_to_dir_key(cwd: str) -> str:
    """Convert a working directory path to the Claude projects directory key.

    Claude encodes '/', '.' and '_' as '-' in directory names.
    """
    return cwd.replace("/", "-").replace(".", "-").replace("_", "-")


def format_time_ago(timestamp: float) -> str:
    """Format a unix timestamp as a human-readable 'X ago' string."""
    seconds = int(time.time() - timestamp)
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def parse_project_name(dir_key: str) -> str:
    """Convert a directory key like '-Users-foo-Documents-proj' to a display name."""
    name = dir_key
    name = re.sub(r"-Users-[^-]+-Documents-", "", name)
    name = re.sub(r"-Users-[^-]+-Downloads-?", "~/Downloads/", name)
    name = re.sub(r"-Users-[^-]+-", "~/", name)
    name = re.sub(r"^-Users-[^-]+$", "~", name)
    return name


def _read_first_message(file_path: Path) -> str:
    """Read the first user message from a session JSONL file."""
    try:
        with open(file_path, "rb") as f:
            data = f.read(8192)
        for line in data.decode("utf-8", errors="replace").split("\n"):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                if d.get("type") == "user" and d.get("message", {}).get("role") == "user":
                    content = d["message"]["content"]
                    if isinstance(content, str):
                        return content[:120]
                    if isinstance(content, list):
                        for c in content:
                            if c.get("type") == "text":
                                return str(c["text"])[:120]
                    break
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    except OSError:
        pass
    return ""


def get_session_messages(cwd: str, count: int = 20) -> list[Message]:
    """Read recent messages from the most recent session JSONL file for a project."""
    if not cwd:
        return []

    proj_key = _cwd_to_dir_key(cwd)
    proj_dir = PROJECTS_DIR / proj_key
    try:
        if not proj_dir.exists():
            return []

        files: list[tuple[Path, float]] = []
        for f in proj_dir.iterdir():
            if f.suffix == ".jsonl" and "subagent" not in f.name:
                files.append((f, f.stat().st_mtime))
        files.sort(key=lambda x: x[1], reverse=True)
        if not files:
            return []

        file_path = files[0][0]

        # Stream the whole file but keep only the last `count` valid messages.
        # A tail-only read can land mid-line on a giant assistant entry and
        # return zero parseable messages.
        recent: deque[Message] = deque(maxlen=count)
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    role = d.get("message", {}).get("role")
                    if role not in ("user", "assistant"):
                        continue
                    content = d["message"]["content"]
                    ts = d.get("timestamp", "")
                    text = ""
                    has_tool_use = False
                    has_tool_result = False
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        for c in content:
                            if c.get("type") == "text" and c.get("text", "").strip() and not text:
                                text = c["text"].strip()
                            if c.get("type") == "tool_use":
                                has_tool_use = True
                            if c.get("type") == "tool_result":
                                has_tool_result = True

                    if text:
                        recent.append(
                            Message(
                                role=role,
                                text=text[:300],
                                has_tool_use=has_tool_use,
                                has_tool_result=has_tool_result,
                                timestamp=ts,
                            )
                        )
                    elif has_tool_use or has_tool_result:
                        display = "(using tools...)" if has_tool_use else "(tool result)"
                        recent.append(
                            Message(
                                role=role,
                                text=display,
                                has_tool_use=has_tool_use,
                                has_tool_result=has_tool_result,
                                timestamp=ts,
                            )
                        )
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
        return list(recent)
    except OSError:
        return []


def _find_session_file(cwd: str, session_id: str = "") -> Path | None:
    """Find a session JSONL file by session_id, or the most recent one for a cwd."""
    proj_dir = PROJECTS_DIR / _cwd_to_dir_key(cwd)

    if session_id:
        if "/" in session_id or "\\" in session_id or ".." in session_id:
            return None
        file_path = proj_dir / f"{session_id}.jsonl"
    else:
        try:
            files = [
                (f, f.stat().st_mtime)
                for f in proj_dir.iterdir()
                if f.suffix == ".jsonl" and "subagent" not in f.name
            ]
        except OSError:
            return None
        if not files:
            return None
        files.sort(key=lambda x: x[1], reverse=True)
        file_path = files[0][0]

    try:
        resolved = file_path.resolve()
    except (ValueError, OSError):
        return None

    if not str(resolved).startswith(str(PROJECTS_DIR.resolve())) or not resolved.is_file():
        return None
    return file_path


def get_session_history(cwd: str, session_id: str = "", count: int = 500) -> list[Message]:
    """Read messages from a specific session JSONL file.

    If session_id is empty, uses the most recent session file for the cwd.
    """
    if not cwd:
        return []

    file_path = _find_session_file(cwd, session_id)
    if file_path is None:
        return []

    try:
        msgs: list[Message] = []
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                if len(msgs) >= count:
                    break
                try:
                    d = json.loads(line)
                    role = d.get("message", {}).get("role")
                    if role not in ("user", "assistant"):
                        continue
                    content = d["message"]["content"]
                    ts = d.get("timestamp", "")
                    text = ""
                    has_tool_use = False
                    has_tool_result = False
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        for c in content:
                            if c.get("type") == "text" and c.get("text", "").strip() and not text:
                                text = c["text"].strip()
                            if c.get("type") == "tool_use":
                                has_tool_use = True
                            if c.get("type") == "tool_result":
                                has_tool_result = True

                    if text:
                        msgs.append(
                            Message(
                                role=role,
                                text=text[:1000],
                                has_tool_use=has_tool_use,
                                has_tool_result=has_tool_result,
                                timestamp=ts,
                            )
                        )
                    elif has_tool_use or has_tool_result:
                        display = "(using tools...)" if has_tool_use else "(tool result)"
                        msgs.append(
                            Message(
                                role=role,
                                text=display,
                                has_tool_use=has_tool_use,
                                has_tool_result=has_tool_result,
                                timestamp=ts,
                            )
                        )
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

        return msgs
    except OSError:
        return []


def get_claude_sessions() -> list[LiveSession]:
    """Get all running Claude Code sessions with their details."""
    pids = find_claude_pids()
    sessions: list[LiveSession] = []

    for pid in pids:
        info = get_process_info(pid)
        if not info:
            continue

        cwd = get_process_cwd(pid)
        messages = get_session_messages(cwd)

        status = "idle"
        cpu_num = 0.0
        with contextlib.suppress(ValueError):
            cpu_num = float(info.cpu)

        if messages:
            last = messages[-1]
            if last.role == "user":
                status = "working"
                # If the last user message is old and CPU is low, Claude
                # is no longer processing (e.g. after /clear or /compact).
                if last.timestamp and cpu_num < 5:
                    try:
                        ts = datetime.fromisoformat(
                            last.timestamp.replace("Z", "+00:00")
                        )
                        age = time.time() - ts.timestamp()
                        if age > 30:
                            status = "idle"
                    except (ValueError, OSError):
                        pass
            elif last.has_tool_use:
                status = "thinking"

        if status == "idle" and cpu_num > 10:
            status = "working"

        sessions.append(
            LiveSession(
                pid=info.pid,
                tty=info.tty,
                cpu=f"{info.cpu}%",
                mem=f"{info.mem}%",
                elapsed=info.elapsed,
                cwd=cwd,
                project_name=os.path.basename(cwd) if cwd else "unknown",
                status=status,
                messages=messages,
            )
        )

    return sessions


def get_recent_sessions(limit: int = 20) -> list[RecentSession]:
    """Get recently used Claude Code sessions."""
    try:
        if not PROJECTS_DIR.exists():
            return []

        sessions: list[RecentSession] = []
        for proj_dir in PROJECTS_DIR.iterdir():
            if not proj_dir.is_dir():
                continue
            for f in proj_dir.iterdir():
                if f.suffix != ".jsonl" or "subagent" in f.name:
                    continue
                stat = f.stat()
                project_name = parse_project_name(proj_dir.name)
                first_message = _read_first_message(f) or "(no message)"
                sessions.append(
                    RecentSession(
                        session_id=f.stem,
                        project_name=project_name,
                        cwd=proj_dir.name.replace("-", "/"),
                        last_modified=stat.st_mtime * 1000,
                        last_modified_str=format_time_ago(stat.st_mtime),
                        first_message=first_message,
                    )
                )

        sessions.sort(key=lambda s: s.last_modified, reverse=True)
        return sessions[:limit]
    except OSError:
        return []


def get_project_roster() -> list[ProjectRoster]:
    """Get the project roster with session counts."""
    try:
        if not PROJECTS_DIR.exists():
            return []

        projects: list[ProjectRoster] = []
        for proj_dir in PROJECTS_DIR.iterdir():
            if not proj_dir.is_dir():
                continue

            files: list[tuple[Path, float]] = []
            for f in proj_dir.iterdir():
                if f.suffix == ".jsonl" and "subagent" not in f.name:
                    files.append((f, f.stat().st_mtime))
            if not files:
                continue
            files.sort(key=lambda x: x[1], reverse=True)

            cwd = proj_dir.name.replace("-", "/")
            project_name = parse_project_name(proj_dir.name)
            latest_session = files[0][0].stem
            first_message = _read_first_message(files[0][0]) or "(no message)"

            projects.append(
                ProjectRoster(
                    dir_key=proj_dir.name,
                    cwd=cwd,
                    project_name=project_name,
                    latest_session=latest_session,
                    session_count=len(files),
                    last_modified=files[0][1] * 1000,
                    last_modified_str=format_time_ago(files[0][1]),
                    first_message=first_message,
                )
            )

        projects.sort(key=lambda p: p.last_modified, reverse=True)
        return projects
    except OSError:
        return []
