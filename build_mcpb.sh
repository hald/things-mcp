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
# Convert relative imports to absolute imports for flat MCPB structure
echo "Copying source files..."
sed 's/from \.formatters import/from formatters import/; s/from \. import url_scheme/import url_scheme/' \
    src/things_mcp/server.py > "$TEMP_DIR/server/main.py"
cp src/things_mcp/url_scheme.py "$TEMP_DIR/server/"
cp src/things_mcp/formatters.py "$TEMP_DIR/server/"

# Create minimal pyproject.toml for uv dependency resolution
# (stripped of build system config that breaks in flat MCPB structure)
echo "Creating minimal pyproject.toml for dependencies..."
cat > "$TEMP_DIR/server/pyproject.toml" << 'EOF'
[project]
name = "things-mcp"
version = "0.7.0"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.28.1",
    "fastmcp>=2.0.0",
    "things-py>=0.0.15",
]
EOF

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
