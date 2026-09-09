# TinyGo/P2 final handoff report

Result: **FULL_PHYSICAL_PROOF**

## Final regression closure

- Fixed `firmware/protocol.c`: the P2 libc-specific `stdin->_flag &= ~_IOCOOKED` access is now under `#ifndef HOST_TEST`, after P2 UART initialization. Target behavior is unchanged; Linux libc no longer sees P2-private `_flag` / `_IOCOOKED` names.
- Added `CIntegration.test_p2_stdio_flag_access_is_excluded_from_host_build`, a source-structure guard for that boundary.
- `scripts/host_check.py` now writes the new final rerun to `reports/final-host-validation.json`; it does not overwrite `reports/host-validation.json`. The authoritative ZIP-supplied original is separately preserved at `reports/host-validation-supplied.json`. Existing parent failure evidence is retained unchanged: `.work/reports/parent-final-build-and-hil.log` and `reports/host-validation-final-parent-check.json`.

## Final commands and results (this run)

All project execution used `docker exec -w /work/propeller2/tinygo-p2-handoff propeller2`.

- `clang -std=c11 -Wall -Wextra -Werror -DHOST_TEST -DBASELINE -fsyntax-only firmware/protocol.c`: PASS.
- `PATH=/work/propeller2/tinygo-p2-handoff/.work/toolchains/go1.18.10/bin:$PATH make host-test`: PASS; 39 Python tests, Go reference tests, and gofmt. Report: `reports/final-host-validation.json`.
- `P2_JOBS=2 make probe-full && make baseline && make firmware`: PASS.
- Final pre-hardening C HIL: `.work/hil/20260908T094845.445103Z-c/`, PASS `138/138`.
- Final pre-hardening Go HIL: `.work/hil/20260908T094908.091010Z-go/`, PASS `138/138`.
- The idle container was then recreated without force removal. Current container `1b065c89589f4c094fae85124a933f7b6de538bc2c9c6fb8c311b829e867286f` is image `sha256:ba28be8aa42cbd961c6796fb08fcad02d32e96fb9ee4af8c805636243908dac6`, `--network none`, `--cap-drop ALL`, `--security-opt no-new-privileges:true`, 5 GiB memory, 6 GiB memory+swap, 2 CPUs, UID/GID `10000:10000`, group 18, and only `/dev/ttyUSB0:rw` plus the project bind. It is not privileged and has no Docker socket.
- Final post-hardening C HIL: `.work/hil/20260908T094957.806127Z-c/`, PASS `138/138`.
- Final post-hardening Go HIL: `.work/hil/20260908T095016.006774Z-go/`, PASS `138/138`.

Each HIL run used only `project.py hil --allow-ram-reset`, pinned `loadp2`, `-ZERO`, and an ELF payload. No flash/SD/PSRAM/non-console GPIO action, `-9`, `@address`, second serial client, holder kill, broad device mapping, or privileged container was used.

## Artifact identities and literal evidence review

Final identities match the physically proven originals exactly:

| artifact | SHA-256 |
|---|---|
| `probe/arith.go` | `2462b1e4d8df6978dad925b3dfce9ed107fcfc4f5b9649baec41460206d2d192` |
| `.work/out/probe/go.o` | `a616147e8ac1062e6d4de300a58d63f7a1687bd203f28a94d32f676989df05ed` |
| `.work/out/firmware/go.elf` | `e474d1b9bfbf1b738060c682ad66395de0eec37803b0fc71ac8572caad618401` |
| `.work/out/firmware/c.elf` | `b8ccea0f8768de984a036dfb22e836ac048ab407f8a76433b9ae291f13060de9` |

Read-only independent provenance replay passed: `verify_link_provenance.py` confirms the 20-byte `p2_add` and 44-byte `p2_mix` bodies in `go.o` are byte-identical in the linked Go ELF; IR has target `p2`, both exports, and zero runtime calls. `replay_hil_evidence.py --require-full` passed with 11 retained records: 3 C passes, 6 Go passes, three distinct fresh Go downloads, shared final Go image/loader/profile, and consistent recorded arithmetic.

The required negative control remains retained: `.work/hil/20260908T093854.338600Z-go/` fails the first addition after changing only `P2Add` to `(a + b) ^ 1`; `.work/hil/20260908T093933.148141Z-go/` is the byte-restored positive pass. Parent independent pin/mutation/identity review is retained at `.work/reports/independent-mutation-and-pins.json`.

Acceptance/ABI/anti-proxy findings addressed:

