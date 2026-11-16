#!/usr/bin/env bash
set -euo pipefail
work=${1:?Usage: build-loaders.sh SOURCE_ROOT}
work=$(cd "$work" && pwd)
mkdir -p "$work/spin2cpp/build"
make -C "$work/spin2cpp" -j "${P2_BUILD_JOBS:-3}" build/flexspin
assembler="$work/spin2cpp/build/flexspin -2"
make -C "$work/loadp2" P2ASM="$assembler" build/loadp2
if command -v x86_64-w64-mingw32-gcc >/dev/null; then
    make -C "$work/loadp2" CROSS=win32 CC=x86_64-w64-mingw32-gcc \
        P2ASM="$assembler" build-win32/loadp2.exe
    x86_64-w64-mingw32-strip "$work/loadp2/build-win32/loadp2.exe"
fi
