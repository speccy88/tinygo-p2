# TinyGo/P2 Phase 2 — complete bounded implementation report

This report supersedes earlier checkpoint status, not their evidence. Gate names below follow `parent-cache/HERMES_PHASE2_PROMPT.md`. Finalization repaired extraction/build/package helpers only; the ordinary Go application, P2 target/runtime, Phase 1 and physical evidence were not changed. Finalization is offline: no serial opens, RAM reloads, persistent-device writes, network enablement, extra devices or SDK changes.

## Result and environment

The ordinary TinyGo CLI builds the Go-owned application into the exact physical-evidence ELF:

`132b9cf87bc521cf433e8b33e58d24544d0dde3dcf6e13592058b3b1a14416a8`

Fresh extracted preverification: `logs/extracted-preverify3/receipt.json`, PASS. It records all five Python suites (4/2/5/5/5 tests), the original 39-test host suite plus Go references/gofmt, Go application tests, three independent physical-record replays, and an actual fresh CLI/application build. `FINAL_REPRODUCTION_AND_ARCHIVE.md` records subsequent archive checks and exact commands. Final archive acceptance and delivery are separate: only a matching final-byte receipt establishes archive acceptance; this report is not a transport receipt.

Second fresh candidate extraction also passed all these commands (`logs/final-candidate-run6/receipt.json`). Historical independent runs 6/7 failed only at the final installed-Phase-1 host check because the default container PATH lacked Go/gofmt; the original failures remain preserved. **Run 8 mandatory acceptance now passed, return code 0** (`logs/independent-run8-candidate-receipt.json`): the supplied verifier explicitly selects the pinned Go PATH for that separate check. This implementation did not edit the verifier, Phase 1 or the container environment. A fresh run 8 all-suite extraction also passed all 11 commands (`logs/run8-candidate-all-suites/receipt.json`), including 21 Python behavioral tests, original 39 host tests plus Go/gofmt, application tests, three raw-record replays and real CLI/application rebuilding. Final reports and evidence are restaged before the final-byte recheck; the matching external `archives/tinygo-p2-phase2-handoff.verification.json` is the final archive attestation.

Execution environment: existing Linux/x86_64 `propeller2`, `docker exec --user 10000:10000`, network `none`, not privileged, capabilities dropped, no-new-privileges. Existing device mappings were not changed or used.

Pins (with retained compatibility changes, not pristine upstream trees):

- TinyGo v0.23.0: `cf0b7edc78e42038a0bb522b3f1a5b76928e730e`.
- LLVM 14.0.0git/P2 backend: `72a9bb1ef2656d9953d1f41a8196d425ff2ab0b1`.
- P2LLVM: `bdcefcce7860b2232c06f35726fea679a3a7309c`.
- loadp2: `21e074cc7ee6fbd4fb12ef5352544b3457a6729c` (retained evidence; not executed now).
- Go SDK: Go 1.18.10 linux/amd64.
- go-llvm controlled local snapshot: `fc868cbb5731eda2886115d93f83655a31fc4745`. This is NOT upstream module revision `512c94c1e71f`; the separately pinned module is `tinygo.org/x/go-llvm v0.0.0-20220420140351-512c94c1e71f`.

## Gate 2A — Preserve Phase 1 and patch reproducibility: PASS

The compact original Phase 1 archive is `baseline/tinygo-p2-final-handoff-20260908.tar.gz`, SHA-256 `fa0dd650831443e846bc2f82979104458d140108576f377cbe60fed8ef75c305`. Original source/object/ELF identities and parent attestation are retained, not rewritten. Original 39 host tests, Go reference tests and gofmt were rerun from that archive in a disposable project-shaped extraction; see `logs/extracted-preverify3/phase1-host-regression.log`.

`patch-manifest.json` binds exact repository identities, patch digests and all intended-file pre/post hashes for the go-llvm DI-expression backport, libc time `-O1` workaround, and LLVM AsmPrinter visibility export. Raw historical patches remain in the immutable baseline/snapshots; corrected canonical patches are in `patches/`. Historical malformed hunk metadata was corrected explicitly, not silently treated as upstream content. `src/apply_phase2_patches.py` validates all inputs before applying, recognizes already-applied state, and rejects unexpected content without partial mutation. Fresh/idempotent and atomicity tests pass from extraction.

