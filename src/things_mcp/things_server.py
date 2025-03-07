from typing import Any, List, Optional, Dict
import logging
import asyncio
import sys
import re
import traceback
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

# Import our direct MCP tool definitions for Windsurf compatibility
from mcp_tools import get_mcp_tools_list
from handlers import handle_tool_call
from utils import validate_tool_registration, app_state
import url_scheme

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

server = Server("things")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools for Things integration with Windsurf compatibility."""
    return get_mcp_tools_list()

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests with Windsurf compatibility."""
    try:
        # Handle both prefixed and non-prefixed tool names consistently
        # If name has mcp2_ prefix, remove it for handler compatibility
        # If name doesn't have prefix, use it directly
        
        original_name = name
        base_name = name
        
        # Check if the name has the 'mcp2_' prefix and remove it if present
        if name.startswith("mcp2_"):
            base_name = name[5:]  # Remove the 'mcp2_' prefix
            logger.info(f"Received prefixed tool call: {name} -> mapping to {base_name}")
        else:
            # No prefix, check if the name is one of our supported tools
            # This allows both prefixed and direct calls to work
            logger.info(f"Received non-prefixed tool call: {name}")
        
        # Log the incoming arguments for debugging
        argument_summary = str(arguments)[:100] + "..." if arguments and len(str(arguments)) > 100 else str(arguments)
        logger.info(f"MCP tool call received: {original_name} (handling as: {base_name}) with arguments: {argument_summary}")
        
        # Call the appropriate handler with robust error handling
        try:
            return await handle_tool_call(base_name, arguments)
        except Exception as e:
            error_message = f"Error executing tool {name}: {str(e)}"
            logger.error(error_message)
            logger.error(traceback.format_exc())
            return [types.TextContent(type="text", text=f"⚠️ {error_message}")]
    except Exception as outer_e:
        # Catch-all to prevent server crashes
        logger.error(f"Critical error in tool call handler: {str(outer_e)}")
        logger.error(traceback.format_exc())
        return [types.TextContent(type="text", text=f"⚠️ Critical error: {str(outer_e)}")]

async def main():
    # Get our MCP tools with proper naming for Windsurf
    mcp_tools = get_mcp_tools_list()
    
    # Log successful registration
    logger.info(f"Registered {len(mcp_tools)} MCP-compatible tools for Things")
    
    # Check if Things app is available
    if not app_state.update_app_state():
        logger.warning("Things app is not running at startup. MCP will attempt to launch it when needed.")
        try:
            # Try to launch Things
            if url_scheme.launch_things():
                logger.info("Successfully launched Things app")
            else:
                logger.error("Unable to launch Things app. Some operations may fail.")
        except Exception as e:
            logger.error(f"Error launching Things app: {str(e)}")
    else:
        logger.info("Things app is running and ready for operations")
    
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="things",
                server_version="0.1.1",  # Updated version with reliability enhancements
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())