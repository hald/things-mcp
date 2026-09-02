import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_todo():
    """Sample todo data for testing."""
    return {
        'uuid': 'test-todo-uuid',
        'title': 'Test Todo',
        'type': 'to-do',
        'status': 'open',
        'notes': 'Test notes',
        'start': 'Inbox',
        'start_date': '2024-01-15',
        'deadline': '2024-01-20',
        'tags': ['work', 'urgent'],
        'checklist': [
            {'title': 'First item', 'status': 'completed'},
            {'title': 'Second item', 'status': 'open'}
        ],
        'project': 'project-uuid',
        'area': 'area-uuid',
        'heading': 'heading-uuid'
    }

@pytest.fixture
def mock_completed_todo():
    """Sample completed todo data for testing."""
    return {
        'uuid': 'completed-todo-uuid',
        'title': 'Completed Todo',
        'type': 'to-do',
        'status': 'completed',
        'stop_date': '2024-01-18',
        'tags': ['done']
    }

@pytest.fixture
def mock_project():
    """Sample project data for testing."""
    return {
        'uuid': 'test-project-uuid',
        'title': 'Test Project',
        'type': 'project',
        'notes': 'Project description',
        'area': 'area-uuid',
        'tags': ['important']
    }

@pytest.fixture
def mock_area():
    """Sample area data for testing."""
    return {
        'uuid': 'test-area-uuid',
        'title': 'Test Area',
        'type': 'area',
        'notes': 'Area description'
    }

@pytest.fixture
def mock_tag():
    """Sample tag data for testing."""
    return {
        'uuid': 'test-tag-uuid',
        'title': 'work',
        'type': 'tag',
        'shortcut': 'cmd+1'
    }

@pytest.fixture
def mock_things_token():
    """Mock the things.token() function."""
    with patch('things.token') as mock:
        mock.return_value = 'test-auth-token'
        yield mock

@pytest.fixture
def mock_things_get():
    """Mock the things.get() function."""
    with patch('things.get') as mock:
        def side_effect(uuid):
            if uuid == 'project-uuid':
                return {'title': 'Mock Project', 'uuid': 'project-uuid'}
            elif uuid == 'area-uuid':
                return {'title': 'Mock Area', 'uuid': 'area-uuid'}
            return None
        mock.side_effect = side_effect
        yield mock

@pytest.fixture
def mock_things_todos():
    """Mock the things.todos() function."""
    with patch('things.todos') as mock:
        mock.return_value = [
            {'title': 'Task 1', 'uuid': 'task-1'},
            {'title': 'Task 2', 'uuid': 'task-2'}
        ]
        yield mock

@pytest.fixture
def mock_things_projects():
    """Mock the things.projects() function."""
    with patch('things.projects') as mock:
        mock.return_value = [
            {'title': 'Project 1', 'uuid': 'project-1'},
            {'title': 'Project 2', 'uuid': 'project-2'}
        ]
        yield mock

@pytest.fixture(autouse=True)
def no_real_recurrence_templates():
    """Keep tests off the developer's real Things database.

    ``get_today`` / ``get_upcoming`` / ``search_todos`` project occurrences of
    repeating to-dos by reading the Things SQLite file directly (things.py
    filters template rows out, so there is no API to mock). Without this, a
    server-level test would pick up whatever repeats happen to exist on the
    machine running the suite.

    Tests that exercise the projection supply their own templates explicitly
    (see tests/test_recurring_visibility.py) or override this fixture.
    """
    with patch('things_mcp.recurrence.fetch_templates', return_value=[]):
        yield
