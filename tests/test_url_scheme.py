import json
import pytest
from unittest.mock import patch, Mock
import subprocess
import urllib.parse
from things_mcp.url_scheme import (
    execute_url, construct_url, add_todo, add_project, add_area, update_area,
    update_todo, update_project, show, search, format_when_with_reminder,
    json_command,
)


class TestExecuteUrl:
    """Test the execute_url function."""

    @patch('subprocess.run')
    def test_execute_url_success(self, mock_run):
        """Test successful URL execution via osascript with open -g."""
        mock_run.return_value = Mock(returncode=0)

        execute_url("things:///add?title=Test")

        mock_run.assert_called_once_with(
            ['osascript', '-e', 'do shell script "open -g \\"things:///add?title=Test\\""'],
            check=True, capture_output=True, text=True
        )

    @patch('subprocess.run')
    def test_execute_url_fallback(self, mock_run):
        """Test fallback to open -g directly when osascript fails."""
        # First call (osascript) fails, second call (open -g) succeeds
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, 'osascript'),
            Mock(returncode=0)
        ]

        execute_url("things:///add?title=Test")

        assert mock_run.call_count == 2
        mock_run.assert_called_with(['open', '-g', 'things:///add?title=Test'], check=True)


class TestAddArea:
    """Test the add_area function (AppleScript-based since URL scheme has no add-area)."""

    @patch('subprocess.run')
    def test_add_area_basic(self, mock_run):
        """Test basic Area creation returns the new UUID."""
        mock_run.return_value = Mock(stdout="ABC123XYZ\n", returncode=0)

        uuid = add_area("Backlog")

        assert uuid == "ABC123XYZ"
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0][0] == 'osascript'
        assert args[0][1] == '-e'
        assert 'tell application "Things3"' in args[0][2]
        assert 'name:"Backlog"' in args[0][2]
        assert kwargs.get('check') is True
        assert kwargs.get('capture_output') is True
        assert kwargs.get('text') is True

    @patch('subprocess.run')
    def test_add_area_escapes_double_quotes(self, mock_run):
        """Titles containing double quotes are escaped to prevent AppleScript injection."""
        mock_run.return_value = Mock(stdout="UUID1\n", returncode=0)

        add_area('Project "Alpha"')

        script = mock_run.call_args[0][0][2]
        assert 'name:"Project \\"Alpha\\""' in script

    @patch('subprocess.run')
    def test_add_area_escapes_backslashes(self, mock_run):
        """Backslashes in titles are escaped before quote escaping."""
        mock_run.return_value = Mock(stdout="UUID2\n", returncode=0)

        add_area('foo\\bar')

        script = mock_run.call_args[0][0][2]
        assert 'name:"foo\\\\bar"' in script


class TestUpdateArea:
    """Test the update_area function (AppleScript-based; URL scheme has no area ops)."""

    @patch('subprocess.run')
    def test_update_area_renames(self, mock_run):
        """Setting title emits 'set name of theArea' targeting the given id."""
        mock_run.return_value = Mock(returncode=0)

        update_area('AREA1', title='Renamed')

        mock_run.assert_called_once()
        script = mock_run.call_args[0][0][2]
        assert 'area id "AREA1"' in script
        assert 'set name of theArea to "Renamed"' in script

    @patch('subprocess.run')
    def test_update_area_sets_tags(self, mock_run):
        """Tags are comma-joined into the 'tag names' property."""
        mock_run.return_value = Mock(returncode=0)

        update_area('AREA1', tags=['Work', 'Home'])

        script = mock_run.call_args[0][0][2]
        assert 'set tag names of theArea to "Work,Home"' in script

    @patch('subprocess.run')
    def test_update_area_title_and_tags_together(self, mock_run):
        """Both fields produce both statements in one AppleScript call."""
        mock_run.return_value = Mock(returncode=0)

        update_area('AREA1', title='New', tags=['Work'])

        script = mock_run.call_args[0][0][2]
        assert 'set name of theArea to "New"' in script
        assert 'set tag names of theArea to "Work"' in script

    @patch('subprocess.run')
    def test_update_area_escapes_quotes(self, mock_run):
        """Double quotes in the title are escaped to prevent AppleScript injection."""
        mock_run.return_value = Mock(returncode=0)

        update_area('AREA1', title='Area "X"')

        script = mock_run.call_args[0][0][2]
        assert 'set name of theArea to "Area \\"X\\""' in script

    @patch('subprocess.run')
    def test_update_area_noop_when_nothing_provided(self, mock_run):
        """With no fields, no AppleScript runs at all."""
        update_area('AREA1')
        mock_run.assert_not_called()


