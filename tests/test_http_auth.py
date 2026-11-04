"""Tests for bearer-token authentication on the HTTP transport."""

import hashlib
import json

import pytest
from fastmcp import FastMCP
from starlette.testclient import TestClient

from things_mcp import server
from things_mcp.scope import (
    DENY_ALL, SCOPE_CLAIM, SCOPE_ENV, UNRESTRICTED,
    Credential, Scope, token_digest,
)
from things_mcp.server import (
    AUTH_TOKEN_ENV,
    TOKENS_FILE_ENV,
    BearerTokenVerifier,
    _current_scope,
    _http_auth_from_env,
)

TOKEN = "a" * 64
OTHER_TOKEN = "b" * 64


def credential(token=TOKEN, name="test", scope=UNRESTRICTED):
    return Credential(name=name, digest=token_digest(token), scope=scope)


def write_tokens_file(tmp_path, entries):
    path = tmp_path / "tokens.json"
    path.write_text(json.dumps({"tokens": entries}))
    return str(path)


def sha(token):
    return hashlib.sha256(token.encode()).hexdigest()
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

    async def test_strong_token_is_unrestricted_by_default(self):
        verifier = _http_auth_from_env({AUTH_TOKEN_ENV: TOKEN})
        access = await verifier.verify_token(TOKEN)
        assert Scope.from_claim(access.claims[SCOPE_CLAIM]) == UNRESTRICTED

    async def test_env_token_uses_env_scope(self):
        verifier = _http_auth_from_env({AUTH_TOKEN_ENV: TOKEN, SCOPE_ENV: "Work;Clients->Acme"})
        access = await verifier.verify_token(TOKEN)
        assert Scope.from_claim(access.claims[SCOPE_CLAIM]) == Scope(
            entries=frozenset({"Work", "Clients->Acme"})
        )

    def test_scope_env_without_env_token_refuses_to_start(self, tmp_path):
        path = write_tokens_file(tmp_path, [{"name": "a", "sha256": sha(TOKEN), "unrestricted": True}])
        with pytest.raises(SystemExit, match="only applies"):
            _http_auth_from_env({TOKENS_FILE_ENV: path, SCOPE_ENV: "p"})

    async def test_tokens_file_maps_each_token_to_its_scope(self, tmp_path):
        path = write_tokens_file(tmp_path, [
            {"name": "work", "sha256": sha(TOKEN), "scope": ["Work", "Clients->Acme"]},
            {"name": "admin", "sha256": sha(OTHER_TOKEN), "unrestricted": True},
        ])
        verifier = _http_auth_from_env({TOKENS_FILE_ENV: path})

        work = await verifier.verify_token(TOKEN)
        admin = await verifier.verify_token(OTHER_TOKEN)

        assert work.client_id == "work"
        assert Scope.from_claim(work.claims[SCOPE_CLAIM]) == Scope(
            entries=frozenset({"Work", "Clients->Acme"})
        )
        assert Scope.from_claim(admin.claims[SCOPE_CLAIM]) == UNRESTRICTED
        assert await verifier.verify_token("c" * 64) is None

    def test_invalid_tokens_file_refuses_to_start(self, tmp_path):
        path = write_tokens_file(tmp_path, [{"name": "a", "sha256": sha(TOKEN)}])
        with pytest.raises(SystemExit, match="at least one area or project"):
            _http_auth_from_env({TOKENS_FILE_ENV: path})

    def test_missing_tokens_file_refuses_to_start(self, tmp_path):
        with pytest.raises(SystemExit, match=TOKENS_FILE_ENV):
            _http_auth_from_env({TOKENS_FILE_ENV: str(tmp_path / "missing.json")})

    def test_same_token_twice_refuses_to_start(self, tmp_path):
        path = write_tokens_file(tmp_path, [{"name": "dup", "sha256": sha(TOKEN), "unrestricted": True}])
        with pytest.raises(SystemExit, match="more than once"):
            _http_auth_from_env({AUTH_TOKEN_ENV: TOKEN, TOKENS_FILE_ENV: path})

    def test_duplicate_names_refuse_to_start(self, tmp_path):
        path = write_tokens_file(tmp_path, [
            {"name": "same", "sha256": sha(TOKEN), "unrestricted": True},
            {"name": "same", "sha256": sha(OTHER_TOKEN), "unrestricted": True},
        ])
        with pytest.raises(SystemExit, match="unique name"):
            _http_auth_from_env({TOKENS_FILE_ENV: path})


class TestBearerTokenVerifier:
    async def test_accepts_matching_token(self):
        access = await BearerTokenVerifier([credential()]).verify_token(TOKEN)
        assert access is not None
        assert access.client_id == "test"

    @pytest.mark.parametrize("candidate", ["", "wrong", TOKEN[:-1], TOKEN + "a", "ä" * 64])
    async def test_rejects_other_tokens(self, candidate):
        assert await BearerTokenVerifier([credential()]).verify_token(candidate) is None


class TestCurrentScope:
    def test_without_auth_uses_process_scope(self, monkeypatch):
        scope = Scope(entries=frozenset({"->Solo"}))
        monkeypatch.setattr(server.mcp, "auth", None)
        monkeypatch.setattr(server, "PROCESS_SCOPE", scope)
        assert _current_scope() == scope

    def test_with_auth_uses_the_token_claim(self, mocker, monkeypatch):
        scope = Scope(entries=frozenset({"Work"}))
        monkeypatch.setattr(server.mcp, "auth", BearerTokenVerifier([]))
        mocker.patch.object(server, "get_access_token", return_value=server.AccessToken(
            token="t", client_id="c", scopes=[], claims={SCOPE_CLAIM: scope.to_claim()},
        ))
        assert _current_scope() == scope

    def test_with_auth_but_no_token_denies_everything(self, mocker, monkeypatch):
        monkeypatch.setattr(server.mcp, "auth", BearerTokenVerifier([]))
        mocker.patch.object(server, "get_access_token", return_value=None)
        assert _current_scope() == DENY_ALL

    @pytest.mark.parametrize("claim", [None, "all", {"entries": "Work"}, {"entries": [1]}, {"entries": [" "]}, {"unrestricted": "yes"}])
    def test_malformed_claim_denies_everything(self, claim):
        assert Scope.from_claim(claim) == DENY_ALL


class TestHttpEndpoint:
    """Exercise FastMCP's real Starlette app with our verifier installed."""

    @pytest.fixture
    def client(self):
        app = FastMCP("test", auth=BearerTokenVerifier([credential()])).http_app()
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
