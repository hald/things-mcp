from datetime import datetime, timedelta
import pytest
from things_mcp.server import (
    get_todos, get_today, search_todos, search_advanced,
    get_logbook, _parse_logbook_period, _today_fallback, get_tag_usage,
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


# --- get_tag_usage (#14) ------------------------------------------------------

def _set_tag_data(mocker, *, tags, open_counts, all_counts):
    """Wire up things.tags / things.todos / things.tasks for tag-usage tests.

    open_counts and all_counts are dicts keyed by tag title.
    """
    mocker.patch('things.tags', return_value=[{'title': t, 'uuid': f'u-{t}'} for t in tags])
    mocker.patch('things.todos', side_effect=lambda tag, **kw: [0] * open_counts.get(tag, 0))
    mocker.patch('things.tasks', side_effect=lambda tag, **kw: [0] * all_counts.get(tag, 0))


@pytest.mark.asyncio
async def test_get_tag_usage_sorts_by_total_desc(mocker):
    _set_tag_data(
        mocker,
        tags=['work', 'home', 'shopping'],
        open_counts={'work': 5, 'home': 2, 'shopping': 0},
        all_counts={'work': 30, 'home': 10, 'shopping': 0},
    )

    result = await get_tag_usage.fn()

    lines = result.split('\n')
    assert lines[0].startswith('work:')
    assert lines[1].startswith('home:')
    assert lines[2].startswith('shopping:')
    assert '5 open, 30 total' in lines[0]


@pytest.mark.asyncio
async def test_get_tag_usage_only_unused(mocker):
    _set_tag_data(
        mocker,
        tags=['work', 'old-tag-1', 'old-tag-2'],
        open_counts={'work': 5, 'old-tag-1': 0, 'old-tag-2': 0},
        all_counts={'work': 30, 'old-tag-1': 0, 'old-tag-2': 0},
    )

    result = await get_tag_usage.fn(only_unused=True)

    assert 'old-tag-1' in result
    assert 'old-tag-2' in result
    assert 'work' not in result


@pytest.mark.asyncio
async def test_get_tag_usage_empty(mocker):
    mocker.patch('things.tags', return_value=[])
    result = await get_tag_usage.fn()
    assert result == 'No tags found'
