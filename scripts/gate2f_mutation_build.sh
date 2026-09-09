#!/bin/sh
# Controlled mutation builder. All paths are absolute before source mutation.
set -eu
ROOT=${ROOT:-/work/propeller2/tinygo-p2-handoff}
ROOT=$(CDPATH= cd -- "$ROOT" && pwd -P)
APP=${APP:-$ROOT/.work/phase2/src/p2goapp}
APP=$(CDPATH= cd -- "$APP" && pwd -P)
STAMP=$(date -u +%Y%m%dT%H%M%S.%NZ)
D=${ARTIFACT_ROOT:-$ROOT/.work/phase2/artifacts}/gate2f-mutation-$STAMP
mkdir -p "$D"
cp "$APP/core.go" "$D/core-original.go"
cp "$APP/main.go" "$D/main.go"
sha256sum "$D/core-original.go" > "$D/source-before.sha256"
restore() { rc=$?; cp "$D/core-original.go" "$APP/core.go"; sha256sum "$APP/core.go" > "$D/source-restored.sha256"; exit "$rc"; }
trap restore EXIT HUP INT TERM
python3 -c 'from pathlib import Path; import sys; p=Path(sys.argv[1]); s=p.read_text(); a="return local ^ st.sum ^ st.fold"; b="return (local ^ st.sum ^ st.fold) ^ 1"; assert s.count(a)==1; p.write_text(s.replace(a,b))' "$APP/core.go"
cp "$APP/core.go" "$D/core-mutated.go"; sha256sum "$D/core-mutated.go" > "$D/source-mutated.sha256"
export LD_LIBRARY_PATH="$ROOT/.work/build/llvm/lib" GOROOT="$ROOT/.work/toolchains/go1.18.10" PATH="$ROOT/.work/toolchains/go1.18.10/bin:$PATH" GOMODCACHE="$ROOT/.work/cache/go-mod" GOWORK=off
TINYGO=${TINYGO:-$ROOT/.work/phase2/src/tinygo/build/tinygo}
if "$TINYGO" build -target="$ROOT/.work/phase2/src/tinygo/targets/p2.json" -scheduler=none -gc=none -opt=z -panic=print -work -x -o "$D/p2goapp-mutated.elf" "$APP" >"$D/build.log" 2>&1; then
  cat "$D/build.log"
else rc=$?; cat "$D/build.log"; exit "$rc"; fi
sha256sum "$D/p2goapp-mutated.elf" > "$D/SHA256SUMS.txt"
printf '%s\n' "$D"
