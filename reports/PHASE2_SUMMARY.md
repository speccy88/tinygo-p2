# TinyGo/P2 Phase 2 final implementation candidate — 2026-09-08

The real ordinary TinyGo/P2 project is functional and has been rebuilt from a fresh archive extraction. This is a bounded one-cog port/application proof, not a general-purpose TinyGo P2 platform or a transport-delivery claim.

**Mandatory independent acceptance passed in run 8 (return code 0).** The exact required command verified every archive hash, all 12 frozen source files, the original Phase 1 attestation, fresh extracted tests, the real CLI/application rebuild and the original host regression. The prior run 6/7 PATH failures remain preserved. The supplied verifier now explicitly selects the pinned Go PATH for its separate host-check invocation; this implementation did not edit the verifier, Phase 1 or container-global environment. Run 8's successful receipt is `logs/independent-run8-candidate-receipt.json`. These report/evidence additions are restaged and repacked; the final-byte check is recorded outside the archive at `archives/tinygo-p2-phase2-handoff.verification.json` in the workspace. Only the receipt matching the final archive digest attests those final bytes. This remains an implementation candidate, not delivery.

Canonical hardware-matched ELF SHA-256:
`132b9cf87bc521cf433e8b33e58d24544d0dde3dcf6e13592058b3b1a14416a8`

## Original gates 2A–2F

- **2A PASS:** immutable Phase 1 retained; original 39 host tests, Go reference/gofmt, strict patch identity/idempotence/atomicity and cold-binding restoration tests pass. Historical warm scalar rebuild retained; no clean SDK bootstrap claimed.
- **2B PASS:** actual extracted CLI rebuilt with `byollvm` against pinned Clang/LLD headers; TinyGo 0.23.0 / Go 1.18.10 / LLVM 14.0.0git starts and builds real P2 code.
- **2C PASS, bounded:** experimental P2 target and native ELF; actual loader Go/Cgo selection is separated from ignored Go assembly. Temporary extraction target rendering leaves frozen profiles unchanged.
- **2D PASS, preserved physical:** PTRA-safe cog bootstrap enters normal Go runtime/import init/main, with exactly ordered observable UART initialization markers.
- **2E PASS, bounded:** Go owns the serial protocol and calculation; calls/live locals, arrays/structs/globals/loops and signed/wrap behavior exercised. Actual unsupported-allocation and no-scheduler failures retained.
- **2F PASS, preserved physical:** final-1/2/3 each 138 correct/unique challenges plus four malformed inputs; three distinct raw records independently replayed from extraction. Exact Go XOR-1 negative, byte-identical restoration/fresh positive, real bounds panic/no continuation and separate C control retained.

## Finalization repairs and real execution

- Offline `validate_raw()` no longer imports HIL or a historical root; an isolated standalone-import regression test passes. Original `hil.py` is also packaged unmodified for historical tools.
- CLI build explicitly selects `.work/phase2/src/llvm/clang/include/clang-c/Index.h` and pinned LLD API headers, not the absent extracted `src/tinygo/llvm-project` API tree. SDK sources remain unchanged.
- Fresh build caches and deletion of the extracted bundled CLI prevent an old binary from masquerading as a rebuild. The new CLI builds the actual extracted Go application to the canonical ELF.
- Prior portability repairs to restoration/patch/provenance tests are included by deliberate restaging; the old archive's `/.work/phase2/...` failure is preserved, not confused with the new tree.
- `logs/extracted-preverify3/receipt.json`: all five Python suites PASS (21 tests), archived original host regression PASS (39 tests plus Go/gofmt), Go app tests PASS, real CLI/app rebuild PASS. Full commands and later final-archive checks: `FINAL_REPRODUCTION_AND_ARCHIVE.md`.
- `logs/run8-candidate-all-suites/receipt.json`: all 11 commands returned 0, including all five suites, original host tests, Go app tests, three distinct raw-record replays, and a fresh CLI/whole-program rebuild. Required independent command separately passed against the same bytes. No further application, target/runtime, SDK or helper source changes were needed in run 8; stale packaging was repaired by restaging the existing portability fixes and complete reports/evidence.

The archive includes the complete patched TinyGo/application sources, controlled binding bundle, raw/canonical patches, immutable Phase 1 archive, all physical evidence and failures, effective loader trace, retained link inputs, and original/offline-parent tests. Complete sorted per-file hashes are in `MANIFEST.sha256`; a SHA256 sidecar and final-byte verification receipt live beside the release archive. Read the receipt matching the exact archive digest rather than treating older archived receipts as attestations of newer bytes.

## Boundaries

One cog, `scheduler=none`, `gc=none`. No general heap allocation/GC, goroutines, multicog execution, atomics, tuple ABI, general IRQ/time/drivers, networking or persistent storage; i64 remains untested. Hardware locks are critical sections, not general IRQ masking. Pure folded initialization is not evidence of runtime side effects.

This archive is **not SDK-self-contained**: it requires the separately installed pinned Go/LLVM/Clang/LLD baseline and cached module inputs. Finalization used only the established non-root, network-none Linux/x86_64 container; no hardware or serial was accessed. No source Git repository/remote was invented, no push was attempted, and implementation is a candidate for independent acceptance/delivery, not delivery itself.

Full details: `PHASE2_REPORT.md`, `CAPABILITY_MATRIX.md`, `FINAL_REPRODUCTION_AND_ARCHIVE.md`.