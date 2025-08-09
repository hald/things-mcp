import urllib.parse
import webbrowser
import subprocess
import things
import json
from typing import Optional, Dict, Any, Union

def execute_url(url: str) -> None:
    """Execute a Things URL without bringing Things to the foreground."""
    try:
        subprocess.run([
            'osascript', '-e', 
            f'tell application "Things3" to open location "{url}"'
        ], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        # Fallback to webbrowser if osascript fails
        import webbrowser
        webbrowser.open(url)

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

def add_heading(project_id: str, title: str) -> str:
    """Construct URL to add a new heading to a project."""
    data = [{
        'type': 'project',
        'operation': 'update',
        'id': project_id,
        'attributes': {
            'items': [
                {
                    'type': 'heading',
                    'attributes': {'title': title}
                }
            ]
        }
    }]
    params = {
        'data': json.dumps(data, separators=(',', ':')),
        'auth-token': things.token()
    }
    return construct_url('json', params)

def update_todo(id: str, title: Optional[str] = None, notes: Optional[str] = None,
                when: Optional[str] = None, deadline: Optional[str] = None,
                tags: Optional[list[str]] = None, completed: Optional[bool] = None,
                canceled: Optional[bool] = None, list: Optional[str] = None,
                list_id: Optional[str] = None, heading: Optional[str] = None,
                heading_id: Optional[str] = None) -> str:
    """Construct URL to update an existing todo.
    
    Note: list_id takes precedence over list if both are provided.
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
