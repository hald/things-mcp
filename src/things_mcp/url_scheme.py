import urllib.parse
import subprocess
import things
from typing import Optional, Dict, Any, Union

# When parameter accepted values:
# - Keywords: "today", "tomorrow", "evening", "anytime", "someday"
# - Date string: "yyyy-mm-dd" (e.g., "2024-01-15") or natural language ("in 3 days", "next tuesday")
# - DateTime string: "yyyy-mm-dd@HH:MM" (e.g., "2024-01-15@14:30") - adds a reminder at that time
# - ISO8601: "2024-01-15T14:30:00Z" or with timezone offset


def format_when_with_reminder(date: str, time: str) -> str:
    """Format a date and time into a Things datetime string for reminders.

    Args:
        date: Date in yyyy-mm-dd format, or "today"/"tomorrow"/natural language
        time: Time in HH:MM (24h) or H:MMPM (12h) format (e.g., "14:30" or "2:30PM")

    Returns:
        Formatted datetime string (e.g., "2024-01-15@14:30")

    Example:
        >>> format_when_with_reminder("2024-01-15", "14:30")
        '2024-01-15@14:30'
        >>> format_when_with_reminder("tomorrow", "9:00AM")
        'tomorrow@9:00AM'
    """
    return f"{date}@{time}"

