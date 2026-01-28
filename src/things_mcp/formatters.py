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

def format_todo(todo: dict) -> str:
    """Helper function to format a single todo into a readable string."""
    logger.debug(f"Formatting todo: {todo}")
    todo_text = f"Title: {todo['title']}"

    # Add UUID for reference
    todo_text += f"\nUUID: {todo['uuid']}"

    # Add type
    todo_text += f"\nType: {todo['type']}"

    # Add status if present
    if todo.get('status'):
        todo_text += f"\nStatus: {todo['status']}"

    # Add start/list location
    if todo.get('start'):
        todo_text += f"\nList: {todo['start']}"

    # Add dates
    if todo.get('start_date'):
        todo_text += f"\nStart Date: {todo['start_date']}"
    if todo.get('deadline'):
        todo_text += f"\nDeadline: {todo['deadline']}"
    if todo.get('stop_date'):  # Completion date
        todo_text += f"\nCompleted: {todo['stop_date']}"

    # Add creation and modification dates
    if todo.get('created'):
        todo_text += f"\nCreated: {todo['created']}"
        # Calculate age since creation
        try:
            age_text = _calculate_age(todo['created'])
            todo_text += f"\nAge: {age_text}"
        except (ValueError, TypeError):
            pass

    if todo.get('modified'):
        todo_text += f"\nModified: {todo['modified']}"
        # Calculate time since last modification
        try:
            modified_age = _calculate_age(todo['modified'])
            todo_text += f"\nLast modified: {modified_age}"
        except (ValueError, TypeError):
            pass

    # Add notes if present
    if todo.get('notes'):
        todo_text += f"\nNotes: {todo['notes']}"

    # Add project info if present
    if todo.get('project'):
        try:
            project = things.get(todo['project'])
            if project:
                todo_text += f"\nProject: {project['title']}"
        except Exception:
            pass

    # Add heading info if present
    if todo.get('heading'):
        try:
            heading = things.get(todo['heading'])
            if heading:
                todo_text += f"\nHeading: {heading['title']}"
        except Exception:
            pass

    # Add area info if present
    if todo.get('area'):
        try:
            area = things.get(todo['area'])
            if area:
                todo_text += f"\nArea: {area['title']}"
        except Exception:
            pass

    # Add tags if present
    if todo.get('tags'):
        todo_text += f"\nTags: {', '.join(todo['tags'])}"

    # Add checklist if present and contains items
    if isinstance(todo.get('checklist'), list):
        todo_text += "\nChecklist:"
        for item in todo['checklist']:
            checkbox = "✓" if item.get('status') == 'completed' else "☐"
            todo_text += f"\n  {checkbox} {item['title']}"

    return todo_text

def format_project(project: dict, include_items: bool = False) -> str:
    """Helper function to format a single project."""
    project_text = f"Title: {project['title']}\nUUID: {project['uuid']}"

    if project.get('area'):
        try:
            area = things.get(project['area'])
            if area:
                project_text += f"\nArea: {area['title']}"
        except Exception:
            pass

    if project.get('notes'):
        project_text += f"\nNotes: {project['notes']}"

    # Add creation and modification dates
    if project.get('created'):
        project_text += f"\nCreated: {project['created']}"
        # Calculate age since creation
        try:
            age_text = _calculate_age(project['created'])
            project_text += f"\nAge: {age_text}"
        except (ValueError, TypeError):
            pass

    if project.get('modified'):
        project_text += f"\nModified: {project['modified']}"
        # Calculate time since last modification
        try:
            modified_age = _calculate_age(project['modified'])
            project_text += f"\nLast modified: {modified_age}"
        except (ValueError, TypeError):
            pass

    # Always show headings for projects
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

    # Add creation and modification dates
    if area.get('created'):
        area_text += f"\nCreated: {area['created']}"
        try:
            age_text = _calculate_age(area['created'])
            area_text += f"\nAge: {age_text}"
        except (ValueError, TypeError):
            pass

    if area.get('modified'):
        area_text += f"\nModified: {area['modified']}"
        try:
            modified_age = _calculate_age(area['modified'])
            area_text += f"\nLast modified: {modified_age}"
        except (ValueError, TypeError):
            pass

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

    # Add project info if present
    if heading.get('project'):
        if heading.get('project_title'):
            heading_text += f"\nProject: {heading['project_title']}"
        else:
            try:
                project = things.get(heading['project'])
                if project:
                    heading_text += f"\nProject: {project['title']}"
            except Exception:
                pass

    # Add dates
    if heading.get('created'):
        heading_text += f"\nCreated: {heading['created']}"
        try:
            age_text = _calculate_age(heading['created'])
            heading_text += f"\nAge: {age_text}"
        except (ValueError, TypeError):
            pass
    if heading.get('modified'):
        heading_text += f"\nModified: {heading['modified']}"
        try:
            modified_age = _calculate_age(heading['modified'])
            heading_text += f"\nLast modified: {modified_age}"
        except (ValueError, TypeError):
            pass

    # Add notes if present
    if heading.get('notes'):
        heading_text += f"\nNotes: {heading['notes']}"

    if include_items:
        # Get todos under this heading
        todos = things.todos(heading=heading['uuid'])
        if todos:
            heading_text += "\n\nTasks under heading:"
            for todo in todos:
                heading_text += f"\n- {todo['title']}"

    return heading_text