class TestConstructUrl:
    """Test the construct_url function."""
    
    def test_construct_url_basic(self):
        """Test basic URL construction without parameters."""
        url = construct_url("add", {})
        assert url == "things:///add"
    
    def test_construct_url_with_params(self):
        """Test URL construction with parameters."""
        params = {"title": "Test Task", "notes": "Test notes"}
        url = construct_url("add", params)
        assert url == "things:///add?title=Test%20Task&notes=Test%20notes"
    
    def test_construct_url_skip_none_values(self):
        """Test that None values are skipped."""
        params = {"title": "Test", "notes": None, "when": "today"}
        url = construct_url("add", params)
        assert url == "things:///add?title=Test&when=today"
        assert "notes" not in url
    
    def test_construct_url_boolean_values(self):
        """Test boolean value conversion."""
        params = {"title": "Test", "completed": True, "canceled": False}
        url = construct_url("add", params)
        assert "completed=true" in url
        assert "canceled=false" in url
    
    def test_construct_url_list_values(self):
        """Test list value conversion."""
        params = {"title": "Test", "tags": ["work", "urgent"]}
        url = construct_url("add", params)
        assert "tags=work%2Curgent" in url
    
    def test_construct_url_encodes_slash_in_values(self):
        """Slashes in parameter values must be percent-encoded (issue #47)."""
        params = {"title": "Example 2/13 project title"}
        url = construct_url("update-project", params)
        assert "title=Example%202%2F13%20project%20title" in url
        assert "2/13" not in url

    @patch('things.token')
    def test_construct_url_auth_token_update(self, mock_token):
        """Test auth token inclusion for update command."""
        mock_token.return_value = "test-auth-token"
        params = {"id": "123", "title": "Updated"}
        url = construct_url("update", params)
        assert "auth-token=test-auth-token" in url
    
    @patch('things.token')
    def test_construct_url_auth_token_update_project(self, mock_token):
        """Test auth token inclusion for update-project command."""
        mock_token.return_value = "test-auth-token"
        params = {"id": "123", "title": "Updated Project"}
        url = construct_url("update-project", params)
        assert "auth-token=test-auth-token" in url


class TestAddTodo:
    """Test the add_todo function."""
    
    def test_add_todo_minimal(self):
        """Test adding todo with minimal parameters."""
        url = add_todo("Test Todo")
        assert url == "things:///add?title=Test%20Todo"
    
    def test_add_todo_full(self):
        """Test adding todo with all parameters."""
        url = add_todo(
            title="Test Todo",
            notes="Test notes",
            when="today",
            deadline="2024-01-20",
            tags=["work", "urgent"],
            checklist_items=["Item 1", "Item 2"],
            list_id="inbox-id",
            list_title="Inbox",
            heading="Important",
            heading_id="heading-uuid",
            completed=False
        )
        
        assert "title=Test%20Todo" in url
        assert "notes=Test%20notes" in url
        assert "when=today" in url
        assert "deadline=2024-01-20" in url
        assert "tags=work%2Curgent" in url
        assert "checklist-items=Item%201%0AItem%202" in url
        assert "list-id=inbox-id" in url
        assert "list=Inbox" in url
        assert "heading=Important" in url
        assert "heading-id=heading-uuid" in url
        assert "completed=false" in url
    
    def test_add_todo_tags_handling(self):
        """Test proper tag handling in add_todo."""
        url = add_todo("Test", tags=["tag1", "tag2", "tag3"])
        assert "tags=tag1%2Ctag2%2Ctag3" in url
    
    def test_add_todo_checklist_newlines(self):
        """Test checklist items are newline-separated."""
        url = add_todo("Test", checklist_items=["First", "Second", "Third"])
        assert "checklist-items=First%0ASecond%0AThird" in url


