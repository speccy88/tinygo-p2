# Final reproduction, failures, and archive acceptance

This is an implementation-candidate record, not delivery. Hardware evidence is preserved from earlier physical runs; all work documented here is offline in the established Linux/x86_64 `propeller2` container as UID/GID 10000, network none. No SDK/source baseline modification, device access, new network or device exposure, or clean toolchain bootstrap occurred.

## Preserved actual failures

- `logs/independent-old-archive-failure-1788891532595626836.log` is an unmodified copy of the independent OLD archive failure. Its patch suite resolved `/.work/phase2/src/apply_phase2_patches.py` and failed both tests. The workspace already had the correct `PHASE2_ROOT/src/apply_phase2_patches.py`; packaging must restage that fix, not edit a nonexistent extracted path.
- `logs/extracted-preverify2-results.log`: `restore=0 patches=0 review=1 app=0 reproduce=2`.
- `logs/extracted-review-preverify2.log`: `ModuleNotFoundError: No module named 'hil'` when importing the panic helper from a standalone extraction.
- `logs/extracted-reproduce-preverify2.log`: missing `clang-c/Index.h` from the intentionally incomplete extracted TinyGo `llvm-project` tree; no ELF was emitted. The historical `.git` warning did not cause this header failure.
- Prior warm-build, ABI/ThinLTO, startup, serial and provenance failures remain in their original logs/artifacts/hil directories. They are not new successes or new hardware runs.

## Exact bounded repairs

- `scripts/gate2f_panic_hil.py`: lazy HIL import/root discovery in live `main()` only; offline `validate_raw()` has no HIL dependency. Existing live behavior and panic acceptance checks retained.
- `scripts/test_phase2_review_utilities.py`: existing five tests retained; the first panic test additionally imports a lone copied helper with isolated Python (`-I`), explicitly proving no `hil` import occurs.
- `scripts/reproduce_from_extraction.sh`: explicit baseline Clang/LLD API include trees and guards; executable resource-header relink; fresh caches and actual CLI removal/rebuild; explicit archive build label; version/hash logging and fail-closed canonical ELF check. Original target JSON is untouched; only a temporary extraction profile is rendered.
- `src/tinygo/Makefile`: `GIT_SHA1` override retains normal Git default for source checkouts and makes archive builds deterministic/nonfatal without Git internals.
- `scripts/package_final_deliverable.py`: stage additionally includes the exact unchanged original `scripts/hil.py`. Source copies, not just Git diff, retain late added files and prior test portability repairs.
- `scripts/verify_extracted_archive.py`: new offline runner verifies complete archive member/manifest hashes, safely extracts to a unique `/tmp` root, executes all five suites, archived original host tests, raw replays and real CLI/application build, and emits fail-closed machine-readable receipts with exact commands and log hashes. The independently supplied verifier/controller/manifests are untouched.
- Reports: `PHASE2_REPORT.md`, `PHASE2_SUMMARY.md`, `CAPABILITY_MATRIX.md`, this file; `FINAL_ELF_LAYOUT.txt` is fresh real pinned-tool output. Gate names corrected to the original request, and historic premature closure claims superseded by real results.

Preserved earlier workspace fixes are in `tests/test_restore_go_llvm.py`, `tests/test_apply_phase2_patches.py`, and `scripts/test_phase2_review_utilities.py`: extracted `PHASE2_ROOT` is distinct from baseline-only SDK/module ZIP inputs. No ordinary Go app, P2 target/runtime, loader trace, original evidence or Phase 1 source was edited.

## First fresh extraction: preverify3 — PASS

Host copy of the supplied parent inputs (only into this workspace):

```sh
cp -a /opt/data/profiles/coder/cache/tinygo-p2-phase2-input phase2-parent-inputs-run6
cp /opt/data/profiles/coder/cache/reliability/p2-independent/1788891532595626836/extracted-tests-and-rebuild.log phase2/logs/independent-old-archive-failure-1788891532595626836.log
```

The following stage/pack/test command actually returned 0:

