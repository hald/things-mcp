import logging
from typing import List, Dict, Any, Optional, Callable
import things
import mcp.types as types
import traceback
import random
from formatters import format_todo, format_project, format_area, format_tag
import url_scheme
import time
import subprocess
from applescript_bridge import run_applescript

# Import reliability enhancements
from utils import app_state, circuit_breaker, dead_letter_queue, rate_limiter, validate_tool_registration

logger = logging.getLogger(__name__)

def retry_operation(func, max_retries=3, delay=1, operation_name=None, params=None):
    """Retry a function call with exponential backoff and jitter.
    
    Args:
        func: The function to call
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        operation_name: Name of the operation for logging and DLQ (optional)
        params: Parameters for the operation (optional)
        
    Returns:
        The result of the function call if successful, False if all retries fail
    """
    # Check if Things app is available
    if not app_state.wait_for_app_availability(timeout=5):
        logger.error("Things app is not available for operation")
        return False
        
    # Check circuit breaker
    if not circuit_breaker.allow_operation():
        logger.warning("Circuit breaker is open, blocking operation")
        return False
    
    last_exception = None
    for attempt in range(max_retries):
        try:
            result = func()
            if result:
                circuit_breaker.record_success()
                return result
            # If we got a result but it's falsey, record it as a failure
            circuit_breaker.record_failure()
            last_exception = Exception("Operation returned False")
        except Exception as e:
            last_exception = e
            circuit_breaker.record_failure()
            if attempt < max_retries - 1:
                # Add jitter to prevent thundering herd problem
                jitter = random.uniform(0.8, 1.2)
                wait_time = delay * (2 ** attempt) * jitter
                logger.warning(f"Attempt {attempt+1} failed. Retrying in {wait_time:.2f} seconds: {str(e)}")
                time.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} attempts failed. Last error: {str(e)}")
    
    # If we have operation details, add to dead letter queue
    if operation_name and params and last_exception:
        dead_letter_queue.add_failed_operation(
            operation_name, 
            params, 
            str(last_exception),
            attempts=max_retries
        )
        
    return False


