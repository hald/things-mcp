from datetime import datetime, timedelta
import pytest
from things_mcp.server import (
    get_todos, get_today, search_todos, search_advanced,
    get_logbook, _parse_logbook_period,
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


# --- get_logbook (#46): filter by stop_date, not creation date ----------------

def _completed(uuid, title, stop_date):
    return {
        'uuid': uuid,
        'title': title,
        'type': 'to-do',
        'status': 'completed',
        'stop_date': stop_date,
    }


def test_parse_logbook_period_accepts_dwmy():
    assert _parse_logbook_period('7d') == timedelta(days=7)
    assert _parse_logbook_period('2w') == timedelta(days=14)
    assert _parse_logbook_period('3m') == timedelta(days=90)
    assert _parse_logbook_period('1y') == timedelta(days=365)


def test_parse_logbook_period_rejects_garbage():
    assert _parse_logbook_period('') is None
    assert _parse_logbook_period('week') is None
    assert _parse_logbook_period('7') is None
    assert _parse_logbook_period('-3d') is None


@pytest.mark.asyncio
async def test_get_logbook_includes_tasks_completed_in_window_even_if_created_earlier(mocker):
    """Regression for #46: tasks created long ago but completed recently must appear."""
    today = datetime.now().date().isoformat()
    long_ago_completed_recently = _completed('a', 'Old task done today', today)
    mocker.patch('things.tasks', return_value=[long_ago_completed_recently])

    result = await get_logbook.fn(period='7d')

    assert 'Old task done today' in result


@pytest.mark.asyncio
async def test_get_logbook_excludes_tasks_completed_before_window(mocker):
    long_ago = (datetime.now() - timedelta(days=60)).date().isoformat()
    today = datetime.now().date().isoformat()
    mocker.patch('things.tasks', return_value=[
        _completed('a', 'Within window', today),
        _completed('b', 'Outside window', long_ago),
    ])

    result = await get_logbook.fn(period='7d')

    assert 'Within window' in result
    assert 'Outside window' not in result


@pytest.mark.asyncio
async def test_get_logbook_sorts_newest_completion_first(mocker):
    today = datetime.now().date().isoformat()
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    two_days_ago = (datetime.now() - timedelta(days=2)).date().isoformat()
    mocker.patch('things.tasks', return_value=[
        _completed('a', 'Two days ago', two_days_ago),
        _completed('b', 'Today', today),
        _completed('c', 'Yesterday', yesterday),
    ])

    result = await get_logbook.fn(period='7d')

    assert result.index('Today') < result.index('Yesterday') < result.index('Two days ago')


@pytest.mark.asyncio
async def test_get_logbook_respects_limit(mocker):
    today = datetime.now().date().isoformat()
    mocker.patch('things.tasks', return_value=[
        _completed(f'u{i}', f'Task {i}', today) for i in range(10)
    ])

    result = await get_logbook.fn(period='7d', limit=3)

    assert sum(1 for line in result.split('\n') if line.startswith('Title:')) == 3


@pytest.mark.asyncio
async def test_get_logbook_invalid_period(mocker):
    mocker.patch('things.tasks', return_value=[])

    result = await get_logbook.fn(period='lol')

    assert 'Invalid period' in result