def execute_url(url: str) -> None:
    """Execute a Things URL without bringing Things to the foreground."""
    try:
        # Use 'do shell script' with 'open -g' to open in background
        subprocess.run([
            'osascript', '-e',
            f'do shell script "open -g \\"{url}\\""'
        ], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        # Fallback - still try with open -g directly
        subprocess.run(['open', '-g', url], check=True)

def construct_url(command: str, params: Dict[str, Any]) -> str:
    """Construct a Things URL from command and parameters."""
    # Start with base URL
    url = f"things:///{command}"

    # Get authentication token if needed
    if command in ['update', 'update-project']:
        token = things.token()
        if token:
            params['auth-token'] = token

    # URL encode parameters
    if params:
        encoded_params = []
        for key, value in params.items():
            if value is None:
                continue
            # Handle boolean values
            if isinstance(value, bool):
                value = str(value).lower()
            # Handle lists (for tags, checklist items etc)
            elif isinstance(value, list):
                value = ','.join(str(v) for v in value)
            encoded_params.append(f"{key}={urllib.parse.quote(str(value))}")

        url += "?" + "&".join(encoded_params)

    return url

def add_todo(title: str, notes: Optional[str] = None, when: Optional[str] = None,
             deadline: Optional[str] = None, tags: Optional[list[str]] = None,
             checklist_items: Optional[list[str]] = None, list_id: Optional[str] = None,
             list_title: Optional[str] = None, heading: Optional[str] = None,
             heading_id: Optional[str] = None,
             completed: Optional[bool] = None) -> str:
    """Construct URL to add a new todo.

    Args:
        title: Title of the todo
        notes: Notes for the todo
        when: Schedule the todo. Accepts:
            - Keywords: "today", "tomorrow", "evening", "anytime", "someday"
            - Date: "yyyy-mm-dd" or natural language ("in 3 days", "next tuesday")
            - DateTime (adds reminder): "yyyy-mm-dd@HH:MM" (e.g., "2024-01-15@14:30")
        deadline: Deadline date (yyyy-mm-dd)
        tags: List of tag names
        checklist_items: List of checklist item titles
        list_id: UUID of project/area to add to
        list_title: Title of project/area to add to
        heading: Heading title within project
        heading_id: UUID of heading within project
        completed: Mark as completed on creation
    """
    params = {
        'title': title,
        'notes': notes,
        'when': when,
        'deadline': deadline,
        'checklist-items': '\n'.join(checklist_items) if checklist_items else None,
        'list-id': list_id,
        'list': list_title,
        'heading': heading,
        'heading-id': heading_id,
        'completed': completed
    }

    # Handle tags separately since they need to be comma-separated
    if tags:
        params['tags'] = ','.join(tags)
    return construct_url('add', {k: v for k, v in params.items() if v is not None})

def add_project(title: str, notes: Optional[str] = None, when: Optional[str] = None,
                deadline: Optional[str] = None, tags: Optional[list[str]] = None,
                area_id: Optional[str] = None, area_title: Optional[str] = None,
                todos: Optional[list[str]] = None) -> str:
    """Construct URL to add a new project.

    Args:
        title: Title of the project
        notes: Notes for the project
        when: Schedule the project. Accepts:
            - Keywords: "today", "tomorrow", "evening", "anytime", "someday"
            - Date: "yyyy-mm-dd" or natural language ("in 3 days", "next tuesday")
            - DateTime (adds reminder): "yyyy-mm-dd@HH:MM" (e.g., "2024-01-15@14:30")
        deadline: Deadline date (yyyy-mm-dd)
        tags: List of tag names
        area_id: UUID of area to add to
        area_title: Title of area to add to
        todos: List of todo titles to create in the project
    """
    params = {
        'title': title,
        'notes': notes,
        'when': when,
        'deadline': deadline,
        'area-id': area_id,
        'area': area_title,
        # Change todos to be newline separated
        'to-dos': '\n'.join(todos) if todos else None
    }

    # Handle tags separately since they need to be comma-separated
    if tags:
        params['tags'] = ','.join(tags)

    return construct_url('add-project', {k: v for k, v in params.items() if v is not None})

def update_todo(id: str, title: Optional[str] = None, notes: Optional[str] = None,
                when: Optional[str] = None, deadline: Optional[str] = None,
                tags: Optional[list[str]] = None, completed: Optional[bool] = None,
                canceled: Optional[bool] = None, list: Optional[str] = None,
                list_id: Optional[str] = None, heading: Optional[str] = None,
                heading_id: Optional[str] = None) -> str:
    """Construct URL to update an existing todo.

    Args:
        id: UUID of the todo to update
        title: New title
        notes: New notes
        when: Reschedule the todo. Accepts:
            - Keywords: "today", "tomorrow", "evening", "anytime", "someday"
            - Date: "yyyy-mm-dd" or natural language ("in 3 days", "next tuesday")
            - DateTime (adds reminder): "yyyy-mm-dd@HH:MM" (e.g., "2024-01-15@14:30")
        deadline: New deadline (yyyy-mm-dd)
        tags: New tags (replaces existing)
        completed: Mark as completed
        canceled: Mark as canceled
        list: Title of project/area to move to
        list_id: UUID of project/area to move to (takes precedence over list)
        heading: Heading title to move under
        heading_id: UUID of heading to move under (takes precedence over heading)
    """
    params = {
        'id': id,
        'title': title,
        'notes': notes,
        'when': when,
        'deadline': deadline,
        'tags': tags,
        'completed': completed,
        'canceled': canceled,
        'list': list,
        'list-id': list_id,
        'heading': heading,
        'heading-id': heading_id
    }
    return construct_url('update', {k: v for k, v in params.items() if v is not None})

def update_project(id: str, title: Optional[str] = None, notes: Optional[str] = None,
                   when: Optional[str] = None, deadline: Optional[str] = None,
                   tags: Optional[list[str]] = None, completed: Optional[bool] = None,
                   canceled: Optional[bool] = None) -> str:
    """Construct URL to update an existing project.

    Args:
        id: UUID of the project to update
        title: New title
        notes: New notes
        when: Reschedule the project. Accepts:
            - Keywords: "today", "tomorrow", "evening", "anytime", "someday"
            - Date: "yyyy-mm-dd" or natural language ("in 3 days", "next tuesday")
            - DateTime (adds reminder): "yyyy-mm-dd@HH:MM" (e.g., "2024-01-15@14:30")
        deadline: New deadline (yyyy-mm-dd)
        tags: New tags (replaces existing)
        completed: Mark as completed
        canceled: Mark as canceled
    """
    params = {
        'id': id,
        'title': title,
        'notes': notes,
        'when': when,
        'deadline': deadline,
        'tags': tags,
        'completed': completed,
        'canceled': canceled
    }
    return construct_url('update-project', {k: v for k, v in params.items() if v is not None})

def show(id: str, query: Optional[str] = None, filter_tags: Optional[list[str]] = None) -> str:
    """Construct URL to show a specific item or list."""
    params = {
        'id': id,
        'query': query,
        'filter': filter_tags
    }
    return construct_url('show', {k: v for k, v in params.items() if v is not None})

def search(query: str) -> str:
    """Construct URL to perform a search."""
    return construct_url('search', {'query': query})
