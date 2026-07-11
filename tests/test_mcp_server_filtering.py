"""Integration tests for MCP server functions with Someday filtering."""

import pytest
from tests._helpers import tool_text
from unittest.mock import patch

import things_mcp.server as things_server


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

        result = tool_text(await things_server.get_anytime())

        # Should only include task-2 and task-3
        assert 'task-1' not in result
        assert 'Active task' in result
        assert 'No project' in result

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

        result = tool_text(await things_server.get_today())

        # Should only include task-5
        assert 'Today someday task' not in result
        assert 'Today active task' in result

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

        result = tool_text(await things_server.get_upcoming())

        # Should only include task-7
        assert 'Upcoming someday' not in result
        assert 'Upcoming active' in result

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.anytime')
    async def test_get_anytime_handles_empty_list(self, mock_anytime):
        """Test that get_anytime handles empty results gracefully."""
        mock_anytime.return_value = []

        result = tool_text(await things_server.get_anytime())

        assert result == "No items found"

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

        result = tool_text(await things_server.get_anytime())

        assert result == "No items found"

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

        result = tool_text(await things_server.get_someday())

        assert 'Explicitly someday' in result
        assert 'In someday project' in result
        assert 'In active project' not in result

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

        result = tool_text(await things_server.get_someday())

        # task-1 should appear only once
        assert result.count('Already someday') == 1
        assert 'Another someday proj task' in result


class TestTodayAnytimeDedupe:
    """Test that get_today/get_anytime drop top-level duplicates of nested project children."""

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.today')
    @patch('things_mcp.server.things.projects')
    async def test_get_today_drops_top_level_project_children(self, mock_projects, mock_today):
        """Children of a project in the result appear once, nested in the project's items."""
        child_1 = {'uuid': 'child-1', 'title': 'First child', 'project': 'proj-1', 'type': 'to-do'}
        child_2 = {'uuid': 'child-2', 'title': 'Second child', 'project': 'proj-1', 'type': 'to-do'}
        project = {'uuid': 'proj-1', 'title': 'Started project', 'type': 'project',
                   'items': [child_1, child_2]}
        standalone_1 = {'uuid': 'solo-1', 'title': 'Standalone one', 'type': 'to-do'}
        standalone_2 = {'uuid': 'solo-2', 'title': 'Standalone two', 'type': 'to-do'}
        mock_today.return_value = [project, child_1, child_2, standalone_1, standalone_2]
        mock_projects.return_value = []

        result = await things_server.get_today()

        sc = result.structured_content
        assert [item['uuid'] for item in sc['items']] == ['proj-1', 'solo-1', 'solo-2']
        assert sc['count'] == 3
        assert sc['total'] == 3
        # Children stay nested in the project entry, exactly once
        assert [item['uuid'] for item in sc['items'][0]['items']] == ['child-1', 'child-2']
        text = tool_text(result)
        assert text.count('Title:') == 3
        assert 'Standalone one' in text
        assert 'Standalone two' in text
        assert 'First child' not in text

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.anytime')
    @patch('things_mcp.server.things.projects')
    async def test_get_anytime_drops_top_level_project_children(self, mock_projects, mock_anytime):
        """Children of a project in the result appear once, nested in the project's items."""
        child_1 = {'uuid': 'child-1', 'title': 'First child', 'project': 'proj-1', 'type': 'to-do'}
        child_2 = {'uuid': 'child-2', 'title': 'Second child', 'project': 'proj-1', 'type': 'to-do'}
        project = {'uuid': 'proj-1', 'title': 'Started project', 'type': 'project',
                   'items': [child_1, child_2]}
        standalone = {'uuid': 'solo-1', 'title': 'Standalone todo', 'type': 'to-do'}
        mock_anytime.return_value = [project, child_1, child_2, standalone]
        mock_projects.return_value = []

        result = await things_server.get_anytime()

        sc = result.structured_content
        assert [item['uuid'] for item in sc['items']] == ['proj-1', 'solo-1']
        assert sc['count'] == 2
        assert sc['total'] == 2
        assert [item['uuid'] for item in sc['items'][0]['items']] == ['child-1', 'child-2']
        text = tool_text(result)
        assert text.count('Title:') == 2
        assert 'Standalone todo' in text
        assert 'First child' not in text

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.tasks')
    @patch('things_mcp.server.things.today')
    @patch('things_mcp.server.things.projects')
    async def test_get_today_drops_top_level_heading_children(self, mock_projects, mock_today, mock_tasks):
        """Tasks under a heading resolve to the heading's project and are deduplicated."""
        heading_child = {'uuid': 'hchild-1', 'title': 'Heading child', 'heading': 'heading-1', 'type': 'to-do'}
        heading = {'uuid': 'heading-1', 'title': 'Phase 1', 'type': 'heading', 'items': [heading_child]}
        project = {'uuid': 'proj-1', 'title': 'Started project', 'type': 'project', 'items': [heading]}
        standalone = {'uuid': 'solo-1', 'title': 'Standalone todo', 'type': 'to-do'}
        mock_today.return_value = [project, heading_child, standalone]
        mock_projects.return_value = []
        mock_tasks.return_value = [{'uuid': 'heading-1', 'project': 'proj-1'}]

        result = await things_server.get_today()

        sc = result.structured_content
        assert [item['uuid'] for item in sc['items']] == ['proj-1', 'solo-1']
        assert sc['count'] == 2
        assert sc['total'] == 2
        mock_tasks.assert_called_once_with(type='heading', project='proj-1')

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.anytime')
    @patch('things_mcp.server.things.projects')
    async def test_get_anytime_keeps_children_of_projects_not_in_result(self, mock_projects, mock_anytime):
        """A task whose parent project is not in the result stays top-level."""
        mock_anytime.return_value = [
            {'uuid': 'proj-1', 'title': 'Visible project', 'type': 'project', 'items': []},
            {'uuid': 'task-1', 'title': 'Child of absent project', 'project': 'other-proj', 'type': 'to-do'},
        ]
        mock_projects.return_value = []

        result = await things_server.get_anytime()

        sc = result.structured_content
        assert [item['uuid'] for item in sc['items']] == ['proj-1', 'task-1']
        assert sc['count'] == 2
        assert sc['total'] == 2

    @pytest.mark.asyncio
    @patch('things_mcp.server.things.today')
    @patch('things_mcp.server.things.projects')
    async def test_get_today_paginates_deduplicated_list(self, mock_projects, mock_today):
        """limit/offset and the Showing header operate on the deduplicated list."""
        child = {'uuid': 'child-1', 'title': 'Only child', 'project': 'proj-1', 'type': 'to-do'}
        project = {'uuid': 'proj-1', 'title': 'Started project', 'type': 'project', 'items': [child]}
        standalone_1 = {'uuid': 'solo-1', 'title': 'Standalone one', 'type': 'to-do'}
        standalone_2 = {'uuid': 'solo-2', 'title': 'Standalone two', 'type': 'to-do'}
        mock_today.return_value = [project, child, standalone_1, standalone_2]
        mock_projects.return_value = []

        result = await things_server.get_today(limit=2)

        text = tool_text(result)
        assert 'Showing 1-2 of 3 items' in text
        sc = result.structured_content
        assert sc['total'] == 3
        assert sc['count'] == 2
        assert [item['uuid'] for item in sc['items']] == ['proj-1', 'solo-1']
