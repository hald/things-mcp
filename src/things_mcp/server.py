from typing import List
import logging
import os
import things
from fastmcp import FastMCP
from .formatters import format_todo, format_project, format_area, format_tag, format_heading
from . import url_scheme

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Transport configuration via environment variables
TRANSPORT = os.environ.get("THINGS_MCP_TRANSPORT", "stdio")  # "stdio" or "http"
HTTP_HOST = os.environ.get("THINGS_MCP_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("THINGS_MCP_PORT", "8000"))

# Initialize FastMCP server
mcp = FastMCP("Things")

# List view tools
@mcp.tool
async def get_inbox() -> str:
    """Get todos from Inbox"""
    todos = things.inbox(include_items=True)
    if not todos:
        return "No items found"
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool
async def get_today() -> str:
    """Get todos due today"""
    todos = things.today(include_items=True)
    if not todos:
        return "No items found"
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool
async def get_upcoming() -> str:
    """Get upcoming todos"""
    todos = things.upcoming(include_items=True)
    if not todos:
        return "No items found"
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool
async def get_anytime() -> str:
    """Get todos from Anytime list"""
    todos = things.anytime(include_items=True)
    if not todos:
        return "No items found"
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool
async def get_someday() -> str:
    """Get todos from Someday list"""
    todos = things.someday(include_items=True)
    if not todos:
        return "No items found"
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool
async def get_logbook(period: str = "7d", limit: int = 50) -> str:
    """Get completed todos from Logbook, defaults to last 7 days

    Args:
        period: Time period to look back (e.g., '3d', '1w', '2m', '1y'). Defaults to '7d'
        limit: Maximum number of entries to return. Defaults to 50
    """
    todos = things.last(period, status='completed', include_items=True)
    if todos and len(todos) > limit:
        todos = todos[:limit]
    if not todos:
        return "No items found"
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool
async def get_trash() -> str:
    """Get trashed todos"""
    todos = things.trash(include_items=True)
    if not todos:
        return "No items found"
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

# Basic operations
@mcp.tool
async def get_todos(project_uuid: str = None, include_items: bool = True) -> str:
    """Get todos from Things, optionally filtered by project

    Args:
        project_uuid: Optional UUID of a specific project to get todos from
        include_items: Include checklist items
    """
    if project_uuid:
        project = things.get(project_uuid)
        if not project or project.get('type') != 'project':
            return f"Error: Invalid project UUID '{project_uuid}'"

    todos = things.todos(project=project_uuid, start=None, include_items=include_items)
    if not todos:
        return "No todos found"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool
async def get_projects(include_items: bool = False) -> str:
    """Get all projects from Things

    Args:
        include_items: Include tasks within projects
    """
    projects = things.projects()
    if not projects:
        return "No projects found"

    formatted_projects = [format_project(project, include_items) for project in projects]
    return "\n\n---\n\n".join(formatted_projects)

@mcp.tool
async def get_areas(include_items: bool = False) -> str:
    """Get all areas from Things

    Args:
        include_items: Include projects and tasks within areas
    """
    areas = things.areas()
    if not areas:
        return "No areas found"

    formatted_areas = [format_area(area, include_items) for area in areas]
    return "\n\n---\n\n".join(formatted_areas)

# Tag operations
@mcp.tool
async def get_tags(include_items: bool = False) -> str:
    """Get all tags

    Args:
        include_items: Include items tagged with each tag
    """
    tags = things.tags()
    if not tags:
        return "No tags found"

    formatted_tags = [format_tag(tag, include_items) for tag in tags]
    return "\n\n---\n\n".join(formatted_tags)

@mcp.tool
async def get_tagged_items(tag: str) -> str:
    """Get items with a specific tag

    Args:
        tag: Tag title to filter by
    """
    todos = things.todos(tag=tag, include_items=True)
    if not todos:
        return f"No items found with tag '{tag}'"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool
async def get_headings(project_uuid: str = None) -> str:
    """Get headings from Things

    Args:
        project_uuid: Optional UUID of a specific project to get headings from
    """
    if project_uuid:
        project = things.get(project_uuid)
        if not project or project.get('type') != 'project':
            return f"Error: Invalid project UUID '{project_uuid}'"
        headings = things.tasks(type='heading', project=project_uuid)
    else:
        headings = things.tasks(type='heading')

    if not headings:
        return "No headings found"

    formatted_headings = [format_heading(heading) for heading in headings]
    return "\n\n---\n\n".join(formatted_headings)

# Search operations
@mcp.tool
async def search_todos(query: str) -> str:
    """Search todos by title or notes

    Args:
        query: Search term to look for in todo titles and notes
    """
    todos = things.search(query, include_items=True)
    if not todos:
        return f"No todos found matching '{query}'"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool
async def search_advanced(
    status: str = None,
    start_date: str = None,
    deadline: str = None,
    tag: str = None,
    area: str = None,
    type: str = None,
    last: str = None
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
    """
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
    if not todos:
        return "No matching todos found"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

# Recent items
@mcp.tool
async def get_recent(period: str) -> str:
    """Get recently created items

    Args:
        period: Time period (e.g., '3d', '1w', '2m', '1y')
    """
    todos = things.last(period, include_items=True)
    if not todos:
        return f"No items found in the last {period}"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

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
