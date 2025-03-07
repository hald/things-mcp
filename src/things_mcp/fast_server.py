#!/usr/bin/env python3
"""
Things MCP Server implementation using the FastMCP pattern.
This provides a more modern and maintainable approach to the Things integration.
"""
import logging
import asyncio
import traceback
from typing import Dict, Any, Optional, List, Union
import things

from mcp.server.fastmcp import FastMCP
import mcp.types as types

# Import supporting modules
from .formatters import format_todo, format_project, format_area, format_tag
from .utils import app_state, circuit_breaker, dead_letter_queue, rate_limiter
from .url_scheme import (
    add_todo, add_project, update_todo, update_project, show, 
    search, launch_things, execute_url
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create the FastMCP server
mcp = FastMCP(
    "Things", 
    description="Interact with the Things task management app",
    version="0.1.1"
)

# LIST VIEWS

@mcp.tool(name="get-inbox")
def get_inbox() -> str:
    """Get todos from Inbox"""
    todos = things.inbox()
    
    if not todos:
        return "No items found in Inbox"
    
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool(name="get-today")
def get_today() -> str:
    """Get todos due today"""
    todos = things.today()
    
    if not todos:
        return "No items due today"
    
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool(name="get-upcoming")
def get_upcoming() -> str:
    """Get upcoming todos"""
    todos = things.upcoming()
    
    if not todos:
        return "No upcoming items"
    
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool(name="get-anytime")
def get_anytime() -> str:
    """Get todos from Anytime list"""
    todos = things.anytime()
    
    if not todos:
        return "No items in Anytime list"
    
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool(name="get-someday")
def get_someday() -> str:
    """Get todos from Someday list"""
    todos = things.someday()
    
    if not todos:
        return "No items in Someday list"
    
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool(name="get-logbook")
def get_logbook(period: str = "7d", limit: int = 50) -> str:
    """
    Get completed todos from Logbook, defaults to last 7 days
    
    Args:
        period: Time period to look back (e.g., '3d', '1w', '2m', '1y'). Defaults to '7d'
        limit: Maximum number of entries to return. Defaults to 50
    """
    todos = things.last(period, status='completed')
    
    if not todos:
        return "No completed items found"
    
    if todos and len(todos) > limit:
        todos = todos[:limit]
        
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool(name="get-trash")
def get_trash() -> str:
    """Get trashed todos"""
    todos = things.trash()
    
    if not todos:
        return "No items in trash"
    
    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

# BASIC TODO OPERATIONS

@mcp.tool(name="get-todos")
def get_todos(project_uuid: Optional[str] = None, include_items: bool = True) -> str:
    """
    Get todos from Things, optionally filtered by project
    
    Args:
        project_uuid: Optional UUID of a specific project to get todos from
        include_items: Include checklist items
    """
    if project_uuid:
        project = things.get(project_uuid)
        if not project or project.get('type') != 'project':
            return f"Error: Invalid project UUID '{project_uuid}'"

    todos = things.todos(project=project_uuid, start=None)
    
    if not todos:
        return "No todos found"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool(name="get-projects")
def get_projects(include_items: bool = False) -> str:
    """
    Get all projects from Things
    
    Args:
        include_items: Include tasks within projects
    """
    projects = things.projects()

    if not projects:
        return "No projects found"

    formatted_projects = [format_project(project, include_items) for project in projects]
    return "\n\n---\n\n".join(formatted_projects)

@mcp.tool(name="get-areas")
def get_areas(include_items: bool = False) -> str:
    """
    Get all areas from Things
    
    Args:
        include_items: Include projects and tasks within areas
    """
    areas = things.areas()

    if not areas:
        return "No areas found"

    formatted_areas = [format_area(area, include_items) for area in areas]
    return "\n\n---\n\n".join(formatted_areas)

# TAG OPERATIONS

@mcp.tool(name="get-tags")
def get_tags(include_items: bool = False) -> str:
    """
    Get all tags
    
    Args:
        include_items: Include items tagged with each tag
    """
    tags = things.tags()

    if not tags:
        return "No tags found"

    formatted_tags = [format_tag(tag, include_items) for tag in tags]
    return "\n\n---\n\n".join(formatted_tags)

@mcp.tool(name="get-tagged-items")
def get_tagged_items(tag: str) -> str:
    """
    Get items with a specific tag
    
    Args:
        tag: Tag title to filter by
    """
    todos = things.todos(tag=tag)

    if not todos:
        return f"No items found with tag '{tag}'"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

# SEARCH OPERATIONS

@mcp.tool(name="search-todos")
def search_todos(query: str) -> str:
    """
    Search todos by title or notes
    
    Args:
        query: Search term to look for in todo titles and notes
    """
    todos = things.search(query)

    if not todos:
        return f"No todos found matching '{query}'"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)

