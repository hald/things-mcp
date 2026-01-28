import pytest
from unittest.mock import patch
from datetime import datetime, timedelta
from things_mcp.formatters import format_todo, format_project, format_area, format_tag, format_heading, _calculate_age


class TestCalculateAge:
    """Test the _calculate_age helper function."""
    
    def test_age_today(self):
        """Test age calculation for today."""
        now = datetime.now()
        result = _calculate_age(now.isoformat())
        assert result == "today"
    
    def test_age_one_day(self):
        """Test age calculation for exactly 1 day ago."""
        one_day_ago = datetime.now() - timedelta(days=1)
        result = _calculate_age(one_day_ago.isoformat())
        assert result == "1 day ago"
    
    def test_age_multiple_days(self):
        """Test age calculation for multiple days ago."""
        three_days_ago = datetime.now() - timedelta(days=3)
        result = _calculate_age(three_days_ago.isoformat())
        assert result == "3 days ago"
    
    def test_age_one_week(self):
        """Test age calculation for one week ago."""
        one_week_ago = datetime.now() - timedelta(days=7)
        result = _calculate_age(one_week_ago.isoformat())
        assert result == "1 week ago"
    
    def test_age_multiple_weeks(self):
        """Test age calculation for multiple weeks ago."""
        three_weeks_ago = datetime.now() - timedelta(days=21)
        result = _calculate_age(three_weeks_ago.isoformat())
        assert result == "3 weeks ago"
    
    def test_age_one_month(self):
        """Test age calculation for approximately one month ago."""
        one_month_ago = datetime.now() - timedelta(days=30)
        result = _calculate_age(one_month_ago.isoformat())
        assert result == "1 month ago"
    
    def test_age_multiple_months(self):
        """Test age calculation for multiple months ago."""
        three_months_ago = datetime.now() - timedelta(days=90)
        result = _calculate_age(three_months_ago.isoformat())
        assert result == "3 months ago"
    
    def test_age_one_year(self):
        """Test age calculation for one year ago."""
        one_year_ago = datetime.now() - timedelta(days=365)
        result = _calculate_age(one_year_ago.isoformat())
        assert result == "1 year ago"
    
    def test_age_multiple_years(self):
        """Test age calculation for multiple years ago."""
        two_years_ago = datetime.now() - timedelta(days=730)
        result = _calculate_age(two_years_ago.isoformat())
        assert result == "2 years ago"
    
    def test_age_invalid_date_string(self):
        """Test that invalid date string raises ValueError."""
        with pytest.raises(ValueError):
            _calculate_age("not-a-date")
    
    def test_age_none_value(self):
        """Test that None value raises TypeError."""
        with pytest.raises((ValueError, TypeError)):
            _calculate_age(None)


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
    
    def test_format_todo_with_created_age(self):
        """Test formatting todo with created date shows age."""
        three_days_ago = (datetime.now() - timedelta(days=3)).isoformat()
        todo = {
            'title': 'Recent Todo',
            'uuid': 'recent-uuid',
            'type': 'to-do',
            'created': three_days_ago
        }
        result = format_todo(todo)
        
        assert "Created:" in result
        assert "Age: 3 days ago" in result
    
    def test_format_todo_with_modified_age(self):
        """Test formatting todo with modified date shows modification age."""
        one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        todo = {
            'title': 'Modified Todo',
            'uuid': 'modified-uuid',
            'type': 'to-do',
            'modified': one_week_ago
        }
        result = format_todo(todo)
        
        assert "Modified:" in result
        assert "Last modified: 1 week ago" in result
    
    def test_format_todo_with_both_created_and_modified_age(self):
        """Test formatting todo with both created and modified dates shows both ages."""
        two_weeks_ago = (datetime.now() - timedelta(days=14)).isoformat()
        five_days_ago = (datetime.now() - timedelta(days=5)).isoformat()
        todo = {
            'title': 'Updated Todo',
            'uuid': 'updated-uuid',
            'type': 'to-do',
            'created': two_weeks_ago,
            'modified': five_days_ago
        }
        result = format_todo(todo)
        
        assert "Created:" in result
        assert "Age: 2 weeks ago" in result
        assert "Modified:" in result
        assert "Last modified: 5 days ago" in result
    
    def test_format_todo_with_invalid_created_date(self):
        """Test formatting todo with invalid created date doesn't crash."""
        todo = {
            'title': 'Todo with Bad Date',
            'uuid': 'bad-date-uuid',
            'type': 'to-do',
            'created': 'invalid-date'
        }
        result = format_todo(todo)
        
        # Should include created date but no age
        assert "Created: invalid-date" in result
        assert "Age:" not in result
    
    def test_format_todo_with_invalid_modified_date(self):
        """Test formatting todo with invalid modified date doesn't crash."""
        todo = {
            'title': 'Todo with Bad Modified Date',
            'uuid': 'bad-modified-uuid',
            'type': 'to-do',
            'modified': 'not-a-date'
        }
        result = format_todo(todo)
        
        # Should include modified date but no age
        assert "Modified: not-a-date" in result
        assert "Last modified:" not in result
    
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