- Real TinyGo hook output is ELF32 little-endian EM_P2=300 with native C-ABI `p2_add` / `p2_mix`; no hidden context parameter, unresolved helper, or runtime call is accepted by the checks.
- C baseline is separately compiled with `BASELINE`; the Go firmware link input is the generated `go.o`, and no C fallback defines Go exports.
- The mutation’s live arithmetic failure and restored pass rule out an unchanged C proxy for this proof scope.
- P2 ELF load segments remain within checked HUB bounds; link inputs/maps/disassembly are retained.
- Compatibility inventory is complete: `go-llvm-llvm14dev-di-expression.patch`, `libc-time-O1.patch`, `scripts/project.py` compatibility fixes, P2 raw-input handling, and the LLVM source diff’s minimal `LLVM_EXTERNAL_VISIBILITY` annotation on `LLVMInitializeP2AsmPrinter` (`.work/evidence/llvm.diff`). No LLVM rebuild or scope expansion was made in this closure.

## Scope limitation

This proves only the pinned, scalar compiler-hook path and C-callable leaf functions on this board. It does **not** establish a supported general TinyGo P2 target, ordinary `tinygo build`, runtime/package initialization, GC, goroutines, drivers, networking, multicog scheduling, or persistent-storage support.

## Deliverable

- Compact source/evidence archive (not a bundled LLVM/Go SDK installation): `.work/archives/tinygo-p2-final-handoff-20260908.tar.gz` with checksum file `.work/archives/tinygo-p2-final-handoff-20260908.tar.gz.SHA256`.
- It contains project source, overlays, tests, scripts, locks, documentation, Dockerfile recipe, reports, patches, build artifacts, HIL/mutation records, evidence, and logs; it excludes `.work/src`, `.work/build`, `.work/cache`, and `.work/toolchains`.
- No Git remote exists for this non-repository handoff; patches are retained as files rather than claiming a push.

## Parent final verification and acceptance closure

After the specialist stopped, the controlling agent restarted the idle container, read its live configuration back, and independently ran the complete warm build/test/download path. The container is left available, network-isolated and non-root; restarting its `sleep infinity` process does not reset the P2.

- Gate 0 PASS: `make host-test preflight` passed 39 Python tests, standard-Go tests (including 10,000 randomized reference pairs), formatting, and Linux/x86_64 preflight with Go 1.18.10.
- Gate 1 PASS: real C P2 backend control remains in `.work/out/c-control/`; the pinned LLVM shared-symbol export repair remains verified and recorded.
- Gate 2 PASS: addition-only TinyGo IR/object/assembly/disassembly and hashes remain preserved separately in `.work/out/probe-add/`.
- Gate 3 PASS: parent reran `make probe-full baseline firmware`; original Go object and both linked ELF hashes remained unchanged. `.work/reports/independent-link-provenance-final.json` independently verifies native leaf bodies, target/ABI, no runtime calls, and HUB bounds.
- Gate 4 PASS: three retained successful physical C runs, 414 correct replies / 828 computed values in total.
- Gate 5 PASS: seven retained successful physical Go RAM runs, 966 correct replies / 1,932 computed values in total, including the required three fresh loads, restoration, and subsequent verification runs. Every successful run returned 138/138. The parent's own final fresh load is `.work/hil/20260908T095655.498663Z-go/`.
- Negative control PASS: the deliberate wrong-Go build was rejected for the actual wrong addition; source/object/ELF restoration is byte-exact. Original source also matches the supplied ZIP directly. See `.work/reports/independent-mutation-and-pins.json`.
- Final independent replay covers all 12 recorded attempts: ten successful runs and the two retained failures (initial cooked-input C bring-up and deliberate Go mutation). See `.work/reports/independent-hil-replay-final.json`; no failure record was deleted.
- Exact parent build and live execution output: `.work/reports/parent-final-build-and-hil-success.log`. The earlier failing parent rerun remains separately retained.

Pinned source revisions rechecked from each checkout: TinyGo `cf0b7edc78e42038a0bb522b3f1a5b76928e730e`; p2llvm `bdcefcce7860b2232c06f35726fea679a3a7309c`; LLVM `72a9bb1ef2656d9953d1f41a8196d425ff2ab0b1`; loadp2 `21e074cc7ee6fbd4fb12ef5352544b3457a6729c`.

**Remaining blockers: none for this scoped scalar Go compile-and-run proof.** The general TinyGo runtime/target limitations above remain unchanged.

