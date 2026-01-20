# GLIBC 2.27
FROM centos:7

ARG GOVERSION="1.14.10"
RUN echo -n el7_64 > /etc/packager.txt

#RUN yum install -y rpm-build ruby wget gcc softhsm git && \
#    yum clean all

VOLUME /go
VOLUME /build/artifacts

ENV RUBYLIB /packager/lib
ENV PATH /usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/go/bin
ENV GOPATH /go
ENV GO111MODULE on

COPY lib /packager/lib/
COPY bin /packager/bin/
COPY install-choria.sh /bin

CMD /packager/bin/packager.rb

RUN apt-get update && apt-get install -y \
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
    git

# Build cmake
RUN <<EOF
    version=4.2
    build=1
    cd /tmp
    wget https://cmake.org/files/v$version/cmake-$version.$build.tar.gz
    tar -xzvf cmake-$version.$build.tar.gz
    cd cmake-$version.$build
    ./bootstrap
    make
    make install
    cd ..
    rm -fr cmake-$version.$build
EOF

# Install rustc/rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- --default-toolchain nightly -y
ENV PATH="/root/.cargo/bin:${PATH}"
ENV CARGO_HOME=/root/.cargo
ENV RUSTUP_HOME=/root/.rustup

# Install Go
RUN curl -L https://go.dev/dl/go1.21.5.linux-amd64.tar.gz | tar -C /usr/local -xzf -
ENV PATH="/usr/local/go/bin:${PATH}"

# Install Python and uv
ENV UV_PYTHON="cpython-3.14.2-linux-x86_64-gnu"
ENV UV_CACHE_DIR="/cache/uv"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"
RUN uv python install

# Create cache directories
RUN mkdir -p /cache/go \
    /cache/cargo \
    /cache/cmake \
    /cache/npm \
    /cache/uv \
    /cache/ccache

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
