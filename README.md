# TinyGo / Propeller 2 — experimental Phase 2

A version-pinned, one-cog TinyGo P2 port/application proof: ordinary `tinygo build`, real imported package initialization and Go `main`, and a Go-owned UART challenge application. This is **not** a general-purpose TinyGo P2 platform. Only `scheduler=none`, `gc=none` is supported by this proof.

The historical Phase 2 hardware runs proved the application on a P2-EC32MB Rev B with 20 MHz TCXO, 160 MHz clock and UART pins 62/63. Publication preparation ran **no new HIL, serial access, board reset or flash operation**. The offline clean compiler/application rebuild reproduces that exact recorded ELF:

```text
132b9cf87bc521cf433e8b33e58d24544d0dde3dcf6e13592058b3b1a14416a8
```

## Source layout

- `src/tinygo/`: complete patched TinyGo source supplied by the sealed archive, without its generated compiler. Upstream submodules/SDK are not bundled.
- `src/p2goapp/`, `src/p2panic/`: ordinary Go application, host tests, imported init package and bounds-panic example.
- `src/p2llvm/`, `src/go-llvm/`: available P2 libraries/tools and patched LLVM binding sources.
- `binding/`, `patches/`, `patch-manifest.json`: controlled go-llvm bundle, immutable upstream ZIP metadata, cold restore tool and guarded patches.
- `scripts/`, `tests/`, `utilities/`, `parent-cache/*.py`: reproduction and offline verification. The `parent-cache` name is historical; only verifier/fixture material is selected for Git, not agent sessions/prompts.
- `hil/`, `artifacts/`, `reports/`: compact historical evidence and reports; verbose build/failure logs are release-archive-only.
- `phase1/`: browsable original scalar C-calling-Go project. Its compiler hook deliberately bypassed runtime/init/main; do not confuse this with the later ordinary Phase 2 application.
- `baseline/tinygo-p2-final-handoff-20260908.tar.gz`: byte-identical immutable Phase 1 handoff including its full original evidence.
- `provenance/`: per-file source identities, explicit exclusions, notices and packaging changes.

Start with `reports/PHASE2_SUMMARY.md`, `reports/CAPABILITY_MATRIX.md` and `reports/FINAL_REPRODUCTION_AND_ARCHIVE.md`. Reports under `project/` and `phase1/` are historical; references to absent handoff instructions, old workspace paths or earlier delivery status are not current instructions.

## Pinned external SDK — deliberately separate

Use the established Linux/x86-64 `propeller2` container and the separately installed baseline. Pins are in `project/sources.lock.json`: TinyGo v0.23.0, Go 1.18.10, ne75 P2 LLVM 14.0.0git, and the original P2LLVM/loader revisions. No upgrade, native Mac migration or clean SDK bootstrap is claimed.

The baseline must provide `.work/toolchains/go1.18.10`, `.work/build/llvm`, `.work/phase2/src/llvm/{clang,lld}`, cached Phase 2 Go modules and the pinned go-llvm upstream ZIP from `.work/cache/go-mod/cache/download/`. The old SDK is a compatibility experiment, not a production/server recommendation.

The archived reproduction script is unchanged and requires both roots:

```sh
BASELINE_ROOT=/path/to/pinned/baseline \
P2_ROOT=/path/to/tinygo-p2 \
OUT_ELF=/tmp/p2goapp-reproduced.elf \
sh scripts/reproduce_from_extraction.sh
```

It deletes/rebuilds the local TinyGo CLI, uses fresh compilation caches, renders a temporary target profile and fails if the ELF differs. It does not flash hardware. Original historical `gate2f_*build.sh` and HIL tools may contain old absolute paths; they are not the portable publication entry point.

## Offline verification

```sh
python3 scripts/repository_check.py --inventory-only
```

For the complete host-only check, run as UID/GID 10000 in the existing container:

```sh
python3 scripts/repository_check.py \
  --root /work/propeller2/tinygo-p2 \
  --archive /path/to/tinygo-p2-phase2-handoff.tar.gz \
  --baseline-root /work/propeller2/tinygo-p2-handoff \
  --log-dir /tmp/tinygo-p2-check-UNIQUE
```

This packaging-only runner checks source identities, safely verifies the sealed archive, creates a disposable source copy, restores excluded historical log fixtures only there, cold-restores the binding, runs all 21 Phase 2 Python tests, 39 Phase 1 host tests plus Go reference/gofmt checks, Go application tests, three offline raw-record replays, and the actual clean CLI/application rebuild. It copies module inputs before use so Go locks cannot mutate the original cache; installed compiler/SDK trees remain external read-only inputs. Full commands, logs and a machine-readable receipt remain outside Git. Use a fresh log directory for every invocation. `--skip-build` is available for an additional core-test rerun, not as a replacement for the full rebuild gate.

## Sealed full evidence / publication status

The complete Phase 2 archive is 31,264,908 bytes, SHA-256:

```text
f1da3d3a31090ecad29d17691d21fab095321584c7ce83cce9b8d07064130f80
```

The private repository is [speccy88/tinygo-p2](https://github.com/speccy88/tinygo-p2). The evidence prerelease is [phase2-verified-20260908](https://github.com/speccy88/tinygo-p2/releases/tag/phase2-verified-20260908), with that exact archive, its original `.SHA256` and original `.verification.json` sidecars as release assets, not Git blobs. Access requires an authorized GitHub account. The full archive retains historical agent handoff context as originally sealed, so it is intended for this private evidence asset set, not a public upload. It must never be silently repacked or redacted under the same verified identity.

Unsupported/unproven: general allocation/heap/GC, goroutines/channels/scheduling, multicog, atomics, general interrupts/time/drivers/networking/storage; i64 is untested. See the capability matrix for narrower details. See `NOTICE.md` for license boundaries; no blanket license replaces upstream terms.
