import pytest
from things_mcp.server import (
    get_todos, get_today, search_todos, search_advanced, get_tag_usage,
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
