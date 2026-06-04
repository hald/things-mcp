import pytest
from things_mcp.server import get_todos, get_today, search_todos, search_advanced, _today_fallback


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
async def test_get_today_recovers_from_things_py_sort_typeerror(mocker, mock_todo):
    """Regression for #43: when things.today() crashes on the upstream
    None-vs-str sort, get_today should fall back to a local safe aggregation."""
    mocker.patch(
        'things.today',
        side_effect=TypeError("'<' not supported between instances of 'NoneType' and 'str'"),
    )
    mock_tasks = mocker.patch('things.tasks')
    # First call (regular_today_tasks) has a dated task; second (unconfirmed_scheduled)
    # is empty; third (unconfirmed_overdue) yields a deadline-only task with start_date=None.
    overdue = {
        'uuid': 'overdue-uuid',
        'title': 'Overdue with no start_date',
        'type': 'to-do',
        'status': 'open',
        'today_index': 0,
        'start_date': None,
        'deadline': '2026-06-04',
    }
    mock_tasks.side_effect = [[mock_todo], [], [overdue]]

    result = await get_today.fn()

    assert "Test Todo" in result
    assert "Overdue with no start_date" in result


def test_today_fallback_sort_handles_none_start_date(mocker):
    """The fallback must not raise TypeError when start_date is None."""
    dated = {'uuid': 'a', 'title': 'A', 'today_index': 1, 'start_date': '2026-06-04'}
    undated = {'uuid': 'b', 'title': 'B', 'today_index': 0, 'start_date': None}
    mock_tasks = mocker.patch('things.tasks')
    mock_tasks.side_effect = [[dated], [], [undated]]

    result = _today_fallback()

    # Undated row sorts after the dated one because we push None to the end.
    assert [r['uuid'] for r in result] == ['b', 'a']


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
