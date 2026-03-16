import pytest
from tests.conftest import tool_text
from things_mcp.server import get_headings


@pytest.mark.asyncio
async def test_get_headings_all(mocker):
    """Test getting all headings."""
    mock_tasks = mocker.patch('things.tasks')
    mock_tasks.return_value = [
        {
            'uuid': 'heading1-uuid',
            'type': 'heading',
            'title': 'Phase 1',
            'project': 'project-uuid',
            'project_title': 'Main Project'
        },
        {
            'uuid': 'heading2-uuid', 
            'type': 'heading',
            'title': 'Phase 2',
            'project': 'project-uuid',
            'project_title': 'Main Project'
        }
    ]
    
    result = await get_headings.fn()
    text = tool_text(result)
    
    assert "Phase 1" in text
    assert "Phase 2" in text
    assert "Main Project" in text
    assert result.structured_content["json"]["count"] == 2
    mock_tasks.assert_called_once_with(type='heading')


@pytest.mark.asyncio  
async def test_get_headings_by_project(mocker):
    """Test getting headings for a specific project."""
    mock_get = mocker.patch('things.get')
    mock_get.return_value = {'type': 'project', 'title': 'Test Project'}
    
    mock_tasks = mocker.patch('things.tasks')
    mock_tasks.return_value = [
        {
            'uuid': 'heading1-uuid',
            'type': 'heading', 
            'title': 'Sprint 1',
            'project': 'project-uuid',
            'project_title': 'Test Project'
        }
    ]
    
    result = await get_headings.fn(project_uuid='project-uuid')
    text = tool_text(result)
    
    assert "Sprint 1" in text
    assert "Test Project" in text
    assert result.structured_content["json"]["items"][0]["project_title"] == "Test Project"
    mock_get.assert_called_once_with('project-uuid')
    mock_tasks.assert_called_once_with(type='heading', project='project-uuid')


@pytest.mark.asyncio
async def test_get_headings_invalid_project(mocker):
    """Test getting headings with invalid project UUID."""
    mock_get = mocker.patch('things.get')
    mock_get.return_value = {'type': 'to-do', 'title': 'Not a Project'}
    
    result = await get_headings.fn(project_uuid='invalid-uuid')
    
    assert "Error: Invalid project UUID" in tool_text(result)
    assert result.structured_content["json"]["success"] is False
    mock_get.assert_called_once_with('invalid-uuid')


@pytest.mark.asyncio
async def test_get_headings_no_headings(mocker):
    """Test when no headings are found."""
    mock_tasks = mocker.patch('things.tasks')
    mock_tasks.return_value = []
    
    result = await get_headings.fn()
    
    assert "No headings found" in tool_text(result)
    assert result.structured_content["json"]["count"] == 0
    mock_tasks.assert_called_once_with(type='heading')
