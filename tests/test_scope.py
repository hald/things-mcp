"""Tests for limiting MCP access to configured Areas and Projects."""

import hashlib
import json
from contextlib import asynccontextmanager

import httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from tests._helpers import tool_text
from things_mcp import scope as scope_module
from things_mcp import server
from things_mcp.scope import (
    DENY_ALL, SCOPE_ENV, UNRESTRICTED, Credential, Scope,
    ScopeError, ScopeView, load_credentials_file, scope_from_env, token_digest,
)

# A small Things database:
#
#   Area "Work" (in scope)       -> to-do T_AREA, project "Launch" -> T_PROJECT,
#                                   heading H_WORK -> T_HEADING,
#                                   completed project "Launch" (P_OLD, same name)
#   Area "Home" (out of scope)   -> project "Garden" -> T_HOME, heading H_HOME -> T_HOME_HEADING,
#                                   project "Client" (scoped on its own) -> T_CLIENT
#   No area                      -> project "Solo" -> T_SOLO
#   Inbox                        -> T_INBOX
AREAS = [
    {"uuid": "A_WORK", "type": "area", "title": "Work"},
    {"uuid": "A_HOME", "type": "area", "title": "Home"},
]
PROJECTS = [
    {"uuid": "P_WORK", "type": "project", "title": "Launch", "status": "incomplete",
     "area": "A_WORK", "area_title": "Work"},
    {"uuid": "P_OLD", "type": "project", "title": "Launch", "status": "completed",
     "area": "A_WORK", "area_title": "Work"},
    {"uuid": "P_HOME", "type": "project", "title": "Garden", "status": "incomplete",
     "area": "A_HOME", "area_title": "Home"},
    {"uuid": "P_CLIENT", "type": "project", "title": "Client", "status": "incomplete",
     "area": "A_HOME", "area_title": "Home"},
    {"uuid": "P_SOLO", "type": "project", "title": "Solo", "status": "incomplete"},
]
HEADINGS = [
    {"uuid": "H_WORK", "type": "heading", "title": "Phase 1", "project": "P_WORK"},
    {"uuid": "H_HOME", "type": "heading", "title": "Beds", "project": "P_HOME"},
]
TODOS = [
    {"uuid": "T_AREA", "type": "to-do", "title": "Area task", "area": "A_WORK"},
    {"uuid": "T_PROJECT", "type": "to-do", "title": "Project task", "project": "P_WORK",
     "tags": ["work"]},
    {"uuid": "T_HEADING", "type": "to-do", "title": "Heading task", "heading": "H_WORK"},
    {"uuid": "T_CLIENT", "type": "to-do", "title": "Client task", "project": "P_CLIENT"},
    {"uuid": "T_INBOX", "type": "to-do", "title": "Inbox task", "start": "Inbox"},
    {"uuid": "T_HOME", "type": "to-do", "title": "Home task", "project": "P_HOME",
     "tags": ["secret"]},
    {"uuid": "T_HOME_HEADING", "type": "to-do", "title": "Home heading task", "heading": "H_HOME"},
    {"uuid": "T_SOLO", "type": "to-do", "title": "Solo task", "project": "P_SOLO"},
]
TAGS = [
    {"uuid": "TAG_WORK", "type": "tag", "title": "work"},
    {"uuid": "TAG_SECRET", "type": "tag", "title": "secret"},
]
EVERYTHING = {item["uuid"]: item for item in [*AREAS, *PROJECTS, *HEADINGS, *TODOS, *TAGS]}

# One area plus one project from a different area, in a single list.
SCOPE = Scope(entries=frozenset({"Work", "Home->Client"}))
IN_SCOPE_TODOS = {"T_AREA", "T_PROJECT", "T_HEADING", "T_CLIENT"}


def _copy(items):
    return [dict(item) for item in items]


