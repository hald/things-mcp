"""
Configuration module for Things MCP.
Stores settings and user-specific configuration values.
"""
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_CONFIG = {
    "things_auth_token": "",  # Empty by default, must be set by user
    "retry_attempts": 3,
    "retry_delay": 1.0
}

# Path to the configuration file
CONFIG_DIR = Path.home() / ".things-mcp"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Global configuration dictionary
_config = None

def load_config():
    """Load configuration from file, create with defaults if it doesn't exist."""
    global _config
    
    # Create config directory if it doesn't exist
    if not CONFIG_DIR.exists():
        try:
            CONFIG_DIR.mkdir(parents=True)
            logger.info(f"Created configuration directory: {CONFIG_DIR}")
        except Exception as e:
            logger.error(f"Failed to create config directory: {e}")
            return DEFAULT_CONFIG
    
    # Check if config file exists
    if not CONFIG_FILE.exists():
        # Create default config file
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            logger.info(f"Created default configuration file: {CONFIG_FILE}")
            _config = DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"Failed to create config file: {e}")
            _config = DEFAULT_CONFIG.copy()
    else:
        # Load existing config
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
                
                # Ensure all required keys are present
                _config = DEFAULT_CONFIG.copy()
                _config.update(loaded_config)
                
            logger.info(f"Loaded configuration from: {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            _config = DEFAULT_CONFIG.copy()
    
    return _config

def save_config():
    """Save current configuration to file."""
    if _config is None:
        logger.error("Cannot save config: No configuration loaded")
        return False
    
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(_config, f, indent=2)
        logger.info(f"Saved configuration to: {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False

def get_config():
    """Get the current configuration, loading it if necessary."""
    global _config
    if _config is None:
        _config = load_config()
    return _config

def set_config_value(key, value):
    """Set a configuration value and save to file."""
    config = get_config()
    config[key] = value
    return save_config()

def get_config_value(key, default=None):
    """Get a configuration value, return default if not found."""
    config = get_config()
    return config.get(key, default)

def get_things_auth_token():
    """Get the Things authentication token."""
    return get_config_value("things_auth_token", "")

def set_things_auth_token(token):
    """Set the Things authentication token."""
    return set_config_value("things_auth_token", token)

# Initialize configuration on module import
load_config()
