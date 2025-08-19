#!/bin/bash

set -e

echo "Building Things MCP DXT package..."

# Clean previous build
echo "Cleaning previous builds..."
rm -rf dist/
mkdir -p dist/

# Create temporary directory for DXT contents
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
# Use Homebrew Python to match runtime environment
/opt/homebrew/bin/python3 -m pip install --target "$TEMP_DIR/server/lib" "httpx>=0.28.1" "fastmcp>=2.0.0" "things-py>=0.0.15"

# Extract version from manifest.json
VERSION=$(grep '"version"' manifest.json | head -1 | sed 's/.*"version": *"\([^"]*\)".*/\1/')

# Use dxt pack to create the package
# Install with "npm install -g @anthropic-ai/dxt"
echo "Packaging with dxt pack..."
dxt pack "$TEMP_DIR" "dist/things-mcp-${VERSION}.dxt"

# Clean up temp directory
rm -rf "$TEMP_DIR"

echo "DXT package created successfully: dist/things-mcp-${VERSION}.dxt"
ls -la dist/

echo "Build completed successfully!"