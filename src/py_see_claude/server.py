"""HTTP server for py-see-claude dashboard."""

from __future__ import annotations

import base64
import hmac
import json
import os
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any
from urllib.parse import parse_qs, urlparse

from py_see_claude.sessions import (
    get_claude_sessions,
    get_project_roster,
    get_recent_sessions,
)
from py_see_claude.terminal import focus_terminal, launch_session, new_session, send_message

PORT = int(os.environ.get("PORT", "3456"))
STATIC_DIR = Path(__file__).parent / "static"

# Optional HTTP Basic Auth
AUTH_CREDENTIALS = os.environ.get("SEE_CLAUDE_AUTH", "")

# Optional multi-machine remotes
REMOTES_RAW = os.environ.get("SEE_CLAUDE_REMOTES", "")


def _parse_remotes() -> list[dict[str, str | int]]:
    """Parse SEE_CLAUDE_REMOTES env var.

    Format: name=host:port,name2=host2:port2,...
    """
    if not REMOTES_RAW:
        return []
    remotes: list[dict[str, str | int]] = []
    for entry in REMOTES_RAW.split(","):
        entry = entry.strip()
        if not entry or "=" not in entry:
            continue
        name, hostport = entry.split("=", 1)
        name = name.strip()
        hostport = hostport.strip()
        if ":" not in hostport:
            continue
        host, port_str = hostport.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            continue
        remotes.append({"name": name, "host": host, "port": port})
    return remotes


def _check_auth(headers: Any) -> bool:
    """Check HTTP Basic Auth credentials.

    Returns True if auth is not configured or credentials are valid.
    Uses hmac.compare_digest for constant-time comparison.
    """
    if not AUTH_CREDENTIALS:
        return True

    auth_header = headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return False

    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False

    return hmac.compare_digest(decoded, AUTH_CREDENTIALS)


