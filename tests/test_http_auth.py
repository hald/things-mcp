"""Tests for bearer-token authentication on the HTTP transport."""

import pytest
from fastmcp import FastMCP
from starlette.testclient import TestClient

from things_mcp import server
from things_mcp.server import (
    AUTH_TOKEN_ENV,
    BearerTokenVerifier,
    _http_auth_from_env,
)

TOKEN = "a" * 64
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


class TestHttpAuthFromEnv:
    def test_missing_token_refuses_to_start(self):
        with pytest.raises(SystemExit, match=AUTH_TOKEN_ENV):
            _http_auth_from_env({})

    def test_blank_token_refuses_to_start(self):
        with pytest.raises(SystemExit, match=AUTH_TOKEN_ENV):
            _http_auth_from_env({AUTH_TOKEN_ENV: "   "})

    def test_short_token_refuses_to_start(self):
        with pytest.raises(SystemExit, match="at least"):
            _http_auth_from_env({AUTH_TOKEN_ENV: "short"})

    def test_strong_token_returns_verifier(self):
        assert isinstance(_http_auth_from_env({AUTH_TOKEN_ENV: TOKEN}), BearerTokenVerifier)


class TestBearerTokenVerifier:
    async def test_accepts_matching_token(self):
        access = await BearerTokenVerifier(TOKEN).verify_token(TOKEN)
        assert access is not None
        assert access.client_id == "things-mcp"

    @pytest.mark.parametrize("candidate", ["", "wrong", TOKEN[:-1], TOKEN + "a", "ä" * 64])
    async def test_rejects_other_tokens(self, candidate):
        assert await BearerTokenVerifier(TOKEN).verify_token(candidate) is None


class TestHttpEndpoint:
    """Exercise FastMCP's real Starlette app with our verifier installed."""

    @pytest.fixture
    def client(self):
        app = FastMCP("test", auth=BearerTokenVerifier(TOKEN)).http_app()
        with TestClient(app) as client:
            yield client

    def test_request_without_token_is_rejected(self, client):
        response = client.post("/mcp", json=INITIALIZE, headers=HEADERS)
        assert response.status_code == 401

    def test_request_with_wrong_token_is_rejected(self, client):
        response = client.post(
            "/mcp", json=INITIALIZE,
            headers={**HEADERS, "Authorization": "Bearer wrong"},
        )
        assert response.status_code == 401

    def test_request_with_token_is_accepted(self, client):
        response = client.post(
            "/mcp", json=INITIALIZE,
            headers={**HEADERS, "Authorization": f"Bearer {TOKEN}"},
        )
        assert response.status_code == 200


class TestMain:
    def test_http_mode_installs_auth_before_serving(self, mocker, monkeypatch):
        monkeypatch.setattr(server, "TRANSPORT", "http")
        monkeypatch.setenv(AUTH_TOKEN_ENV, TOKEN)
        monkeypatch.setattr(server.mcp, "auth", None)
        run = mocker.patch.object(server.mcp, "run")

        server.main()

        assert isinstance(server.mcp.auth, BearerTokenVerifier)
        run.assert_called_once_with(
            transport="http", host=server.HTTP_HOST, port=server.HTTP_PORT
        )

    def test_http_mode_without_token_never_serves(self, mocker, monkeypatch):
        monkeypatch.setattr(server, "TRANSPORT", "http")
        monkeypatch.delenv(AUTH_TOKEN_ENV, raising=False)
        monkeypatch.setattr(server.mcp, "auth", None)
        run = mocker.patch.object(server.mcp, "run")

        with pytest.raises(SystemExit):
            server.main()

        run.assert_not_called()

    def test_stdio_mode_needs_no_token(self, mocker, monkeypatch):
        monkeypatch.setattr(server, "TRANSPORT", "stdio")
        monkeypatch.delenv(AUTH_TOKEN_ENV, raising=False)
        monkeypatch.setattr(server.mcp, "auth", None)
        run = mocker.patch.object(server.mcp, "run")

        server.main()

        run.assert_called_once_with()
        assert server.mcp.auth is None
