#!/usr/bin/env bash
set -euo pipefail
work=${TINYGO_P2_WORK:-"$HOME/tinygo-p2-work"}
export PATH="$work/llvm15-build/bin:$work/go/bin:/usr/local/bin:/usr/bin:/bin"
export LD_LIBRARY_PATH="$work/llvm15-build/lib"
export TINYGOROOT="$work/tinygo"
# LLVM backend changes can retain the same version string. Separate cached
# objects by the complete patched-source bundle, including its target profiles.
bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
fingerprint=$(sha256sum "$bundle/source-manifest.json")
fingerprint=${fingerprint%% *}
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$work/cache/$fingerprint}"
# Go 1.27's JSON v2 implementation exceeds P2 hub RAM in common applications.
# Keep its compatible compact implementation unless explicitly overridden.
export GOEXPERIMENT="${GOEXPERIMENT-nojsonv2}"
exec "$work/tinygo/build/tinygo" "$@"
