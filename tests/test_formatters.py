import pytest
from unittest.mock import patch
from formatters import format_todo, format_project, format_area, format_tag


class TestFormatTodo:
    """Test the format_todo function."""
    
    def test_format_todo_minimal(self):
        """Test formatting todo with minimal fields."""
        todo = {
            'title': 'Simple Todo',
            'uuid': 'simple-uuid',
            'type': 'to-do'
        }
        result = format_todo(todo)
        
        assert "Title: Simple Todo" in result
        assert "UUID: simple-uuid" in result
        assert "Type: to-do" in result
    
    def test_format_todo_with_status(self):
        """Test formatting todo with status."""
        todo = {
            'title': 'Todo with Status',
            'uuid': 'status-uuid',
            'type': 'to-do',
            'status': 'completed'
        }
        result = format_todo(todo)
        
        assert "Status: completed" in result
    
    def test_format_todo_with_dates(self):
        """Test formatting todo with various dates."""
        todo = {
            'title': 'Todo with Dates',
            'uuid': 'dates-uuid',
            'type': 'to-do',
            'start_date': '2024-01-15',
            'deadline': '2024-01-20',
            'stop_date': '2024-01-18'
        }
        result = format_todo(todo)
        
        assert "Start Date: 2024-01-15" in result
        assert "Deadline: 2024-01-20" in result
        assert "Completed: 2024-01-18" in result
    
    def test_format_todo_with_notes(self):
        """Test formatting todo with notes."""
        todo = {
            'title': 'Todo with Notes',
            'uuid': 'notes-uuid',
            'type': 'to-do',
            'notes': 'Important details here'
        }
        result = format_todo(todo)
        
        assert "Notes: Important details here" in result
    
    @patch('things.get')
    def test_format_todo_with_project(self, mock_get):
        """Test formatting todo with project reference."""
        mock_get.return_value = {'title': 'Test Project'}
        
        todo = {
            'title': 'Todo in Project',
            'uuid': 'project-todo-uuid',
            'type': 'to-do',
            'project': 'project-uuid'
        }
        result = format_todo(todo)
        
        assert "Project: Test Project" in result
        mock_get.assert_called_once_with('project-uuid')
    
    @patch('things.get')
    def test_format_todo_with_area(self, mock_get):
        """Test formatting todo with area reference."""
        mock_get.return_value = {'title': 'Work Area'}
        
        todo = {
            'title': 'Todo in Area',
            'uuid': 'area-todo-uuid',
            'type': 'to-do',
            'area': 'area-uuid'
        }
        result = format_todo(todo)
        
        assert "Area: Work Area" in result
        mock_get.assert_called_once_with('area-uuid')

    @patch('things.get')
    def test_format_todo_with_heading(self, mock_get):
        """Test formatting todo with heading reference."""
        mock_get.return_value = {'title': 'Feature Heading'}

        todo = {
            'title': 'Todo in Heading',
            'uuid': 'heading-todo-uuid',
            'type': 'to-do',
            'heading': 'heading-uuid'
        }
        result = format_todo(todo)

        assert "Heading: Feature Heading" in result
        mock_get.assert_called_once_with('heading-uuid')
    
    def test_format_todo_with_tags(self):
        """Test formatting todo with tags."""
        todo = {
            'title': 'Tagged Todo',
            'uuid': 'tagged-uuid',
            'type': 'to-do',
            'tags': ['urgent', 'work', 'important']
        }
        result = format_todo(todo)
        
        assert "Tags: urgent, work, important" in result
    
    def test_format_todo_with_checklist(self):
        """Test formatting todo with checklist items."""
        todo = {
            'title': 'Todo with Checklist',
            'uuid': 'checklist-uuid',
            'type': 'to-do',
            'checklist': [
                {'title': 'First item', 'status': 'completed'},
                {'title': 'Second item', 'status': 'open'},
                {'title': 'Third item', 'status': 'completed'}
            ]
        }
        result = format_todo(todo)
        
        assert "Checklist:" in result
        assert "  ✓ First item" in result
        assert "  □ Second item" in result
        assert "  ✓ Third item" in result
    
    def test_format_todo_with_start_location(self):
        """Test formatting todo with start/list location."""
        todo = {
            'title': 'Todo in List',
            'uuid': 'list-todo-uuid',
            'type': 'to-do',
            'start': 'Today'
        }
        result = format_todo(todo)
        
        assert "List: Today" in result
    
    @patch('things.get')
    def test_format_todo_complete(self, mock_get, mock_todo):
        """Test formatting todo with all fields using fixture."""
        mock_get.side_effect = lambda uuid: {
            'project-uuid': {'title': 'Mock Project'},
            'area-uuid': {'title': 'Mock Area'},
            'heading-uuid': {'title': 'Mock Heading'}
        }.get(uuid)
        
        result = format_todo(mock_todo)
        
        assert "Title: Test Todo" in result
        assert "UUID: test-todo-uuid" in result
        assert "Type: to-do" in result
        assert "Status: open" in result
        assert "List: Inbox" in result
        assert "Start Date: 2024-01-15" in result
        assert "Deadline: 2024-01-20" in result
        assert "Notes: Test notes" in result
        assert "Project: Mock Project" in result
        assert "Area: Mock Area" in result
        assert "Heading: Mock Heading" in result
        assert "Tags: work, urgent" in result
        assert "✓ First item" in result
        assert "□ Second item" in result


