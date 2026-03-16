from typing import Callable, List
import logging
import os
import things
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from .formatters import format_todo, format_project, format_area, format_tag, format_heading
from .models import (
    ActionResult,
    ActionEnvelope,
    ItemListResult,
    ListEnvelope,
)
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


def _tool_list_result(
    *,
    items: list[dict],
    formatter: Callable[[dict], str],
    result_type,
    empty_message: str,
    invalid_message: str | None = None,
) -> ToolResult:
    if invalid_message:
        payload = result_type(success=False, message=invalid_message, count=0, error=invalid_message)
        return ToolResult(content=invalid_message, structured_content={"json": payload.model_dump()})

    if not items:
        payload = result_type(message=empty_message, count=0)
        return ToolResult(content=empty_message, structured_content={"json": payload.model_dump()})

    payload = result_type(
        message=f"Found {len(items)} item{'s' if len(items) != 1 else ''}",
        count=len(items),
        items=items,
    )
    text = "\n\n---\n\n".join(formatter(item) for item in items)
    return ToolResult(content=text, structured_content={"json": payload.model_dump()})


def _action_result(
    action: str,
    message: str,
    *,
    title: str | None = None,
    target_id: str | None = None,
) -> ToolResult:
    payload = ActionResult(
        action=action,
        message=message,
        title=title,
        target_id=target_id,
    )
    return ToolResult(content=message, structured_content={"json": payload.model_dump()})

# List view tools
@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_inbox() -> ToolResult:
    """Get todos from Inbox"""
    todos = things.inbox(include_items=True)
    return _tool_list_result(
        items=todos,
        formatter=format_todo,
        result_type=ItemListResult,
        empty_message="No items found",
    )

@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_today() -> ToolResult:
    """Get todos due today"""
    todos = things.today(include_items=True)
    # Filter out tasks from Someday projects
    todos = filter_someday_project_tasks(todos)
    return _tool_list_result(
        items=todos,
        formatter=format_todo,
        result_type=ItemListResult,
        empty_message="No items found",
    )

@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_upcoming() -> ToolResult:
    """Get upcoming todos"""
    todos = things.upcoming(include_items=True)
    # Filter out tasks from Someday projects
    todos = filter_someday_project_tasks(todos)
    return _tool_list_result(
        items=todos,
        formatter=format_todo,
        result_type=ItemListResult,
        empty_message="No items found",
    )

@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_anytime() -> ToolResult:
    """Get todos from Anytime list"""
    todos = things.anytime(include_items=True)
    # Filter out tasks from Someday projects
    todos = filter_someday_project_tasks(todos)
    return _tool_list_result(
        items=todos,
        formatter=format_todo,
        result_type=ItemListResult,
        empty_message="No items found",
    )

@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_someday() -> ToolResult:
    """Get todos from Someday list, including tasks in Someday projects"""
    todos = things.someday(include_items=True)
    if todos is None:
        todos = []
    # Also include tasks that have start="Anytime" but belong to a Someday project
    # (directly or via a heading), since Things.py doesn't inherit project Someday status
    someday_project_ids, heading_to_project = _get_someday_context()
    if someday_project_ids:
        anytime_todos = things.anytime(include_items=True) or []
        existing_uuids = {t['uuid'] for t in todos}
        for todo in anytime_todos:
            if _is_in_someday_project(todo, someday_project_ids, heading_to_project) and todo['uuid'] not in existing_uuids:
                todos.append(todo)
    return _tool_list_result(
        items=todos,
        formatter=format_todo,
        result_type=ItemListResult,
        empty_message="No items found",
    )

@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_logbook(period: str = "7d", limit: int = 50) -> ToolResult:
    """Get completed todos from Logbook, defaults to last 7 days

    Args:
        period: Time period to look back (e.g., '3d', '1w', '2m', '1y'). Defaults to '7d'
        limit: Maximum number of entries to return. Defaults to 50
    """
    todos = things.last(period, status='completed', include_items=True)
    if todos and len(todos) > limit:
        todos = todos[:limit]
    return _tool_list_result(
        items=todos,
        formatter=format_todo,
        result_type=ItemListResult,
        empty_message="No items found",
    )

@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_trash() -> ToolResult:
    """Get trashed todos"""
    todos = things.trash(include_items=True)
    return _tool_list_result(
        items=todos,
        formatter=format_todo,
        result_type=ItemListResult,
        empty_message="No items found",
    )

# Basic operations
@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_todos(project_uuid: str = None, include_items: bool = True) -> ToolResult:
    """Get todos from Things, optionally filtered by project

    Args:
        project_uuid: Optional UUID of a specific project to get todos from
        include_items: Include checklist items
    """
    if project_uuid:
        project = things.get(project_uuid)
        if not project or project.get('type') != 'project':
            message = f"Error: Invalid project UUID '{project_uuid}'"
            return _tool_list_result(
                items=[],
                formatter=format_todo,
                result_type=ItemListResult,
                empty_message="No todos found",
                invalid_message=message,
            )

    todos = things.todos(project=project_uuid, start=None, include_items=include_items)
    return _tool_list_result(
        items=todos,
        formatter=format_todo,
        result_type=ItemListResult,
        empty_message="No todos found",
    )