def _matches(item, kwargs):
    status = kwargs.get("status", "incomplete")
    if status is not None and item.get("status", "incomplete") != status:
        return False
    for key in ("area", "project", "heading"):
        if kwargs.get(key) is not None and item.get(key) != kwargs[key]:
            return False
    tag = kwargs.get("tag")
    if tag is not None:
        if tag not in {t["title"] for t in TAGS}:
            raise ValueError(f"Unrecognized tag type: {tag!r}")
        if tag not in item.get("tags", []):
            return False
    return True


def fake_tasks(uuid=None, **kwargs):
    if uuid:
        return dict(EVERYTHING[uuid])
    pool = {"to-do": TODOS, "project": PROJECTS, "heading": HEADINGS}
    kinds = [kwargs["type"]] if kwargs.get("type") else ["to-do", "project", "heading"]
    return [dict(i) for kind in kinds for i in pool[kind] if _matches(i, kwargs)]


@pytest.fixture
def fake_things(mocker):
    mocker.patch("things.get", side_effect=lambda uuid, default=None: dict(EVERYTHING[uuid]) if uuid in EVERYTHING else default)
    mocker.patch("things.tasks", side_effect=fake_tasks)
    mocker.patch("things.todos", side_effect=lambda uuid=None, **kw: fake_tasks(uuid, type="to-do", **kw))
    mocker.patch("things.projects", side_effect=lambda uuid=None, **kw: fake_tasks(uuid, type="project", **kw))
    mocker.patch("things.areas", side_effect=lambda uuid=None, **kw: [
        dict(a) for a in AREAS if kw.get("tag") is None
    ])
    mocker.patch("things.tags", side_effect=lambda **kw: _copy(TAGS))
    mocker.patch("things.inbox", side_effect=lambda **kw: _copy([t for t in TODOS if t.get("start") == "Inbox"]))
    mocker.patch("things.search", side_effect=lambda query, **kw: _copy(TODOS))
    mocker.patch("things.token", return_value="auth-token")
    return mocker.patch("things_mcp.server.url_scheme.execute_url")


@pytest.fixture
def scoped(fake_things, monkeypatch):
    monkeypatch.setattr(server.mcp, "auth", None)
    monkeypatch.setattr(server, "PROCESS_SCOPE", SCOPE)
    return fake_things


def uuids(result):
    return {item["uuid"] for item in result.structured_content["items"]}


class TestScopeFromEnv:
    def test_unset_is_unrestricted(self):
        assert scope_from_env({}) == UNRESTRICTED

    def test_entries_are_separated_by_semicolons(self):
        scope = scope_from_env({SCOPE_ENV: " Work; Home -> Client ;"})
        assert scope == Scope(entries=frozenset({"Work", "Home -> Client"}))

    def test_commas_and_spaces_stay_part_of_a_name(self):
        scope = scope_from_env({SCOPE_ENV: "Errands, misc;Side projects"})
        assert scope == Scope(entries=frozenset({"Errands, misc", "Side projects"}))

    @pytest.mark.parametrize("value", ["", " ; "])
    def test_empty_value_denies_everything(self, value):
        assert scope_from_env({SCOPE_ENV: value}) == DENY_ALL


