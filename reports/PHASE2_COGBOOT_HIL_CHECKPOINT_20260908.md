# Phase2 cog-boot / Gates 2C–2D checkpoint (2026-09-08)

## Outcome

The real ordinary TinyGo CLI image was rebuilt successfully after replacing the unsafe direct-Hub entry with the established P2LLVM/loadp2 cog bootstrap layout. Hardware loading is **blocked before any serial-open/reset** because this execution environment has no `/dev/ttyUSB0` (and no `/dev/ttyUSB*` or `/dev/ttyACM*` device). Therefore no C transport baseline, Phase2 RAM load, or UART marker capture occurred in this run.

## Final artifact

- ELF: `.work/phase2/out/p2goapp-phase2.elf`
- SHA-256: `13da110c3d796ce08d6eb9ea028f533ffab414728dc88e86bc46f5e36d022d7a`
- Previous direct-Hub ELF retained as `.work/phase2/artifacts/20260908T_phase2_cogboot_attempt1/p2goapp-before.elf` (`3b7cacc5b6a21c484be71e966580b197eb75eaf479b953b67a3100e769dc8117`).
- CLI log: `.work/phase2/logs/20260908T_phase2_cogboot_attempt5_initrtlib.log`
- ELF inspection: `reports/20260908T_phase2_cogboot_attempt5_initrtlib_readobj.txt`
- Disassembly: `reports/20260908T_phase2_cogboot_attempt5_initrtlib_disasm.txt`

The fresh CLI command was:

```sh
export PATH="$ROOT/.work/toolchains/go1.18.10/bin:$PATH"
export LD_LIBRARY_PATH="$ROOT/.work/build/llvm/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export TINYGOROOT="$ROOT/.work/phase2/src/tinygo"
export GOROOT="$ROOT/.work/toolchains/go1.18.10"
export GOCACHE="$ROOT/.work/phase2/cache/go-build"
export GOPATH="$ROOT/.work/phase2/cache/go-path"
export LLVM_CONFIG="$ROOT/.work/build/llvm/bin/llvm-config"
cd "$ROOT/.work/phase2/src/p2goapp"
"$TINYGOROOT/build/tinygo" build -target="$TINYGOROOT/targets/p2.json" -scheduler=none -gc=none -o "$ROOT/.work/phase2/out/p2goapp-phase2.elf" .
```

`ROOT=/opt/data/propeller2/tinygo-p2-handoff` for this host. `p2.json` now names the host-visible linker script path. The previous `/work/...` value failed here before loading because it was not mounted in this runtime.

## Boot / layout evidence

`llvm-readobj` reports ELF32 little-endian `elf32-p2`, machine `0x12C`, entry `0x0`, 40-byte section headers. The final linker layout is:

- `__entry=0x0`, size 8: P2LLVM-style `rdlong r0,ptra; jmp #\\16`; it has no stack write.
- `__start0=0x40`, size 16: starts cog 0 at `__start` with `coginit`.
- `__start=0x50`: begins with the established `SETQ2 #511; AUGS #1; RDLONG $0,#0` cog-image copy, then sets `PTRA=0x70000` **before** BSS clearing, clock/UART calls, lock allocation, or Go entry.
- Hub Go/runtime text begins at `0xA00`; `main=0xAA4`, `runtime.run=0xAA8`, `runtime.initAll=0xAB0`, and `main.main=0xB1C` are all Hub calls from the cog startup.
- `.bss=0xCA8..0xCAC`, `.heap=0xCAC..0xCCAC`, `.stack=0x70000..0x7C000`; the linker assertion prevents heap/stack overlap.
- Startup programs only TX pin 62 (`DIRL/WRPIN/WXPIN/DIRH`) and no pin-63 or other GPIO constants appear in `p2_start.c`. It applies the 20 MHz TCXO / 160 MHz sequence once. The single lock is a hardware lock for the existing interrupt critical-section API; it does not claim IRQ support.

## Source changes

- `.work/phase2/src/tinygo/targets/p2_start.c`: cog bootstrap restored, PTRA-safe startup, BSS owner, clock/UART owner, hardware lock, and Go entry.
- `.work/phase2/src/tinygo/targets/p2.ld`: restored cog/LUT and Hub split (`0x0`, `0x40`, `0x200`, `0xA00`) with one heap/stack owner.
- `.work/phase2/src/tinygo/targets/p2.json`: host-visible linker path for this host.
- `.work/phase2/src/tinygo/llvm-project/clang/lib/Headers`: repaired a pre-existing broken `/work/...` symlink to the isolated LLVM Clang 14 headers; required to run the verified host CLI rebuild.

Diff exports: `.work/phase2/artifacts/20260908T_phase2_cogboot_attempt1/tinygo-final.diff` and `go-llvm-final.diff`. Hashes are in `final-hashes.sha256`.

## Hardware preflight blocker and exact resume procedure

`.work/phase2/reports/20260908T_phase2_hil_preflight_blocked.json` records:

- `/dev/ttyUSB0`: absent;
- no eligible serial candidates;
- `/proc/*/fd` scan: no holders;
- no `loadp2` process was started, so no reset or device-side side effect occurred.

When `/dev/ttyUSB0` is actually exposed, first repeat the `/proc/*/fd` ownership scan and require no holders. Then RAM-load the existing Phase1 C baseline and record it distinctly as C using one `loadp2` PTY owner; only after it passes, use one new loadp2 PTY invocation for this final Phase2 ELF:

```sh
$ROOT/.work/bin/loadp2 -p /dev/ttyUSB0 -b 115200 -l 115200 -ZERO -v -t $ROOT/.work/phase2/out/p2goapp-phase2.elf
```

Do not reopen the serial port or use a second terminal. Capture raw bytes in a new unique directory. Required Go-produced order is exactly `P2 PHASE2 INIT\r\n` followed by `READY P2GO\r\n`; any other output, timeout, loader error, or crash is a failed/unexplained hardware outcome and must be retained and diagnosed offline. No flash, SD, PSRAM, extra devices, `-9`, `@address`, or nonconsole GPIO.