@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_projects(include_items: bool = False) -> ToolResult:
    """Get all projects from Things

    Args:
        include_items: Include tasks within projects
    """
    projects = things.projects(include_items=include_items)
    return _tool_list_result(
        items=projects,
        formatter=lambda project: format_project(project, include_items),
        result_type=ItemListResult,
        empty_message="No projects found",
    )

@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_areas(include_items: bool = False) -> ToolResult:
    """Get all areas from Things

    Args:
        include_items: Include projects and tasks within areas
    """
    areas = things.areas(include_items=include_items)
    return _tool_list_result(
        items=areas,
        formatter=lambda area: format_area(area, include_items),
        result_type=ItemListResult,
        empty_message="No areas found",
    )

# Tag operations
@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_tags(include_items: bool = False) -> ToolResult:
    """Get all tags

    Args:
        include_items: Include items tagged with each tag
    """
    tags = things.tags(include_items=include_items)
    return _tool_list_result(
        items=tags,
        formatter=lambda tag: format_tag(tag, include_items),
        result_type=ItemListResult,
        empty_message="No tags found",
    )

@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_tagged_items(tag: str) -> ToolResult:
    """Get items with a specific tag

    Args:
        tag: Tag title to filter by
    """
    todos = things.todos(tag=tag, include_items=True)
    return _tool_list_result(
        items=todos,
        formatter=format_todo,
        result_type=ItemListResult,
        empty_message=f"No items found with tag '{tag}'",
    )

@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_headings(project_uuid: str = None) -> ToolResult:
    """Get headings from Things

    Args:
        project_uuid: Optional UUID of a specific project to get headings from
    """
    if project_uuid:
        project = things.get(project_uuid)
        if not project or project.get('type') != 'project':
            message = f"Error: Invalid project UUID '{project_uuid}'"
            return _tool_list_result(
                items=[],
                formatter=format_heading,
                result_type=ItemListResult,
                empty_message="No headings found",
                invalid_message=message,
            )
        headings = things.tasks(type='heading', project=project_uuid)
    else:
        headings = things.tasks(type='heading')

    return _tool_list_result(
        items=headings,
        formatter=format_heading,
        result_type=ItemListResult,
        empty_message="No headings found",
    )

# Search operations
@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def search_todos(query: str) -> ToolResult:
    """Search todos by title or notes

    Args:
        query: Search term to look for in todo titles and notes
    """
    todos = things.search(query, include_items=True)
    return _tool_list_result(
        items=todos,
        formatter=format_todo,
        result_type=ItemListResult,
        empty_message=f"No todos found matching '{query}'",
    )

@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def search_advanced(
    status: str = None,
    start_date: str = None,
    deadline: str = None,
    tag: str = None,
    area: str = None,
    type: str = None,
    last: str = None
) -> ToolResult:
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
    return _tool_list_result(
        items=todos,
        formatter=format_todo,
        result_type=ItemListResult,
        empty_message="No matching todos found",
    )

# Recent items
@mcp.tool(output_schema=ListEnvelope.model_json_schema())
async def get_recent(period: str) -> ToolResult:
    """Get recently created items

    Args:
        period: Time period (e.g., '3d', '1w', '2m', '1y')
    """
    todos = things.last(period, include_items=True)
    return _tool_list_result(
        items=todos,
        formatter=format_todo,
        result_type=ItemListResult,
        empty_message=f"No items found in the last {period}",
    )

# Things URL Scheme tools
@mcp.tool(output_schema=ActionEnvelope.model_json_schema())
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
) -> ToolResult:
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
    return _action_result("create", f"Created new todo: {title}", title=title)

@mcp.tool(output_schema=ActionEnvelope.model_json_schema())
async def add_project(
    title: str,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    tags: List[str] = None,
    area_id: str = None,
    area_title: str = None,
    todos: List[str] = None
) -> ToolResult:
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
    return _action_result("create", f"Created new project: {title}", title=title)

@mcp.tool(output_schema=ActionEnvelope.model_json_schema())
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
) -> ToolResult:
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
    return _action_result("update", f"Updated todo with ID: {id}", target_id=id)

@mcp.tool(output_schema=ActionEnvelope.model_json_schema())
async def update_project(
    id: str,
    title: str = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    tags: List[str] = None,
    completed: bool = None,
    canceled: bool = None
) -> ToolResult:
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
    return _action_result("update", f"Updated project with ID: {id}", target_id=id)

@mcp.tool(output_schema=ActionEnvelope.model_json_schema())
async def show_item(
    id: str,
    query: str = None,
    filter_tags: List[str] = None
) -> ToolResult:
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
    return _action_result("show", f"Showing item: {id}", target_id=id)

@mcp.tool(output_schema=ActionEnvelope.model_json_schema())
async def search_items(query: str) -> ToolResult:
    """Search for items in Things

    Args:
        query: Search query
    """
    url = url_scheme.search(query)
    url_scheme.execute_url(url)
    return _action_result("search", f"Searching for '{query}'", title=query)


def main():
    """Main entry point for the Things MCP server."""
    if TRANSPORT == "http":
        mcp.run(transport="http", host=HTTP_HOST, port=HTTP_PORT)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
