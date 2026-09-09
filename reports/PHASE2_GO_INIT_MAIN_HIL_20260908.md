# Phase2 ordinary Go init/main physical milestone — 2026-09-08

## Result

**PASS (bounded init/main milestone):** a fresh ordinary TinyGo CLI ELF was RAM-loaded on the verified P2 and produced Go-originated markers in order:

1. `P2 PHASE2 IMPORT INIT`
2. `P2 PHASE2 INIT`
3. `READY P2GO`

Raw loader/serial capture and pass JSON: `.work/phase2/hil/20260908T121552Z-go-init-main/`.

## Source and artifact identity

- TinyGo `0.23.0`, Go `1.18.10`, LLVM `14.0.0git` (P2 target registered).
- Final ELF SHA-256: `1ab708b1bc77a93c9c390434161d4942c2678eec06cb33f7c3dbcaa3356aa836`.
- Identity file: `.work/phase2/reports/20260908T121600_phase2_final_identities.txt`.
- ELF inspection/disassembly: `.work/phase2/reports/20260908T121500_phase2_uartwait_final_inspection.txt`.
  It is ELF32 P2 (`Machine 0x12C`), entry `0x0`, section-header entry size 40, Hub Go text at `0xA00+`, BSS at `0xCD4..0xCD8`, and stack `0x70000..0x7C000`.

## Changes

- Fixed TinyGo target linker script path from the Hermes `/opt/data/...` namespace to the actual serial-container `/work/propeller2/...` namespace.
- Retargeted the local Clang resource-header symlink to the container’s `/work/.../.work/build/llvm/.../include` path.
- Added `p2goapp/bootpkg`: its `init` prints the first marker and initializes `State`; main package init reads that state before printing its own marker.
- Corrected P2 startup clock `HUBSET` operands to use registers for full 32-bit clock words; disassembly shows `hubset r0` / `hubset r1` instead of truncated immediates.
- Added the required `waitx #20` after `wypin`, matching the pinned P2 lib UART primitive. The preceding two failed RAM runs had dropped/garbled output; they are retained in `.work/phase2/hil/20260908T121005Z-go-init-main/` and `20260908T121301Z-go-init-main/`.
- Added `.work/phase2/scripts/boot_hil.py`, a single-PTY, `loadp2`-owned marker capture. Its command uses only `-ZERO -v -t <ELF>`; no flash, `-9`, or additional serial client.

## Physical preflight and regression

- USB identity: sole `/dev/ttyUSB0`, FTDI `0403:6001`, serial `A500507h`; no holders before or after HIL. Evidence: `.work/phase2/reports/20260908T120700_serial_preflight.json` and `.work/phase2/logs/20260908T121500_phase2_evidence_and_serial_release.log`.
- Container has only the `/dev/ttyUSB0` mapping, network `none`, no privileged mode, and `no-new-privileges`: `.work/phase2/reports/20260908T120700_container_hardening.txt`.
- Phase1 immutable C transport regression passed 18/18 (10 edge + 8 random), copied under Phase2 label at `.work/phase2/hil/phase1-c-regression-20260908T120849Z/`.

## Commands

Build inside `propeller2`:

```sh
export PATH="$ROOT/.work/toolchains/go1.18.10/bin:$PATH" GOROOT="$ROOT/.work/toolchains/go1.18.10"
export LD_LIBRARY_PATH="$ROOT/.work/build/llvm/lib" TINYGOROOT="$ROOT/.work/phase2/src/tinygo"
export GOCACHE="$ROOT/.work/phase2/cache/go-build" GOPATH="$ROOT/.work/phase2/cache/go-path"
cd "$ROOT/.work/phase2/src/p2goapp"
"$TINYGOROOT/build/tinygo" build -target="$TINYGOROOT/targets/p2.json" -scheduler=none -gc=none -o "$ROOT/.work/phase2/out/p2goapp-phase2.elf" .
```

RAM-only HIL inside `propeller2`:

```sh
python3 .work/phase2/scripts/boot_hil.py
```

## Scope boundary

This proves imported-package init, main-package init, `runtime.run`, and `main` on physical hardware. It does not claim the later Go-owned challenge application, atomic/multivalue ABI expansion, Gate2A repairs, GC, scheduler, or multicog support.