class TestLoadCredentialsFile:
    def write(self, tmp_path, data):
        path = tmp_path / "tokens.json"
        path.write_text(json.dumps(data))
        return str(path)

    def test_valid_file(self, tmp_path):
        digest = hashlib.sha256(b"x" * 40).hexdigest()
        path = self.write(tmp_path, {"tokens": [
            {"name": "work", "sha256": digest, "scope": ["Work", " Clients->Acme "]},
        ]})
        [credential] = load_credentials_file(path)
        assert credential.name == "work"
        assert credential.digest == token_digest("x" * 40)
        assert credential.scope == Scope(entries=frozenset({"Work", "Clients->Acme"}))

    @pytest.mark.parametrize("data, message", [
        ({"tokens": []}, "non-empty"),
        ({"tokens": [], "extra": 1}, "single"),
        ({"tokens": [{"name": "a", "sha256": "abc", "unrestricted": True}]}, "64 hex"),
        ({"tokens": [{"sha256": "0" * 64, "unrestricted": True}]}, "name"),
        ({"tokens": [{"name": "a", "sha256": "0" * 64, "scope": ["A"], "unrestricted": True}]}, "not both"),
        ({"tokens": [{"name": "a", "sha256": "0" * 64}]}, "at least one"),
        ({"tokens": [{"name": "a", "sha256": "0" * 64, "scope": []}]}, "at least one"),
        ({"tokens": [{"name": "a", "sha256": "0" * 64, "scope": "A"}]}, "list"),
        ({"tokens": [{"name": "a", "sha256": "0" * 64, "scope": ["Work", " "]}]}, "non-empty"),
        ({"tokens": [{"name": "a", "sha256": "0" * 64, "areas": ["A"]}]}, "unknown keys"),
        ({"tokens": [{"name": "a", "token": "secret", "unrestricted": True}]}, "unknown keys"),
    ])
    def test_invalid_files_are_rejected(self, tmp_path, data, message):
        with pytest.raises(ValueError, match=message):
            load_credentials_file(self.write(tmp_path, data))


