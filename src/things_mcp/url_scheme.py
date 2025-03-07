import urllib.parse
import webbrowser
import things
import subprocess
import platform
import random
import time
import logging
import json
from typing import Optional, Dict, Any, Union, Callable
from utils import app_state, circuit_breaker, dead_letter_queue, rate_limiter, is_things_running

logger = logging.getLogger(__name__)
        
def launch_things() -> bool:
    """Launch Things app if not already running.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if is_things_running():
            return True
            
        result = subprocess.run(
            ['open', '-a', 'Things3'],
            capture_output=True,
            text=True,
            check=False
        )
        
        # Give Things time to launch
        time.sleep(2)
        
        return is_things_running()
    except Exception as e:
        logger.error(f"Error launching Things: {str(e)}")
        return False

def execute_url(url: str) -> bool:
    """Execute a Things URL by opening it in the default browser.
    Returns True if successful, False otherwise.
    """
    # Ensure any + signs in the URL are replaced with %20
    url = url.replace("+", "%20")
    
    # Log the URL for debugging
    logger.debug(f"Executing URL: {url}")
    
    # Apply rate limiting
    rate_limiter.wait_if_needed()
    
    # Check if circuit breaker allows the operation
    if not circuit_breaker.allow_operation():
        logger.warning("Circuit breaker is open, blocking operation")
        return False
    
    try:
        # Check if Things is running, attempt to launch if not
        if not is_things_running():
            logger.info("Things is not running, attempting to launch")
            if not launch_things():
                logger.error("Failed to launch Things")
                circuit_breaker.record_failure()
                return False
        
        # Execute the URL
        result = webbrowser.open(url)
        
        if not result:
            circuit_breaker.record_failure()
            logger.error(f"Failed to open URL: {url}")
            return False
        
        # Add a small delay to allow Things time to process the command
        # Add jitter to prevent thundering herd problem
        delay = 0.5 + random.uniform(0, 0.2)  # 0.5-0.7 seconds
        time.sleep(delay)
        
        circuit_breaker.record_success()
        return True
    except Exception as e:
        logger.error(f"Failed to execute URL: {url}, Error: {str(e)}")
        circuit_breaker.record_failure()
        return False


def execute_xcallback_url(action: str, params: Dict[str, Any]) -> bool:
    """Execute a Things X-Callback-URL.
    
    Args:
        action: The X-Callback action to perform
        params: Parameters for the action
        
    Returns:
        bool: True if successful, False otherwise
    """
    # The correct format for Things URLs (no 'x-callback-url/' prefix)
    base_url = "things:///"
    
    # Add callback parameters, but only if we need them
    # For now, avoid using callbacks since we don't have a handler for them
    callback_params = params.copy()
    
    # Don't add callback URLs - this avoids the "no application set to open URL" error
    # If we need callbacks later, we'd need to register a URL handler for our app
    
    # Construct URL - action is part of the path (not a separate query parameter)
    url = f"{base_url}{action}?{urllib.parse.urlencode(callback_params)}"
    
    # Log the URL for debugging
    logger.debug(f"Executing URL: {url}")
    
    return execute_url(url)

def construct_url(command: str, params: Dict[str, Any]) -> str:
    """Construct a Things URL from command and parameters."""
    # Pre-process all string parameters to replace any + signs with spaces
    cleaned_params = {}
    for key, value in params.items():
        if isinstance(value, str):
            # Replace any + signs with spaces in the original input
            cleaned_params[key] = value.replace("+", " ")
        else:
            cleaned_params[key] = value
    
    # Use the cleaned params from now on
    params = cleaned_params
    
    # Start with base URL
    url = f"things:///{command}"
    
    # Get authentication token if needed - applies to all commands to ensure reliability
    try:
        # Import here to avoid circular imports
        import config
        
        # Get token from config system
        token = config.get_things_auth_token()
        
        if token:
            # Add token to all params for consistent behavior
            params['auth-token'] = token
            logger.debug(f"Auth token from config used for {command} operation")
        else:
            logger.warning(f"No Things auth token found in config. URL may not work without a token.")
            # Note: We continue without a token, which may cause the operation to fail
    except Exception as e:
        logger.error(f"Error getting auth token: {str(e)}")
        # Continue without token - the operation may fail
    
    # Disable JSON API for now as it's causing formatting issues
    # JSON API is currently experimental and unreliable
    # We'll use the standard URL scheme instead which is more reliable
    use_json_api = False
    
    if False and command in ['add'] and use_json_api:
        # This code is disabled but kept for reference
        logger.info("JSON API is currently disabled due to formatting issues")
        pass
    
    # Standard URL scheme encoding
    if params:
        encoded_params = []
        for key, value in params.items():
            if value is None:
                continue
            # Handle boolean values
            if isinstance(value, bool):
                value = str(value).lower()
            # Handle lists (for tags, checklist items etc)
            elif isinstance(value, list) and key == 'tags':
                # Important: Tags are sensitive to formatting in Things URL scheme
                # Based on testing, using a simple comma-separated list without spaces works best
                encoded_tags = []
                for tag in value:
                    # Ensure tag is properly encoded as string
                    tag_str = str(tag).strip()
                    if tag_str:  # Only add non-empty tags
                        encoded_tags.append(tag_str)
                
                # Only include non-empty tag lists
                if encoded_tags:
                    # Join with commas - Things expects comma-separated tags without spaces between commas
                    # Use a simple comma with no spacing for maximum compatibility
                    value = ','.join(encoded_tags)
                else:
                    # If no valid tags, don't include this parameter
                    continue
            # Handle other lists
            elif isinstance(value, list):
                value = ','.join(str(v) for v in value)
            
            # Ensure proper encoding of the value - use quote_plus to handle spaces correctly
            # Then replace + with %20 to ensure Things handles spaces correctly
            encoded_value = urllib.parse.quote(str(value), safe='')
            # Replace + with %20 for better compatibility with Things
            encoded_value = encoded_value.replace('+', '%20')
            encoded_params.append(f"{key}={encoded_value}")
        
        url += "?" + "&".join(encoded_params)
    
    return url


def should_use_json_api() -> bool:
    """Determine if the JSON API should be used based on Things version."""
    from utils import detect_things_version
    
    version = detect_things_version()
    if not version:
        # Default to using JSON API if version can't be determined
        return True
    
    try:
        # Parse version string (e.g., '3.15.4')
        major, minor, _ = map(int, version.split('.'))
        
        # JSON API is available in Things 3.4+
        return major > 3 or (major == 3 and minor >= 4)
    except Exception:
        # Default to standard URL scheme if version parsing fails
        return False

def add_todo(title: str, notes: Optional[str] = None, when: Optional[str] = None,
             deadline: Optional[str] = None, tags: Optional[list[str]] = None,
             checklist_items: Optional[list[str]] = None, list_id: Optional[str] = None,
             list_title: Optional[str] = None, heading: Optional[str] = None,
             completed: Optional[bool] = None) -> str:
    """Construct URL to add a new todo."""
    params = {
        'title': title,
        'notes': notes,
        'when': when,
        'deadline': deadline,
        'checklist-items': '\n'.join(checklist_items) if checklist_items else None,
        'list-id': list_id,
        'list': list_title,
        'heading': heading,
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
    """Construct URL to add a new project."""
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
                tags: Optional[Union[list[str], str]] = None, add_tags: Optional[Union[list[str], str]] = None, 
                checklist_items: Optional[list[str]] = None,
                completed: Optional[bool] = None, canceled: Optional[bool] = None) -> str:
    """Construct URL to update an existing todo."""
    params = {
        'id': id,
        'title': title,
        'notes': notes,
        'when': when,
        'deadline': deadline,
        'tags': tags,
        'add-tags': add_tags,  # Support for adding tags without replacing existing ones
        'checklist-items': '\n'.join(checklist_items) if checklist_items else None,
        'completed': completed,
        'canceled': canceled
    }
    return construct_url('update', {k: v for k, v in params.items() if v is not None})

def update_project(id: str, title: Optional[str] = None, notes: Optional[str] = None,
                   when: Optional[str] = None, deadline: Optional[str] = None,
                   tags: Optional[list[str]] = None, completed: Optional[bool] = None,
                   canceled: Optional[bool] = None) -> str:
    """Construct URL to update an existing project."""
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