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

# Copy pyproject.toml so uv can resolve dependencies at runtime
echo "Copying pyproject.toml for uv dependency resolution..."
cp pyproject.toml "$TEMP_DIR/server/"

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
