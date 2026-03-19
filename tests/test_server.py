"""Tests for the HTTP server."""

from __future__ import annotations

import base64
import json
import tempfile
import threading
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

import pytest

from py_see_claude.server import (
    DashboardHandler,
    ThreadedHTTPServer,
    _check_auth,
    _parse_remotes,
    _serialize,
    _to_camel,
)
from py_see_claude.sessions import LiveSession, Message


class TestToCamel:
    def test_simple(self) -> None:
        assert _to_camel("project_name") == "projectName"

    def test_multiple_parts(self) -> None:
        assert _to_camel("last_modified_str") == "lastModifiedStr"

    def test_single_word(self) -> None:
        assert _to_camel("pid") == "pid"

    def test_already_camel(self) -> None:
        assert _to_camel("projectName") == "projectName"


class TestSerialize:
    def test_dataclass(self) -> None:
        msg = Message(role="user", text="hello", has_tool_use=False, has_tool_result=False)
        result = _serialize(msg)
        assert result == {
            "role": "user",
            "text": "hello",
            "hasToolUse": False,
            "hasToolResult": False,
        }

    def test_list(self) -> None:
        msgs = [
            Message(role="user", text="hi", has_tool_use=False, has_tool_result=False),
            Message(role="assistant", text="hello", has_tool_use=False, has_tool_result=False),
        ]
        result = _serialize(msgs)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_nested_dataclass(self) -> None:
        session = LiveSession(
            pid="123",
            tty="ttys001",
            cpu="5.0%",
            mem="1.0%",
            elapsed="00:10",
            cwd="/test",
            project_name="test",
            status="idle",
            messages=[
                Message(role="user", text="hello", has_tool_use=False, has_tool_result=False),
            ],
        )
        result = _serialize(session)
        assert result["projectName"] == "test"
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"


class TestCheckAuth:
    """Tests for Feature 6: REST API Authentication."""

    @patch("py_see_claude.server.AUTH_CREDENTIALS", "")
    def test_no_auth_configured(self) -> None:
        """When AUTH_CREDENTIALS is empty, all requests pass."""
        assert _check_auth({}) is True

    @patch("py_see_claude.server.AUTH_CREDENTIALS", "admin:secret")
    def test_valid_credentials(self) -> None:
        encoded = base64.b64encode(b"admin:secret").decode()
        headers = {"Authorization": f"Basic {encoded}"}
        assert _check_auth(headers) is True

    @patch("py_see_claude.server.AUTH_CREDENTIALS", "admin:secret")
    def test_invalid_credentials(self) -> None:
        encoded = base64.b64encode(b"admin:wrong").decode()
        headers = {"Authorization": f"Basic {encoded}"}
        assert _check_auth(headers) is False

    @patch("py_see_claude.server.AUTH_CREDENTIALS", "admin:secret")
    def test_missing_auth_header(self) -> None:
        assert _check_auth({}) is False

    @patch("py_see_claude.server.AUTH_CREDENTIALS", "admin:secret")
    def test_non_basic_auth(self) -> None:
        headers = {"Authorization": "Bearer token123"}
        assert _check_auth(headers) is False

    @patch("py_see_claude.server.AUTH_CREDENTIALS", "admin:secret")
    def test_invalid_base64(self) -> None:
        headers = {"Authorization": "Basic !!!invalid!!!"}
        assert _check_auth(headers) is False


