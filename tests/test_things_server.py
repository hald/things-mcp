import pytest
from unittest.mock import patch
import things_server


@patch('things_server.time.sleep', return_value=None)
@patch('things_server.things.tasks')
@patch('things_server.url_scheme.execute_url')
@patch('things_server.url_scheme.add_heading', return_value='dummy-url')
@pytest.mark.asyncio
async def test_add_heading_retry_success(mock_add_heading, mock_execute, mock_tasks, mock_sleep):
    heading_obj = {'uuid': 'heading-uuid', 'title': 'New Heading', 'index': 1}
    mock_tasks.side_effect = [[], [], [heading_obj]]
    result = await things_server.add_heading.fn(project_id='project-123', title='New Heading')
    assert "with ID: heading-uuid" in result
    assert mock_tasks.call_count == 3


@patch('things_server.time.sleep', return_value=None)
@patch('things_server.things.tasks', return_value=[])
@patch('things_server.url_scheme.execute_url')
@patch('things_server.url_scheme.add_heading', return_value='dummy-url')
@pytest.mark.asyncio
async def test_add_heading_retry_timeout(mock_add_heading, mock_execute, mock_tasks, mock_sleep):
    result = await things_server.add_heading.fn(project_id='project-123', title='New Heading')
    assert "could not verify its ID" in result
    assert mock_tasks.call_count == 20
