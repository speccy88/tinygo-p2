#!/bin/sh
set -eu
ROOT=/work/propeller2/tinygo-p2-handoff; cd "$ROOT"; STAMP=$(date -u +%Y%m%dT%H%M%S.%NZ); D=.work/phase2/artifacts/gate2f-restored-$STAMP; mkdir -p "$D"; cp .work/phase2/src/p2goapp/core.go "$D/core-restored.go"; cp .work/phase2/src/p2goapp/main.go "$D/main-restored.go"; sha256sum "$D"/* > "$D/source.sha256"
export LD_LIBRARY_PATH="$ROOT/.work/build/llvm/lib" GOROOT="$ROOT/.work/toolchains/go1.18.10" PATH="$ROOT/.work/toolchains/go1.18.10/bin:$PATH" GOMODCACHE="$ROOT/.work/cache/go-mod" GOWORK=off
cd .work/phase2/src/p2goapp
if "$ROOT/.work/phase2/src/tinygo/build/tinygo" build -target="$ROOT/.work/phase2/src/tinygo/targets/p2.json" -scheduler=none -gc=none -opt=z -panic=print -work -x -o "$ROOT/$D/p2goapp-restored.elf" . >"$ROOT/$D/build.log" 2>&1; then
  cat "$ROOT/$D/build.log"
else rc=$?; cat "$ROOT/$D/build.log"; exit "$rc"; fi
sha256sum "$ROOT/$D/p2goapp-restored.elf" > "$ROOT/$D/SHA256SUMS.txt"; printf '%s\n' "$ROOT/$D"
