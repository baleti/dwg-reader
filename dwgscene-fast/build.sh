#!/bin/sh
# Build the optional native scene kernels (dwgscene_fast.abi3.so next to this dir; git-ignored). Run niced, preferably on host1/host2.
set -e
cd "$(dirname "$0")"
nice -n 19 cargo build --release --offline
cp target/release/libdwgscene_fast.so dwgscene_fast.abi3.so.tmp && mv -f dwgscene_fast.abi3.so.tmp dwgscene_fast.abi3.so
echo "built dwgscene_fast.abi3.so"