@mcp.tool(name="search-advanced")
def search_advanced(
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    deadline: Optional[str] = None,
    tag: Optional[str] = None,
    area: Optional[str] = None,
    type: Optional[str] = None
) -> str:
    """
    Advanced todo search with multiple filters
    
    Args:
        status: Filter by todo status (incomplete/completed/canceled)
        start_date: Filter by start date (YYYY-MM-DD)
        deadline: Filter by deadline (YYYY-MM-DD)
        tag: Filter by tag
        area: Filter by area UUID
        type: Filter by item type (to-do/project/heading)
    """
    # Build filter parameters
    kwargs = {}
    
    # Add filters that are provided
    if status:
        kwargs['status'] = status
    if deadline:
        kwargs['deadline'] = deadline
    if start_date:
        kwargs['start'] = start_date
    if tag:
        kwargs['tag'] = tag
    if area:
        kwargs['area'] = area
    if type:
        kwargs['type'] = type
        
    # Execute search with applicable filters
    try:
        todos = things.todos(**kwargs)
        
        if not todos:
            return "No items found matching your search criteria"
            
        formatted_todos = [format_todo(todo) for todo in todos]
        return "\n\n---\n\n".join(formatted_todos)
    except Exception as e:
        return f"Error in advanced search: {str(e)}"

# MODIFICATION OPERATIONS

@mcp.tool(name="add-todo")
def add_task(
    title: str,
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[List[str]] = None,
    checklist_items: Optional[List[str]] = None,
    list_id: Optional[str] = None,
    list_title: Optional[str] = None,
    heading: Optional[str] = None
) -> str:
    """
    Create a new todo in Things
    
    Args:
        title: Title of the todo
        notes: Notes for the todo
        when: When to schedule the todo (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD)
        deadline: Deadline for the todo (YYYY-MM-DD)
        tags: Tags to apply to the todo
        checklist_items: Checklist items to add
        list_id: ID of project/area to add to
        list_title: Title of project/area to add to
        heading: Heading to add under
    """
    try:
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                return "Error: Unable to launch Things app"
                
        # Execute the add_todo URL command
        result = add_todo(
            title=title,
            notes=notes,
            when=when,
            deadline=deadline,
            tags=tags,
            checklist_items=checklist_items,
            list_id=list_id,
            list_title=list_title,
            heading=heading
        )
        
        if not result:
            return "Error: Failed to create todo"
            
        return f"Successfully created todo: {title}"
    except Exception as e:
        logger.error(f"Error creating todo: {str(e)}")
        return f"Error creating todo: {str(e)}"

@mcp.tool(name="add-project")
def add_new_project(
    title: str,
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[List[str]] = None,
    area_id: Optional[str] = None,
    area_title: Optional[str] = None,
    todos: Optional[List[str]] = None
) -> str:
    """
    Create a new project in Things
    
    Args:
        title: Title of the project
        notes: Notes for the project
        when: When to schedule the project
        deadline: Deadline for the project
        tags: Tags to apply to the project
        area_id: ID of area to add to
        area_title: Title of area to add to
        todos: Initial todos to create in the project
    """
    try:
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                return "Error: Unable to launch Things app"
                
        # Execute the add_project URL command
        result = add_project(
            title=title,
            notes=notes,
            when=when,
            deadline=deadline,
            tags=tags,
            area_id=area_id,
            area_title=area_title,
            todos=todos
        )
        
        if not result:
            return "Error: Failed to create project"
            
        return f"Successfully created project: {title}"
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        return f"Error creating project: {str(e)}"