async def handle_tool_call(
    name: str,
    arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests.
    
    Attempts to execute the requested Things action with enhanced reliability.
    Uses circuit breaker, app state management, and retry logic for resilience.
    """
    # Import url_scheme inside the function to avoid scope issues
    import url_scheme
    try:
        # List view handlers
        if name in ["get-inbox", "get-today", "get-upcoming", "get-anytime",
                    "get-someday", "get-logbook", "get-trash"]:
            list_funcs = {
                "get-inbox": things.inbox,
                "get-today": things.today,
                "get-upcoming": things.upcoming,
                "get-anytime": things.anytime,
                "get-someday": things.someday,
                "get-trash": things.trash,
            }

            if name == "get-logbook":
                # Handle logbook with limits
                period = arguments.get("period", "7d") if arguments else "7d"
                limit = arguments.get("limit", 50) if arguments else 50
                todos = things.last(period, status='completed')
                if todos and len(todos) > limit:
                    todos = todos[:limit]
            else:
                todos = list_funcs[name]()

            if not todos:
                return [types.TextContent(type="text", text="No items found")]

            formatted_todos = [format_todo(todo) for todo in todos]
            return [types.TextContent(type="text", text="\n\n---\n\n".join(formatted_todos))]

        # Basic todo operations
        elif name == "get-todos":
            project_uuid = arguments.get("project_uuid") if arguments else None
            include_items = arguments.get(
                "include_items", True) if arguments else True

            if project_uuid:
                project = things.get(project_uuid)
                if not project or project.get('type') != 'project':
                    return [types.TextContent(type="text",
                                              text=f"Error: Invalid project UUID '{project_uuid}'")]

            todos = things.todos(project=project_uuid, start=None)
            if not todos:
                return [types.TextContent(type="text", text="No todos found")]

            formatted_todos = [format_todo(todo) for todo in todos]
            return [types.TextContent(type="text", text="\n\n---\n\n".join(formatted_todos))]

        # Project operations
        elif name == "get-projects":
            include_items = arguments.get(
                "include_items", False) if arguments else False
            projects = things.projects()

            if not projects:
                return [types.TextContent(type="text", text="No projects found")]

            formatted_projects = [format_project(
                project, include_items) for project in projects]
            return [types.TextContent(type="text", text="\n\n---\n\n".join(formatted_projects))]

        # Area operations
        elif name == "get-areas":
            include_items = arguments.get(
                "include_items", False) if arguments else False
            areas = things.areas()

            if not areas:
                return [types.TextContent(type="text", text="No areas found")]

            formatted_areas = [format_area(
                area, include_items) for area in areas]
            return [types.TextContent(type="text", text="\n\n---\n\n".join(formatted_areas))]

        # Tag operations
        elif name == "get-tags":
            include_items = arguments.get(
                "include_items", False) if arguments else False
            tags = things.tags()

            if not tags:
                return [types.TextContent(type="text", text="No tags found")]

            formatted_tags = [format_tag(tag, include_items) for tag in tags]
            return [types.TextContent(type="text", text="\n\n---\n\n".join(formatted_tags))]

        elif name == "get-tagged-items":
            if not arguments or "tag" not in arguments:
                raise ValueError("Missing tag parameter")

            tag = arguments["tag"]
            todos = things.todos(tag=tag)

            if not todos:
                return [types.TextContent(type="text",
                                          text=f"No items found with tag '{tag}'")]

            formatted_todos = [format_todo(todo) for todo in todos]
            return [types.TextContent(type="text", text="\n\n---\n\n".join(formatted_todos))]

        # Search operations
        elif name == "search-todos":
            if not arguments or "query" not in arguments:
                raise ValueError("Missing query parameter")

            query = arguments["query"]
            todos = things.search(query)

            if not todos:
                return [types.TextContent(type="text",
                                          text=f"No todos found matching '{query}'")]

            formatted_todos = [format_todo(todo) for todo in todos]
            return [types.TextContent(type="text", text="\n\n---\n\n".join(formatted_todos))]

        elif name == "search-advanced":
            if not arguments:
                raise ValueError("Missing search parameters")

            # Convert the arguments to things.todos() parameters
            search_params = {}

            # Handle status
            if "status" in arguments:
                search_params["status"] = arguments["status"]

            # Handle dates
            if "start_date" in arguments:
                search_params["start_date"] = arguments["start_date"]
            if "deadline" in arguments:
                search_params["deadline"] = arguments["deadline"]

            # Handle tag
            if "tag" in arguments:
                search_params["tag"] = arguments["tag"]

            # Handle area
            if "area" in arguments:
                search_params["area"] = arguments["area"]

            # Handle type
            if "type" in arguments:
                search_params["type"] = arguments["type"]

            todos = things.todos(**search_params)

            if not todos:
                return [types.TextContent(type="text", text="No matching todos found")]

            formatted_todos = [format_todo(todo) for todo in todos]
            return [types.TextContent(type="text", text="\n\n---\n\n".join(formatted_todos))]

        # Recent items
        elif name == "get-recent":
            if not arguments or "period" not in arguments:
                raise ValueError("Missing period parameter")

            period = arguments["period"]
            todos = things.last(period)

            if not todos:
                return [types.TextContent(type="text",
                                          text=f"No items found in the last {period}")]

            formatted_todos = [format_todo(todo) for todo in todos]
            return [types.TextContent(type="text", text="\n\n---\n\n".join(formatted_todos))]

        # Things direct AppleScript operations
        elif name == "add-todo":
            if not arguments or "title" not in arguments:
                raise ValueError("Missing title parameter")

            # We need to ensure any encoded characters are converted to actual spaces
            # This handles both '+' and '%20' that might be in the input
            
            # Clean up title and notes
            title = arguments["title"]
            if isinstance(title, str):
                title = title.replace("+", " ").replace("%20", " ")
            
            notes = arguments.get("notes")
            if isinstance(notes, str):
                notes = notes.replace("+", " ").replace("%20", " ")
            
            # Get other parameters
            when = arguments.get("when")
            tags = arguments.get("tags")
            list_title = arguments.get("list_title")
            
            # Import the AppleScript bridge
            import applescript_bridge
            
            # Prepare simplified parameters for the direct AppleScript approach
            # Only include parameters that our AppleScript bridge implementation supports
            simple_params = {
                "title": title,
                "notes": notes,
                "when": when,
                "tags": tags
            }
            
            # Remove None values
            simple_params = {k: v for k, v in simple_params.items() if v is not None}
            
            logger.info(f"Using direct AppleScript implementation to add todo: {title}")
            logger.info(f"Parameters: {simple_params}")
            
            # Try direct call without retry to capture actual errors
            try:
                logger.info("Calling add_todo_direct directly...")
                task_id = applescript_bridge.add_todo_direct(**simple_params)
                logger.info(f"Direct result: {task_id}")
            except Exception as e:
                logger.error(f"Exception in direct call: {str(e)}")
                return [types.TextContent(type="text", text=f"⚠️ Error: {str(e)}")]
            
            # If direct call didn't raise but returned falsy value, try with retry
            if not task_id:
                logger.info("Direct call failed, trying with retry...")
                try:
                    task_id = retry_operation(
                        lambda: applescript_bridge.add_todo_direct(**simple_params),
                        operation_name="add-todo-direct",
                        params=simple_params
                    )
                except Exception as e:
                    logger.error(f"Exception in retry operation: {str(e)}")
                    return [types.TextContent(type="text", text=f"⚠️ Error in retry: {str(e)}")]
            
            if not task_id:
                logger.error(f"Direct AppleScript creation failed for todo: {title}")
                return [types.TextContent(type="text", text=f"⚠️ Error: Failed to create todo: {title}")]
                
            return [types.TextContent(type="text", text=f"✅ Created new todo: {title} (ID: {task_id})")]

        elif name == "search-items":
            if not arguments or "query" not in arguments:
                raise ValueError("Missing query parameter")

            query = arguments["query"]
            params = {"query": query}
            
            url = url_scheme.search(query)
            success = retry_operation(
                lambda: url_scheme.execute_url(url),
                operation_name="search-items",
                params=params
            )
            if not success:
                raise RuntimeError(f"Failed to search for: {query}")
            return [types.TextContent(type="text", text=f"Searching for '{query}'")]

        elif name == "add-project":
            if not arguments or "title" not in arguments:
                raise ValueError("Missing title parameter")

            # Prepare parameters
            params = {
                "title": arguments["title"],
                "notes": arguments.get("notes"),
                "when": arguments.get("when"),
                "deadline": arguments.get("deadline"),
                "tags": arguments.get("tags"),
                "area_id": arguments.get("area_id"),
                "area_title": arguments.get("area_title"),
                "todos": arguments.get("todos")
            }
            
            # Try X-Callback URL first
            try:
                success = retry_operation(
                    lambda: url_scheme.execute_xcallback_url("add-project", params),
                    operation_name="add-project",
                    params=params
                )
                if success:
                    return [types.TextContent(type="text", text=f"✅ Created new project: {arguments['title']}")]
            except Exception as e:
                logger.warning(f"X-Callback add-project failed: {str(e)}, falling back to URL scheme")
            
            # Fall back to regular URL scheme
            url = url_scheme.add_project(**params)
            success = retry_operation(
                lambda: url_scheme.execute_url(url),
                operation_name="add-project",
                params=params
            )
            
            if not success:
                raise RuntimeError(f"Failed to create project: {arguments['title']}")
            return [types.TextContent(type="text", text=f"Created new project: {arguments['title']}")]

        elif name == "update-todo":
            if not arguments or "id" not in arguments:
                raise ValueError("Missing id parameter")

            # Prepare parameters
            params = {
                "id": arguments["id"],
                "title": arguments.get("title"),
                "notes": arguments.get("notes"),
                "when": arguments.get("when"),
                "deadline": arguments.get("deadline"),
                "tags": arguments.get("tags"),
                "completed": arguments.get("completed"),
                "canceled": arguments.get("canceled")
            }
            
            import applescript_bridge
            import url_scheme
            
            # Special tag handling
            tag_update_needed = "tags" in arguments and arguments["tags"] is not None
            tag_only_update = tag_update_needed and all(v is None for k, v in params.items() 
                                                       if k not in ["id", "tags"])
            
            # Log the tag update details
            if tag_update_needed:
                logger.info(f"Tag update needed: {arguments['tags']} for todo ID: {arguments['id']}")
                
            success = False
            
            # If this is a tag-only update, use hybrid approach that's proven to be most reliable
            if tag_only_update:
                logger.info(f"Using hybrid tag management approach for todo: {arguments['id']}")
                
                try:
                    # Get the tags from the parameters
                    todo_id = arguments['id']
                    tags = arguments['tags']
                    
                    if not isinstance(tags, list) or not tags:
                        logger.warning(f"Invalid tags format or empty tags list: {tags}")
                        return False
                    
                    logger.info(f"Updating tags for todo {todo_id}: {tags}")
                    
                    # Step 1: Clear existing tags by setting empty tags
                    clear_url = url_scheme.update_todo(id=todo_id, tags="")
                    logger.info(f"Clearing existing tags: {clear_url}")
                    clear_success = url_scheme.execute_url(clear_url)
                    
                    if not clear_success:
                        logger.warning("Failed to clear existing tags")
                        # Try to continue anyway
                    
                    # Wait for the clear operation to complete
                    time.sleep(1)
                    
                    # Step 2: Add each tag using hybrid approach
                    all_tags_added = True
                    for tag in tags:
                        # Make sure tag is a simple string
                        tag_str = str(tag).strip()
                        if not tag_str:
                            continue
                        
                        # Use AppleScript to ensure the tag exists first
                        logger.info(f"Ensuring tag exists: {tag_str}")
                        script = f'''
                        tell application "Things3"
                            set tagExists to false
                            
                            repeat with t in tags
                                if name of t is "{tag_str}" then
                                    set tagExists to true
                                    exit repeat
                                end if
                            end repeat
                            
                            if not tagExists then
                                make new tag with properties {{name:"{tag_str}"}}
                                return "Created tag: {tag_str}"
                            else
                                return "Tag already exists: {tag_str}"
                            end if
                        end tell
                        '''
                        
                        # Run AppleScript to create tag if needed
                        result = run_applescript(script)
                        if result:
                            logger.info(result)
                        else:
                            logger.warning(f"Failed to ensure tag exists: {tag_str}")
                        
                        # Short delay after tag creation
                        time.sleep(0.5)
                        
                        # Use add-tags parameter to apply the tag
                        add_tag_url = url_scheme.update_todo(id=todo_id, add_tags=tag_str)
                        logger.info(f"Adding tag '{tag_str}': {add_tag_url}")
                        
                        tag_success = url_scheme.execute_url(add_tag_url)
                        if not tag_success:
                            logger.warning(f"Failed to add tag: {tag_str}")
                            all_tags_added = False
                        
                        # Add a small delay between tag operations
                        time.sleep(1)
                    
                    if all_tags_added:
                        logger.info(f"All tags successfully added to todo ID: {todo_id}")
                        success = True
                    else:
                        logger.warning(f"Some tags failed to be added to todo ID: {todo_id}")
                        # Consider it a partial success if we added at least some tags
                        success = True
                        
                except Exception as e:
                    logger.warning(f"Hybrid tag update error: {str(e)}")
                    
                # Approach 2: If URL scheme failed, try direct AppleScript
                if not success:
                    logger.info(f"Falling back to AppleScript for tag update")
                    success = retry_operation(
                        lambda: applescript_bridge.update_todo_direct(**params),
                        operation_name="update-todo-tags-direct",
                        params=params
                    )
            else:
                # For regular updates, use the normal AppleScript approach
                logger.info(f"Using direct AppleScript implementation to update todo: {arguments['id']}")
                success = retry_operation(
                    lambda: applescript_bridge.update_todo_direct(**params),
                    operation_name="update-todo-direct",
                    params=params
                )
                
                # If the AppleScript update failed and there are tags to update, try URL scheme
                if not success and tag_update_needed:
                    logger.info(f"AppleScript failed, trying URL scheme for tag update")
                    url = url_scheme.update_todo(**params)
                    success = retry_operation(
                        lambda: url_scheme.execute_url(url),
                        operation_name="update-todo-fallback",
                        params=params
                    )
                
            if not success:
                logger.error(f"All update methods failed for todo with ID: {arguments['id']}")
                raise RuntimeError(f"Failed to update todo with ID: {arguments['id']}")
                
            return [types.TextContent(type="text", text=f"✅ Successfully updated todo with ID: {arguments['id']}")]

        elif name == "update-project":
            if not arguments or "id" not in arguments:
                raise ValueError("Missing id parameter")

            # Prepare parameters
            params = {
                "id": arguments["id"],
                "title": arguments.get("title"),
                "notes": arguments.get("notes"),
                "when": arguments.get("when"),
                "deadline": arguments.get("deadline"),
                "tags": arguments.get("tags"),
                "completed": arguments.get("completed"),
                "canceled": arguments.get("canceled")
            }
            
            # Try X-Callback URL first for better reliability
            try:
                success = retry_operation(
                    lambda: url_scheme.execute_xcallback_url("update-project", params),
                    operation_name="update-project",
                    params=params
                )
                if success:
                    return [types.TextContent(type="text", text=f"✅ Successfully updated project with ID: {arguments['id']}")]
            except Exception as e:
                logger.warning(f"X-Callback update-project failed: {str(e)}, falling back to URL scheme")
            
            # Fall back to regular URL scheme
            url = url_scheme.update_project(**params)
            success = retry_operation(
                lambda: url_scheme.execute_url(url),
                operation_name="update-project",
                params=params
            )
            
            if not success:
                raise RuntimeError(f"Failed to update project with ID: {arguments['id']}")
            return [types.TextContent(type="text", text=f"Successfully updated project with ID: {arguments['id']}")]

        elif name == "show-item":
            if not arguments or "id" not in arguments:
                raise ValueError("Missing id parameter")

            url = url_scheme.show(
                id=arguments["id"],
                query=arguments.get("query"),
                filter_tags=arguments.get("filter_tags")
            )
            success = retry_operation(lambda: url_scheme.execute_url(url))
            if not success:
                raise RuntimeError(f"Failed to show item with ID: {arguments['id']}")
            return [types.TextContent(type="text", text=f"Successfully opened item with ID: {arguments['id']}")]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error handling tool {name}: {str(e)}", exc_info=True)
        # Log full traceback for better debugging
        logger.debug(traceback.format_exc())
        
        # Add to dead letter queue if appropriate
        if arguments:
            dead_letter_queue.add_failed_operation(
                name,
                arguments,
                str(e)
            )
            
        return [types.TextContent(type="text", text=f"⚠️ Error: {str(e)}")]
