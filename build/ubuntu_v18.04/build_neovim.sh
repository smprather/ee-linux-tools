#!/bin/bash

DEPLOY_DIR="/deploy/$PLATFORM"

# Build neovim
mkdir -p "$DEPLOY_DIR"
cd /tool_repos/neovim
make distclean
make CMAKE_BUILD_TYPE=RelWithDebInfo CMAKE_INSTALL_PREFIX="$DEPLOY_DIR"
make install


