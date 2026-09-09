# Phase 2 capability matrix

Gate names follow the original `parent-cache/HERMES_PHASE2_PROMPT.md`, not earlier mislabeled closure tables. PASS is bounded to this one-cog application and preserved evidence. Finalization itself was offline.

| Gate / capability | Result | Evidence and boundary |
|---|---|---|
| 2A — preserve proof / reproducible patches | PASS | Immutable Phase 1 archive, original 39 tests plus Go reference/gofmt rerun from extraction; strict patch fresh/idempotent/atomicity and cold-binding tests. Historical warm scalar rebuild retained. No clean SDK bootstrap attempted. |
| 2B — real TinyGo CLI | PASS | Fresh extracted `make tinygo` with `byollvm`, pinned Clang/LLD headers; CLI reports TinyGo 0.23.0 / Go 1.18.10 / LLVM 14.0.0git. Bundled executable removed before building. |
| 2C — experimental target / loader | PASS, bounded | LLVM target P2; linux/arm is only a Go source-selection surrogate. Actual loader trace: 10 packages, 104 parsed Go/Cgo files, 2 ignored Go assembly files. Native P2 ELF, not rewritten ARM/WASM IR; ThinLTO disabled for this backend. |
| 2D — runtime boot / init / main | PASS, preserved physical | Cog bootstrap/PTRA precede normal runtime init/main. Ordered observable imported-init UART, main init, `READY P2E 1`. Pure folded initialization is not mislabeled runtime execution. |
| 2E — ordinary Go application | PASS, bounded | Go-owned protocol/calculation, nested calls/live locals, fixed arrays/structs, globals, loops, signed/unsigned behavior. Go tests pass; genuine escaping allocation fails on `runtime.alloc`, goroutine rejected without scheduler. |
| 2F — hardware proof / regressions | PASS, preserved physical | Three distinct final-1/2/3 RAM records each 138 correct/unique plus 4 malformed; all replayed from extraction. Exact Go XOR-1 mutation fails normal validation; byte-restored source/ELF and fresh positive; actual bounds-panic diagnostic/no continuation. Separate C control stays labeled C. |
| Cold controlled `go-llvm` restoration | PASS | `restore_go_llvm.py` validates full upstream ZIP, pinned local snapshot, authoritative patch digest, and pre/post images. Real temporary restore plus destination/modified-patch/wrong-ZIP rejection tests pass. |
| Portable link provenance | PASS | Retained object and linker-script copies are hash/size checked and replayed with pinned LLD without historical `/tmp`, cache, or `/work` inputs. Corruption and wrong-relocation-target negative checks pass. |
| P2 ABI | Demonstrated scalar/by-reference only | Nested calls, PTRA stack arguments/live locals, R31 scalar return. Pinned LLD resolves `R_P2_20`, `R_P2_32`, `R_P2_AUG20`. Generated tuple/multi-scalar return failed; no general atomic/tuple ABI. i64 remains untested. |
| Memory layout | Inspected, not a runtime capacity claim | Fresh ELF 11,640 bytes; PT_LOAD file-backed bytes 4,778; .bss 96; heap/stack reservations each 49,152. Reserved high-water 0x7c000 leaves 16,384 bytes below 524,288-byte Hub limit. See `FINAL_ELF_LAYOUT.txt`. |
| Extracted release tests | PASS | Five Python suites: 4/2/5/5/5 tests; original 39 host tests; Go app tests; actual CLI and whole-program build. `logs/extracted-preverify3/receipt.json` and `FINAL_REPRODUCTION_AND_ARCHIVE.md`. Canonical ELF digest unchanged. |
| Mandatory independent acceptance | PASS in run 8; final bytes bound by external receipt | Exact required command returned 0, including every archive hash, 12 frozen files, original Phase 1 identities, extracted build/tests and host regression. Historical PATH failures retained; supplied verifier now selects pinned Go explicitly. No verifier/container-global edits by this implementation. See `FINAL_REPRODUCTION_AND_ARCHIVE.md` and the external receipt matching the final archive. |

## Runtime and source-selection qualifications

* The configuration is **one cog**, `-scheduler=none`, and `-gc=none`; it is not a multi-cog, scheduler, or general GC claim.
* Critical-section locks are not a claim of general IRQ masking.
* Compile-time-folded pure initialization is distinct from the observable imported `init` UART effects.
* `Package.parseFiles` parses Go/Cgo files. Any Go `SFiles` are reported as ignored by the target-scoped loader trace and are not evidence of foreign-ISA assembly being lowered.
* This archive is not SDK-self-contained. Pinned Go/LLVM/Clang/LLD headers/libraries and cached module inputs are required explicitly; no original application/compiler source fallback or network fetch is used.
* Time/sleep abort rather than pretend to work. General IRQ handling, `machine` drivers, heap allocation/GC, goroutines, atomics and multicog Go execution are not implemented.
* No finalization serial, flash, SD, PSRAM, non-console GPIO or persistent-device access occurred. Final-byte verification is not a transport delivery receipt.