```sh
docker exec --user 10000:10000 propeller2 sh -c '
set -eu
B=/work/propeller2/tinygo-p2-handoff
P=$B/.work/phase2
A=$B/.work/archives/tinygo-p2-phase2-preverify3.tar.gz
S=$B/.work/archives/tinygo-p2-phase2-preverify3-stage
python3 "$P/scripts/package_final_deliverable.py" "$B" "$S" "$B/.work/phase2-parent-inputs-run6"
tar --sort=name --owner=10000 --group=10000 --numeric-owner -czf "$A" -C "$S" .
sha256sum "$A"
python3 "$P/scripts/verify_extracted_archive.py" --archive "$A" --baseline-root "$B" --log-dir "$P/logs/extracted-preverify3"
'
```

Preverify archive SHA-256: `c33514f7dddf8a3782aed8f11fb721783ce8a5acfe335ee629457535c3286f06`, 29,929,041 bytes. This is disposable preverification evidence, NOT the final release archive.

- Fresh extraction: `/tmp/p2-archive-check-byra90j2`.
- Project-shaped parent/Phase 1 replay copy: `/tmp/p2-archived-parent-en0bgabe`. It is constructed from archive contents; historical parent validators do not read the installed application tree.
- Full receipt: `logs/extracted-preverify3/receipt.json`, `passed: true`.
- Five suites: restoration 4, patch guard 2, review utilities 5, parent Gate2E 5, parent controls 5; all 21 tests PASS, each return code 0.
- Original Phase 1 host check: 39 tests, Go references and gofmt PASS, return code 0.
- Go application: pinned Go 1.18.10 `go test -count=1 ./...`, PASS, return code 0.
- All three final-1/2/3 physical raw records replayed PASS, return code 0; distinct vector files, 138 correct/unique plus 4 malformed each.
- Real CLI plus application build: PASS, return code 0. New CLI SHA-256 `2e68b6de4bd122e57e9f31fd11b2537a8ccf74445834bffbf17f9814ef3e03ef`.
- CLI version: `tinygo version 0.23.0 linux/amd64 (using go version go1.18.10 and LLVM version 14.0.0git)`.
- Fresh `/tmp/p2-archive-check-byra90j2/fresh-final.elf`: SHA-256 `132b9cf87bc521cf433e8b33e58d24544d0dde3dcf6e13592058b3b1a14416a8`, identical to `hil/gate2f-final-1-20260908T131715.175151Z/hardware.json` and retained original final ELF.

## Exact successful extracted commands and environment

For the first extraction, `E=/tmp/p2-archive-check-byra90j2`, `R=/tmp/p2-archived-parent-en0bgabe`, `B=/work/propeller2/tinygo-p2-handoff`. The runner records the full resolved paths/argv/cwd in its receipt. Actual commands, each rc=0:

```sh
export PHASE2_ROOT="$E" P2_BASELINE_ROOT="$B" BASELINE_ROOT="$B" P2_ROOT="$E"
export GOROOT="$B/.work/toolchains/go1.18.10"
export PATH="$GOROOT/bin:$PATH" GOWORK=off GOPROXY=off GOSUMDB=off
export GOCACHE="$R/.work/cache/archive-go"
export OUT_ELF="$E/fresh-final.elf"
cd "$E"
python3 tests/test_restore_go_llvm.py
python3 tests/test_apply_phase2_patches.py
python3 scripts/test_phase2_review_utilities.py
P2_ROOT="$R" P2_RECORD="$R/.work/phase2/hil/gate2f-final-1-20260908T131715.175151Z" \
  P2_ELF="$R/.work/phase2/artifacts/gate2f-final-cli-20260908T131540.392502595Z/p2goapp-final.elf" \
  python3 "$E/parent-cache/test_verify_gate2e_record.py"
P2_ROOT="$R" python3 "$E/parent-cache/test_verify_gate2f_controls.py"
(cd "$R" && python3 scripts/host_check.py)
(cd "$E/src/p2goapp" && "$GOROOT/bin/go" test -count=1 ./...)
sh scripts/reproduce_from_extraction.sh
```