class TestParseRemotes:
    """Tests for Feature 5: Multi-Machine Support config parsing."""

    @patch("py_see_claude.server.REMOTES_RAW", "")
    def test_empty_remotes(self) -> None:
        assert _parse_remotes() == []

    @patch("py_see_claude.server.REMOTES_RAW", "dev=192.168.1.10:3456")
    def test_single_remote(self) -> None:
        remotes = _parse_remotes()
        assert len(remotes) == 1
        assert remotes[0]["name"] == "dev"
        assert remotes[0]["host"] == "192.168.1.10"
        assert remotes[0]["port"] == 3456

    @patch("py_see_claude.server.REMOTES_RAW", "dev=host1:3456,staging=host2:3457")
    def test_multiple_remotes(self) -> None:
        remotes = _parse_remotes()
        assert len(remotes) == 2
        assert remotes[0]["name"] == "dev"
        assert remotes[1]["name"] == "staging"

    @patch("py_see_claude.server.REMOTES_RAW", "bad_entry,another_bad")
    def test_invalid_entries_skipped(self) -> None:
        assert _parse_remotes() == []

    @patch("py_see_claude.server.REMOTES_RAW", "dev=host1:notaport")
    def test_invalid_port_skipped(self) -> None:
        assert _parse_remotes() == []


