import pytest
from things_mcp.server import get_logbook, get_today, get_todos, search_todos, search_advanced


@pytest.mark.asyncio
async def test_get_todos_includes_checklist(mocker, mock_todo, mock_things_get):
    mock_things_todos = mocker.patch('things.todos')
    mock_things_todos.return_value = [mock_todo]

    result = await get_todos.fn(include_items=True)

    assert "Showing " not in result
    assert "Checklist:" in result
    assert "First item" in result
    mock_things_todos.assert_called_once_with(project=None, start=None, include_items=True)


@pytest.mark.asyncio
async def test_get_todos_applies_limit_and_offset(mocker):
    mock_things_todos = mocker.patch('things.todos')
    mock_things_todos.return_value = [
        {'uuid': 'task-1', 'title': 'First Task', 'type': 'to-do'},
        {'uuid': 'task-2', 'title': 'Second Task', 'type': 'to-do'},
        {'uuid': 'task-3', 'title': 'Third Task', 'type': 'to-do'},
    ]

    result = await get_todos.fn(limit=1, offset=1)

    assert "Showing 2-2 of 3 items" in result
    assert "Second Task" in result
    assert "First Task" not in result
    assert "Third Task" not in result
    mock_things_todos.assert_called_once_with(project=None, start=None, include_items=True)


@pytest.mark.asyncio
async def test_get_todos_rejects_non_positive_limit(mocker):
    mock_things_todos = mocker.patch('things.todos')

    result = await get_todos.fn(limit=0)

    assert result == "Error: limit must be a positive integer"
    mock_things_todos.assert_not_called()


@pytest.mark.asyncio
async def test_get_today_includes_checklist(mocker, mock_todo, mock_things_get):
    mock_today = mocker.patch('things.today')
    mock_projects = mocker.patch('things_mcp.server.things.projects')
    mock_today.return_value = [mock_todo]
    mock_projects.return_value = []

    result = await get_today.fn()

    assert "Checklist:" in result
    assert "First item" in result
    mock_today.assert_called_once_with(include_items=True)


@pytest.mark.asyncio
async def test_get_today_paginates_after_someday_filtering(mocker):
    mock_today = mocker.patch('things.today')
    mock_projects = mocker.patch('things_mcp.server.things.projects')
    mock_tasks = mocker.patch('things_mcp.server.things.tasks')

    mock_today.return_value = [
        {'uuid': 'task-1', 'title': 'Someday Task', 'type': 'to-do', 'project': 'someday-proj'},
        {'uuid': 'task-2', 'title': 'Active Task A', 'type': 'to-do'},
        {'uuid': 'task-3', 'title': 'Active Task B', 'type': 'to-do'},
    ]
    mock_projects.return_value = [{'uuid': 'someday-proj'}]
    mock_tasks.return_value = []

    result = await get_today.fn(limit=1, offset=1)

    assert "Showing 2-2 of 2 items" in result
    assert "Active Task B" in result
    assert "Someday Task" not in result
    assert "Active Task A" not in result


@pytest.mark.asyncio
async def test_search_todos_includes_checklist(mocker, mock_todo, mock_things_get):
    mock_search = mocker.patch('things.search')
    mock_search.return_value = [mock_todo]

    result = await search_todos.fn("Test")

    assert "Checklist:" in result
    assert "First item" in result
    mock_search.assert_called_once_with("Test", include_items=True)


@pytest.mark.asyncio
async def test_search_advanced_paginates_without_passing_pagination_to_things(mocker):
    """Test search_advanced paginates locally after querying Things."""
    mock_things_todos = mocker.patch('things.todos')
    mock_things_todos.return_value = [
        {'uuid': 'task-1', 'title': 'First Match', 'type': 'to-do'},
        {'uuid': 'task-2', 'title': 'Second Match', 'type': 'to-do'},
    ]

    result = await search_advanced.fn(status="incomplete", limit=1, offset=1)

    mock_things_todos.assert_called_once_with(
        include_items=True, status="incomplete"
    )
    assert "Showing 2-2 of 2 items" in result
    assert "Second Match" in result
    assert "First Match" not in result


@pytest.mark.asyncio
async def test_search_advanced_with_type_project(mocker, mock_project, mock_things_get):
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
async def test_search_advanced_without_type(mocker, mock_todo, mock_things_get):
    """Test search_advanced without type still uses things.todos()."""
    mock_things_todos = mocker.patch('things.todos')
    mock_things_todos.return_value = [mock_todo]

    result = await search_advanced.fn(status="incomplete")

    # Should call things.todos() when no type specified
    mock_things_todos.assert_called_once_with(
        include_items=True, status="incomplete"
    )
    assert "Test Todo" in result


@pytest.mark.asyncio
async def test_get_logbook_supports_offset(mocker):
    mock_last = mocker.patch('things.last')
    mock_last.return_value = [
        {'uuid': 'task-1', 'title': 'Completed A', 'type': 'to-do'},
        {'uuid': 'task-2', 'title': 'Completed B', 'type': 'to-do'},
        {'uuid': 'task-3', 'title': 'Completed C', 'type': 'to-do'},
    ]

    result = await get_logbook.fn(limit=1, offset=1)

    mock_last.assert_called_once_with("7d", status='completed', include_items=True)
    assert "Showing 2-2 of 3 items" in result
    assert "Completed B" in result
    assert "Completed A" not in result
    assert "Completed C" not in result