class TestAddProject:
    """Test the add_project function."""
    
    def test_add_project_minimal(self):
        """Test adding project with minimal parameters."""
        url = add_project("Test Project")
        assert url == "things:///add-project?title=Test%20Project"
    
    def test_add_project_full(self):
        """Test adding project with all parameters."""
        url = add_project(
            title="Test Project",
            notes="Project notes",
            when="someday",
            deadline="2024-12-31",
            tags=["important", "work"],
            area_id="area-123",
            area_title="Work Area",
            todos=["Task 1", "Task 2", "Task 3"]
        )
        
        assert "title=Test%20Project" in url
        assert "notes=Project%20notes" in url
        assert "when=someday" in url
        assert "deadline=2024-12-31" in url
        assert "tags=important%2Cwork" in url
        assert "area-id=area-123" in url
        assert "area=Work%20Area" in url
        assert "to-dos=Task%201%0ATask%202%0ATask%203" in url
    
    def test_add_project_todos_newlines(self):
        """Test todos are newline-separated."""
        url = add_project("Test", todos=["First", "Second"])
        assert "to-dos=First%0ASecond" in url


class TestUpdateTodo:
    """Test the update_todo function."""
    
    @patch('things.token')
    def test_update_todo_minimal(self, mock_token):
        """Test updating todo with minimal parameters."""
        mock_token.return_value = "auth-token"
        url = update_todo("todo-123")
        assert "id=todo-123" in url
        assert "auth-token=auth-token" in url
    
    @patch('things.token')
    def test_update_todo_full(self, mock_token):
        """Test updating todo with all parameters."""
        mock_token.return_value = "auth-token"
        url = update_todo(
            id="todo-123",
            title="Updated Title",
            notes="Updated notes",
            when="tomorrow",
            deadline="2024-02-01",
            tags=["updated", "tag"],
            completed=True,
            canceled=False,
            list="Inbox",
            list_id="inbox-id",
            heading="New Heading",
            heading_id="heading-uuid"
        )
        
        assert "id=todo-123" in url
        assert "title=Updated%20Title" in url
        assert "notes=Updated%20notes" in url
        assert "when=tomorrow" in url
        assert "deadline=2024-02-01" in url
        assert "tags=updated%2Ctag" in url
        assert "completed=true" in url
        assert "canceled=false" in url
        assert "list=Inbox" in url
        assert "list-id=inbox-id" in url
        assert "heading=New%20Heading" in url
        assert "heading-id=heading-uuid" in url


    @patch('things.token')
    def test_update_todo_replaces_checklist(self, mock_token):
        """checklist_items replaces the entire checklist via 'checklist-items' param."""
        mock_token.return_value = "auth-token"
        url = update_todo(id="todo-123", checklist_items=["Step 1", "Step 2"])
        # newline join → "Step 1\nStep 2", then URL-encoded to %0A between items
        assert "checklist-items=Step%201%0AStep%202" in url

    @patch('things.token')
    def test_update_todo_prepends_checklist(self, mock_token):
        mock_token.return_value = "auth-token"
        url = update_todo(id="todo-123", prepend_checklist_items=["New first"])
        assert "prepend-checklist-items=New%20first" in url

    @patch('things.token')
    def test_update_todo_appends_checklist(self, mock_token):
        mock_token.return_value = "auth-token"
        url = update_todo(id="todo-123", append_checklist_items=["Extra A", "Extra B"])
        assert "append-checklist-items=Extra%20A%0AExtra%20B" in url

    @patch('things.token')
    def test_update_todo_add_tags_appends(self, mock_token):
        """add_tags maps to URL scheme 'add-tags' (append, doesn't replace)."""
        mock_token.return_value = "auth-token"
        url = update_todo(id="todo-123", add_tags=["new1", "new2"])
        assert "add-tags=new1%2Cnew2" in url
        # 'tags=' (without the add- prefix) should not be present when only add_tags is set
        assert "&tags=" not in url and not url.endswith("tags=new1%2Cnew2")


