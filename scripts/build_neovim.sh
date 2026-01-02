#!/bin/bash
mkdir -p /deploy/GLIBC_227
cd /external/neovim
make distclean
make CMAKE_BUILD_TYPE=RelWithDebInfo CMAKE_INSTALL_PREFIX=/deploy/GLIBC_227
make install


