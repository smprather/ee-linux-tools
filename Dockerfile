# Dockerfile

FROM ubuntu:18.04

# Install necessary packages
RUN apt update && \
    apt install -y build-essential && \
    apt install -y sudo git curl fuse cmake

# Install build dependencies and Neovim pre-requisites
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
    git

# Build cmake
RUN <<EOF
	version=4.2
	build=1
	## don't modify from here
	cd /tmp
	wget https://cmake.org/files/v$version/cmake-$version.$build.tar.gz
	tar -xzvf cmake-$version.$build.tar.gz
	cd cmake-$version.$build/
	./bootstrap
	make
	make install
EOF

# Install wezterm dependencies
COPY neovim /build/external

# Add entrypoint
#COPY docker-entrypoint.sh /usr/local/bin/
#ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["/bin/bash"]