class TestUpdateProject:
    """Test the update_project function."""
    
    @patch('things.token')
    def test_update_project_minimal(self, mock_token):
        """Test updating project with minimal parameters."""
        mock_token.return_value = "auth-token"
        url = update_project("project-123")
        assert "id=project-123" in url
        assert "auth-token=auth-token" in url
    
    @patch('things.token')
    def test_update_project_full(self, mock_token):
        """Test updating project with all parameters."""
        mock_token.return_value = "auth-token"
        url = update_project(
            id="project-123",
            title="Updated Project",
            notes="Updated description",
            when="anytime",
            deadline="2024-06-30",
            tags=["updated"],
            completed=False,
            canceled=True
        )
        
        assert "id=project-123" in url
        assert "title=Updated%20Project" in url
        assert "notes=Updated%20description" in url
        assert "when=anytime" in url
        assert "deadline=2024-06-30" in url
        assert "tags=updated" in url
        assert "completed=false" in url
        assert "canceled=true" in url


class TestShow:
    """Test the show function."""
    
    def test_show_minimal(self):
        """Test show with just ID."""
        url = show("item-123")
        assert url == "things:///show?id=item-123"
    
    def test_show_with_query(self):
        """Test show with query."""
        url = show("list-123", query="important")
        assert "id=list-123" in url
        assert "query=important" in url
    
    def test_show_with_filter_tags(self):
        """Test show with filter tags."""
        url = show("list-123", filter_tags=["work", "urgent"])
        assert "id=list-123" in url
        assert "filter=work%2Curgent" in url


class TestSearch:
    """Test the search function."""
    
    def test_search_simple(self):
        """Test simple search."""
        url = search("test query")
        assert url == "things:///search?query=test%20query"
    
    def test_search_special_chars(self):
        """Test search with special characters."""
        url = search("test & query + special")
        assert "query=test%20%26%20query%20%2B%20special" in url


class TestFormatWhenWithReminder:
    """Test the format_when_with_reminder helper function."""

    def test_format_with_iso_date_and_24h_time(self):
        """Test formatting with ISO date and 24-hour time."""
        result = format_when_with_reminder("2024-01-15", "14:30")
        assert result == "2024-01-15@14:30"

    def test_format_with_iso_date_and_12h_time(self):
        """Test formatting with ISO date and 12-hour time."""
        result = format_when_with_reminder("2024-01-15", "2:30PM")
        assert result == "2024-01-15@2:30PM"

    def test_format_with_keyword_date(self):
        """Test formatting with keyword date like 'tomorrow'."""
        result = format_when_with_reminder("tomorrow", "9:00AM")
        assert result == "tomorrow@9:00AM"

    def test_format_with_today(self):
        """Test formatting with 'today' keyword."""
        result = format_when_with_reminder("today", "18:00")
        assert result == "today@18:00"

    def test_format_integrates_with_add_todo(self):
        """Test that formatted datetime works in add_todo URL."""
        when = format_when_with_reminder("2024-06-15", "10:00")
        url = add_todo("Test task", when=when)
        assert "when=2024-06-15%4010%3A00" in url  # @ is %40, : is %3A


class TestJsonCommand:
    """Test the json_command function used for bulk operations."""

    def _decode_data_param(self, url: str):
        assert url.startswith("things:///json?")
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        return json.loads(qs['data'][0]), qs

    def test_json_command_includes_auth_token(self):
        url = json_command([{"type": "to-do", "attributes": {"title": "x"}}], auth_token="abc")
        _, qs = self._decode_data_param(url)
        assert qs['auth-token'] == ['abc']

    def test_json_command_skips_token_when_absent(self):
        url = json_command([{"type": "to-do", "attributes": {"title": "x"}}])
        assert "auth-token=" not in url

    def test_json_command_serializes_multiple_updates(self):
        payload = [
            {"type": "to-do", "operation": "update", "id": "u1",
             "attributes": {"list-id": "shopping-uuid"}},
            {"type": "to-do", "operation": "update", "id": "u2",
             "attributes": {"list-id": "shopping-uuid"}},
        ]
        url = json_command(payload, auth_token="t")
        decoded, _ = self._decode_data_param(url)
        assert decoded == payload