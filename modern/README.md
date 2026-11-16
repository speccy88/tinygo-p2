# TinyGo 0.44 for Propeller 2

This directory contains the modern P2 port, its pinned toolchain bootstrap,
source patches, runtime sources, examples, and physical-board test harness.
The historical TinyGo 0.23 sources and evidence elsewhere in this repository
remain a separate baseline.

The port has been built natively and exercised on a P2-EC32MB through the
ROM serial loader. See [VALIDATION.md](VALIDATION.md) for the exact hardware
coverage, toolchain identities, result receipts, and remaining limits.

## Toolchain

- TinyGo 0.44.0, using Go 1.27.4.
- LLVM 15.0.7 with the ne75 P2 backend ported to its supported APIs.
- P2 little-endian ELF, 32-bit pointers, upward-growing hub stacks.
- Linux x86-64 build under WSL2, with a Windows command wrapper and RAM loader.

TinyGo 0.44 supports LLVM 15 and newer. This port updates the P2 backend to
LLVM 15 instead of routing modern Go output through the old LLVM 14 compiler.
The exact upstream revisions and Go download hash are in `toolchain.lock.json`.

The bootstrap needs Git, Python 3.12+, curl, CMake, Ninja, a host Clang/C++
compiler, LLD, zlib development headers, and ordinary Linux C/C++ development
headers. It downloads the
pinned Go toolchain, verifies its SHA-256, restores the source revisions, and
applies the patches and overlay. Existing local changes are preserved if they
do not match the bundle.

```sh
bash modern/build-toolchain.sh "$HOME/tinygo-p2-work"
```

The compiler build defaults to three jobs. Set `P2_BUILD_JOBS` to change this.
The build stays in the Linux filesystem; the repository may be on Windows.
`prepare-sources.py` performs the source restoration separately from compiling.

## Build and load

From the repository root in PowerShell:

```powershell
./modern/tinygo.ps1 version
Set-Location modern/examples
../tinygo.ps1 build -target=p2 -o ../hil/build/conformance.elf ./conformance
../hil/.venv/Scripts/python.exe ../hil/conformance.py `
    --port COM12 --suite language ../hil/build/conformance.elf
