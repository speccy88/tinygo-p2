#!/usr/bin/env bash
set -euo pipefail
bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work=${1:-"$HOME/tinygo-p2-work"}
work=$(cd "$work" && pwd)
host_clang=${P2_HOST_CLANG:-$(command -v clang)}
export PATH="$work/llvm15-build/bin:$work/go/bin:/usr/local/bin:/usr/bin:/bin"
export LD_LIBRARY_PATH="$work/llvm15-build/lib"
export TINYGOROOT="$work/tinygo"
export CGO_CPPFLAGS="\"-I$work/llvm15-build/include\" \"-I$work/p2llvm/llvm15/llvm/include\" \"-I$work/p2llvm/llvm15/clang/include\" \"-I$work/llvm15-build/tools/clang/include\""
export CGO_LDFLAGS="\"-L$work/llvm15-build/lib\" \"-Wl,-rpath,$work/llvm15-build/lib\""
export GOMAXPROCS=${P2_BUILD_JOBS:-3}
python3 "$work/p2llvm/tests/run.py" --build-dir "$work/llvm15-build" --llvm-source "$work/p2llvm/llvm15"
python3 "$work/p2llvm/tests/tools/check_multi3.py" --host-clang "$host_clang"
python3 "$bundle/hil/check_runtime_asm.py" --tools "$work/llvm15-build/bin" --tinygo "$work/tinygo" --output "$work/check-runtime-asm" --startup-c
python3 "$bundle/hil/test_p2_memory_model.py" "$work/tinygo/src/runtime/p2_memory.S"
python3 "$bundle/hil/test_gc_root_scan.py" --tinygo "$work/tinygo" --go "$work/go/bin/go"
python3 "$bundle/hil/check_psram_api.py" --tinygo-root "$work/tinygo" --go "$work/go/bin/go"
cd "$work/tinygo"
go test -p "$GOMAXPROCS" -tags llvm15 ./compiler -run TestP2 -count=1
go test -p "$GOMAXPROCS" -tags llvm15 ./compileopts ./goenv ./tools/gen-critical-atomics
printf 'Host checks passed. Physical-board acceptance is a separate step.\n'