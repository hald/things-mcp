#!/usr/bin/env python3
"""
Main entry point for running the Things MCP server.
This version uses the modern FastMCP pattern for better maintainability.
"""
import logging
import sys
from src.things_mcp.fast_server import run_things_mcp_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Things FastMCP Server")
    try:
        run_things_mcp_server()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error running server: {str(e)}")
        sys.exit(1)