`binding/restore_go_llvm.py` validates the full pinned module ZIP, controlled bundle identity, exact compatibility-patch hash and intended preimages before creating an absent destination; it checks postimages after application. Four real tests cover cold restoration, existing destination refusal, tampered patch, and corrupt ZIP. No global module cache or original source is used as a replacement application checkout.

Historical warm scalar rebuild: `logs/20260908T130700_gate2a_scalar_warm_build.log`, actual `go test -mod=readonly -tags=byollvm,p2probe ./compiler -run ^TestP2ScalarProof$ -count=1 -v -timeout=10m`, followed by pinned Clang/LLD commands. The original Go ELF identity was retained. Production patch-state check: `reports/20260908T131100_gate2a_patch_application.json`. Short physical scalar records and the distinct C transport control remain preserved. No full clean SDK/toolchain bootstrap was attempted in finalization; the SDK is an explicit prerequisite.

## Gate 2B — Real TinyGo CLI: PASS

The extracted CLI is rebuilt by `make tinygo`, not by renaming the scalar hook or invoking the bundled binary. `reproduce_from_extraction.sh` first deletes only the extracted CLI binary and creates fresh Go/TinyGo build caches. The actual Makefile command is `go build -buildmode exe -o build/tinygo -tags byollvm -ldflags="-X github.com/tinygo-org/tinygo/goenv.GitSha1=cf0b7edc-phase2-archive" .` with Makefile-derived pinned CGO flags, logged verbatim. The archive label is explicit and avoids a nonexistent `.git` lookup; it is not a new upstream revision.

Verified result: `tinygo version 0.23.0 linux/amd64 (using go version go1.18.10 and LLVM version 14.0.0git)`. The fresh P2 whole-program ELF demonstrates the actual P2 TargetMachine. CLI hashes are recorded per extraction; unlike the canonical P2 ELF, native CLI byte identity across arbitrary source paths is not a promised property.

## Gate 2C — Experimental P2 target and loader: PASS, bounded

`src/tinygo/targets/p2.json` uses LLVM target `p2`, GOOS `linux` and GOARCH `arm` as a Go package-selection surrogate, with `p2`, `baremetal`, `scheduler.none`, `gc.none` tags. This is not ARM code retargeting. The actual loader trace in `artifacts/gate2f-loader-trace-20260908T140446.301348854Z/effective-loader-selection.json` reports 10 packages, 104 parsed Go/Cgo files, and 2 ignored Go assembly files. This supersedes the earlier surrogate `go list` inventory (16 packages/250 source inputs), which by itself did not establish TinyGo's effective selection. `loader.Load` calls the retained trace; `Package.parseFiles` parses Go/Cgo rather than Go `SFiles`.

The real backend supplies P2 layout `e-p:32:32-i32:32-i64:32`; final output is ELF32 little-endian machine `0x12c`, entry `0x0`, with 40-byte section headers. P2's ThinLTO path is disabled target-specifically because the pinned LLD rejected its object as `invalid e_shentsize 10240`; the final path emits native P2 objects, without rewriting ELF headers. The profile disables automatic stack sizing and C jump tables/unwinding; the retained IR/object/ELF describe the demonstrated program, not arbitrary lowering support. No debug-unwind support is claimed.

Historical absolute target profiles remain unchanged. The extraction recipe renders only a temporary JSON with the extracted `p2.ld` path and recreates a resource-header symlink to the installed SDK. It does not search the intentionally incomplete packaged `src/tinygo/llvm-project/clang/include` for libclang API headers.

## Gate 2D — Runtime startup and Go main: PASS on preserved hardware

The proven P2 cog bootstrap establishes the one-cog layout, PTRA, data/BSS and clock/UART state before Go prologues. Go runtime entry calls the normal `scheduler_none.run`: `initHeap -> initAll -> callMain`. The no-GC initializer does not pretend to allocate. PTRA is established at `0x70000` before calls; cog/LUT reservations are `0x000..0x200` / `0x200..0xa00`, and ordinary Hub code follows.

The imported package's observable UART side effect precedes main-package init and readiness exactly once: `P2 PHASE2 IMPORT INIT`, `P2 PHASE2 INIT`, `READY P2E 1`. Pure nonzero initializers may be folded at compile time; the report does not mislabel that as executed initialization. Historical boot milestone and clock/UART failures: `PHASE2_GO_INIT_MAIN_HIL_20260908.md`, `hil/20260908T121005Z-go-init-main`, `hil/20260908T121301Z-go-init-main`; successful milestone: `hil/20260908T121552Z-go-init-main`.

