#!/bin/bash

set -e

DEPLOY_DIR="/deploy/$PLATFORM"
TOOL_REPOS_DIR="/tool_repos"

echo "Building tree-sitter CLI..."

# Navigate to tree-sitter repository
cd "$TOOL_REPOS_DIR/tree-sitter"

# Build tree-sitter CLI using Cargo
cd crates/cli
cargo build --release

# Create deployment directory structure
mkdir -p "$DEPLOY_DIR/bin"

# Install the tree-sitter binary
cp target/release/tree-sitter "$DEPLOY_DIR/bin/"

# Verify the installation
echo "Verifying tree-sitter installation..."
"$DEPLOY_DIR/bin/tree-sitter" --version

echo "tree-sitter build complete!"
