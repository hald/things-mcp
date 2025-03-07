"""
Utility classes and functions for enhancing Things MCP reliability.
"""
import json
import time
import logging
import os
import platform
import subprocess
import urllib.parse
import mcp.types as types
from typing import Dict, Any, Optional, Callable, List, Union

logger = logging.getLogger(__name__)


def is_things_running() -> bool:
    """Check if Things app is running.
    
    Returns:
        bool: True if Things is running, False otherwise
    """
    try:
        if platform.system() != 'Darwin':
            logger.warning("Things availability check only works on macOS")
            return True
            
        result = subprocess.run(
            ['osascript', '-e', 'tell application "System Events" to (name of processes) contains "Things3"'],
            capture_output=True,
            text=True,
            check=False
        )
        is_running = result.stdout.strip().lower() == 'true'
        
        # If Things is running, also check if it's responsive
        if is_running:
            # Simple ping to see if Things responds
            ping_result = subprocess.run(
                ['osascript', '-e', 'tell application "Things3" to return name'],
                capture_output=True,
                text=True,
                check=False,
                timeout=2  # 2 second timeout
            )
            is_responsive = ping_result.returncode == 0
            
            if not is_responsive:
                logger.warning("Things is running but not responsive")
                return False
                
        return is_running
    except subprocess.TimeoutExpired:
        logger.warning("Things app check timed out")
        return False
    except Exception as e:
        logger.error(f"Error checking if Things is running: {str(e)}")
        return False

class ThingsAppState:
    """Track and manage Things app state"""
    
    def __init__(self):
        self.is_available = False
        self.last_check_time = 0
        self.check_interval = 5  # seconds
        self.update_app_state()
    
    def update_app_state(self):
        """Update app availability state"""
        current_time = time.time()
        if current_time - self.last_check_time > self.check_interval:
            self.is_available = is_things_running()
            self.last_check_time = current_time
        return self.is_available
    
    def wait_for_app_availability(self, timeout=10):
        """Wait for app to become available within timeout"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.update_app_state():
                return True
            time.sleep(0.5)
        return False


def validate_tool_registration(tools: list[types.Tool]) -> bool:
    """
    Validate that all required Things MCP tools are properly registered.
    
    Args:
        tools: List of registered tools
        
    Returns:
        bool: True if all required tools are registered, False otherwise
    """
    required_tool_names = [
        "get-inbox", "get-today", "get-upcoming", "get-anytime",
        "get-someday", "get-logbook", "get-trash", "get-todos",
        "get-projects", "get-areas", "get-tags", "get-tagged-items",
        "search-todos", "search-advanced", "get-recent", "add-todo",
        "search-items", "add-project", "update-todo", "update-project", "show-item"
    ]
    
    registered_tool_names = [tool.name for tool in tools]
    
    # Check if all required tools are registered
    missing_tools = [name for name in required_tool_names if name not in registered_tool_names]
    
    if missing_tools:
        logger.error(f"Missing required tool registrations: {missing_tools}")
        return False
        
    # Check if all registered tools have proper descriptions and parameters
    for tool in tools:
        if not tool.description or len(tool.description) < 10:
            logger.warning(f"Tool '{tool.name}' has an insufficient description")
        
        # Basic parameter validation could be added here
        # This would depend on your tool schema requirements
    
    return True


class CircuitBreaker:
    """Circuit breaker to prevent repeated failed attempts"""
    
    # Circuit states
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Not allowing operations
    HALF_OPEN = "half-open"  # Testing if system has recovered
    
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.state = self.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = 0
    
    def record_failure(self):
        """Record a failure and potentially open the circuit"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def record_success(self):
        """Record a success and reset the circuit if in half-open state"""
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
            self.failure_count = 0
            logger.info("Circuit breaker closed after successful operation")
        elif self.state == self.CLOSED:
            self.failure_count = 0
    
    def allow_operation(self):
        """Check if operation should be allowed"""
        if self.state == self.CLOSED:
            return True
        
        if self.state == self.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = self.HALF_OPEN
                logger.info("Circuit breaker half-open, testing system recovery")
                return True
            return False
        
        # Half-open state allows a single test operation
        return True