Raw replay argv and their complete output are in `physical-record-replay-{1,2,3}.log` and the receipt. No live HIL entry point was called.

The real byollvm build selected:

```text
CC=/usr/bin/clang
CXX=/usr/bin/clang++
LLVM_BUILDDIR=/work/propeller2/tinygo-p2-handoff/.work/build/llvm
CLANG_SRC=/work/propeller2/tinygo-p2-handoff/.work/phase2/src/llvm/clang
LLD_SRC=/work/propeller2/tinygo-p2-handoff/.work/phase2/src/llvm/lld
GOMODCACHE=/work/propeller2/tinygo-p2-handoff/.work/phase2/cache/go-mod
```

The Makefile-derived CGO command, including all pinned libraries and LLVM/configured/API include paths, is logged verbatim at `logs/extracted-preverify3/fresh-cli-and-app.log:5`. No absent TinyGo llvm-project API-header path appears there. Recipe scratch/cache paths are logged, and `-mod=readonly`/offline module resolution is enforced.

Fresh layout inspection also returned 0:

```sh
docker exec --user 10000:10000 propeller2 sh -c '/work/propeller2/tinygo-p2-handoff/.work/build/llvm/bin/llvm-readobj --file-headers --sections --program-headers /tmp/p2-archive-check-byra90j2/fresh-final.elf > /work/propeller2/tinygo-p2-handoff/.work/phase2/reports/FINAL_ELF_LAYOUT.txt'
```

## Historical run 6/7: second fresh candidate extraction — PASS; independent environment blocker

The following stage/pack/own-runner command actually returned 0 after the report updates (the old Phase 2 archive/sidecar were preserved separately first):

```sh
docker exec --user 10000:10000 propeller2 sh -c '
set -eu
B=/work/propeller2/tinygo-p2-handoff
P=$B/.work/phase2
A=$B/.work/archives/tinygo-p2-phase2-handoff.tar.gz
S=$B/.work/archives/tinygo-p2-phase2-final-run6-stage
python3 "$P/scripts/package_final_deliverable.py" "$B" "$S" "$B/.work/phase2-parent-inputs-run6"
tar --sort=name --owner=10000 --group=10000 --numeric-owner -czf "$A" -C "$S" .
(cd "$B/.work/archives" && sha256sum tinygo-p2-phase2-handoff.tar.gz > tinygo-p2-phase2-handoff.tar.gz.SHA256 && sha256sum -c tinygo-p2-phase2-handoff.tar.gz.SHA256)
python3 "$P/scripts/verify_extracted_archive.py" --archive "$A" --baseline-root "$B" --log-dir "$P/logs/final-candidate-run6"
'
```

Candidate archive before this final report update: SHA-256 `05c711b2526f1b8da9bfa827b36c8230552e9ac9600c8527b8f222f625b9dc04`, 30,376,040 bytes; 2,559 members / 2,338 regular files / 2,337 manifest-covered files. These are NOT asserted as the last sealed archive identities: all reports/evidence added here require a new stage/pack/check. Its receipt is preserved at `logs/final-candidate-run6/receipt.json`.

- Second extraction: `/tmp/p2-archive-check-53fiij0c`; project-shaped archived-parent copy `/tmp/p2-archived-parent-co8ej1kz`.
- All five extracted suites again PASS (4/2/5/5/5); archived original 39-test host check plus Go/gofmt PASS; Go app tests PASS; all three full raw record replays PASS. Every command rc=0.
- Fresh CLI SHA-256 `e5a67f4e9468b5ec4f2fb10ab5e56a1d4c7534604095bffac71ec0b5a4601518`; real version TinyGo0.23/Go1.18.10/LLVM14.0.0git.
- Actual fresh CLI/application build rc=0; fresh ELF canonical SHA-256 `132b9cf87bc521cf433e8b33e58d24544d0dde3dcf6e13592058b3b1a14416a8`.

