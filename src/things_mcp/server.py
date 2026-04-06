from typing import Callable, List
import logging
import os
import things
from fastmcp import FastMCP
from .formatters import format_todo, format_project, format_area, format_tag, format_heading
from . import url_scheme

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Transport configuration via environment variables
TRANSPORT = os.environ.get("THINGS_MCP_TRANSPORT", "stdio")  # "stdio" or "http"
HTTP_HOST = os.environ.get("THINGS_MCP_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("THINGS_MCP_PORT", "8000"))

# Initialize FastMCP server
mcp = FastMCP("Things")


# Build a set of Someday project UUIDs and a mapping of heading UUID -> project UUID
# for headings that belong to Someday projects.
def _get_someday_context():
    """Return (someday_project_ids, heading_to_project) for Someday filtering.

    Returns:
        Tuple of (set of Someday project UUIDs, dict mapping heading UUID to project UUID)
    """
    try:
        someday_project_ids = {p['uuid'] for p in (things.projects(start='Someday') or [])}
    except Exception:
        return set(), {}
    if not someday_project_ids:
        return set(), {}
    # Build heading -> project mapping for headings inside Someday projects
    heading_to_project = {}
    for proj_id in someday_project_ids:
        try:
            headings = things.tasks(type='heading', project=proj_id)
            for h in (headings or []):
                heading_to_project[h['uuid']] = proj_id
        except Exception:
            pass
    return someday_project_ids, heading_to_project


def _is_in_someday_project(todo, someday_project_ids, heading_to_project):
    """Check if a todo belongs to a Someday project, directly or via heading."""
    if todo.get('project') in someday_project_ids:
        return True
    if not todo.get('project') and todo.get('heading'):
        return todo['heading'] in heading_to_project
    return False


# Helper function to filter out tasks from Someday projects
def filter_someday_project_tasks(todos):
    """Filter out tasks that belong to Someday projects.

    This matches Things UI behavior where tasks from Someday projects
    don't appear in Today, Upcoming, or Anytime views. Handles both
    direct project membership and tasks under headings in Someday projects.

    Args:
        todos: List of todo dictionaries

    Returns:
        Filtered list excluding tasks from Someday projects
    """
    someday_project_ids, heading_to_project = _get_someday_context()
    if not someday_project_ids:
        return todos
    return [todo for todo in todos if not _is_in_someday_project(todo, someday_project_ids, heading_to_project)]


def _validate_pagination(limit: int | None, offset: int) -> str | None:
    """Validate pagination inputs shared by read/query tools."""
    if limit is not None and limit <= 0:
        return "Error: limit must be a positive integer"
    if offset < 0:
        return "Error: offset must be a non-negative integer"
    return None


def _format_paginated_results(
    items: list[dict],
    formatter: Callable[[dict], str],
    empty_message: str,
    limit: int | None = None,
    offset: int = 0,
) -> str:
    """Apply limit/offset pagination and format a collection for MCP output."""
    end = None if limit is None else offset + limit
    paginated_items = items[offset:end]
    if not paginated_items:
        return empty_message

    formatted_items = [formatter(item) for item in paginated_items]
    result = "\n\n---\n\n".join(formatted_items)

    if limit is None and offset == 0:
        return result

    start_index = offset + 1
    end_index = offset + len(paginated_items)
    item_label = "item" if len(items) == 1 else "items"
    return f"Showing {start_index}-{end_index} of {len(items)} {item_label}\n\n{result}"


# List view tools
@mcp.tool
async def get_inbox(limit: int | None = None, offset: int = 0) -> str:
    """Get todos from Inbox

    Args:
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    todos = things.inbox(include_items=True) or []
    return _format_paginated_results(todos, format_todo, "No items found", limit, offset)

@mcp.tool
async def get_today(limit: int | None = None, offset: int = 0) -> str:
    """Get todos due today

    Args:
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    todos = things.today(include_items=True) or []
    # Filter out tasks from Someday projects
    todos = filter_someday_project_tasks(todos)
    return _format_paginated_results(todos, format_todo, "No items found", limit, offset)

@mcp.tool
async def get_upcoming(limit: int | None = None, offset: int = 0) -> str:
    """Get upcoming todos

    Args:
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    todos = things.upcoming(include_items=True) or []
    # Filter out tasks from Someday projects
    todos = filter_someday_project_tasks(todos)
    return _format_paginated_results(todos, format_todo, "No items found", limit, offset)

@mcp.tool
async def get_anytime(limit: int | None = None, offset: int = 0) -> str:
    """Get todos from Anytime list

    Args:
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    todos = things.anytime(include_items=True) or []
    # Filter out tasks from Someday projects
    todos = filter_someday_project_tasks(todos)
    return _format_paginated_results(todos, format_todo, "No items found", limit, offset)

@mcp.tool
async def get_someday(limit: int | None = None, offset: int = 0) -> str:
    """Get todos from Someday list, including tasks in Someday projects

    Args:
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    todos = things.someday(include_items=True) or []
    # Also include tasks that have start="Anytime" but belong to a Someday project
    # (directly or via a heading), since Things.py doesn't inherit project Someday status
    someday_project_ids, heading_to_project = _get_someday_context()
    if someday_project_ids:
        anytime_todos = things.anytime(include_items=True) or []
        existing_uuids = {t['uuid'] for t in todos}
        for todo in anytime_todos:
            if _is_in_someday_project(todo, someday_project_ids, heading_to_project) and todo['uuid'] not in existing_uuids:
                todos.append(todo)
    return _format_paginated_results(todos, format_todo, "No items found", limit, offset)

@mcp.tool
async def get_logbook(period: str = "7d", limit: int | None = 50, offset: int = 0) -> str:
    """Get completed todos from Logbook, defaults to last 7 days

    Args:
        period: Time period to look back (e.g., '3d', '1w', '2m', '1y'). Defaults to '7d'
        limit: Maximum number of items to return. Defaults to 50.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    todos = things.last(period, status='completed', include_items=True) or []
    return _format_paginated_results(todos, format_todo, "No items found", limit, offset)

@mcp.tool
async def get_trash(limit: int | None = None, offset: int = 0) -> str:
    """Get trashed todos

    Args:
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    todos = things.trash(include_items=True) or []
    return _format_paginated_results(todos, format_todo, "No items found", limit, offset)

# Basic operations
@mcp.tool
async def get_todos(
    project_uuid: str = None,
    include_items: bool = True,
    limit: int | None = None,
    offset: int = 0
) -> str:
    """Get todos from Things, optionally filtered by project

    Args:
        project_uuid: Optional UUID of a specific project to get todos from
        include_items: Include checklist items
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    if project_uuid:
        project = things.get(project_uuid)
        if not project or project.get('type') != 'project':
            return f"Error: Invalid project UUID '{project_uuid}'"

    todos = things.todos(project=project_uuid, start=None, include_items=include_items) or []
    return _format_paginated_results(todos, format_todo, "No todos found", limit, offset)

@mcp.tool
async def get_projects(include_items: bool = False, limit: int | None = None, offset: int = 0) -> str:
    """Get all projects from Things

    Args:
        include_items: Include tasks within projects
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    projects = things.projects() or []
    return _format_paginated_results(
        projects,
        lambda project: format_project(project, include_items),
        "No projects found",
        limit,
        offset,
    )

@mcp.tool
async def get_areas(include_items: bool = False, limit: int | None = None, offset: int = 0) -> str:
    """Get all areas from Things

    Args:
        include_items: Include projects and tasks within areas
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    areas = things.areas() or []
    return _format_paginated_results(
        areas,
        lambda area: format_area(area, include_items),
        "No areas found",
        limit,
        offset,
    )

# Tag operations
@mcp.tool
async def get_tags(include_items: bool = False, limit: int | None = None, offset: int = 0) -> str:
    """Get all tags

    Args:
        include_items: Include items tagged with each tag
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    tags = things.tags() or []
    return _format_paginated_results(
        tags,
        lambda tag: format_tag(tag, include_items),
        "No tags found",
        limit,
        offset,
    )

@mcp.tool
async def get_tagged_items(tag: str, limit: int | None = None, offset: int = 0) -> str:
    """Get items with a specific tag

    Args:
        tag: Tag title to filter by
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    todos = things.todos(tag=tag, include_items=True) or []
    return _format_paginated_results(todos, format_todo, f"No items found with tag '{tag}'", limit, offset)

@mcp.tool
async def get_headings(project_uuid: str = None, limit: int | None = None, offset: int = 0) -> str:
    """Get headings from Things

    Args:
        project_uuid: Optional UUID of a specific project to get headings from
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    if project_uuid:
        project = things.get(project_uuid)
        if not project or project.get('type') != 'project':
            return f"Error: Invalid project UUID '{project_uuid}'"
        headings = things.tasks(type='heading', project=project_uuid)
    else:
        headings = things.tasks(type='heading')

    return _format_paginated_results(headings or [], format_heading, "No headings found", limit, offset)

# Search operations
@mcp.tool
async def search_todos(query: str, limit: int | None = None, offset: int = 0) -> str:
    """Search todos by title or notes

    Args:
        query: Search term to look for in todo titles and notes
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    todos = things.search(query, include_items=True) or []
    return _format_paginated_results(todos, format_todo, f"No todos found matching '{query}'", limit, offset)

@mcp.tool
async def search_advanced(
    status: str = None,
    start_date: str = None,
    deadline: str = None,
    tag: str = None,
    area: str = None,
    type: str = None,
    last: str = None,
    limit: int | None = None,
    offset: int = 0
) -> str:
    """Advanced todo search with multiple filters

    Args:
        status: Filter by todo status (incomplete, completed, canceled)
        start_date: Filter by start date (YYYY-MM-DD)
        deadline: Filter by deadline (YYYY-MM-DD)
        tag: Filter by tag
        area: Filter by area UUID
        type: Filter by item type (to-do, project, heading)
        last: Filter by creation date (e.g., '3d' for last 3 days, '1w' for last week, '1y' for last year)
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    search_params = {}
    if status:
        search_params["status"] = status
    if start_date:
        search_params["start_date"] = start_date
    if deadline:
        search_params["deadline"] = deadline
    if tag:
        search_params["tag"] = tag
    if area:
        search_params["area"] = area
    if last:
        search_params["last"] = last

    if type:
        # Use things.tasks() when type is specified since things.todos()
        # hardcodes type="to-do"
        todos = things.tasks(type=type, include_items=True, **search_params)
    else:
        todos = things.todos(include_items=True, **search_params)
    return _format_paginated_results(todos or [], format_todo, "No matching todos found", limit, offset)

# Recent items
@mcp.tool
async def get_recent(period: str, limit: int | None = None, offset: int = 0) -> str:
    """Get recently created items

    Args:
        period: Time period (e.g., '3d', '1w', '2m', '1y')
        limit: Maximum number of items to return. Omit to return all items.
        offset: Number of items to skip before returning results.
    """
    pagination_error = _validate_pagination(limit, offset)
    if pagination_error:
        return pagination_error

    todos = things.last(period, include_items=True) or []
    return _format_paginated_results(todos, format_todo, f"No items found in the last {period}", limit, offset)

# Things URL Scheme tools
@mcp.tool
async def add_todo(
    title: str,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    tags: List[str] = None,
    checklist_items: List[str] = None,
    list_id: str = None,
    list_title: str = None,
    heading: str = None,
    heading_id: str = None
) -> str:
    """Create a new todo in Things

    Args:
        title: Title of the todo
        notes: Notes for the todo
        when: When to schedule the todo (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD).
            Use YYYY-MM-DD@HH:MM format to add a reminder (e.g., 2024-01-15@14:30)
        deadline: Deadline for the todo (YYYY-MM-DD)
        tags: Tags to apply to the todo
        checklist_items: Checklist items to add
        list_id: ID of project/area to add to
        list_title: Title of project/area to add to
        heading: Heading title to add under
        heading_id: Heading ID to add under (takes precedence over heading)
    """
    url = url_scheme.add_todo(
        title=title,
        notes=notes,
        when=when,
        deadline=deadline,
        tags=tags,
        checklist_items=checklist_items,
        list_id=list_id,
        list_title=list_title,
        heading=heading,
        heading_id=heading_id
    )
    url_scheme.execute_url(url)
    return f"Created new todo: {title}"

@mcp.tool
async def add_project(
    title: str,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    tags: List[str] = None,
    area_id: str = None,
    area_title: str = None,
    todos: List[str] = None
) -> str:
    """Create a new project in Things

    Args:
        title: Title of the project
        notes: Notes for the project
        when: When to schedule the project (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD).
            Use YYYY-MM-DD@HH:MM format to add a reminder (e.g., 2024-01-15@14:30)
        deadline: Deadline for the project (YYYY-MM-DD)
        tags: Tags to apply to the project
        area_id: ID of area to add to
        area_title: Title of area to add to
        todos: Initial todos to create in the project
    """
    url = url_scheme.add_project(
        title=title,
        notes=notes,
        when=when,
        deadline=deadline,
        tags=tags,
        area_id=area_id,
        area_title=area_title,
        todos=todos
    )
    url_scheme.execute_url(url)
    return f"Created new project: {title}"

@mcp.tool
async def update_todo(
    id: str,
    title: str = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    tags: List[str] = None,
    completed: bool = None,
    canceled: bool = None,
    list: str = None,
    list_id: str = None,
    heading: str = None,
    heading_id: str = None
) -> str:
    """Update an existing todo in Things

    Args:
        id: ID of the todo to update
        title: New title
        notes: New notes
        when: New schedule (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD).
            Use YYYY-MM-DD@HH:MM format to add a reminder (e.g., 2024-01-15@14:30)
        deadline: New deadline (YYYY-MM-DD)
        tags: New tags
        completed: Mark as completed
        canceled: Mark as canceled
        list: The title of a project or area to move the to-do into
        list_id: The ID of a project or area to move the to-do into (takes precedence over list)
        heading: The heading title to move the to-do under
        heading_id: The heading ID to move the to-do under (takes precedence over heading)
    """
    url = url_scheme.update_todo(
        id=id,
        title=title,
        notes=notes,
        when=when,
        deadline=deadline,
        tags=tags,
        completed=completed,
        canceled=canceled,
        list=list,
        list_id=list_id,
        heading=heading,
        heading_id=heading_id
    )
    url_scheme.execute_url(url)
    return f"Updated todo with ID: {id}"

@mcp.tool
async def update_project(
    id: str,
    title: str = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    tags: List[str] = None,
    completed: bool = None,
    canceled: bool = None
) -> str:
    """Update an existing project in Things

    Args:
        id: ID of the project to update
        title: New title
        notes: New notes
        when: New schedule (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD).
            Use YYYY-MM-DD@HH:MM format to add a reminder (e.g., 2024-01-15@14:30)
        deadline: New deadline (YYYY-MM-DD)
        tags: New tags
        completed: Mark as completed
        canceled: Mark as canceled
    """
    url = url_scheme.update_project(
        id=id,
        title=title,
        notes=notes,
        when=when,
        deadline=deadline,
        tags=tags,
        completed=completed,
        canceled=canceled
    )
    url_scheme.execute_url(url)
    return f"Updated project with ID: {id}"

@mcp.tool
async def show_item(
    id: str,
    query: str = None,
    filter_tags: List[str] = None
) -> str:
    """Show a specific item or list in Things

    Args:
        id: ID of item to show, or one of: inbox, today, upcoming, anytime, someday, logbook
        query: Optional query to filter by
        filter_tags: Optional tags to filter by
    """
    url = url_scheme.show(
        id=id,
        query=query,
        filter_tags=filter_tags
    )
    url_scheme.execute_url(url)
    return f"Showing item: {id}"

@mcp.tool
async def search_items(query: str) -> str:
    """Search for items in Things

    Args:
        query: Search query
    """
    url = url_scheme.search(query)
    url_scheme.execute_url(url)
    return f"Searching for '{query}'"


def main():
    """Main entry point for the Things MCP server."""
    if TRANSPORT == "http":
        mcp.run(transport="http", host=HTTP_HOST, port=HTTP_PORT)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
