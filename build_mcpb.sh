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

# Copy manifest (uvx will fetch the package from PyPI)
cp manifest.json "$TEMP_DIR/"

# Create minimal stub (required by MCPB format, but uvx handles actual execution)
mkdir -p "$TEMP_DIR/server"
echo "# Stub file - actual server is fetched via uvx from PyPI" > "$TEMP_DIR/server/stub.py"

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
