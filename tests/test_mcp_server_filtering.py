"""Integration tests for MCP server functions with Someday filtering."""

import pytest
from unittest.mock import patch

import things_mcp.server as things_server
from tests.conftest import tool_text


class TestMCPServerFiltering:
    """Test that MCP server functions properly filter Someday project tasks."""

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.anytime')
    @patch('things_mcp.server.things.projects')
    async def test_get_anytime_filters_someday_tasks(self, mock_projects, mock_anytime):
        """Test that get_anytime filters out tasks from Someday projects."""
        mock_anytime.return_value = [
            {'uuid': 'task-1', 'title': 'Someday task', 'project': 'someday-proj', 'type': 'to-do'},
            {'uuid': 'task-2', 'title': 'Active task', 'project': 'active-proj', 'type': 'to-do'},
            {'uuid': 'task-3', 'title': 'No project', 'type': 'to-do'},
        ]

        mock_projects.return_value = [
            {'uuid': 'someday-proj', 'title': 'Someday Project'}
        ]

        result = await things_server.get_anytime.fn()
        text = tool_text(result)

        # Should only include task-2 and task-3
        assert 'task-1' not in text
        assert 'Active task' in text
        assert 'No project' in text
        assert result.structured_content["json"]["count"] == 2

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.today')
    @patch('things_mcp.server.things.projects')
    async def test_get_today_filters_someday_tasks(self, mock_projects, mock_today):
        """Test that get_today filters out tasks from Someday projects."""
        mock_today.return_value = [
            {'uuid': 'task-4', 'title': 'Today someday task', 'project': 'someday-proj', 'type': 'to-do'},
            {'uuid': 'task-5', 'title': 'Today active task', 'type': 'to-do'},
        ]

        mock_projects.return_value = [
            {'uuid': 'someday-proj'}
        ]

        result = await things_server.get_today.fn()
        text = tool_text(result)

        # Should only include task-5
        assert 'Today someday task' not in text
        assert 'Today active task' in text
        assert result.structured_content["json"]["count"] == 1

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.upcoming')
    @patch('things_mcp.server.things.projects')
    async def test_get_upcoming_filters_someday_tasks(self, mock_projects, mock_upcoming):
        """Test that get_upcoming filters out tasks from Someday projects."""
        mock_upcoming.return_value = [
            {'uuid': 'task-6', 'title': 'Upcoming someday', 'project': 'someday-proj', 'type': 'to-do'},
            {'uuid': 'task-7', 'title': 'Upcoming active', 'project': 'active-proj', 'type': 'to-do'},
        ]

        mock_projects.return_value = [
            {'uuid': 'someday-proj'}
        ]

        result = await things_server.get_upcoming.fn()
        text = tool_text(result)

        # Should only include task-7
        assert 'Upcoming someday' not in text
        assert 'Upcoming active' in text
        assert result.structured_content["json"]["count"] == 1

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.anytime')
    async def test_get_anytime_handles_empty_list(self, mock_anytime):
        """Test that get_anytime handles empty results gracefully."""
        mock_anytime.return_value = []

        result = await things_server.get_anytime.fn()

        assert tool_text(result) == "No items found"
        assert result.structured_content["json"]["count"] == 0

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.anytime')
    @patch('things_mcp.server.things.projects')
    async def test_get_anytime_all_filtered_returns_empty(self, mock_projects, mock_anytime):
        """Test that get_anytime returns 'No items found' when all tasks are filtered."""
        mock_anytime.return_value = [
            {'uuid': 'task-1', 'title': 'Someday 1', 'project': 'someday-proj', 'type': 'to-do'},
            {'uuid': 'task-2', 'title': 'Someday 2', 'project': 'someday-proj', 'type': 'to-do'},
        ]

        mock_projects.return_value = [
            {'uuid': 'someday-proj'}
        ]

        result = await things_server.get_anytime.fn()

        assert tool_text(result) == "No items found"
        assert result.structured_content["json"]["count"] == 0

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.anytime')
    @patch('things_mcp.server.things.someday')
    @patch('things_mcp.server.things.projects')
    async def test_get_someday_includes_tasks_from_someday_projects(self, mock_projects, mock_someday, mock_anytime):
        """Test that get_someday includes tasks from Someday projects even if their start is Anytime."""
        mock_someday.return_value = [
            {'uuid': 'task-1', 'title': 'Explicitly someday', 'type': 'to-do'},
        ]

        mock_anytime.return_value = [
            {'uuid': 'task-2', 'title': 'In someday project', 'project': 'someday-proj', 'type': 'to-do'},
            {'uuid': 'task-3', 'title': 'In active project', 'project': 'active-proj', 'type': 'to-do'},
        ]

        mock_projects.return_value = [
            {'uuid': 'someday-proj'}
        ]

        result = await things_server.get_someday.fn()
        text = tool_text(result)

        assert 'Explicitly someday' in text
        assert 'In someday project' in text
        assert 'In active project' not in text
        assert result.structured_content["json"]["count"] == 2

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.anytime')
    @patch('things_mcp.server.things.someday')
    @patch('things_mcp.server.things.projects')
    async def test_get_someday_no_duplicates(self, mock_projects, mock_someday, mock_anytime):
        """Test that get_someday doesn't duplicate tasks already in the someday list."""
        mock_someday.return_value = [
            {'uuid': 'task-1', 'title': 'Already someday', 'project': 'someday-proj', 'type': 'to-do'},
        ]

        mock_anytime.return_value = [
            {'uuid': 'task-1', 'title': 'Already someday', 'project': 'someday-proj', 'type': 'to-do'},
            {'uuid': 'task-2', 'title': 'Another someday proj task', 'project': 'someday-proj', 'type': 'to-do'},
        ]

        mock_projects.return_value = [
            {'uuid': 'someday-proj'}
        ]

        result = await things_server.get_someday.fn()
        text = tool_text(result)

        # task-1 should appear only once
        assert text.count('Already someday') == 1
        assert 'Another someday proj task' in text
        assert result.structured_content["json"]["count"] == 2
