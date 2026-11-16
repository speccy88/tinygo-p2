#!/usr/bin/env bash
set -euo pipefail

bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work=${1:-"$HOME/tinygo-p2-work"}
jobs=${P2_BUILD_JOBS:-3}
mkdir -p "$work"
work=$(cd "$work" && pwd)

for tool in git curl python3 cmake ninja clang clang++ ld.lld; do
    command -v "$tool" >/dev/null || { echo "Missing build prerequisite: $tool" >&2; exit 1; }
done

python3 "$bundle/prepare-sources.py" "$work"

llvm_source="$work/p2llvm/llvm15"
llvm_build="$work/llvm15-build"
cmake -S "$llvm_source/llvm" -B "$llvm_build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
    -DCMAKE_C_FLAGS_RELEASE=-O1 -DCMAKE_CXX_FLAGS_RELEASE=-O1 \
    -DLLVM_ENABLE_PROJECTS='clang;lld' \
    -DLLVM_TARGETS_TO_BUILD=X86 -DLLVM_EXPERIMENTAL_TARGETS_TO_BUILD=P2 \
    -DLLVM_ENABLE_ASSERTIONS=ON -DLLVM_ENABLE_BINDINGS=OFF \
    -DCLANG_ENABLE_ARCMT=OFF -DCLANG_ENABLE_STATIC_ANALYZER=OFF \
    -DCLANG_LINK_CLANG_DYLIB=OFF \
    -DLLVM_BUILD_LLVM_DYLIB=ON -DLLVM_LINK_LLVM_DYLIB=ON \
    -DLLVM_ENABLE_TERMINFO=OFF -DLLVM_ENABLE_ZLIB=ON \
    -DLLVM_ENABLE_ZSTD=OFF -DLLVM_ENABLE_LIBXML2=OFF \
    -DLLVM_USE_LINKER=lld -DLLVM_PARALLEL_LINK_JOBS=1
ninja -C "$llvm_build" -j "$jobs" \
    clang libclang lld llc opt llvm-config llvm-ar llvm-ranlib \
    llvm-objcopy llvm-objdump llvm-readelf llvm-nm llvm-as llvm-dis llvm-mc \
    llvm-symbolizer llvm-addr2line FileCheck not count split-file LLVM

cmake -S "$work/p2llvm/libp2" -B "$work/p2-builtins" -G Ninja \
    -Dllvm="$llvm_build/bin"
ninja -C "$work/p2-builtins" -j "$jobs" compiler_builtins
mkdir -p "$work/tinygo/lib/p2"
cp "$work/p2-builtins/lib/builtins/libcompiler_builtins.a" "$work/tinygo/lib/p2/"

export PATH="$llvm_build/bin:$work/go/bin:/usr/local/bin:/usr/bin:/bin"
export CGO_CPPFLAGS="\"-I$llvm_build/include\" \"-I$llvm_source/llvm/include\" \"-I$llvm_source/clang/include\" \"-I$llvm_build/tools/clang/include\""
export CGO_LDFLAGS="\"-L$llvm_build/lib\" \"-Wl,-rpath,$llvm_build/lib\""
export LD_LIBRARY_PATH="$llvm_build/lib"
export TINYGOROOT="$work/tinygo"
export GOMAXPROCS="$jobs"
if [ -d "$work/gomodcache" ]; then
    export GOMODCACHE="$work/gomodcache"
fi
# Let libclang find its headers relative to TINYGOROOT in relocatable SDKs.
mkdir -p "$work/tinygo/lib/clang"
cp -a "$("$llvm_build/bin/clang" -print-resource-dir)/." "$work/tinygo/lib/clang/"
cd "$work/tinygo"
go build -p "$jobs" -trimpath -tags llvm15 -o build/tinygo .
./build/tinygo version
go test -p "$jobs" -tags llvm15 ./compileopts ./goenv
