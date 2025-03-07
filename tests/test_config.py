"""
Tests for the configuration module of Things MCP.
"""
import os
import tempfile
import unittest
from unittest.mock import patch, mock_open

# Import from src directly to avoid import errors
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.things_mcp.config import (
    get_config_path,
    get_config,
    get_config_value,
    set_config_value,
    get_things_auth_token,
    set_things_auth_token
)


class TestConfiguration(unittest.TestCase):
    """Test the configuration functionality of Things MCP."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test config
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "config.json")
        
        # Patch the config path function to return our test path
        self.patcher = patch('src.things_mcp.config.get_config_path', 
                            return_value=self.config_path)
        self.mock_get_path = self.patcher.start()

    def tearDown(self):
        """Tear down test fixtures."""
        # Stop the patcher
        self.patcher.stop()
        
        # Clean up the temporary directory
        self.temp_dir.cleanup()

    def test_get_config_empty(self):
        """Test that get_config returns an empty dict when no config exists."""
        # Mock os.path.exists to return False
        with patch('os.path.exists', return_value=False):
            config = get_config()
            self.assertEqual(config, {})

    def test_get_set_config_value(self):
        """Test setting and getting a config value."""
        # Mock file operations
        mock_json = {'test_key': 'test_value'}
        
        with patch('json.load', return_value=mock_json), \
             patch('json.dump') as mock_dump, \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()):
            
            # Test get_config_value
            value = get_config_value('test_key', default='default')
            self.assertEqual(value, 'test_value')
            
            # Test get_config_value with default
            value = get_config_value('nonexistent_key', default='default')
            self.assertEqual(value, 'default')
            
            # Test set_config_value
            set_config_value('new_key', 'new_value')
            
            # Check that json.dump was called
            mock_dump.assert_called_once()

    def test_auth_token_functions(self):
        """Test the auth token getter and setter functions."""
        # Mock the get_config_value and set_config_value functions
        with patch('src.things_mcp.config.get_config_value', 
                  return_value='test_token') as mock_get, \
             patch('src.things_mcp.config.set_config_value') as mock_set:
            
            # Test getting the token
            token = get_things_auth_token()
            self.assertEqual(token, 'test_token')
            mock_get.assert_called_with('things_auth_token', '')
            
            # Test setting the token
            set_things_auth_token('new_token')
            mock_set.assert_called_with('things_auth_token', 'new_token')


if __name__ == '__main__':
    unittest.main()
