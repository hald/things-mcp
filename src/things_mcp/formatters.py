import logging
import things
from datetime import datetime

logger = logging.getLogger(__name__)


def _calculate_age(date_str: str) -> str:
    """Helper function to calculate human-readable age from a date string.

    Args:
        date_str: ISO format date string

    Returns:
        Human-readable age string (e.g., "3 days ago", "2 weeks ago")

    Raises:
        ValueError: If date string cannot be parsed
        TypeError: If date_str is not a string
    """
    date_obj = datetime.fromisoformat(str(date_str))
    age = datetime.now() - date_obj
    days = age.days

    if days == 0:
        return "today"
    elif days == 1:
        return "1 day ago"
    elif days < 7:
        return f"{days} days ago"
    elif days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    elif days < 365:
        months = days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    else:
        years = days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"


def _lookup_title(uuid):
    """Fetch an item by uuid and return its title, or None if missing/broken.

    Wraps the things.get + try/except + None check pattern used to display
    parent project, area, and heading titles next to a task.
    """
    if not uuid:
        return None
    try:
        obj = things.get(uuid)
    except Exception:
        return None
    return obj['title'] if obj and obj.get('title') else None


def _append_timestamps(text: str, item: dict) -> str:
    """Append 'Created/Age' and 'Modified/Last modified' lines if present.

    Both blocks were duplicated across format_todo / format_project /
    format_area / format_heading with the same try/except shape. Centralise
    here so the four formatters stay in lock-step.
    """
    if item.get('created'):
        text += f"\nCreated: {item['created']}"
        try:
            text += f"\nAge: {_calculate_age(item['created'])}"
        except (ValueError, TypeError):
            pass
    if item.get('modified'):
        text += f"\nModified: {item['modified']}"
        try:
            text += f"\nLast modified: {_calculate_age(item['modified'])}"
        except (ValueError, TypeError):
            pass
    return text


def format_todo(todo: dict) -> str:
    """Helper function to format a single todo into a readable string."""
    todo_text = f"Title: {todo['title']}"
    todo_text += f"\nUUID: {todo['uuid']}"
    todo_text += f"\nType: {todo['type']}"

    if todo.get('status'):
        todo_text += f"\nStatus: {todo['status']}"

    # Look up parent project once (used for both List status and Project display).
    # For heading-level tasks without a project field, resolve heading -> project.
    parent_project = None
    if todo.get('project'):
        try:
            parent_project = things.get(todo['project'])
        except Exception:
            pass
    elif todo.get('heading'):
        try:
            heading_obj = things.get(todo['heading'])
            if heading_obj and heading_obj.get('project'):
                parent_project = things.get(heading_obj['project'])
        except Exception:
            pass

    # Start/list location with Someday inheritance from the parent project.
    if todo.get('start'):
        effective_start = todo['start']
        if effective_start != 'Someday' and parent_project and parent_project.get('start') == 'Someday':
            effective_start = 'Someday'
            todo_text += f"\nList: {effective_start} (inherited from project)"
        else:
            todo_text += f"\nList: {effective_start}"

    if todo.get('start_date'):
        todo_text += f"\nStart Date: {todo['start_date']}"
    if todo.get('deadline'):
        todo_text += f"\nDeadline: {todo['deadline']}"
    if todo.get('stop_date'):
        todo_text += f"\nCompleted: {todo['stop_date']}"

    todo_text = _append_timestamps(todo_text, todo)

    if todo.get('notes'):
        todo_text += f"\nNotes: {todo['notes']}"

    if parent_project:
        todo_text += f"\nProject: {parent_project['title']}"

    heading_title = _lookup_title(todo.get('heading'))
    if heading_title:
        todo_text += f"\nHeading: {heading_title}"

    area_title = _lookup_title(todo.get('area'))
    if area_title:
        todo_text += f"\nArea: {area_title}"

    if todo.get('tags'):
        todo_text += f"\nTags: {', '.join(todo['tags'])}"

    if isinstance(todo.get('checklist'), list):
        todo_text += "\nChecklist:"
        for item in todo['checklist']:
            checkbox = "✓" if item.get('status') == 'completed' else "☐"
            todo_text += f"\n  {checkbox} {item['title']}"

    return todo_text


def format_project(project: dict, include_items: bool = False) -> str:
    """Helper function to format a single project."""
    project_text = f"Title: {project['title']}\nUUID: {project['uuid']}"

    area_title = _lookup_title(project.get('area'))
    if area_title:
        project_text += f"\nArea: {area_title}"

    if project.get('notes'):
        project_text += f"\nNotes: {project['notes']}"

    project_text = _append_timestamps(project_text, project)

    # Always show headings for projects.
    headings = things.tasks(type='heading', project=project['uuid'])
    if headings:
        project_text += "\n\nHeadings:"
        for heading in headings:
            project_text += f"\n- {heading['title']}"

    if include_items:
        todos = things.todos(project=project['uuid'])
        if todos:
            project_text += "\n\nTasks:"
            for todo in todos:
                project_text += f"\n- {todo['title']}"

    return project_text


def format_area(area: dict, include_items: bool = False) -> str:
    """Helper function to format a single area."""
    area_text = f"Title: {area['title']}\nUUID: {area['uuid']}"

    if area.get('notes'):
        area_text += f"\nNotes: {area['notes']}"

    area_text = _append_timestamps(area_text, area)

    if include_items:
        projects = things.projects(area=area['uuid'])
        if projects:
            area_text += "\n\nProjects:"
            for project in projects:
                area_text += f"\n- {project['title']}"

        todos = things.todos(area=area['uuid'])
        if todos:
            area_text += "\n\nTasks:"
            for todo in todos:
                area_text += f"\n- {todo['title']}"

    return area_text


def format_tag(tag: dict, include_items: bool = False) -> str:
    """Helper function to format a single tag."""
    tag_text = f"Title: {tag['title']}\nUUID: {tag['uuid']}"

    if tag.get('shortcut'):
        tag_text += f"\nShortcut: {tag['shortcut']}"

    if include_items:
        todos = things.todos(tag=tag['title'])
        if todos:
            tag_text += "\n\nTagged Items:"
            for todo in todos:
                tag_text += f"\n- {todo['title']}"

    return tag_text


def format_heading(heading: dict, include_items: bool = False) -> str:
    """Helper function to format a single heading."""
    heading_text = f"Title: {heading['title']}\nUUID: {heading['uuid']}"
    heading_text += f"\nType: heading"

    if heading.get('project'):
        # Prefer the inlined project_title if things-py already provided it,
        # otherwise fall back to a fresh lookup.
        project_title = heading.get('project_title') or _lookup_title(heading.get('project'))
        if project_title:
            heading_text += f"\nProject: {project_title}"

    heading_text = _append_timestamps(heading_text, heading)

    if heading.get('notes'):
        heading_text += f"\nNotes: {heading['notes']}"

    if include_items:
        todos = things.todos(heading=heading['uuid'])
        if todos:
            heading_text += "\n\nTasks under heading:"
            for todo in todos:
                heading_text += f"\n- {todo['title']}"

    return heading_text
