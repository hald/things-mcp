"""Every tool advertises a title and behavior hints (MCP tool annotations)."""
import pytest

from things_mcp.server import mcp

READ_ONLY = {
    "get_inbox", "get_today", "get_upcoming", "get_anytime", "get_someday",
    "get_logbook", "get_trash", "get_todos", "get_projects", "get_areas",
    "get_tags", "get_tagged_items", "get_tag_usage", "get_headings",
    "search_todos", "search_advanced", "get_recent",
}
CREATES = {"add_todo", "add_project", "add_area"}
EDITS = {"update_todo", "bulk_update_todos", "update_project", "update_area"}
SHOWS = {"show_item", "search_items"}


@pytest.fixture(scope="module")
async def tools():
    return {t.name: t for t in await mcp.list_tools()}


async def test_every_tool_is_classified(tools):
    assert set(tools) == READ_ONLY | CREATES | EDITS | SHOWS


async def test_every_tool_has_a_title(tools):
    for name, tool in tools.items():
        assert tool.title, name
        assert tool.annotations.title == tool.title, name


async def test_hints(tools):
    for name, tool in tools.items():
        a = tool.annotations
        assert a.openWorldHint is False, name
        assert a.readOnlyHint is (name in READ_ONLY), name
        if name not in READ_ONLY:
            assert a.destructiveHint is (name in EDITS), name