class DeadLetterQueue:
    """Store persistently failed operations for manual review"""
    
    def __init__(self, dlq_file="things_dlq.json"):
        self.dlq_file = dlq_file
        self.queue = self._load_queue()
        
    def _load_queue(self):
        """Load persisted queue"""
        try:
            if os.path.exists(self.dlq_file):
                with open(self.dlq_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading DLQ: {str(e)}")
            return []
    
    def _save_queue(self):
        """Persist queue to disk"""
        try:
            with open(self.dlq_file, 'w') as f:
                json.dump(self.queue, f)
        except Exception as e:
            logger.error(f"Error saving DLQ: {str(e)}")
    
    def add_failed_operation(self, operation, params, error, attempts=1):
        """Add failed operation to dead letter queue"""
        entry = {
            "operation": operation,
            "params": params,
            "error": str(error),
            "attempts": attempts,
            "timestamp": time.time(),
            "added_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        self.queue.append(entry)
        self._save_queue()
        logger.warning(f"Added to DLQ: {operation} with error: {str(error)}")
    
    def retry_all(self):
        """Attempt to retry all operations in the DLQ"""
        if not self.queue:
            return {"success": True, "retried": 0, "failed": 0}
        
        from url_scheme import construct_url, execute_url
        from handlers import retry_operation
        
        success_count = 0
        failure_count = 0
        remaining_queue = []
        
        for entry in self.queue:
            try:
                url = construct_url(entry["operation"], entry["params"])
                result = retry_operation(lambda: execute_url(url))
                
                if result:
                    success_count += 1
                else:
                    entry["attempts"] += 1
                    remaining_queue.append(entry)
                    failure_count += 1
            except Exception:
                entry["attempts"] += 1
                remaining_queue.append(entry)
                failure_count += 1
        
        self.queue = remaining_queue
        self._save_queue()
        
        return {
            "success": failure_count == 0,
            "retried": success_count + failure_count,
            "failed": failure_count
        }


class RateLimiter:
    """Intelligent rate limiter for Things operations"""
    
    def __init__(self, operations_per_minute=30):
        self.operations_per_minute = operations_per_minute
        self.operation_interval = 60 / operations_per_minute
        self.last_operation_time = 0
    
    def wait_if_needed(self):
        """Wait if necessary to maintain rate limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_operation_time
        
        if time_since_last < self.operation_interval:
            # Need to wait
            wait_time = self.operation_interval - time_since_last
            time.sleep(wait_time)
        
        self.last_operation_time = time.time()
    
    def __call__(self, func):
        """Decorator to rate limit a function"""
        def wrapper(*args, **kwargs):
            self.wait_if_needed()
            return func(*args, **kwargs)
        return wrapper


def get_auth_token() -> Optional[str]:
    """Get the Things authentication token from various possible sources.
    
    The function tries to get the token from:
    1. Environment variable THINGS_AUTH_TOKEN
    2. Local config file
    3. Hardcoded fallback value
    
    Returns:
        str: Authentication token if found, None otherwise
    """
    # Try environment variable first
    token = os.environ.get('THINGS_AUTH_TOKEN')
    if token:
        logger.info("Using Things authentication token from environment variable")
        return token
    
    # Try local config file
    try:
        config_path = os.path.expanduser("~/.things_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                if 'auth_token' in config and config['auth_token']:
                    logger.info("Using Things authentication token from config file")
                    return config['auth_token']
    except Exception as e:
        logger.warning(f"Failed to read auth token from config file: {str(e)}")
    
    # No token found from dynamic sources
    logger.warning("No Things authentication token found in environment or config")
    return None


def detect_things_version():
    """Detect installed Things version"""
    try:
        # Use AppleScript to get Things version
        script = 'tell application "Things3" to return version'
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        logger.error(f"Error detecting Things version: {str(e)}")
    
    return None


def validate_tool_registration(tool_list):
    """Validate that all tools are properly registered"""
    required_tools = [
        "get-inbox", "get-today", "get-upcoming", "get-anytime",
        "get-someday", "get-logbook", "get-trash", "get-todos",
        "get-projects", "get-areas", "get-tags", "get-tagged-items",
        "search-todos", "search-advanced", "get-recent", "add-todo",
        "add-project", "update-todo", "update-project", "show-item"
    ]
    
    tool_names = [t.name for t in tool_list]
    missing_tools = [tool for tool in required_tools if tool not in tool_names]
    
    if missing_tools:
        logger.error(f"Missing tool registrations: {missing_tools}")
        return False
    
    logger.info(f"All {len(tool_list)} tools are properly registered")
    return True


# Create global instances
app_state = ThingsAppState()
circuit_breaker = CircuitBreaker()
dead_letter_queue = DeadLetterQueue()
rate_limiter = RateLimiter()
