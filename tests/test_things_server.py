import json
import urllib.parse
import pytest
from things_mcp.server import (
    get_todos, get_today, search_todos, search_advanced, bulk_update_todos,
)


@pytest.mark.asyncio
async def test_get_todos_includes_checklist(mocker, mock_todo):
    mock_things_todos = mocker.patch('things.todos')
    mock_things_todos.return_value = [mock_todo]

    result = await get_todos.fn(include_items=True)

    assert "Checklist:" in result
    assert "First item" in result
    mock_things_todos.assert_called_once_with(project=None, start=None, include_items=True)


@pytest.mark.asyncio
async def test_get_today_includes_checklist(mocker, mock_todo):
    mock_today = mocker.patch('things.today')
    mock_today.return_value = [mock_todo]

    result = await get_today.fn()

    assert "Checklist:" in result
    assert "First item" in result
    mock_today.assert_called_once_with(include_items=True)


@pytest.mark.asyncio
async def test_search_todos_includes_checklist(mocker, mock_todo):
    mock_search = mocker.patch('things.search')
    mock_search.return_value = [mock_todo]

    result = await search_todos.fn("Test")

    assert "Checklist:" in result
    assert "First item" in result
    mock_search.assert_called_once_with("Test", include_items=True)


@pytest.mark.asyncio
async def test_search_advanced_with_type_project(mocker, mock_project):
    """Test search_advanced with type='project' uses things.tasks()."""
    mock_things_tasks = mocker.patch('things.tasks')
    mock_things_tasks.return_value = [mock_project]

    result = await search_advanced.fn(type="project")

    # Should call things.tasks() with type parameter, not things.todos()
    mock_things_tasks.assert_called_once_with(
        type="project", include_items=True
    )
    assert "Test Project" in result


@pytest.mark.asyncio
async def test_search_advanced_without_type(mocker, mock_todo):
    """Test search_advanced without type still uses things.todos()."""
    mock_things_todos = mocker.patch('things.todos')
    mock_things_todos.return_value = [mock_todo]

    result = await search_advanced.fn(status="incomplete")

    # Should call things.todos() when no type specified
    mock_things_todos.assert_called_once_with(
        include_items=True, status="incomplete"
    )
    assert "Test Todo" in result


# --- bulk_update_todos (#22) --------------------------------------------------

def _captured_json_payload(mock_execute_url):
    """Pull the json payload out of the URL handed to execute_url."""
    url = mock_execute_url.call_args[0][0]
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    return json.loads(qs['data'][0])


@pytest.mark.asyncio
async def test_bulk_update_todos_empty_ids(mocker):
    mocker.patch('things_mcp.server.url_scheme.execute_url')
    result = await bulk_update_todos.fn(ids=[], list="Shopping")
    assert "No items to update" in result


@pytest.mark.asyncio
async def test_bulk_update_todos_no_changes(mocker):
    mocker.patch('things.token', return_value='tok')
    mocker.patch('things_mcp.server.url_scheme.execute_url')
    result = await bulk_update_todos.fn(ids=["u1"])
    assert "No changes specified" in result


@pytest.mark.asyncio
async def test_bulk_update_todos_missing_token(mocker):
    mocker.patch('things.token', return_value=None)
    mocker.patch('things_mcp.server.url_scheme.execute_url')
    result = await bulk_update_todos.fn(ids=["u1"], list="Shopping")
    assert "THINGS_AUTH_TOKEN" in result


@pytest.mark.asyncio
async def test_bulk_update_todos_moves_many_in_one_call(mocker):
    mocker.patch('things.token', return_value='tok')
    mock_exec = mocker.patch('things_mcp.server.url_scheme.execute_url')

    result = await bulk_update_todos.fn(
        ids=["u1", "u2", "u3"], list_id="shopping-uuid"
    )

    # Exactly one URL invocation, not N
    assert mock_exec.call_count == 1
    assert "3 todos" in result
    payload = _captured_json_payload(mock_exec)
    assert len(payload) == 3
    assert all(p["operation"] == "update" for p in payload)
    assert [p["id"] for p in payload] == ["u1", "u2", "u3"]
    assert all(p["attributes"] == {"list-id": "shopping-uuid"} for p in payload)


@pytest.mark.asyncio
async def test_bulk_update_todos_list_id_overrides_list_title(mocker):
    mocker.patch('things.token', return_value='tok')
    mock_exec = mocker.patch('things_mcp.server.url_scheme.execute_url')

    await bulk_update_todos.fn(ids=["u1"], list="By Title", list_id="by-uuid")

    payload = _captured_json_payload(mock_exec)
    assert payload[0]["attributes"] == {"list-id": "by-uuid"}
    assert "list" not in payload[0]["attributes"]


@pytest.mark.asyncio
async def test_bulk_update_todos_complete_and_tag(mocker):
    mocker.patch('things.token', return_value='tok')
    mock_exec = mocker.patch('things_mcp.server.url_scheme.execute_url')

    await bulk_update_todos.fn(
        ids=["u1", "u2"], completed=True, add_tags=["reviewed"]
    )

    payload = _captured_json_payload(mock_exec)
    for p in payload:
        assert p["attributes"]["completed"] is True
        assert p["attributes"]["add-tags"] == ["reviewed"]