class TestScopeView:
    def test_membership(self, fake_things):
        view = ScopeView(SCOPE)
        allowed = {uuid for uuid, item in EVERYTHING.items() if view.allows(item)}
        assert allowed == {
            "A_WORK", "P_WORK", "P_OLD", "P_CLIENT", "H_WORK", "TAG_WORK", *IN_SCOPE_TODOS,
        }

    def test_unrestricted_allows_everything_without_queries(self, fake_things, mocker):
        view = ScopeView(UNRESTRICTED)
        assert all(view.allows(item) for item in EVERYTHING.values())
        assert view.filter(TODOS) is TODOS
        assert view.filter(None) == []

    def test_several_areas_and_projects(self, fake_things):
        view = ScopeView(Scope(entries=frozenset({"Work", "Home", "->Solo"})))
        todos = {t["uuid"] for t in view.filter(_copy(TODOS))}
        assert todos == {t["uuid"] for t in TODOS} - {"T_INBOX"}
        assert view.project_ids == {"P_WORK", "P_OLD", "P_HOME", "P_CLIENT", "P_SOLO"}

    def test_several_projects_without_their_areas(self, fake_things):
        view = ScopeView(Scope(entries=frozenset({"Work->Launch", "Home->Garden"})))
        allowed = {uuid for uuid, item in EVERYTHING.items() if view.allows(item)}
        assert allowed == {
            "P_WORK", "P_HOME", "H_WORK", "H_HOME", "TAG_WORK", "TAG_SECRET",
            "T_PROJECT", "T_HEADING", "T_HOME", "T_HOME_HEADING",
        }

    def test_completed_project_with_the_same_name_is_ignored(self, fake_things):
        assert ScopeView(Scope(entries=frozenset({"Work->Launch"}))).project_ids == {"P_WORK"}

    def test_whitespace_around_the_separator_is_ignored(self, fake_things):
        assert ScopeView(Scope(entries=frozenset({"Home -> Client"}))).project_ids == {"P_CLIENT"}

    def test_project_without_an_area(self, fake_things):
        assert ScopeView(Scope(entries=frozenset({"->Solo"}))).project_ids == {"P_SOLO"}

    @pytest.mark.parametrize("entry", [
        "Solo",            # a plain name means an area, not a project
        "Home->Launch",    # right project name, wrong area
        "->Launch",        # Launch is in an area
        "Home task",       # to-dos can't be scoped
        "work",            # names are case-sensitive
    ])
    def test_entries_that_match_nothing_grant_nothing(self, fake_things, entry):
        view = ScopeView(Scope(entries=frozenset({entry})))
        assert not any(view.allows(item) for item in EVERYTHING.values())

    def test_unknown_name_is_logged(self, fake_things, monkeypatch, caplog):
        monkeypatch.setattr(scope_module, "_reported_entries", set())
        ScopeView(Scope(entries=frozenset({"Wrok"})))
        ScopeView(Scope(entries=frozenset({"Wrok"})))
        warnings = [r for r in caplog.records if "'Wrok'" in r.getMessage()]
        assert len(warnings) == 1
        assert "matches no area or project" in warnings[0].getMessage()

    def test_duplicate_area_names_grant_nothing(self, fake_things, mocker, monkeypatch, caplog):
        monkeypatch.setattr(scope_module, "_reported_entries", set())
        mocker.patch("things.areas", return_value=[
            *_copy(AREAS), {"uuid": "A_WORK_2", "type": "area", "title": "Work"},
        ])
        view = ScopeView(Scope(entries=frozenset({"Work"})))
        assert view.area_ids == set()
        assert view.project_ids == set()
        assert "matches 2 areas/projects" in caplog.text

    def test_duplicate_project_names_grant_nothing(self, fake_things, mocker):
        mocker.patch("things.projects", side_effect=lambda **kw: [
            dict(EVERYTHING["P_WORK"]), {**EVERYTHING["P_WORK"], "uuid": "P_WORK_2"},
        ])
        assert ScopeView(Scope(entries=frozenset({"Work->Launch"}))).project_ids == set()

    def test_names_containing_the_separator(self, fake_things, mocker):
        mocker.patch("things.areas", return_value=[
            *_copy(AREAS), {"uuid": "A_ARROW", "type": "area", "title": "R&D->Ops"},
        ])
        assert ScopeView(Scope(entries=frozenset({"R&D->Ops"}))).area_ids == {"A_ARROW"}

    def test_area_and_project_reading_of_one_entry_is_ambiguous(self, fake_things, mocker):
        # "Work->Launch" could be the project Launch in Work, or an area with that name.
        mocker.patch("things.areas", return_value=[
            *_copy(AREAS), {"uuid": "A_ARROW", "type": "area", "title": "Work->Launch"},
        ])
        view = ScopeView(Scope(entries=frozenset({"Work->Launch"})))
        assert view.area_ids == set()
        assert view.project_ids == set()

    def test_deny_all_allows_nothing(self, fake_things):
        view = ScopeView(DENY_ALL)
        assert not any(view.allows(item) for item in EVERYTHING.values())

    def test_filter_hides_area_of_a_project_scoped_on_its_own(self, fake_things):
        [client] = ScopeView(SCOPE).filter(_copy([EVERYTHING["P_CLIENT"]]))
        assert "area" not in client and "area_title" not in client

    def test_filter_drops_nested_out_of_scope_items(self, fake_things):
        tag = {**EVERYTHING["TAG_WORK"], "items": _copy(TODOS)}
        [filtered] = ScopeView(SCOPE).filter([tag])
        assert {i["uuid"] for i in filtered["items"]} == IN_SCOPE_TODOS

    def test_require_gives_the_same_error_for_missing_and_out_of_scope(self, fake_things):
        view = ScopeView(SCOPE)
        with pytest.raises(ScopeError) as missing:
            view.require("NOPE", ("to-do",))
        with pytest.raises(ScopeError) as hidden:
            view.require("T_HOME", ("to-do",))
        assert str(missing.value).replace("NOPE", "X") == str(hidden.value).replace("T_HOME", "X")

    def test_require_checks_the_kind(self, fake_things):
        with pytest.raises(ScopeError):
            ScopeView(SCOPE).require("P_WORK", ("to-do",))

    def test_destination_title_resolves_within_scope(self, fake_things):
        assert ScopeView(SCOPE).resolve_destination(list_title="Launch") == "P_WORK"

    def test_destination_title_outside_scope_is_rejected(self, fake_things):
        with pytest.raises(ScopeError, match="Garden"):
            ScopeView(SCOPE).resolve_destination(list_title="Garden")

    def test_ambiguous_destination_title_is_rejected(self, fake_things, mocker):
        mocker.patch("things.projects", side_effect=lambda **kw: [
            {**EVERYTHING["P_WORK"]}, {**EVERYTHING["P_WORK"], "uuid": "P_WORK_2"},
        ])
        with pytest.raises(ScopeError, match="pass the UUID"):
            ScopeView(SCOPE).resolve_destination(list_title="Launch")

    def test_destination_is_required_for_new_items(self, fake_things):
        with pytest.raises(ScopeError, match="need a destination"):
            ScopeView(SCOPE).resolve_destination()

    def test_destination_is_optional_for_updates(self, fake_things):
        assert ScopeView(SCOPE).resolve_destination(required=False) is None