def _to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _serialize(obj: Any) -> Any:
    """Convert dataclass instances to JSON-serializable dicts with camelCase keys."""
    if hasattr(obj, "__dataclass_fields__"):
        return {_to_camel(k): _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    return obj


def _get_all_data() -> str:
    """Get all session data as JSON string."""
    live = _serialize(get_claude_sessions())
    recent = _serialize(get_recent_sessions())
    roster = _serialize(get_project_roster())
    return json.dumps(
        {
            "live": live,
            "recent": recent,
            "roster": roster,
            "homeDir": os.path.expanduser("~"),
        }
    )


class SSEManager:
    """Manages Server-Sent Events client connections."""

    def __init__(self) -> None:
        self._clients: set[Any] = set()
        self._lock = threading.Lock()

    def add(self, wfile: Any) -> None:
        with self._lock:
            self._clients.add(wfile)

    def remove(self, wfile: Any) -> None:
        with self._lock:
            self._clients.discard(wfile)

    def broadcast(self, data: str) -> None:
        msg = f"data: {data}\n\n".encode()
        with self._lock:
            dead: list[Any] = []
            for wfile in self._clients:
                try:
                    wfile.write(msg)
                    wfile.flush()
                except (BrokenPipeError, ConnectionError, OSError):
                    dead.append(wfile)
            for d in dead:
                self._clients.discard(d)


sse_manager = SSEManager()


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dashboard."""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    def _add_cors_headers(self) -> None:
        """Add CORS headers for multi-machine support."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, data: dict[str, Any] | list[Any], status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_unauthorized(self) -> None:
        """Send 401 Unauthorized response with WWW-Authenticate header."""
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="See Claude"')
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "12")
        self.end_headers()
        self.wfile.write(b"Unauthorized")

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Handle CORS preflight requests."""
        self.send_response(204)
        self._add_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        # Auth check for all endpoints
        if not _check_auth(self.headers):
            self._send_unauthorized()
            return

        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/api/sessions":
            self._handle_sessions()
        elif path == "/api/stream":
            self._handle_stream()
        elif path == "/api/ls":
            self._handle_ls(params)
        elif path == "/api/focus":
            self._handle_focus(params)
        elif path == "/api/config":
            self._handle_config()
        else:
            self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        # Auth check for all endpoints
        if not _check_auth(self.headers):
            self._send_unauthorized()
            return

        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/mkdir":
            self._handle_mkdir()
        elif path == "/api/new":
            self._handle_new()
        elif path == "/api/send":
            self._handle_send()
        elif path == "/api/launch":
            self._handle_launch()
        else:
            self.send_error(404)

    def _handle_sessions(self) -> None:
        body = _get_all_data().encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _handle_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._add_cors_headers()
        self.end_headers()

        # Send initial data
        data = _get_all_data()
        try:
            self.wfile.write(f"data: {data}\n\n".encode())
            self.wfile.flush()
        except (BrokenPipeError, ConnectionError, OSError):
            return

        sse_manager.add(self.wfile)
        try:
            # Keep the connection alive until it drops
            while True:
                time.sleep(30)
        except Exception:
            pass
        finally:
            sse_manager.remove(self.wfile)

    def _handle_ls(self, params: dict[str, list[str]]) -> None:
        dir_path = params.get("dir", [os.path.expanduser("~")])[0]
        try:
            entries = sorted(
                [
                    e.name
                    for e in Path(dir_path).iterdir()
                    if e.is_dir() and not e.name.startswith(".")
                ]
            )
            self._send_json({"ok": True, "dir": dir_path, "entries": entries})
        except OSError as e:
            self._send_json({"ok": False, "dir": dir_path, "entries": [], "error": str(e)})

    def _handle_focus(self, params: dict[str, list[str]]) -> None:
        tty = params.get("tty", [""])[0]
        cwd = params.get("cwd", [""])[0]
        if tty:
            focus_terminal(tty, cwd=cwd)
        self._send_json({"ok": True})

    def _handle_config(self) -> None:
        """Return server configuration for multi-machine support."""
        remotes = _parse_remotes()
        self._send_json({"remotes": remotes})

    def _handle_mkdir(self) -> None:
        try:
            body = json.loads(self._read_body())
            dir_path = body["path"]
            # Security: reject paths with ..
            if ".." in dir_path:
                self._send_json({"ok": False, "error": "Invalid path"}, status=400)
                return
            os.makedirs(dir_path, exist_ok=True)
            self._send_json({"ok": True})
        except (json.JSONDecodeError, KeyError, OSError) as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def _handle_new(self) -> None:
        try:
            body = json.loads(self._read_body())
            ok = new_session(
                directory=body["dir"],
                prompt=body.get("prompt", ""),
                skip_perms=body.get("skipPerms", False),
            )
            if ok:
                self._send_json({"ok": True})
            else:
                self._send_json(
                    {"ok": False, "error": "Not supported on this platform"}, status=500
                )
        except (json.JSONDecodeError, KeyError, OSError) as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def _handle_send(self) -> None:
        try:
            body = json.loads(self._read_body())
            ok = send_message(tty=body["tty"], message=body["message"], cwd=body.get("cwd", ""))
            if ok:
                self._send_json({"ok": True})
            else:
                self._send_json({"ok": False, "error": "Send failed or not supported"}, status=500)
        except (json.JSONDecodeError, KeyError) as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def _handle_launch(self) -> None:
        try:
            body = json.loads(self._read_body())
            ok = launch_session(
                session_id=body["sessionId"],
                cwd=body["cwd"],
                skip_perms=body.get("skipPerms", False),
            )
            if ok:
                self._send_json({"ok": True})
            else:
                self._send_json(
                    {"ok": False, "error": "Launch failed or not supported"}, status=500
                )
        except (json.JSONDecodeError, KeyError, OSError) as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)

    def _serve_static(self, path: str) -> None:
        if path in ("/", ""):
            path = "/index.html"

        file_path = STATIC_DIR / path.lstrip("/")

        # Security: prevent directory traversal
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(STATIC_DIR.resolve())):
                self.send_error(403)
                return
        except (ValueError, OSError):
            self.send_error(403)
            return

        if not file_path.is_file():
            # Serve index.html as SPA fallback
            file_path = STATIC_DIR / "index.html"

        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }

        ext = file_path.suffix
        content_type = content_types.get(ext, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except OSError:
            self.send_error(404)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a new thread."""

    daemon_threads = True


def _sse_broadcaster() -> None:
    """Background thread that broadcasts session data to SSE clients."""
    while True:
        time.sleep(2)
        try:
            data = _get_all_data()
            sse_manager.broadcast(data)
        except Exception:
            pass


def run_server(port: int | None = None) -> None:
    """Start the dashboard server."""
    listen_port = port if port is not None else PORT
    server = ThreadedHTTPServer(("", listen_port), DashboardHandler)

    broadcaster = threading.Thread(target=_sse_broadcaster, daemon=True)
    broadcaster.start()

    print(f"\n  py-see-claude running at http://localhost:{listen_port}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        server.shutdown()
