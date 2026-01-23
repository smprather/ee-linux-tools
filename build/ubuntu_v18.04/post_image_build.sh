#!/bin/bash
version=4.2
build=1
if [ ! -d cmake-$version.$build ]; then
    wget https://cmake.org/files/v$version/cmake-$version.$build.tar.gz
    tar -xzvf cmake-$version.$build.tar.gz
    cd cmake-$version.$build
    ./bootstrap
    cd ..
fi
cd cmake-$version.$build
make