class TestScopedReads:
    async def test_inbox_is_out_of_scope(self, scoped):
        assert uuids(await server.get_inbox()) == set()

    async def test_todos_are_filtered(self, scoped):
        assert uuids(await server.get_todos()) == IN_SCOPE_TODOS

    async def test_search_is_filtered(self, scoped):
        result = await server.search_todos("task")
        assert uuids(result) == IN_SCOPE_TODOS
        assert "Home task" not in tool_text(result)

    async def test_projects_are_filtered(self, scoped):
        assert uuids(await server.get_projects()) == {"P_WORK", "P_CLIENT"}

    async def test_areas_are_filtered(self, scoped):
        assert uuids(await server.get_areas()) == {"A_WORK"}

    async def test_headings_are_filtered(self, scoped):
        assert uuids(await server.get_headings()) == {"H_WORK"}

    async def test_out_of_scope_project_looks_missing(self, scoped):
        hidden = tool_text(await server.get_todos(project_uuid="P_HOME"))
        missing = tool_text(await server.get_todos(project_uuid="NOPE"))
        assert hidden.replace("P_HOME", "X") == missing.replace("NOPE", "X")

    async def test_tags_only_show_tags_used_in_scope(self, scoped):
        result = await server.get_tags(include_items=True)
        assert uuids(result) == {"TAG_WORK"}
        assert "Home task" not in tool_text(result)

    async def test_out_of_scope_tag_looks_unused(self, scoped):
        hidden = await server.get_tagged_items("secret")
        assert uuids(hidden) == set()
        assert "secret" in tool_text(hidden)

    async def test_tag_usage_counts_only_scoped_items(self, scoped):
        assert await server.get_tag_usage() == "work: 1 open, 1 total"

    async def test_unrestricted_tag_usage_handles_empty_results(self, fake_things, monkeypatch, mocker):
        monkeypatch.setattr(server.mcp, "auth", None)
        monkeypatch.setattr(server, "PROCESS_SCOPE", UNRESTRICTED)
        mocker.patch("things.todos", return_value=None)
        mocker.patch("things.tasks", return_value=None)
        assert await server.get_tag_usage() == "secret: 0 open, 0 total\nwork: 0 open, 0 total"

    async def test_unrestricted_is_unchanged(self, fake_things, monkeypatch):
        monkeypatch.setattr(server.mcp, "auth", None)
        monkeypatch.setattr(server, "PROCESS_SCOPE", UNRESTRICTED)
        assert uuids(await server.get_todos()) == {t["uuid"] for t in TODOS}


