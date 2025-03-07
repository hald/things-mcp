"""
Tests for the Things MCP FastMCP server implementation.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Import from src directly to avoid import errors
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the module to test
from src.things_mcp.fast_server import mcp


class TestFastMCPServer(unittest.TestCase):
    """Test the FastMCP server implementation for Things MCP."""

    def test_server_metadata(self):
        """Test the server metadata is correctly defined."""
        self.assertEqual(mcp.server_name, "Things")
        self.assertIsNotNone(mcp.description)
        self.assertIsNotNone(mcp.version)

    def test_tool_registration(self):
        """Test that tools are correctly registered with the server."""
        # Check that the expected tools exist in the server
        expected_tools = [
            "get-inbox", "get-today", "get-upcoming", "get-anytime",
            "get-someday", "get-logbook", "get-trash", "get-todos",
            "get-projects", "get-areas", "get-tags", "search-todos",
            "add-todo", "add-project", "update-todo", "update-project"
        ]
        
        # Get the registered tools from the mcp server
        registered_tools = []
        for handler in mcp.handlers.values():
            if hasattr(handler, 'name'):
                registered_tools.append(handler.name)
        
        # Check that all expected tools are registered
        for tool in expected_tools:
            self.assertIn(tool, registered_tools,
                        f"Expected tool '{tool}' not registered with server")


if __name__ == '__main__':
    unittest.main()