class TestFormatProject:
    """Test the format_project function."""
    
    def test_format_project_minimal(self):
        """Test formatting project with minimal fields."""
        project = {
            'title': 'Simple Project',
            'uuid': 'simple-project-uuid'
        }
        result = format_project(project)
        
        assert "Title: Simple Project" in result
        assert "UUID: simple-project-uuid" in result
    
    @patch('things.get')
    def test_format_project_with_area(self, mock_get):
        """Test formatting project with area."""
        mock_get.return_value = {'title': 'Work Area'}
        
        project = {
            'title': 'Project in Area',
            'uuid': 'area-project-uuid',
            'area': 'area-uuid'
        }
        result = format_project(project)
        
        assert "Area: Work Area" in result
    
    def test_format_project_with_notes(self):
        """Test formatting project with notes."""
        project = {
            'title': 'Project with Notes',
            'uuid': 'notes-project-uuid',
            'notes': 'Project description'
        }
        result = format_project(project)
        
        assert "Notes: Project description" in result
    
    @patch('things.todos')
    def test_format_project_with_items(self, mock_todos):
        """Test formatting project with include_items=True."""
        mock_todos.return_value = [
            {'title': 'Task 1'},
            {'title': 'Task 2'},
            {'title': 'Task 3'}
        ]
        
        project = {
            'title': 'Project with Tasks',
            'uuid': 'tasks-project-uuid'
        }
        result = format_project(project, include_items=True)
        
        assert "Tasks:" in result
        assert "- Task 1" in result
        assert "- Task 2" in result
        assert "- Task 3" in result
        mock_todos.assert_called_once_with(project='tasks-project-uuid')
    
    def test_format_project_without_items(self):
        """Test formatting project with include_items=False."""
        project = {
            'title': 'Project',
            'uuid': 'project-uuid'
        }
        result = format_project(project, include_items=False)
        
        assert "Tasks:" not in result