class TestScopedWrites:
    async def test_add_todo_needs_a_destination(self, scoped):
        with pytest.raises(ScopeError):
            await server.add_todo(title="New")
        scoped.assert_not_called()

    async def test_add_todo_resolves_title_to_scoped_id(self, scoped):
        await server.add_todo(title="New", list_title="Launch")
        url = scoped.call_args[0][0]
        assert "list-id=P_WORK" in url
        assert "list=" not in url

    async def test_add_todo_into_out_of_scope_project_is_rejected(self, scoped):
        with pytest.raises(ScopeError):
            await server.add_todo(title="New", list_id="P_HOME")
        with pytest.raises(ScopeError):
            await server.add_todo(title="New", list_id="P_WORK", heading_id="H_HOME")
        scoped.assert_not_called()

    async def test_add_project_needs_a_scoped_area(self, scoped):
        with pytest.raises(ScopeError):
            await server.add_project(title="New", area_id="A_HOME")
        await server.add_project(title="New", area_title="Work")
        assert "area-id=A_WORK" in scoped.call_args[0][0]

    async def test_update_out_of_scope_todo_is_rejected(self, scoped):
        with pytest.raises(ScopeError):
            await server.update_todo(id="T_HOME", completed=True)
        scoped.assert_not_called()

    async def test_moving_a_todo_out_of_scope_is_rejected(self, scoped):
        with pytest.raises(ScopeError):
            await server.update_todo(id="T_PROJECT", list="Garden")
        with pytest.raises(ScopeError):
            await server.update_todo(id="T_PROJECT", list_id="A_HOME")
        scoped.assert_not_called()

    async def test_update_in_scope_todo_works(self, scoped):
        await server.update_todo(id="T_HEADING", completed=True)
        assert "id=T_HEADING" in scoped.call_args[0][0]

    async def test_bulk_update_rejects_the_whole_batch(self, scoped):
        with pytest.raises(ScopeError):
            await server.bulk_update_todos(ids=["T_PROJECT", "T_HOME"], completed=True)
        scoped.assert_not_called()

    async def test_update_out_of_scope_project_is_rejected(self, scoped):
        with pytest.raises(ScopeError):
            await server.update_project(id="P_HOME", completed=True)
        scoped.assert_not_called()

    async def test_update_out_of_scope_area_is_rejected(self, scoped, mocker):
        update_area = mocker.patch("things_mcp.server.url_scheme.update_area")
        with pytest.raises(ScopeError):
            await server.update_area(id="A_HOME", title="Renamed")
        update_area.assert_not_called()

    @pytest.mark.parametrize("call", [
        lambda: server.add_area(title="New"),
        lambda: server.search_items(query="x"),
        lambda: server.show_item(id="today"),
        lambda: server.show_item(id="T_HOME"),
    ])
    async def test_unboundable_actions_are_rejected(self, scoped, mocker, call):
        add_area = mocker.patch("things_mcp.server.url_scheme.add_area")
        with pytest.raises(ScopeError):
            await call()
        scoped.assert_not_called()
        add_area.assert_not_called()


class TestScopedHttp:
    """A token's scope travels from the verifier to the tool over real HTTP."""

    @asynccontextmanager
    async def client(self, token, monkeypatch):
        scoped_token, admin_token = "s" * 64, "u" * 64
        verifier = server.BearerTokenVerifier([
            Credential("scoped", token_digest(scoped_token), SCOPE),
            Credential("admin", token_digest(admin_token), UNRESTRICTED),
        ])
        monkeypatch.setattr(server.mcp, "auth", verifier)
        app = server.mcp.http_app()

        def factory(headers=None, timeout=None, auth=None, **kwargs):
            return httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test",
                headers=headers, timeout=timeout, auth=auth,
            )

        tokens = {"scoped": scoped_token, "admin": admin_token}
        transport = StreamableHttpTransport(
            "http://test/mcp", headers={"Authorization": f"Bearer {tokens[token]}"},
            httpx_client_factory=factory,
        )
        async with app.router.lifespan_context(app):
            async with Client(transport) as client:
                yield client

    async def test_scoped_token_sees_only_its_scope(self, fake_things, monkeypatch):
        async with self.client("scoped", monkeypatch) as client:
            result = await client.call_tool("get_todos", {})
            assert uuids(result) == IN_SCOPE_TODOS

            denied = await client.call_tool(
                "update_todo", {"id": "T_HOME", "completed": True}, raise_on_error=False,
            )
            assert denied.is_error
            fake_things.assert_not_called()

    async def test_unrestricted_token_sees_everything(self, fake_things, monkeypatch):
        async with self.client("admin", monkeypatch) as client:
            result = await client.call_tool("get_todos", {})
            assert uuids(result) == {t["uuid"] for t in TODOS}