Hardware `LOCKNEW/LOCKTRY/LOCKREL` primitives implement bounded critical sections; this is not general IRQ masking or multicog scheduling. Time/sleep hooks deliberately abort rather than return fabricated timestamps. No full `machine` API is implemented.

## Gate 2E — Go-owned application and negative cases: PASS, bounded

`src/p2goapp` owns command parsing, formatting, the stateful application loop and calculations. `PROTOCOL.md` specifies the independent host oracle. Thin C/PASM primitives own only hardware byte I/O/startup, not the Go application calculation. Retained Go and host tests exercise nested non-inlined calls with live locals, branches/loops, arrays/structs, persistent globals, signed comparisons, uint32 wraparound and bounds checks.

`reports/gate2e-evidence.json` and `logs/gate2e-cli-build-verifyir-printir.log` bind the Go sources and actual ordinary CLI build to the canonical ELF. Allocation negative: `logs/gate2e-negative-allocation.log` rejects a genuinely escaping dynamic allocation at link time for undefined `runtime.alloc`. Goroutine negative: `logs/gate2e-negative-goroutine.log` reports `attempted to start a goroutine without a scheduler`. These are deliberate expected failures, not successful feature support. Actual bounds-panic evidence is separate below.

Observed ABI evidence is scalar/by-reference with PTRA stack handling and R31 scalar return; nested Go calls and relocation targets are retained in `reports/gate2e-disassembly.txt` and final artifacts. The backend's generated tuple/multi-scalar return failed (`runtime.doAtomicAdd`, `unable to allocate function return #1`), so those atomic stand-ins are excluded for P2. General atomic APIs and tuple returns are unsupported; i64 behavior remains untested.

## Gate 2F — Physical application proof and regressions: PASS on preserved records

All raw terminal captures, vectors, JSONL responses, command lines, source snapshots, ELF identities and failures are retained. Three distinct fresh final-image records, each 138 correct challenges/unique IDs and four malformed inputs, were replayed offline from the new extraction:

- `hil/gate2f-final-1-20260908T131715.175151Z`
- `hil/gate2f-final-2-20260908T131719.162611Z`
- `hil/gate2f-final-3-20260908T131723.093446Z`

The historical hardware command is stored in each `command.json`: pinned `.work/bin/loadp2 -p /dev/ttyUSB0 -b 115200 -l 115200 -ZERO -v -t <recorded-ELF>`. This documents past evidence only; it is NOT an instruction or authorization to reload hardware during finalization.

Exact Go XOR-1 mutation: `artifacts/gate2f-mutation-20260908T131809.889528543Z`, physical predicted wrong result `hil/gate2f-mutation-20260908T131831.929435Z`. Byte-restored source/ELF: `artifacts/gate2f-restored-20260908T131856.889558316Z`; fresh positive: `hil/gate2f-restored-positive-20260908T131857.382096Z`. Later release/review positives are retained as additional records, not substituted for the three distinct runs.

Actual bounds panic: `hil/gate2f-panic-20260908T132003.741335Z` and corrected bounded-observation record `hil/gate2f-panic-20260908T134348.315917Z`, with ordered arm/trigger and exact `panic: runtime error: index out of range`, no forbidden continuation. An ELF filename containing `panic` is explicitly rejected as diagnostic evidence. Fresh review positive after panic: `hil/gate2f-review-final-after-panic-20260908T134403.698371Z`.

The independent C control is `hil/phase1-c-regression-20260908T120849Z` (18/18); full original C records remain in the Phase 1 archive. C is never labeled as a Go result.

Portable provenance: `artifacts/gate2f-loader-trace-20260908T140446.301348854Z/metadata.corrected.json` retains exactly two real object inputs and the linker script, with sizes/hashes and original path mapping. Pinned LLD applies `R_P2_20`, `R_P2_32`, `R_P2_AUG20` and reproduces the ELF byte-identically without the original temporary/cache inputs. Corrupt object and wrong-relocation-target controls reject. This object-to-ELF proof is distinct from the now-successful fresh source-to-ELF extraction rebuild.

## Accurate image/memory accounting