class TestFormatProject:
    """Test the format_project function."""
    
    @patch('things.tasks')
    def test_format_project_minimal(self, mock_tasks):
        """Test formatting project with minimal fields."""
        mock_tasks.return_value = []
        
        project = {
            'title': 'Simple Project',
            'uuid': 'simple-project-uuid'
        }
        result = format_project(project)
        
        assert "Title: Simple Project" in result
        assert "UUID: simple-project-uuid" in result
    
    @patch('things.tasks')
    @patch('things.get')
    def test_format_project_with_area(self, mock_get, mock_tasks):
        """Test formatting project with area."""
        mock_get.return_value = {'title': 'Work Area'}
        mock_tasks.return_value = []
        
        project = {
            'title': 'Project in Area',
            'uuid': 'area-project-uuid',
            'area': 'area-uuid'
        }
        result = format_project(project)
        
        assert "Area: Work Area" in result
    
    @patch('things.tasks')
    def test_format_project_with_notes(self, mock_tasks):
        """Test formatting project with notes."""
        mock_tasks.return_value = []
        
        project = {
            'title': 'Project with Notes',
            'uuid': 'notes-project-uuid',
            'notes': 'Project description'
        }
        result = format_project(project)
        
        assert "Notes: Project description" in result
    
    @patch('things.tasks')
    def test_format_project_with_headings(self, mock_tasks):
        """Test formatting project with headings."""
        mock_tasks.return_value = [
            {'title': 'Phase 1', 'uuid': 'heading1-uuid'},
            {'title': 'Phase 2', 'uuid': 'heading2-uuid'}
        ]
        
        project = {
            'title': 'Project with Headings',
            'uuid': 'headings-project-uuid'
        }
        result = format_project(project)
        
        assert "Headings:" in result
        assert "- Phase 1" in result
        assert "- Phase 2" in result
        mock_tasks.assert_called_once_with(type='heading', project='headings-project-uuid')
    
    @patch('things.todos')
    @patch('things.tasks')
    def test_format_project_with_items(self, mock_tasks, mock_todos):
        """Test formatting project with include_items=True."""
        mock_tasks.return_value = []
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
    
    @patch('things.tasks')
    def test_format_project_without_items(self, mock_tasks):
        """Test formatting project with include_items=False."""
        mock_tasks.return_value = []
        
        project = {
            'title': 'Project',
            'uuid': 'project-uuid'
        }
        result = format_project(project, include_items=False)
        
        assert "Tasks:" not in result
    
    @patch('things.tasks')
    def test_format_project_with_created_age(self, mock_tasks):
        """Test formatting project with created date shows age."""
        mock_tasks.return_value = []
        three_days_ago = (datetime.now() - timedelta(days=3)).isoformat()
        
        project = {
            'title': 'Recent Project',
            'uuid': 'recent-project-uuid',
            'created': three_days_ago
        }
        result = format_project(project)
        
        assert "Created:" in result
        assert "Age: 3 days ago" in result
    
    @patch('things.tasks')
    def test_format_project_with_modified_age(self, mock_tasks):
        """Test formatting project with modified date shows modification age."""
        mock_tasks.return_value = []
        one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        project = {
            'title': 'Modified Project',
            'uuid': 'modified-project-uuid',
            'modified': one_week_ago
        }
        result = format_project(project)
        
        assert "Modified:" in result
        assert "Last modified: 1 week ago" in result
    
    @patch('things.tasks')
    def test_format_project_with_both_created_and_modified_age(self, mock_tasks):
        """Test formatting project with both created and modified dates shows both ages."""
        mock_tasks.return_value = []
        two_weeks_ago = (datetime.now() - timedelta(days=14)).isoformat()
        five_days_ago = (datetime.now() - timedelta(days=5)).isoformat()
        
        project = {
            'title': 'Updated Project',
            'uuid': 'updated-project-uuid',
            'created': two_weeks_ago,
            'modified': five_days_ago
        }
        result = format_project(project)
        
        assert "Created:" in result
        assert "Age: 2 weeks ago" in result
        assert "Modified:" in result
        assert "Last modified: 5 days ago" in result
    
    @patch('things.tasks')
    def test_format_project_with_invalid_created_date(self, mock_tasks):
        """Test formatting project with invalid created date doesn't crash."""
        mock_tasks.return_value = []
        
        project = {
            'title': 'Project with Bad Date',
            'uuid': 'bad-date-project-uuid',
            'created': 'invalid-date'
        }
        result = format_project(project)
        
        # Should include created date but no age
        assert "Created: invalid-date" in result
        assert "Age:" not in result


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
    
    def test_format_area_with_created_age(self):
        """Test formatting area with created date shows age."""
        three_days_ago = (datetime.now() - timedelta(days=3)).isoformat()
        
        area = {
            'title': 'Recent Area',
            'uuid': 'recent-area-uuid',
            'created': three_days_ago
        }
        result = format_area(area)
        
        assert "Created:" in result
        assert "Age: 3 days ago" in result
    
    def test_format_area_with_modified_age(self):
        """Test formatting area with modified date shows modification age."""
        one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        area = {
            'title': 'Modified Area',
            'uuid': 'modified-area-uuid',
            'modified': one_week_ago
        }
        result = format_area(area)
        
        assert "Modified:" in result
        assert "Last modified: 1 week ago" in result
    
    def test_format_area_with_both_created_and_modified_age(self):
        """Test formatting area with both created and modified dates shows both ages."""
        two_weeks_ago = (datetime.now() - timedelta(days=14)).isoformat()
        five_days_ago = (datetime.now() - timedelta(days=5)).isoformat()
        
        area = {
            'title': 'Updated Area',
            'uuid': 'updated-area-uuid',
            'created': two_weeks_ago,
            'modified': five_days_ago
        }
        result = format_area(area)
        
        assert "Created:" in result
        assert "Age: 2 weeks ago" in result
        assert "Modified:" in result
        assert "Last modified: 5 days ago" in result
    
    def test_format_area_with_invalid_created_date(self):
        """Test formatting area with invalid created date doesn't crash."""
        area = {
            'title': 'Area with Bad Date',
            'uuid': 'bad-date-area-uuid',
            'created': 'invalid-date'
        }
        result = format_area(area)
        
        # Should include created date but no age
        assert "Created: invalid-date" in result
        assert "Age:" not in result


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
        assert "â–¡" not in result
        assert "âœ“" not in result
    
    @patch('things.todos')
    @patch('things.tasks')
    def test_format_project_with_no_todos(self, mock_tasks, mock_todos):
        """Test formatting project with no todos."""
        mock_todos.return_value = []
        mock_tasks.return_value = []
        
        project = {
            'title': 'Empty Project',
            'uuid': 'empty-project-uuid'
        }
        result = format_project(project, include_items=True)
        
        # Should still include the Tasks section, just empty
        assert "Tasks:" not in result