The exact required acceptance command was then executed, unmodified:

```sh
/opt/hermes/.venv/bin/python /opt/data/profiles/coder/cache/reliability/verify_p2_final.py
```

It returned **1**, not success. Original receipt: `/opt/data/profiles/coder/cache/reliability/p2-independent/1788897753627105868/receipt.json`; unchanged packaged copies: `logs/independent-candidate-run6-receipt.json`, `logs/independent-candidate-run6-extracted.log`, `logs/independent-candidate-run6-host-path-failure.log`.

Successful independent subgates: complete archive hash/member verification, all 12 frozen source files, original six-entry Phase 1 attestation, fresh extracted behavioral suites, Go app tests, fresh CLI and canonical ELF (`/tmp/p2-independent-final-js3nd8kx`). That fresh extracted worker returned 0 and `passed: true`.

The independent gate's LAST command was:

```sh
docker exec --user 10000:10000 -w /work/propeller2/tinygo-p2-handoff propeller2 python3 scripts/host_check.py
```

Actual output: `A host Go installation and gofmt are required.` Return code: 1, before host tests run. `logs/independent-candidate-run6-path-discovery.log` independently confirms `shutil.which('go')` and `shutil.which('gofmt')` are null on the container's default PATH, while both `.work/toolchains/go1.18.10/bin/{go,gofmt}` exist/executable and the pinned Go reports 1.18.10 linux/amd64. The separate extracted command with that directory prepended already passed all 39 original tests plus Go/gofmt twice.

At that time the blocker could not be repaired by editing Phase 2 package content. A separate `docker exec` does not inherit the PATH exported in the extracted worker, and the baseline `scripts/host_check.py` uses `shutil.which`. The needed prerequisite was the existing pinned Go bin directory on that independent host-check process's PATH (or an authorized explicit invocation environment). This task forbids editing the independent verifier, original Phase 1 source, container-global configuration or files outside `.work`; none was changed, and no wrapper/bypass was created. Those historical receipts correctly remain `passed: false`. Run 8 below supersedes this blocker with actual successful execution, not a relabeling of those failures.

## Final packaging and receipt protocol

Final required host paths are under `/opt/data/propeller2/tinygo-p2-handoff/.work`:

- `archives/tinygo-p2-phase2-handoff.tar.gz`
- `archives/tinygo-p2-phase2-handoff.tar.gz.SHA256`
- `phase2/reports/PHASE2_SUMMARY.md`

Staging and packing are distinct steps. Any later source/report edit requires restaging, then packing again, then fresh final-byte extraction/tests/rebuild again. No source/evidence edit to a stage is accepted without remanifesting. The archive excludes SDK/LLVM checkout, build/module caches, Git internals except the explicit controlled bundle, resource symlinks and recursive prior Phase 2 archives. It includes the compact immutable Phase 1 archive and all physical/failure evidence.

The final-byte receipt is external to the archive to avoid a self-referential hash: `archives/tinygo-p2-phase2-handoff.verification.json`. It must bind the exact final digest/size/member and file counts to successful test commands, CLI/ELF identities, complete inventory and log hashes. Archived prior receipts are transparently historical and carry their own different archive digests. Final source/report content is frozen before the last stage/pack; final logs/receipt are kept outside that packaged tree.

The required independent acceptance command is unchanged:

```sh
/opt/hermes/.venv/bin/python /opt/data/profiles/coder/cache/reliability/verify_p2_final.py
```

Only a successful invocation against the final bytes establishes this gate. It separately checks the original Phase 1 attestation, all 12 frozen files, every archive member/hash, extracted behavioral tests, fresh CLI/application rebuild and original host regression. No verifier/controller/protected manifest edits are allowed. Independent acceptance still does not mean a transport receipt or human delivery.

The run 6 final-seal procedure was not completed; its final archive was still the candidate digest `05c711b2526f1b8da9bfa827b36c8230552e9ac9600c8527b8f222f625b9dc04`. Run 8 repairs this stale packaging explicitly below. No hypothetical run 6 seal is counted as execution evidence.