`FINAL_ELF_LAYOUT.txt` was produced by pinned `llvm-readobj --file-headers --sections --program-headers` on the fresh extracted ELF. ELF file: 11,640 bytes. File-backed PT_LOAD bytes: 4,778. Sections: `.text` 4,572, `.rodata` 184, `.data` 22, `.bss` 96 bytes; reserved `.heap` and `.stack` are each 49,152 bytes. Stack reservation is `0x70000..0x7c000`. Maximum loaded/reserved end is `0x7c000` (507,904), below the 524,288-byte Hub limit, leaving 16,384 bytes beyond that reservation. PT_LOAD MemSiz includes address gaps/reservations, not only live data. These are linker reservations, NOT measured maximum stack use, functioning allocation capacity, or a generic runtime footprint. Historical full accounting: `artifacts/gate2f-final-cli-20260908T134314.022218017Z/hub-memory.json`.

## Exact offline reproduction and SDK requirements

This archive is **not SDK-self-contained**. Baseline inputs: `.work/toolchains/go1.18.10`, `.work/build/llvm` (libraries, generated headers and tools), `.work/src/llvm/llvm/include` (as reported by pinned `llvm-config`), `.work/phase2/src/llvm/{clang,lld}` (API headers), `.work/build/llvm/lib/clang/14.0.0/include` (resources), `.work/phase2/cache/go-mod` (CLI dependencies). Cold-binding tests also use the pinned module ZIP under `.work/cache/go-mod/cache/download/tinygo.org/x/go-llvm/@v/` or the Phase 2 equivalent. These are SDK/module prerequisites only, never original TinyGo/application source fallbacks. Nothing downloads or upgrades them.

Inside the established container, after safely extracting to any absent temporary directory:

```sh
export BASELINE_ROOT=/work/propeller2/tinygo-p2-handoff
export P2_ROOT=/tmp/your-extracted-phase2
export PHASE2_ROOT="$P2_ROOT" P2_BASELINE_ROOT="$BASELINE_ROOT"
BASELINE_ROOT="$BASELINE_ROOT" P2_ROOT="$P2_ROOT" OUT_ELF="$P2_ROOT/fresh-final.elf" \
  sh "$P2_ROOT/scripts/reproduce_from_extraction.sh"
```

The recipe sets `GOROOT`, pinned `GOMODCACHE`, `GOWORK=off`, `GOPROXY=off`, `GOSUMDB=off`, `GOFLAGS=-mod=readonly`, `CC=/usr/bin/clang`, `CXX=/usr/bin/clang++`, `LLVM_BUILDDIR`, pinned `CLANG_SRC`/`LLD_SRC`, `LD_LIBRARY_PATH`, `TINYGOROOT`, and fresh `GOCACHE`/`XDG_CACHE_HOME`. It runs `make -C "$P2_ROOT/src/tinygo" tinygo GIT_SHA1=cf0b7edc-phase2-archive`, then the real CLI with `-scheduler=none -gc=none -opt=z -panic=print -work -x -printir -verifyir`. The canonical digest check fails closed.

For all five extracted suites, archived Phase 1 host regression, raw record replay and full build, run `scripts/verify_extracted_archive.py --archive <archive> --baseline-root "$BASELINE_ROOT" --log-dir <new-absent-log-dir>` via `docker exec --user 10000:10000`. Its receipt contains exact argv/cwd/env, return codes, test counts, hash inventory, log hashes and fresh CLI/ELF identities. Historical parent validators receive a disposable project-shaped copy of archive contents, not installed application sources. Full commands/results are in `FINAL_REPRODUCTION_AND_ARCHIVE.md`.

## Preserved failures and non-goals

Earlier ABI/ThinLTO/clock/UART/patch failures and old packaging failures remain in `logs`, `artifacts`, `hil`, and historical reports. In particular, `logs/extracted-review-preverify2.log` and `logs/extracted-reproduce-preverify2.log` show the real missing HIL import/API-header failures. `logs/independent-old-archive-failure-1788891532595626836.log` is the OLD archive's `/.work/phase2/src/apply_phase2_patches.py` failure, not the repaired staged tree. Prior premature closure claims in older reports are superseded by actual extracted receipts, not adopted as evidence.

One cog, `scheduler=none`, `gc=none`. No goroutines, general GC/heap allocation, multicog Go scheduling, atomics, tuple ABI, general IRQ/time/driver support, networking or persistent storage. i64 remains untested. There is no Git repository/remote at the handoff root and no invented commit or push. No transport delivery is claimed by implementation.