```

Create the Windows test environment with `python -m venv modern/hil/.venv`
and install `modern/hil/requirements.txt` into it before the first test.
For an ordinary application, use `hil/p2ram.py` to load its ELF into RAM.
The test harness resets the board, downloads the image through the ROM loader,
checks the ROM checksum response, and uses a fresh host challenge for each run.
It does not program SPI flash.

`tinygo.ps1` accepts optional leading `-Distro` and `-WorkRoot` arguments.
Its default distribution is `Ubuntu-26.04`. The remaining arguments are
forwarded to TinyGo, including `-o`, `-target`, and linker flags.
For Linux command lines, `modern/tinygo.sh` sets the matching tool paths.

To build and load an application into RAM directly from PowerShell:

```powershell
./modern/tinygo.ps1 flash -target=p2 -port=COM12 ./application
```

Add `-monitor 10` for a ten-second serial capture, or `-o application.elf` to
keep the compiled image. The wrappers default to `GOEXPERIMENT=nojsonv2`:
this selects Go 1.27's compact, compatible `encoding/json` implementation
because the newer implementation exceeds P2 hub RAM in common applications.
The Go language version remains 1.27. An explicitly set `GOEXPERIMENT` is
preserved, including an empty value.
Both wrappers keep build caches under a hash of `source-manifest.json`, so a
backend update cannot reuse object code from an older patch with the same
LLVM version number. `XDG_CACHE_HOME` can select an explicit test cache.

## Runtime design

The cores scheduler runs ordinary TinyGo goroutines on all eight cogs. It uses
the existing TinyGo channels, mutexes, timers, and core-affinity machinery.
`machine.CogID()` reports the current cog, and `machine.AssignCore(n)` pins the
calling goroutine. Scheduling remains cooperative, as in TinyGo's cores
scheduler. The P2 task switch saves the ABI's callee-saved registers with SETQ
block transfers and places the stack canary at the upper end of each stack.

Hardware locks serialize the scheduler, atomic operations, printing, and futex
queues. Byte, halfword, word, doubleword, and generic unaligned atomic libcalls
share the same atomic lock. The CAS fallback updates the caller's expected
value after a failed comparison.

The conservative collector stops other cogs using the P2 attention interrupt.
Each cog saves its registers and parks in assembly; the collecting cog scans
roots while the scheduler queue is locked. Integer register snapshots are
scanned explicitly, and conservative scanning includes every byte offset
because the P2 C ABI can spill a pointer on an unaligned stack. Secondary system stacks are outside
the global-data range, so unused stack space is not scanned as global roots.
The memory primitives preserve the real stack pointer and avoid the hub FIFO,
which allows attention interrupts during copying and clearing.

The board profile uses the 20 MHz TCXO, a 160 MHz system clock, and smart-pin
UART on P62/P63 at 115200 baud. GETCT provides the 64-bit time base. GPIO
configuration and writes use cog 0, with a direct path when already on that
cog, because P2 output state from different cogs is OR-combined.

## PSRAM

`machine.PSRAM` exposes the four 8 MiB devices on the P2-EC32MB as explicit
32 MiB byte-addressed storage. Go objects, pointers, stacks, and the garbage
collected heap remain in hub RAM. The external memory is accessed through
`Configure`, `ReadAt`, `WriteAt`, `Size`, and `IDs`.

One goroutine bound to cog 0 owns the shared clock/select and four parallel
quad buses on P40 through P57. Transfers are serialized; unaligned writes
preserve neighboring bytes. The driver checks device identification, range
bounds, and the measured transaction-cycle limit. `MaxTransactionCycles`
exposes the longest measured transaction. A partial failure reports the
confirmed completed prefix.

## Profiles and tests

| Target | Scheduler | Memory policy | Panic behavior |
| --- | --- | --- | --- |
| `p2` | Eight cogs | Conservative GC | Halt |
| `p2-gc` | Eight cogs | Conservative GC (compatibility alias) | Halt |
| `p2-recover` | Eight cogs | Conservative GC | Explicit unwinding |
| `p2-tasks` | One cog | Leaking allocator | Halt |
| `p2-minimal` | None | No heap allocation | Halt |

Each profile is selected with ordinary `tinygo build`. Explicit unwinding is
optional because it increases code size and runtime work. The combined
formatting/JSON acceptance application fits with the default profile but
exceeds hub RAM with explicit unwinding; smaller recovery applications fit.
The linker reserves a 16 KiB primary system stack, seven 8 KiB secondary
system stacks for the cores profiles, and the remaining usable hub RAM for
the heap. Default goroutine stacks are 8 KiB and can be changed with
`-stack-size`. The linker rejects images with less than 64 KiB left for heap.

Run the compiler and runtime host checks after building the toolchain:

```sh
bash modern/verify-host.sh "$HOME/tinygo-p2-work"
```

The hardware suite separates language/concurrency, standard-library, PSRAM,
GC stress, and panic/recovery acceptance. Host tests cover the ROM image
loader, Windows argument forwarding, atomic ABI semantics, PSRAM API failures,
and 6,048 memory-assembly alignment/overlap cases. Host/model checks do not
substitute for compiling and running each native image on the board.

## Source layout

- `patches/llvm15-p2.patch`: complete P2 backend/frontend/linker integration
  against official LLVM 15.0.7, plus port regressions.
- `patches/tinygo-p2.patch`: modifications to existing TinyGo 0.44 files.
- `patches/p2llvm-tools.patch`: P2 compiler builtins, test tooling for a separate
  LLVM source tree, and port documentation.
- `overlays/tinygo/`: new runtime, machine, task-switch, target, and test files.
- `examples/`: standalone Go applications used for acceptance.
- `hil/`: Windows/Python board tooling, independent result oracles, and tests.

`export-sources.py` is a maintainer tool that exports a development checkout
back into this bundle. Run it only after reviewing the source changes. It
exports all three live Git diffs and new TinyGo files, removes stale overlay
copies, and records source hashes in `source-manifest.json`. Upstream
copyright and license terms continue to apply; see the repository's `NOTICE.md`.
