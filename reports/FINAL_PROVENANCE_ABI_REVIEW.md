# Phase 2 final review closure — 2026-09-08

## Result

**Hardware application acceptance remains PASS; release packaging is NOT closed.**  A fresh fixed-pipeline CLI build produced the canonical ELF SHA-256 `132b9cf87bc521cf433e8b33e58d24544d0dde3dcf6e13592058b3b1a14416a8`, then a RAM-only physical re-load after the panic test passed **138/138** valid challenges, four malformed cases, all 138 IDs unique, and the required import/init/READY ordering. Evidence: `hil/gate2f-review-final-after-panic-20260908T134403.698371Z/`, artifact `artifacts/gate2f-final-cli-20260908T134314.022218017Z/`.

## Repairs exercised

| Item | Repair and evidence |
|---|---|
| Phantom linked objects | `capture_link_provenance.py` uses `shlex` on the retained final `ld.lld` command. It finds exactly two real inputs (not five `/bits.o` strings): `/tmp/tinygo2502036514/main.o` and TinyGo cache `obj-a33b…05.o`. Both are copied under `linked-inputs/` with portable paths and hashes in `metadata.corrected.json`; old `metadata.json` remains historical evidence. Pinned LLD relink is byte-identical to the ELF. |
| Relocation-aware check | The verifier accepts only observed P2 `R_P2_20`, `R_P2_AUG20`, and `R_P2_32`; it re-links through pinned `ld.lld`, so relocations are applied by the actual P2 linker rather than masked instruction bytes. Tests reject altered non-relocation code and a same-length rewritten `raw_p2_uart_getc` relocation symbol target. A link command with a missing/changed input is rejected before a claim of provenance. This is static object→ELF proof, not source→object reproducibility. |
| Restore trap / pipeline | `gate2f_mutation_build.sh` canonicalizes ROOT/APP/D before mutation; the trap restores the absolute app path and preserves original failure status. Advertised final/restored/panic builders now capture compiler output to logs and explicitly propagate failure instead of a `build | tee` exit-status hole. Isolated `/bin/false` test mutated only a copied app, returned nonzero, and byte-restored `core.go`. |
| Panic checker | `gate2f_panic_hil.py` now requires ordered `P2 GO BOUNDS ARMED`, `P2 GO BOUNDS TRIGGER`, and an exact target line matching `panic: runtime error: index out of range`; it observes a four-second bounded window and rejects premature terminal EOF/errors. Tests reject a `p2panic.elf` filename without target diagnostic and trigger-before-arm ordering. Real corrected execution of the existing panic ELF passed: raw SHA-256 `41132d7bf0cd7b56cb35cbecf2c7e166294f3c27266f2dbf23e2c3e8e80fa1b6`, 428 bytes, no forbidden continuation. |

`test_phase2_review_utilities.py`: **5 tests PASS** (`review-utility-tests-20260908T134759.680779213Z.log`). Parent's independent `verify_gate2f_controls.py` / `test_verify_gate2f_controls.py` also records the exact one-line mutation, observed XOR1 result, restored source/ELF identity, and exact target panic diagnostic in `coder/cache/tinygo-p2-phase2-input/gate2f-parent-controls.json`; its five fixture tests passed. Parent also reran the unchanged 39 Phase 1 host tests, references, and gofmt (reported in `parent-final-phase1-host-regression.json`).

## Actual identities and build selection

