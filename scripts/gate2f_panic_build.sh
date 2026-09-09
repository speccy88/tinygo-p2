#!/bin/sh
set -eu
ROOT=/work/propeller2/tinygo-p2-handoff; cd "$ROOT"; STAMP=$(date -u +%Y%m%dT%H%M%S.%NZ); D=.work/phase2/artifacts/gate2f-panic-$STAMP; mkdir -p "$D"; cp .work/phase2/src/p2panic/main.go "$D/panic-main.go"; cp .work/phase2/src/p2panic/go.mod "$D/go.mod"; sha256sum "$D"/* > "$D/source.sha256"
export LD_LIBRARY_PATH="$ROOT/.work/build/llvm/lib" GOROOT="$ROOT/.work/toolchains/go1.18.10" PATH="$ROOT/.work/toolchains/go1.18.10/bin:$PATH" GOMODCACHE="$ROOT/.work/cache/go-mod" GOWORK=off
cd .work/phase2/src/p2panic
if "$ROOT/.work/phase2/src/tinygo/build/tinygo" build -target="$ROOT/.work/phase2/src/tinygo/targets/p2.json" -scheduler=none -gc=none -opt=z -panic=print -work -x -printir -verifyir -o "$ROOT/$D/p2panic.elf" . >"$ROOT/$D/build-full.log" 2>&1; then
  cat "$ROOT/$D/build-full.log"
else rc=$?; cat "$ROOT/$D/build-full.log"; exit "$rc"; fi
"$ROOT/.work/build/llvm/bin/llvm-objdump" -d "$ROOT/$D/p2panic.elf" > "$ROOT/$D/p2panic.disassembly.txt"; sha256sum "$ROOT/$D/p2panic.elf" > "$ROOT/$D/SHA256SUMS.txt"; printf "%s\n" "$ROOT/$D"