## Run 8: fresh candidate and required independent acceptance — PASS

Run 7's actual independent receipt and failed/successful logs are preserved unchanged at `logs/independent-run7-{receipt.json,host-path-failure.log,extracted.log}`. Live non-root discovery is `logs/run8-default-path-and-headers.json`: default PATH still lacks Go/gofmt; pinned tools exist; both declared Clang API headers have SHA-256 `07f4b54ec98a23c57387e5ec379b7aac2fc4a1bcf997d2b0f5eae4cdee495877`. No SDK header was changed.

The requested panic-import, byollvm-header and extracted test portability repairs were already in the workspace. Run 8 did not rewrite those functioning helpers or any compiler/application/target/runtime source. It restaged them with the late reports and evidence. The old candidate archive and original sidecar were preserved at `archives/tinygo-p2-phase2-before-run8.tar.gz` and `.SHA256.original` outside the package.

Actual stage/pack commands (return code 0):

```sh
docker exec --user 10000:10000 propeller2 sh -c '
set -eu
B=/work/propeller2/tinygo-p2-handoff
P=$B/.work/phase2
A=$B/.work/archives/tinygo-p2-phase2-handoff.tar.gz
S=$B/.work/archives/tinygo-p2-phase2-run8-candidate-stage
OLD=$B/.work/archives/tinygo-p2-phase2-before-run8.tar.gz
test ! -e "$OLD"
cp -p "$A" "$OLD"
cp -p "$A.SHA256" "$OLD.SHA256.original"
python3 "$P/scripts/package_final_deliverable.py" "$B" "$S" "$B/.work/phase2-parent-inputs-run6"
tar --sort=name --owner=10000 --group=10000 --numeric-owner -czf "$A" -C "$S" .
(cd "$B/.work/archives" && sha256sum tinygo-p2-phase2-handoff.tar.gz > tinygo-p2-phase2-handoff.tar.gz.SHA256 && sha256sum -c tinygo-p2-phase2-handoff.tar.gz.SHA256)
sha256sum "$A"
'
```

Candidate SHA-256 `6f91bd0afbf929fcb9d1deea146dbbd4338fc19bd450d02ca0025a7534d5b4fa`; 30,822,367 bytes; 2,580 members, 2,358 regular files, 2,357 manifest-covered files, 111,390,215 uncompressed bytes. These are the pre-report-update candidate identities, not the final seal.

Both following commands actually returned 0:

```sh
docker exec --user 10000:10000 propeller2 python3 /work/propeller2/tinygo-p2-handoff/.work/phase2/scripts/verify_extracted_archive.py --archive /work/propeller2/tinygo-p2-handoff/.work/archives/tinygo-p2-phase2-handoff.tar.gz --baseline-root /work/propeller2/tinygo-p2-handoff --log-dir /work/propeller2/tinygo-p2-handoff/.work/phase2/logs/run8-candidate-all-suites
/opt/hermes/.venv/bin/python /opt/data/profiles/coder/cache/reliability/verify_p2_final.py
```

All-suite receipt: `logs/run8-candidate-all-suites/receipt.json`, `passed: true`. Every one of its 11 commands returned 0:

- Fresh extraction `/tmp/p2-archive-check-mwya5tuo`; archived parent replay `/tmp/p2-archived-parent-byhdndgr`.
- Five suites: restore 4, patches 2, review 5, parent record verifier 5, parent controls 5 (21 behavioral tests).
- Original 39 host tests plus pinned Go reference/gofmt PASS; application `go test -count=1 ./...` PASS.
- All three distinct final raw records independently replayed PASS, each 138 correct/unique responses and four malformed responses; no live HIL executed.
- Real fresh CLI: `tinygo version 0.23.0 linux/amd64 (using go version go1.18.10 and LLVM version 14.0.0git)`, SHA-256 `3b2364c6e461288ae717d99ee44586a2ce1c1fe2a2d0d90aa38f0abd7797db91`.
- Fresh ELF `/tmp/p2-archive-check-mwya5tuo/fresh-final.elf`: canonical SHA-256 `132b9cf87bc521cf433e8b33e58d24544d0dde3dcf6e13592058b3b1a14416a8`. The full actual byollvm command is `logs/run8-candidate-all-suites/fresh-cli-and-app.log:5`.

