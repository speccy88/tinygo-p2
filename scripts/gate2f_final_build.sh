#!/bin/sh
set -eu
ROOT=/work/propeller2/tinygo-p2-handoff
cd "$ROOT"
STAMP=$(date -u +%Y%m%dT%H%M%S.%NZ)
D=.work/phase2/artifacts/gate2f-final-cli-$STAMP
mkdir -p "$D"
cp .work/phase2/src/p2goapp/main.go "$D/main.go"
cp .work/phase2/src/p2goapp/core.go "$D/core.go"
cp .work/phase2/src/p2goapp/bootpkg/bootpkg.go "$D/bootpkg.go"
cp .work/phase2/src/p2goapp/go.mod "$D/go.mod"
cp .work/phase2/src/p2goapp/PROTOCOL.md "$D/PROTOCOL.md"
cp .work/phase2/src/tinygo/targets/p2.json "$D/p2-target.json"
cp firmware/p2-edge-tcxo.json "$D/board-profile.json"
( sha256sum "$D"/*; LD_LIBRARY_PATH="$ROOT/.work/build/llvm/lib" "$ROOT/.work/phase2/src/tinygo/build/tinygo" version ) > "$D/identity-before.txt"
export LD_LIBRARY_PATH="$ROOT/.work/build/llvm/lib"
export GOROOT="$ROOT/.work/toolchains/go1.18.10"
export PATH="$GOROOT/bin:$PATH"
export GOMODCACHE="$ROOT/.work/cache/go-mod"
export GOWORK=off
cd "$ROOT/.work/phase2/src/p2goapp"
if "$ROOT/.work/phase2/src/tinygo/build/tinygo" build -target="$ROOT/.work/phase2/src/tinygo/targets/p2.json" -scheduler=none -gc=none -opt=z -panic=print -work -x -printir -verifyir -o "$ROOT/$D/p2goapp-final.elf" . >"$ROOT/$D/build-full.log" 2>&1; then
  cat "$ROOT/$D/build-full.log"
else rc=$?; cat "$ROOT/$D/build-full.log"; exit "$rc"; fi
sha256sum "$ROOT/$D/p2goapp-final.elf" > "$ROOT/$D/SHA256SUMS.txt"
printf '%s\n' "$ROOT/$D"