class TestFormatArea:
    """Test the format_area function."""
    
    def test_format_area_minimal(self):
        """Test formatting area with minimal fields."""
        area = {
            'title': 'Simple Area',
            'uuid': 'simple-area-uuid'
        }
        result = format_area(area)
        
        assert "Title: Simple Area" in result
        assert "UUID: simple-area-uuid" in result
    
    def test_format_area_with_notes(self):
        """Test formatting area with notes."""
        area = {
            'title': 'Area with Notes',
            'uuid': 'notes-area-uuid',
            'notes': 'Area description'
        }
        result = format_area(area)
        
        assert "Notes: Area description" in result
    
    @patch('things.projects')
    @patch('things.todos')
    def test_format_area_with_items(self, mock_todos, mock_projects):
        """Test formatting area with include_items=True."""
        mock_projects.return_value = [
            {'title': 'Project A'},
            {'title': 'Project B'}
        ]
        mock_todos.return_value = [
            {'title': 'Todo 1'},
            {'title': 'Todo 2'}
        ]
        
        area = {
            'title': 'Area with Items',
            'uuid': 'items-area-uuid'
        }
        result = format_area(area, include_items=True)
        
        assert "Projects:" in result
        assert "- Project A" in result
        assert "- Project B" in result
        assert "Tasks:" in result
        assert "- Todo 1" in result
        assert "- Todo 2" in result
        
        mock_projects.assert_called_once_with(area='items-area-uuid')
        mock_todos.assert_called_once_with(area='items-area-uuid')
    
    def test_format_area_without_items(self):
        """Test formatting area with include_items=False."""
        area = {
            'title': 'Area',
            'uuid': 'area-uuid'
        }
        result = format_area(area, include_items=False)
        
        assert "Projects:" not in result
        assert "Tasks:" not in result


class TestFormatTag:
    """Test the format_tag function."""
    
    def test_format_tag_minimal(self):
        """Test formatting tag with minimal fields."""
        tag = {
            'title': 'work',
            'uuid': 'work-tag-uuid'
        }
        result = format_tag(tag)
        
        assert "Title: work" in result
        assert "UUID: work-tag-uuid" in result
    
    def test_format_tag_with_shortcut(self):
        """Test formatting tag with shortcut."""
        tag = {
            'title': 'urgent',
            'uuid': 'urgent-tag-uuid',
            'shortcut': 'cmd+u'
        }
        result = format_tag(tag)
        
        assert "Shortcut: cmd+u" in result
    
    @patch('things.todos')
    def test_format_tag_with_items(self, mock_todos):
        """Test formatting tag with include_items=True."""
        mock_todos.return_value = [
            {'title': 'Tagged Todo 1'},
            {'title': 'Tagged Todo 2'},
            {'title': 'Tagged Todo 3'}
        ]
        
        tag = {
            'title': 'important',
            'uuid': 'important-tag-uuid'
        }
        result = format_tag(tag, include_items=True)
        
        assert "Tagged Items:" in result
        assert "- Tagged Todo 1" in result
        assert "- Tagged Todo 2" in result
        assert "- Tagged Todo 3" in result
        
        mock_todos.assert_called_once_with(tag='important')
    
    def test_format_tag_without_items(self):
        """Test formatting tag with include_items=False."""
        tag = {
            'title': 'tag',
            'uuid': 'tag-uuid'
        }
        result = format_tag(tag, include_items=False)
        
        assert "Tagged Items:" not in result


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @patch('things.get')
    def test_format_todo_with_missing_project(self, mock_get):
        """Test formatting todo when project lookup fails."""
        mock_get.side_effect = Exception("Database error")
        
        todo = {
            'title': 'Todo',
            'uuid': 'todo-uuid',
            'type': 'to-do',
            'project': 'missing-project'
        }
        result = format_todo(todo)
        
        # Should not crash, project info just won't be included
        assert "Title: Todo" in result
        assert "Project:" not in result
    
    def test_format_todo_with_empty_checklist(self):
        """Test formatting todo with empty checklist."""
        todo = {
            'title': 'Todo',
            'uuid': 'todo-uuid',
            'type': 'to-do',
            'checklist': []
        }
        result = format_todo(todo)
        
        # Checklist header appears but no items
        assert "Checklist:" in result
        # No checklist items should be present
        assert "□" not in result
        assert "✓" not in result
    
    @patch('things.todos')
    def test_format_project_with_no_todos(self, mock_todos):
        """Test formatting project with no todos."""
        mock_todos.return_value = []
        
        project = {
            'title': 'Empty Project',
            'uuid': 'empty-project-uuid'
        }
        result = format_project(project, include_items=True)
        
        # Should still include the Tasks section, just empty
        assert "Tasks:" not in result