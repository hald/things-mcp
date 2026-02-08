"""Tests for filtering tasks from Someday projects."""

import pytest
from unittest.mock import patch

from things_mcp.server import filter_someday_project_tasks


class TestSomedayFiltering:
    """Test suite for filtering tasks from Someday projects."""

    @patch('things_mcp.server.things.projects')
    def test_filter_removes_someday_project_tasks(self, mock_projects):
        """Test that tasks from Someday projects are filtered out."""
        mock_projects.return_value = [
            {'uuid': 'project-123', 'title': 'Someday Project', 'status': 'someday'}
        ]

        todos = [
            {
                'uuid': 'task-1',
                'title': 'Task in Someday project',
                'project': 'project-123',
                'status': 'incomplete'
            }
        ]

        result = filter_someday_project_tasks(todos)

        assert len(result) == 0
        mock_projects.assert_called_once_with(start='Someday')

    @patch('things_mcp.server.things.projects')
    def test_filter_keeps_active_project_tasks(self, mock_projects):
        """Test that tasks from active projects are kept."""
        # No someday projects
        mock_projects.return_value = []

        todos = [
            {
                'uuid': 'task-2',
                'title': 'Task in active project',
                'project': 'project-456',
                'status': 'incomplete'
            }
        ]

        result = filter_someday_project_tasks(todos)

        assert len(result) == 1
        assert result[0]['uuid'] == 'task-2'

    @patch('things_mcp.server.things.projects')
    def test_filter_keeps_tasks_without_project(self, mock_projects):
        """Test that tasks without a project are kept."""
        mock_projects.return_value = [
            {'uuid': 'someday-proj'}
        ]

        todos = [
            {
                'uuid': 'task-3',
                'title': 'Standalone task',
                'status': 'incomplete'
            }
        ]

        result = filter_someday_project_tasks(todos)

        assert len(result) == 1
        assert result[0]['uuid'] == 'task-3'

    @patch('things_mcp.server.things.projects')
    def test_filter_mixed_tasks(self, mock_projects):
        """Test filtering with a mix of task types."""
        mock_projects.return_value = [
            {'uuid': 'someday-proj'}
        ]

        todos = [
            {'uuid': 'task-1', 'title': 'Someday task', 'project': 'someday-proj'},
            {'uuid': 'task-2', 'title': 'Active task', 'project': 'active-proj'},
            {'uuid': 'task-3', 'title': 'No project task'},
            {'uuid': 'task-4', 'title': 'Another someday', 'project': 'someday-proj'},
        ]

        result = filter_someday_project_tasks(todos)

        assert len(result) == 2
        assert result[0]['uuid'] == 'task-2'
        assert result[1]['uuid'] == 'task-3'

    @patch('things_mcp.server.things.projects')
    def test_filter_handles_exception(self, mock_projects):
        """Test that exceptions during project lookup don't crash the filter."""
        mock_projects.side_effect = Exception("Database error")

        todos = [
            {
                'uuid': 'task-error',
                'title': 'Task that causes error',
                'project': 'error-project'
            }
        ]

        result = filter_someday_project_tasks(todos)

        # Should return all todos when query fails
        assert len(result) == 1
        assert result[0]['uuid'] == 'task-error'

    @patch('things_mcp.server.things.projects')
    def test_filter_empty_list(self, mock_projects):
        """Test filtering an empty list."""
        mock_projects.return_value = []
        result = filter_someday_project_tasks([])
        assert result == []

    @patch('things_mcp.server.things.projects')
    def test_filter_preserves_task_data(self, mock_projects):
        """Test that filtering preserves all task fields."""
        mock_projects.return_value = []

        todos = [
            {
                'uuid': 'task-full',
                'title': 'Full task',
                'project': 'active-proj',
                'notes': 'Some notes',
                'tags': ['tag1', 'tag2'],
                'deadline': '2025-12-31',
                'status': 'incomplete'
            }
        ]

        result = filter_someday_project_tasks(todos)

        assert len(result) == 1
        # Verify all fields are preserved
        assert result[0]['uuid'] == 'task-full'
        assert result[0]['title'] == 'Full task'
        assert result[0]['notes'] == 'Some notes'
        assert result[0]['tags'] == ['tag1', 'tag2']
        assert result[0]['deadline'] == '2025-12-31'

    @patch('things_mcp.server.things.tasks')
    @patch('things_mcp.server.things.projects')
    def test_filter_removes_heading_tasks_in_someday_project(self, mock_projects, mock_tasks):
        """Test that tasks under a heading in a Someday project are filtered out."""
        mock_projects.return_value = [
            {'uuid': 'someday-proj'}
        ]
        mock_tasks.return_value = [
            {'uuid': 'heading-1', 'project': 'someday-proj'}
        ]

        todos = [
            {'uuid': 'task-1', 'title': 'Direct project task', 'project': 'someday-proj'},
            {'uuid': 'task-2', 'title': 'Heading task', 'heading': 'heading-1'},
            {'uuid': 'task-3', 'title': 'Unrelated task'},
        ]

        result = filter_someday_project_tasks(todos)

        assert len(result) == 1
        assert result[0]['uuid'] == 'task-3'