@mcp.tool(name="update-todo")
def update_task(
    id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[List[str]] = None,
    completed: Optional[bool] = None,
    canceled: Optional[bool] = None
) -> str:
    """
    Update an existing todo in Things
    
    Args:
        id: ID of the todo to update
        title: New title
        notes: New notes
        when: New schedule
        deadline: New deadline
        tags: New tags
        completed: Mark as completed
        canceled: Mark as canceled
    """
    try:
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                return "Error: Unable to launch Things app"
                
        # Execute the update_todo URL command
        result = update_todo(
            id=id,
            title=title,
            notes=notes,
            when=when,
            deadline=deadline,
            tags=tags,
            completed=completed,
            canceled=canceled
        )
        
        if not result:
            return "Error: Failed to update todo"
            
        return f"Successfully updated todo with ID: {id}"
    except Exception as e:
        logger.error(f"Error updating todo: {str(e)}")
        return f"Error updating todo: {str(e)}"

@mcp.tool(name="update-project")
def update_existing_project(
    id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[List[str]] = None,
    completed: Optional[bool] = None,
    canceled: Optional[bool] = None
) -> str:
    """
    Update an existing project in Things
    
    Args:
        id: ID of the project to update
        title: New title
        notes: New notes
        when: New schedule
        deadline: New deadline
        tags: New tags
        completed: Mark as completed
        canceled: Mark as canceled
    """
    try:
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                return "Error: Unable to launch Things app"
                
        # Execute the update_project URL command
        result = update_project(
            id=id,
            title=title,
            notes=notes,
            when=when,
            deadline=deadline,
            tags=tags,
            completed=completed,
            canceled=canceled
        )
        
        if not result:
            return "Error: Failed to update project"
            
        return f"Successfully updated project with ID: {id}"
    except Exception as e:
        logger.error(f"Error updating project: {str(e)}")
        return f"Error updating project: {str(e)}"

@mcp.tool(name="show-item")
def show_item(
    id: str,
    query: Optional[str] = None,
    filter_tags: Optional[List[str]] = None
) -> str:
    """
    Show a specific item or list in Things
    
    Args:
        id: ID of item to show, or one of: inbox, today, upcoming, anytime, someday, logbook
        query: Optional query to filter by
        filter_tags: Optional tags to filter by
    """
    try:
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                return "Error: Unable to launch Things app"
                
        # Execute the show URL command
        result = show(
            id=id,
            query=query,
            filter_tags=filter_tags
        )
        
        if not result:
            return f"Error: Failed to show item/list '{id}'"
            
        return f"Successfully opened '{id}' in Things"
    except Exception as e:
        logger.error(f"Error showing item: {str(e)}")
        return f"Error showing item: {str(e)}"

@mcp.tool(name="search-items")
def search_all_items(query: str) -> str:
    """
    Search for items in Things
    
    Args:
        query: Search query
    """
    try:
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                return "Error: Unable to launch Things app"
                
        # Execute the search URL command
        result = search(query=query)
        
        if not result:
            return f"Error: Failed to search for '{query}'"
            
        return f"Successfully searched for '{query}' in Things"
    except Exception as e:
        logger.error(f"Error searching: {str(e)}")
        return f"Error searching: {str(e)}"

@mcp.tool(name="get-recent")
def get_recent(period: str) -> str:
    """
    Get recently created items
    
    Args:
        period: Time period (e.g., '3d', '1w', '2m', '1y')
    """
    try:
        # Check if period format is valid
        if not period or not any(period.endswith(unit) for unit in ['d', 'w', 'm', 'y']):
            return "Error: Period must be in format '3d', '1w', '2m', '1y'"
            
        # Get recent items
        items = things.last(period)
        
        if not items:
            return f"No items found in the last {period}"
            
        formatted_items = []
        for item in items:
            if item.get('type') == 'to-do':
                formatted_items.append(format_todo(item))
            elif item.get('type') == 'project':
                formatted_items.append(format_project(item, include_items=False))
                
        return "\n\n---\n\n".join(formatted_items)
    except Exception as e:
        logger.error(f"Error getting recent items: {str(e)}")
        return f"Error getting recent items: {str(e)}"

# Main entry point
def run_things_mcp_server():
    """Run the Things MCP server"""
    # Check if Things app is available
    if not app_state.update_app_state():
        logger.warning("Things app is not running at startup. MCP will attempt to launch it when needed.")
        try:
            # Try to launch Things
            if launch_things():
                logger.info("Successfully launched Things app")
            else:
                logger.error("Unable to launch Things app. Some operations may fail.")
        except Exception as e:
            logger.error(f"Error launching Things app: {str(e)}")
    else:
        logger.info("Things app is running and ready for operations")
        
    # Run the MCP server
    mcp.run()

if __name__ == "__main__":
    run_things_mcp_server()