* CLI: TinyGo `0.23.0` Linux/amd64, SHA-256 `1667cd2ea3812d912bde8fabed34ee1855705eb8caa646192cbed322692dffbb`; Go `go1.18.10 linux/amd64`, SHA-256 `ee879590a7182bb962d94614d85b22d46378eab4a9f82ebbea35b398f148483`; LLVM `14.0.0git`.
* Pinned `ld.lld` SHA-256 `0a518348432f194b880e7f75fbfe82dc0d2c5d4fdcc28b485330259afdc5be4a`; `llvm-objdump` SHA-256 `8d8571f955b2ca8b0272f9cfcae737875e14b99ada17c4c9655c22822a8a2a73`; `loadp2` SHA-256 `39640fe81ca18eb05b5675ed29cfd377af89b96b22058b08f0195918e7d64af0`.
* TinyGo HEAD `cf0b7edc78e42038a0bb522b3f1a5b76928e730e`; LLVM `72a9bb1ef2656d9953d1f41a8196d425ff2ab0b1`; P2LLVM `bdcefcce7860b2232c06f35726fea679a3a7309c`; local go-llvm HEAD `fc868cbb5731eda2886115d93f83655a31fc4745`.
* `selected-sources.json` records 16 packages / 250 selected Go-tool source inputs with per-file hashes and the exact GOOS/GOARCH/tag command. The actual CLI command, target profile and board profile are retained in `build-full.log`, `p2-target.json`, and `board-profile.json`; corrected link metadata has actual object paths/hashes.

## ABI, bootstrap and HUB accounting

* Object disassembly shows `main.mixChallenge` receives scalar values in R0/R1/R2 and uses stack arguments through PTRA (`setq #10; wrlong r0,ptra++`); its nested `calla` to `main.foldWords` is an `R_P2_20` relocation and its live local is retained in R4 after return from R31. `foldWords` returns `mov r31,r1` and restores stack words using `rdlong r1,--ptra; reta`. This is evidence for the demonstrated scalar/by-reference ABI only; it does not establish tuple/multi-return ABI support.
* Final bootstrap disassembly shows cog/LUT reserved through `0x200`/`0xa00`, hub text thereafter, and `__start` sets PTRA before Go prologues. `hub-memory.json` derives from PT_LOAD `MemSiz`: 4,778 file-backed LOAD bytes; data/BSS/heap/stack load reservation ends at `0x7c000` (507,904); P2 HUB limit `0x80000`; 16,384 bytes remain. This replaces `.text`-only accounting. The ELF is ELF32 little-endian, P2 machine `0x12c`, entry `0x0`.

## Capabilities / limits

| Capability | Status |
|---|---|
| ordinary TinyGo CLI / P2 ELF / startup, import init, main, UART protocol | PASS on physical P2 |
| Go calls, branches, bounded loops, globals, arrays/structs, signed/unsigned/wrap | PASS in 138 physical vectors and retained object provenance |
| bounds panic | PASS: target diagnostic and halt/no continuation |
| heap allocation / GC / goroutines / scheduler / multi-cog / atomics | unsupported by scope (`gc=none`, `scheduler=none`); do not treat as working |
| tuple/multi-scalar returns, general IRQ/time/platform APIs | not demonstrated / unsupported |
| foreign ISA assembly audit | **INCONCLUSIVE, packaging blocker**: GOARCH=arm surrogate `go list` selects 17 Go SDK ARM `.s` files; build log/linked P2 objects show no ARM machine-code input, but this utility does not instrument TinyGo's internal loader sufficiently to prove those files were excluded. Do not state “no foreign assembly selected” until loader selection is captured or target selection is corrected. |
| cold source reproduction | **BLOCKED**: local go-llvm is `fc868…`, not declared module revision `512c94…`; no validated bundle/source recipe was found. No SDK is included. |

`PROTOCOL_SPEC_DRAFT.md` was checked against `core.go`/`main.go`: fields/equations, 64-byte buffer, 37-byte acceptance, CR and LF being independent terminators, reply CRLF, state persistence, and non-inline helper description match.

## Remaining required work before archive

1. Capture TinyGo internal loader's actual selected file list (or correct target selection) and prove ARM `.s` files are excluded; retain that evidence.
2. Add a validated cold go-llvm materialization bundle/recipe producing `fc868…` and explicitly distinguish it from upstream module revision `512c94…`.
3. Re-run the corrected source-selection proof and package only after both blockers close. Do not claim the final archive/reproduction closure yet.