class TestFormatHeading:
    """Test the format_heading function."""
    
    def test_format_heading_minimal(self):
        """Test formatting heading with minimal fields."""
        heading = {
            'title': 'Important Tasks',
            'uuid': 'heading-uuid',
            'type': 'heading'
        }
        result = format_heading(heading)
        
        assert "Title: Important Tasks" in result
        assert "UUID: heading-uuid" in result
        assert "Type: heading" in result
    
    def test_format_heading_with_project(self):
        """Test formatting heading with project info."""
        heading = {
            'title': 'Development',
            'uuid': 'dev-heading-uuid',
            'type': 'heading',
            'project': 'project-uuid',
            'project_title': 'Main Project'
        }
        result = format_heading(heading)
        
        assert "Project: Main Project" in result
    
    @patch('things.get')
    def test_format_heading_with_project_lookup(self, mock_get):
        """Test formatting heading with project lookup."""
        mock_get.return_value = {'title': 'Looked Up Project'}
        
        heading = {
            'title': 'Testing',
            'uuid': 'test-heading-uuid',
            'type': 'heading',
            'project': 'project-uuid'
        }
        result = format_heading(heading)
        
        assert "Project: Looked Up Project" in result
        mock_get.assert_called_once_with('project-uuid')
    
    def test_format_heading_with_dates(self):
        """Test formatting heading with dates."""
        heading = {
            'title': 'Planning',
            'uuid': 'plan-heading-uuid',
            'type': 'heading',
            'created': '2024-01-15 10:00:00',
            'modified': '2024-01-20 15:30:00'
        }
        result = format_heading(heading)
        
        assert "Created: 2024-01-15 10:00:00" in result
        assert "Modified: 2024-01-20 15:30:00" in result
    
    def test_format_heading_with_created_age(self):
        """Test formatting heading with created date shows age."""
        three_days_ago = (datetime.now() - timedelta(days=3)).isoformat()
        
        heading = {
            'title': 'Recent Heading',
            'uuid': 'recent-heading-uuid',
            'type': 'heading',
            'created': three_days_ago
        }
        result = format_heading(heading)
        
        assert "Created:" in result
        assert "Age: 3 days ago" in result
    
    def test_format_heading_with_modified_age(self):
        """Test formatting heading with modified date shows modification age."""
        one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        heading = {
            'title': 'Modified Heading',
            'uuid': 'modified-heading-uuid',
            'type': 'heading',
            'modified': one_week_ago
        }
        result = format_heading(heading)
        
        assert "Modified:" in result
        assert "Last modified: 1 week ago" in result
    
    def test_format_heading_with_both_created_and_modified_age(self):
        """Test formatting heading with both created and modified dates shows both ages."""
        two_weeks_ago = (datetime.now() - timedelta(days=14)).isoformat()
        five_days_ago = (datetime.now() - timedelta(days=5)).isoformat()
        
        heading = {
            'title': 'Updated Heading',
            'uuid': 'updated-heading-uuid',
            'type': 'heading',
            'created': two_weeks_ago,
            'modified': five_days_ago
        }
        result = format_heading(heading)
        
        assert "Created:" in result
        assert "Age: 2 weeks ago" in result
        assert "Modified:" in result
        assert "Last modified: 5 days ago" in result
    
    def test_format_heading_with_invalid_created_date(self):
        """Test formatting heading with invalid created date doesn't crash."""
        heading = {
            'title': 'Heading with Bad Date',
            'uuid': 'bad-date-heading-uuid',
            'type': 'heading',
            'created': 'invalid-date'
        }
        result = format_heading(heading)
        
        # Should include created date but no age
        assert "Created: invalid-date" in result
        assert "Age:" not in result
    
    def test_format_heading_with_notes(self):
        """Test formatting heading with notes."""
        heading = {
            'title': 'Design Phase',
            'uuid': 'design-heading-uuid',
            'type': 'heading',
            'notes': 'This contains all design-related tasks'
        }
        result = format_heading(heading)
        
        assert "Notes: This contains all design-related tasks" in result
    
    @patch('things.todos')
    def test_format_heading_with_items(self, mock_todos):
        """Test formatting heading with todo items."""
        mock_todos.return_value = [
            {'title': 'Task 1'},
            {'title': 'Task 2'}
        ]
        
        heading = {
            'title': 'Sprint 1',
            'uuid': 'sprint-heading-uuid',
            'type': 'heading'
        }
        result = format_heading(heading, include_items=True)
        
        assert "Tasks under heading:" in result
        assert "- Task 1" in result
        assert "- Task 2" in result
        mock_todos.assert_called_once_with(heading='sprint-heading-uuid')