# TinyGo → Propeller 2: version-pinned scalar proof and Codex handoff

**Physical proof completed September 8, 2026 on Linux/x86_64. This is not a completed general TinyGo P2 port.**

The immediate question is narrow: can TinyGo **v0.23.0** compile externally callable Go scalar functions into real **P2 ELF objects**, using ne75's LLVM 14-development backend, and return correct results when called from C on the physical P2?

## Start here

Give Codex this folder and the instructions in **`CODEX_PROMPT.md`**. Its persistent task rules are in **`AGENTS.md`**. The source-level findings and exact reasons for the design are in **`docs/SOURCE_AUDIT.md`**.

## What is implemented

- Locked TinyGo, P2LLVM, LLVM backend and ELF-capable loader revisions.
- Workspace-local downloads and builds, including an optional checksum-verified Go 1.18.10 SDK download.
- Native Apple Silicon build configuration; no default 32-job build, hardcoded Homebrew LLVM path, or system installation.
- An additional TinyGo compiler test hook that feeds actual Go SSA to the existing TinyGo function builder and real P2 target machine.
- An **addition-only** stage, followed by a separate two-function arithmetic/bitwise stage.
- A C startup/serial harness with two clearly distinguished images: C-only baseline and C-calling-Go image.
- ELF/IR checks, source/artifact hashes, recorded build commands, linker maps and disassembly collection.
- RAM-only hardware runner using one `loadp2` process and a pseudo-terminal. It does not reopen the serial port after loading.
- Host tests, negative controls, and structured reports that distinguish host checks from physical hardware results.

## What actually ran here

The final Linux container rerun is `reports/final-host-validation.json`: 39 Python host tests (including the P2-only stdio-field guard), Go reference tests, and overlay formatting passed. The supplied original portable report remains `reports/host-validation.json`.

Actual pinned TinyGo/LLVM compilation produced the P2 object and linked C/Go images. The physical P2 C baseline and Go image each passed all 138 challenge pairs after the final container hardening; the Go object, Go ELF, and C ELF retained their proven SHA-256 identities. Three earlier independent Go RAM downloads, a deliberate Go-source mutation failure, and a byte-for-byte restoration pass are retained under `.work/hil/` and `.work/mutation/`. See `reports/CODEX_REPORT.md` and `docs/PHYSICAL_RUN.md` for commands and limits.

## Why there is a compiler hook rather than `tinygo build -target=p2`

TinyGo v0.23.0's public `CompilePackage` requires a loaded runtime and predeclares `runtime.alloc`, even for a package whose useful payload is just addition. A stock P2 runtime/target does not exist in this baseline. Merely creating `p2.json` is therefore not the minimal experiment.

The added `compiler/zz_p2probe_test.go` uses the **same internal TinyGo SSA-to-LLVM function builder** while intentionally excluding package initialization and the runtime. Only selected straight-line `uint32` leaves are admitted. It does not handwrite their LLVM IR, compile them with C, or generate for ARM/WebAssembly and change the target string afterward.

This is a compiler integration probe. Success does **not** establish normal `tinygo build`, Go `main`, heap allocation, strings, slices, GC, goroutines, channels, `machine`, networking, or multicog execution.

## Reproducing in the verified Linux container

The original Mac-oriented scaffold was executed and proven on Linux/x86_64 inside the pinned container. Use the exact Linux recipe in `docs/PHYSICAL_RUN.md`, including the workspace-local Go 1.18.10 PATH and `P2_JOBS=2`. The Dockerfile is included at `artifacts/Dockerfile.tinygo-p2-dev`; no host toolchain or system installation is modified.

```sh
make host-test
make preflight
make fetch
make fetch-go
make llvm
make backend-control
make probe                 # Original objective: P2 object with p2_add only.
make probe-full            # Separate expansion: p2_add and p2_mix.
make libraries
make loader
make baseline
make firmware
make ports
```

The old Go SDK is installed below `.work/toolchains/`, not over your existing Go installation. Alternatively set `GO18` to the actual `bin/go` inside a Go 1.18.10 SDK. `GO18` is not intended to point at a `golang.org/dl` wrapper. Go 1.18.10 is an archived compatibility baseline, **not a recommended production/server toolchain**.

There is no automatic firmware upload during build commands. Hardware actions are explicit and the exact Linux commands are in `docs/PHYSICAL_RUN.md`:

```sh
python3 scripts/project.py hil --mode c --port /dev/ttyUSB0 --allow-ram-reset
python3 scripts/project.py hil --mode go --port /dev/ttyUSB0 --allow-ram-reset
make evidence
```

Use the exact verified port only after confirming the attached FTDI identity. `--port auto` is allowed only when exactly one eligible USB serial device is present. Never guess among multiple devices.

## Board profile

`firmware/p2-edge-tcxo.json` is physically validated for the attached **P2-EC32MB Rev B with a 20 MHz TCXO**: external-oscillator mode, 160 MHz, console pins 62/63, 115200 baud. This evidence is specific to that confirmed board and does not authorize a different device.

The firmware touches only the console and clock/startup facilities. It uses internal HUB RAM. External PSRAM, SD, SPI flash, motors and other GPIO are outside scope. An actual RAM download resets the MCU and replaces its current RAM program; do not run this while the board is controlling equipment.

## Outputs and success levels

| Evidence | Meaning |
|---|---|
| `reports/host-validation.json` | Supplied original portable host-side report. |
| `reports/final-host-validation.json` | Final Linux host rerun; still host-side only. |
| `.work/out/c-control/` | C backend control, never Go evidence. |
| `.work/out/probe-add/go.o` and `checked.json` | First objective: Go addition compiled into a structurally checked P2 object. |
| `.work/out/probe/` | Expanded two-function compiler probe. |
| `.work/out/firmware/go.elf` | Linked C + Go image; not yet hardware proof. |
| `.work/hil/<timestamp>-go/hardware.json` | Physical-board result after randomized serial challenges, provided `status` is `PASS`. |
| `.work/evidence/` | Hash index and source diffs/status for the return handoff. |

`go.ll`, `go.o` and `go.s` are hashed by the compiler hook and checked again before linking. The hardware runner checks the linked image hash and requires a passing C baseline on the same port and clock profile.

## Return to Fred

Codex should write `reports/CODEX_REPORT.md`, retain all failure logs and patches, and return a small results archive containing the reports, `.work/out`, `.work/hil`, `.work/evidence`, relevant `.work/logs`, and changed source/overlay files. Do not include the entire LLVM checkout, SDK, build tree, caches or private environment values.
