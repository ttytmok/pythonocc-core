#!/bin/bash
# make an in source build do to some problems with install

# Configure step
cmake -G Ninja \
 -DPYTHONOCC_BUILD_TYPE=Release \
 -DCMAKE_PREFIX_PATH=$PREFIX \
 -DCMAKE_LIBRARY_PATH:FILEPATH="$PREFIX/lib" \
 -DCMAKE_INSTALL_PREFIX:FILEPATH=$PREFIX \
 -DCMAKE_SYSTEM_PREFIX_PATH=$PREFIX \
  ${CMAKE_PLATFORM_FLAGS[@]} \
 -DSWIG_HIDE_WARNINGS=ON \
 -DPYTHONOCC_MESHDS_NUMPY=ON \
 -DPYTHONOCC_VERSION=$OCCT_VERSION \

# Build step
ninja

# Install step
ninja install

# fix rpaths
#if [ $(uname) == Darwin ]; then
#    for lib in $(ls $SP_DIR/OCC/_*.so); do
#      install_name_tool -rpath $PREFIX/lib @loader_path/../../../ $lib
#    done
#fi
