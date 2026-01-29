#!/bin/bash

#set -e

DEPLOY_DIR="/deploy/$PLATFORM"
TOOL_REPOS_DIR="/tool_repos"

# Build neovim
#mkdir -p "$DEPLOY_DIR"
#cd /tool_repos/neovim
#make distclean
#make CMAKE_BUILD_TYPE=RelWithDebInfo CMAKE_INSTALL_PREFIX="$DEPLOY_DIR"
#make install


export XDG_CONFIG_HOME="$DEPLOY_DIR/nvim/config"
export XDG_DATA_HOME="$DEPLOY_DIR/nvim/share"
export XDG_STATE_HOME="$DEPLOY_DIR/nvim/local/state"
export VIM="$DEPLOY_DIR/share/nvim/runtime"
export VIMRUNTIME="$DEPLOY_DIR/share/nvim/runtime"
rm -fr $XDG_CONFIG_HOME $XDG_DATA_HOME $XDG_STATE_HOME
mkdir -p $XDG_CONFIG_HOME $XDG_DATA_HOME $XDG_STATE_HOME
mkdir -p $XDG_CONFIG_HOME/nvim
cp $TOOL_REPOS_DIR/myles_dotfiles/.config/nvim/init.lua $XDG_CONFIG_HOME/nvim
$DEPLOY_DIR/bin/nvim -u "$XDG_CONFIG_HOME/nvim/init.lua"
#$DEPLOY_DIR/bin/nvim -V1 -v
#$DEPLOY_DIR/bin/nvim --headless +q


