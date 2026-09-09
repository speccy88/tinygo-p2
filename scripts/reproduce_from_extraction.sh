#!/bin/sh
# Rebuild the ordinary P2 Go app from an extracted Phase 2 root.
# Usage: BASELINE_ROOT=/path/to/pinned/sdk P2_ROOT=/path/to/extracted ./reproduce_from_extraction.sh
set -eu
: "${BASELINE_ROOT:?set BASELINE_ROOT to the installed pinned SDK/build baseline}"
: "${P2_ROOT:?set P2_ROOT to the extracted Phase 2 root}"
: "${OUT_ELF:=/tmp/p2goapp-reproduced.elf}"
GOROOT="$BASELINE_ROOT/.work/toolchains/go1.18.10"
export GOROOT PATH="$GOROOT/bin:$PATH"
export GOMODCACHE="$BASELINE_ROOT/.work/phase2/cache/go-mod" GOWORK=off
export GOPROXY=off GOSUMDB=off GOFLAGS=-mod=readonly
export LD_LIBRARY_PATH="$BASELINE_ROOT/.work/build/llvm/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export TINYGOROOT="$P2_ROOT/src/tinygo"
export CC=/usr/bin/clang CXX=/usr/bin/clang++
export LLVM_BUILDDIR="$BASELINE_ROOT/.work/build/llvm"
export CLANG_SRC="$BASELINE_ROOT/.work/phase2/src/llvm/clang"
export LLD_SRC="$BASELINE_ROOT/.work/phase2/src/llvm/lld"
test -f "$CLANG_SRC/include/clang-c/Index.h"
test -f "$LLD_SRC/include/lld/Common/Driver.h"
# Fresh isolated CLI and application caches: no bundled CLI or old app object
# can stand in for this rebuild. The pinned SDK/module inputs remain external.
BUILD_SCRATCH="$(mktemp -d /tmp/p2-extracted-build.XXXXXX)"
export GOCACHE="$BUILD_SCRATCH/go-build" XDG_CACHE_HOME="$BUILD_SCRATCH/cache"
printf 'BUILD_SCRATCH=%s\nCLANG_SRC=%s\nLLD_SRC=%s\n' "$BUILD_SCRATCH" "$CLANG_SRC" "$LLD_SRC"
HEADERS="$P2_ROOT/src/tinygo/llvm-project/clang/lib/Headers"
BASELINE_HEADERS="$BASELINE_ROOT/.work/build/llvm/lib/clang/14.0.0/include"
[ -d "$BASELINE_HEADERS" ] || { echo "missing pinned baseline Clang headers: $BASELINE_HEADERS" >&2; exit 1; }
mkdir -p "$(dirname "$HEADERS")"
# Only replace a recipe-owned symlink; never delete a supplied header tree.
if [ -L "$HEADERS" ]; then rm "$HEADERS"; fi
[ ! -e "$HEADERS" ] || { echo "refusing to replace header tree: $HEADERS" >&2; exit 1; }
ln -s "$BASELINE_HEADERS" "$HEADERS"
test -L "$HEADERS" && test "$(readlink "$HEADERS")" = "$BASELINE_HEADERS"
rm -f "$P2_ROOT/src/tinygo/build/tinygo"
make -C "$P2_ROOT/src/tinygo" tinygo GIT_SHA1=cf0b7edc-phase2-archive
test -x "$P2_ROOT/src/tinygo/build/tinygo"
"$P2_ROOT/src/tinygo/build/tinygo" version
sha256sum "$P2_ROOT/src/tinygo/build/tinygo"
TARGET_JSON="$(mktemp /tmp/p2-target.XXXXXX.json)"
trap 'rm -f "$TARGET_JSON"' EXIT HUP INT TERM
python3 - "$P2_ROOT/src/tinygo/targets/p2.json" "$TARGET_JSON" "$P2_ROOT/src/tinygo/targets/p2.ld" <<'PY'
import json, sys
source, output, linker = sys.argv[1:]
data = json.load(open(source))
data['linkerscript'] = linker
with open(output, 'w') as stream:
    json.dump(data, stream, indent=2, sort_keys=True)
    stream.write('\n')
PY
cd "$P2_ROOT/src/p2goapp"
"$P2_ROOT/src/tinygo/build/tinygo" build \
  -target="$TARGET_JSON" -scheduler=none -gc=none -opt=z -panic=print \
  -work -x -printir -verifyir -o "$OUT_ELF" .
printf '%s  %s\n' 132b9cf87bc521cf433e8b33e58d24544d0dde3dcf6e13592058b3b1a14416a8 "$OUT_ELF" | sha256sum -c -
sha256sum "$OUT_ELF"
