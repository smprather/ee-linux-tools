# GLIBC 2.27
FROM ubuntu:18.04

WORKDIR /workspace

ENV PLATFORM="ubuntu_v18.04"

RUN apt-get update && apt-get install -y \
    coreutils \
    build-essential \
    curl \
    gettext \
    ninja-build \
    unzip \
    neovim \
    libtool \
    autoconf \
    wget \
    libssl-dev \
    ccache \
    tree \
    git

# Install rustc/rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- --default-toolchain nightly -y
ENV PATH="/root/.cargo/bin:${PATH}"
ENV CARGO_HOME=/root/.cargo
ENV RUSTUP_HOME=/root/.rustup

# Install Go
RUN curl -L https://go.dev/dl/go1.21.5.linux-amd64.tar.gz | tar -C /usr/local -xzf -
ENV PATH="/usr/local/go/bin:${PATH}"

# Install uv and Python
ENV UV_PYTHON="cpython-3.14.2-linux-x86_64-gnu"
ENV UV_CACHE_DIR="/cache/uv"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"
RUN uv python install

# Go cache
ENV GOCACHE=/cache/go/build
ENV GOMODCACHE=/cache/go/mod
# Cargo cache
ENV CARGO_HOME=/cache/cargo
# CMake cache
ENV CMAKE_BUILD_PARALLEL_LEVEL=12
# npm cache
ENV npm_config_cache=/cache/npm
# ccache for C/C++ compilation
ENV CCACHE_DIR=/cache/ccache
ENV CCACHE_BASEDIR="/root"

# Clean up apt stuff that's not needed in the image
RUN rm -rf /var/lib/apt/lists/*

ENV PATH="/workspace/cmake-4.2.1/bin:$PATH"

CMD ["/bin/bash"]

#https://github.com/mozilla/sccache/archive/refs/tags/v0.12.0.tar.gz
#ENV RUSTC_WRAPPER=sccache
#ENV SCCACHE_DIR=/cache/sccache
#RUN mkdir -p /cache/sccache
# Add entrypoint
#COPY docker-entrypoint.sh /usr/local/bin/
#ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
# Install Node.js and npm
#RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
#    && apt-get install -y nodejs
