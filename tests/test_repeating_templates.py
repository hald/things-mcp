"""Tests for repeating to-do templates (things.py 1.1.0+)."""

import pytest
from tests._helpers import tool_text
from things_mcp.formatters import format_todo, format_repeating_template
from things_mcp.server import get_repeating_templates, get_upcoming, _next_instance_sort_key


@pytest.fixture
def mock_template():
    """A repeating to-do's template as things.py returns it: stored as Someday,
    no start_date, and the date Things will generate the next instance."""
    return {
        'uuid': 'template-uuid',
        'title': 'Water the plants',
        'type': 'to-do',
        'status': 'incomplete',
        'notes': 'Every Sunday',
        'start': 'Someday',
        'start_date': None,
        'next_instance_start_date': '2030-01-06',
        'deadline': None,
        'tags': ['Recurring'],
    }


@pytest.fixture
def mock_template_without_next(mock_template):
    """things.py omits next_instance_start_date when it is unset."""
    template = {k: v for k, v in mock_template.items() if k != 'next_instance_start_date'}
    template['uuid'] = 'paused-template-uuid'
    template['title'] = 'Paused chore'
    return template


def test_format_repeating_template_shows_next_instance(mocker, mock_template):
    mocker.patch('things.get', return_value=None)

    text = format_repeating_template(mock_template)

    assert "Repeating: next instance 2030-01-06" in text
    assert "List:" not in text
    assert "Start Date:" not in text
    assert "Tags: Recurring" in text


def test_format_repeating_template_without_next_instance(mocker, mock_template_without_next):
    mocker.patch('things.get', return_value=None)

    text = format_repeating_template(mock_template_without_next)

    assert "Repeating: no next instance scheduled" in text
    assert "List:" not in text


def test_format_todo_treats_next_instance_as_template(mocker, mock_template):
    """get_upcoming formats templates with format_todo; the key marks them."""
    mocker.patch('things.get', return_value=None)

    text = format_todo(mock_template)

    assert "Repeating: next instance 2030-01-06" in text
    assert "List: Someday" not in text


def test_format_todo_unchanged_for_ordinary_todo(mocker, mock_todo):
    mocker.patch('things.get', return_value=None)

    text = format_todo(mock_todo)

    assert "List: Inbox" in text
    assert "Repeating" not in text


def test_next_instance_sort_key_orders_dated_first():
    templates = [
        {'uuid': 'c', 'title': 'b', 'next_instance_start_date': '2030-02-01'},
        {'uuid': 'a', 'title': 'Zed'},
        {'uuid': 'b', 'title': 'a', 'next_instance_start_date': '2030-01-01'},
        {'uuid': 'd', 'title': 'Alpha'},
        {'uuid': 'e', 'title': 'beta'},
        {'uuid': 'f', 'title': None},
    ]

    ordered = sorted(templates, key=_next_instance_sort_key)

    # dated first by date; undated after, by title ignoring case, a missing title first
    assert [t['uuid'] for t in ordered] == ['b', 'c', 'f', 'd', 'e', 'a']


@pytest.mark.asyncio
async def test_get_repeating_templates_reads_through_things_py(mocker, mock_template, mock_template_without_next):
    mock_todos = mocker.patch('things.todos', return_value=[mock_template_without_next, mock_template])
    mocker.patch('things.get', return_value=None)

    result = await get_repeating_templates()

    mock_todos.assert_called_once_with(is_repeating_template=True, include_items=True)
    text = tool_text(result)
    assert text.index('Water the plants') < text.index('Paused chore')
    assert "Repeating: next instance 2030-01-06" in text
    assert "Repeating: no next instance scheduled" in text
    sc = result.structured_content
    assert sc['total'] == 2
    assert [item['uuid'] for item in sc['items']] == ['template-uuid', 'paused-template-uuid']
    # things.py omits the key when unset; the structured item passes that through
    assert sc['items'][0]['next_instance_start_date'] == '2030-01-06'
    assert 'next_instance_start_date' not in sc['items'][1]


@pytest.mark.asyncio
async def test_get_repeating_templates_empty(mocker):
    mocker.patch('things.todos', return_value=[])

    result = await get_repeating_templates()

    assert tool_text(result) == "No repeating todos found"


@pytest.mark.asyncio
async def test_get_repeating_templates_paginates(mocker, mock_template, mock_template_without_next):
    mocker.patch('things.todos', return_value=[mock_template, mock_template_without_next])
    mocker.patch('things.get', return_value=None)

    result = await get_repeating_templates(limit=1, offset=1)

    assert "Showing 2-2 of 2 items" in tool_text(result)
    assert result.structured_content['items'][0]['uuid'] == 'paused-template-uuid'


@pytest.mark.asyncio
async def test_get_repeating_templates_invalid_pagination(mocker):
    mock_todos = mocker.patch('things.todos')

    result = await get_repeating_templates(limit=0)

    assert "error" in result.structured_content
    mock_todos.assert_not_called()


@pytest.mark.asyncio
async def test_get_upcoming_formats_templates_from_things_py(mocker, mock_todo, mock_template):
    """things.upcoming() (1.1.0+) returns the next instance of repeating todos
    as their template; the text channel shows the next instance date."""
    mocker.patch('things.upcoming', return_value=[mock_todo, mock_template])
    mocker.patch('things.projects', return_value=[])
    mocker.patch('things.get', return_value=None)

    result = await get_upcoming()

    text = tool_text(result)
    assert "Start Date: 2024-01-15" in text
    assert "Repeating: next instance 2030-01-06" in text
    assert result.structured_content['total'] == 2
