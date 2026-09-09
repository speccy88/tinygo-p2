# Archive scope

This root is the extracted `P2` directory used by `reports/PHASE2_REPORT.md`.
It intentionally excludes `.work/phase2/src/llvm`, Go/SDK/build caches, all Git internals, recursive prior archives, and unrelated project files. The compact immutable Phase 1 archive is retained at `baseline/tinygo-p2-final-handoff-20260908.tar.gz`; its baseline hash is retained beside it. The bundled TinyGo CLI is dynamically dependent on the separately installed pinned Go/LLVM baseline described in the report.
