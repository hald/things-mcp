import pytest
from tests.conftest import tool_text
from things_mcp.server import get_todos, get_today, search_todos, search_advanced


@pytest.mark.asyncio
async def test_get_todos_includes_checklist(mocker, mock_todo):
    mock_things_todos = mocker.patch('things.todos')
    mock_things_todos.return_value = [mock_todo]

    result = await get_todos.fn(include_items=True)
    text = tool_text(result)

    assert "Checklist:" in text
    assert "First item" in text
    assert result.structured_content["json"]["count"] == 1
    assert result.structured_content["json"]["items"][0]["title"] == "Test Todo"
    mock_things_todos.assert_called_once_with(project=None, start=None, include_items=True)


@pytest.mark.asyncio
async def test_get_today_includes_checklist(mocker, mock_todo):
    mock_today = mocker.patch('things.today')
    mock_today.return_value = [mock_todo]

    result = await get_today.fn()
    text = tool_text(result)

    assert "Checklist:" in text
    assert "First item" in text
    assert result.structured_content["json"]["items"][0]["checklist"][0]["title"] == "First item"
    mock_today.assert_called_once_with(include_items=True)


@pytest.mark.asyncio
async def test_search_todos_includes_checklist(mocker, mock_todo):
    mock_search = mocker.patch('things.search')
    mock_search.return_value = [mock_todo]

    result = await search_todos.fn("Test")
    text = tool_text(result)

    assert "Checklist:" in text
    assert "First item" in text
    assert result.structured_content["json"]["items"][0]["title"] == "Test Todo"
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
    assert result.structured_content["json"]["items"][0]["title"] == "Test Project"
    assert "Test Project" in tool_text(result)


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
    assert result.structured_content["json"]["items"][0]["title"] == "Test Todo"
    assert "Test Todo" in tool_text(result)
