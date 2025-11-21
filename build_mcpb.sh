#!/bin/bash

set -e

echo "Building Things MCP bundle (.mcpb)..."

# Clean previous build
echo "Cleaning previous builds..."
rm -rf dist/
mkdir -p dist/

# Create temporary directory for bundle contents
TEMP_DIR=$(mktemp -d)
echo "Using temporary directory: $TEMP_DIR"

# Copy manifest
cp manifest.json "$TEMP_DIR/"

# Create server directory structure in temp location
mkdir -p "$TEMP_DIR/server"

# Copy source files to temp server directory (with proper naming)
echo "Copying source files..."
cp things_server.py "$TEMP_DIR/server/main.py"
cp url_scheme.py "$TEMP_DIR/server/"
cp formatters.py "$TEMP_DIR/server/"

# Bundle dependencies directly into temp location
echo "Bundling Python dependencies..."
# Use Homebrew Python that will run the code (must match manifest.json command)
/opt/homebrew/bin/python3 -m pip install --target "$TEMP_DIR/server/lib" "httpx>=0.28.1" "fastmcp>=2.0.0" "things-py>=0.0.15"

# Extract version from manifest.json
VERSION=$(grep '"version"' manifest.json | head -1 | sed 's/.*"version": *"\([^"]*\)".*/\1/')

# Use mcpb pack to create the package
# Install with "npm install -g @anthropic-ai/mcpb"
echo "Packaging with mcpb pack..."
mcpb pack "$TEMP_DIR" "dist/things-mcp-${VERSION}.mcpb"

# Clean up temp directory
rm -rf "$TEMP_DIR"

echo "MCPB package created successfully: dist/things-mcp-${VERSION}.mcpb"
ls -la dist/

echo "Build completed successfully!"