Required independent receipt: `/opt/data/profiles/coder/cache/reliability/p2-independent/1788898503105557513/receipt.json`, `passed: true`, copied unchanged to `logs/independent-run8-candidate-receipt.json`. Extracted/build and host logs are `logs/independent-run8-candidate-{extracted,phase1-host}.log`. Independent extraction `/tmp/p2-independent-final-8oghnqor` produced the same canonical ELF. Complete archive hashes, all 12 frozen sources, all six original Phase 1 attestation entries, extracted tests/rebuild and original installed host regression passed.

The supplied verifier observed and executed in run 8 has SHA-256 `3932ace12ced29b86056cd9c9a81eb6d2b8d2b4f5930a0f7592386d8de6eb008`; it now explicitly selects the pinned SDK for the final separate Phase 1 subprocess:

```sh
docker exec --user 10000:10000 -w /work/propeller2/tinygo-p2-handoff propeller2 sh -c 'export GOROOT=/work/propeller2/tinygo-p2-handoff/.work/toolchains/go1.18.10; export PATH="$GOROOT/bin:$PATH"; exec python3 scripts/host_check.py'
```

That exact subprocess appears in the independent receipt with return code 0. This implementation did not edit the supplied verifier, its tests, protected manifest, Phase 1 source/evidence, provider/approval state, services, or container configuration. Its externally supplied invocation correction is distinguished from package repairs; no invented workaround or retroactive success is asserted.

## Final run 8 seal and external receipt

After the above report/evidence additions, stage and pack again, then run both checks on final bytes. The exact final commands are:

```sh
docker exec --user 10000:10000 propeller2 sh -c '
set -eu
B=/work/propeller2/tinygo-p2-handoff
P=$B/.work/phase2
A=$B/.work/archives/tinygo-p2-phase2-handoff.tar.gz
S=$B/.work/archives/tinygo-p2-phase2-run8-final-stage
python3 "$P/scripts/package_final_deliverable.py" "$B" "$S" "$B/.work/phase2-parent-inputs-run6"
tar --sort=name --owner=10000 --group=10000 --numeric-owner -czf "$A" -C "$S" .
(cd "$B/.work/archives" && sha256sum tinygo-p2-phase2-handoff.tar.gz > tinygo-p2-phase2-handoff.tar.gz.SHA256 && sha256sum -c tinygo-p2-phase2-handoff.tar.gz.SHA256)
sha256sum "$A"
'
docker exec --user 10000:10000 propeller2 python3 /work/propeller2/tinygo-p2-handoff/.work/phase2/scripts/verify_extracted_archive.py --archive /work/propeller2/tinygo-p2-handoff/.work/archives/tinygo-p2-phase2-handoff.tar.gz --baseline-root /work/propeller2/tinygo-p2-handoff --log-dir /work/propeller2/tinygo-p2-handoff/.work/archives/run8-final-sealed
/opt/hermes/.venv/bin/python /opt/data/profiles/coder/cache/reliability/verify_p2_final.py
```

No source/report edits follow this last stage. Post-seal logs remain outside the archived tree, preventing circular self-hashes. `archives/run8-final-sealed/receipt.json` binds complete inventory, exact commands/return codes/log hashes, fresh extraction, CLI and canonical ELF to the sealed bytes. The final independent receipt and its original logs are retained separately. `archives/tinygo-p2-phase2-handoff.verification.json` binds both receipts and final archive/sidecar/summary identities; it may report success only when both receipts pass and match the actual final digest. Final-byte receipts, not an older candidate hash in this historical report, establish final archive verification. Delivery/transport remains the parent's separate responsibility.
