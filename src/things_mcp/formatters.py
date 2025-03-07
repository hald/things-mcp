import logging
import things

logger = logging.getLogger(__name__)

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
            status = "✓" if item['status'] == 'completed' else "□"
            todo_text += f"\n  {status} {item['title']}"
    
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