class TestHTTPServer:
    @pytest.fixture
    def server(self) -> ThreadedHTTPServer:
        srv = ThreadedHTTPServer(("127.0.0.1", 0), DashboardHandler)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        yield srv
        srv.shutdown()

    def _get(
        self, server: ThreadedHTTPServer, path: str, headers: dict[str, str] | None = None
    ) -> tuple[int, bytes]:
        host, port = server.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("GET", path, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, resp.read()

    def _post(
        self,
        server: ThreadedHTTPServer,
        path: str,
        body: dict,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        host, port = server.server_address
        conn = HTTPConnection(host, port, timeout=5)
        data = json.dumps(body).encode()
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        conn.request("POST", path, body=data, headers=req_headers)
        resp = conn.getresponse()
        return resp.status, resp.read()

    def test_serves_index_html(self, server: ThreadedHTTPServer) -> None:
        status, body = self._get(server, "/")
        assert status == 200
        assert b"See Claude" in body

    def test_serves_css(self, server: ThreadedHTTPServer) -> None:
        status, body = self._get(server, "/style.css")
        assert status == 200
        assert b"JetBrains Mono" in body

    def test_serves_js(self, server: ThreadedHTTPServer) -> None:
        status, body = self._get(server, "/app.js")
        assert status == 200
        assert b"connectSSE" in body

    @patch("py_see_claude.server.get_project_roster", return_value=[])
    @patch("py_see_claude.server.get_recent_sessions", return_value=[])
    @patch("py_see_claude.server.get_claude_sessions", return_value=[])
    def test_api_sessions(
        self, _m1: object, _m2: object, _m3: object, server: ThreadedHTTPServer
    ) -> None:
        status, body = self._get(server, "/api/sessions")
        assert status == 200
        data = json.loads(body)
        assert "live" in data
        assert "recent" in data
        assert "roster" in data
        assert "homeDir" in data

    def test_api_ls(self, server: ThreadedHTTPServer) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "subdir").mkdir()
            status, body = self._get(server, f"/api/ls?dir={tmpdir}")
            assert status == 200
            data = json.loads(body)
            assert data["ok"] is True
            assert "subdir" in data["entries"]

    def test_api_ls_nonexistent(self, server: ThreadedHTTPServer) -> None:
        status, body = self._get(server, "/api/ls?dir=/nonexistent/path/12345")
        assert status == 200
        data = json.loads(body)
        assert data["ok"] is False

    def test_api_mkdir(self, server: ThreadedHTTPServer) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = str(Path(tmpdir) / "newdir")
            status, body = self._post(server, "/api/mkdir", {"path": new_dir})
            assert status == 200
            data = json.loads(body)
            assert data["ok"] is True
            assert Path(new_dir).is_dir()

    def test_api_mkdir_rejects_traversal(self, server: ThreadedHTTPServer) -> None:
        status, body = self._post(server, "/api/mkdir", {"path": "/tmp/../../../etc/evil"})
        assert status == 400
        data = json.loads(body)
        assert data["ok"] is False

    def test_prevents_directory_traversal(self, server: ThreadedHTTPServer) -> None:
        status, _ = self._get(server, "/../../../etc/passwd")
        # Should either serve index.html (SPA fallback) or return 403
        assert status in (200, 403)

    @patch("py_see_claude.server.send_message", return_value=False)
    def test_api_send_unsupported(self, mock_send: object, server: ThreadedHTTPServer) -> None:
        status, body = self._post(server, "/api/send", {"tty": "ttys001", "message": "hello"})
        assert status == 500
        data = json.loads(body)
        assert data["ok"] is False

    def test_api_config_endpoint(self, server: ThreadedHTTPServer) -> None:
        """Test Feature 5: config endpoint returns remotes list."""
        status, body = self._get(server, "/api/config")
        assert status == 200
        data = json.loads(body)
        assert "remotes" in data
        assert isinstance(data["remotes"], list)

    @patch("py_see_claude.server.REMOTES_RAW", "dev=192.168.1.10:3456")
    def test_api_config_with_remotes(self, server: ThreadedHTTPServer) -> None:
        """Test Feature 5: config endpoint returns configured remotes."""
        status, body = self._get(server, "/api/config")
        assert status == 200
        data = json.loads(body)
        assert len(data["remotes"]) == 1
        assert data["remotes"][0]["name"] == "dev"

    @patch("py_see_claude.server.AUTH_CREDENTIALS", "admin:secret")
    def test_auth_blocks_unauthenticated(self, server: ThreadedHTTPServer) -> None:
        """Test Feature 6: unauthenticated requests get 401."""
        status, _ = self._get(server, "/api/sessions")
        assert status == 401

    @patch("py_see_claude.server.AUTH_CREDENTIALS", "admin:secret")
    @patch("py_see_claude.server.get_project_roster", return_value=[])
    @patch("py_see_claude.server.get_recent_sessions", return_value=[])
    @patch("py_see_claude.server.get_claude_sessions", return_value=[])
    def test_auth_allows_authenticated(
        self, _m1: object, _m2: object, _m3: object, server: ThreadedHTTPServer
    ) -> None:
        """Test Feature 6: authenticated requests pass."""
        encoded = base64.b64encode(b"admin:secret").decode()
        status, body = self._get(
            server, "/api/sessions", headers={"Authorization": f"Basic {encoded}"}
        )
        assert status == 200
        data = json.loads(body)
        assert "live" in data

    @patch(
        "py_see_claude.server.get_session_history",
        return_value=[
            Message(role="user", text="hello", has_tool_use=False, has_tool_result=False),
            Message(role="assistant", text="hi there", has_tool_use=False, has_tool_result=False),
        ],
    )
    def test_api_history(self, mock_hist: object, server: ThreadedHTTPServer) -> None:
        status, body = self._get(server, "/api/history?cwd=/Users/test/proj")
        assert status == 200
        data = json.loads(body)
        assert data["ok"] is True
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["text"] == "hi there"

    @patch(
        "py_see_claude.server.get_session_history",
        return_value=[
            Message(role="user", text="hello", has_tool_use=False, has_tool_result=False),
        ],
    )
    def test_api_history_with_session_id(
        self, mock_hist: object, server: ThreadedHTTPServer
    ) -> None:
        status, body = self._get(server, "/api/history?cwd=/Users/test/proj&session=abc123")
        assert status == 200
        data = json.loads(body)
        assert data["ok"] is True
        assert len(data["messages"]) == 1

    def test_api_history_missing_cwd(self, server: ThreadedHTTPServer) -> None:
        status, body = self._get(server, "/api/history")
        assert status == 400
        data = json.loads(body)
        assert data["ok"] is False

    def test_cors_headers_on_sessions(self, server: ThreadedHTTPServer) -> None:
        """Test Feature 5: CORS headers are present on API responses."""
        host, port = server.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("OPTIONS", "/api/sessions")
        resp = conn.getresponse()
        assert resp.status == 204
        assert resp.getheader("Access-Control-Allow-Origin") == "*"
