# Modern P2 port: validation and design record

Validation date: 2026-11-16. Hardware: Parallax P2-EC32MB Edge, 20 MHz TCXO,
160 MHz system clock, 32 MiB PSRAM, Windows COM12, ROM identification
`Prop_Ver G`. Firmware was downloaded to hub RAM; SPI flash was not programmed.

## Versions and reproducibility

- TinyGo **0.44.0**, upstream commit `344590c7152e620f3b5369fc289e5d91caf9649d`.
- Go **1.27.4**, verified against the archive SHA-256 in `toolchain.lock.json`.
- Official LLVM **15.0.7**, commit `8dfdcc7b7bf66834a761bd8de445840ef68e4d1a`,
  with the P2 backend, Clang target, ELF support, and LLD integration ported from
  ne75/p2llvm commit `b914b1baa8a2055feb52c801b5c3564eda6a9abc`.

TinyGo 0.44 is the latest stable upstream release checked on the validation
date and requires LLVM 15 or newer. The port uses LLVM 15 natively; application
IR is not translated through LLVM 14 or an intermediate host target.
See the [upstream release](https://github.com/tinygo-org/tinygo/releases/tag/v0.44.0).

`source-manifest.json` hashes every exported patch and overlay. A separate
clean checkout was restored from the exact pins using `prepare-sources.py`.
All three patches applied, every overlay matched, the TinyGo CLI rebuilt,
and a fresh build cache produced native P2 firmware. The P2 builtins archive
rebuilt from the clean support sources matched the development archive byte
for byte. This clean-source check reused the already built native LLVM tools;
the LLVM source patch was independently checked against the official base.

The packaged `build-toolchain.sh` entrypoint also completed successfully against
the development tree, rebuilding the requested LLVM tools and all 48 builtin
objects before rebuilding TinyGo and running its configuration tests.

The source bundle includes `build-toolchain.sh`, `verify-host.sh`, Windows and
Linux wrappers, and a checksum-checked ROM loader. The wrappers namespace
application caches by the source-manifest hash, preventing reuse of old P2
code after a backend change that retains the LLVM version string.

## Physical acceptance

Every hardware suite uses a new host-generated nonce, checks exact protocol
completion, and compares results to independent Python calculations. Cogs are
identified by the actual P2 COGID instruction. Language tests require both
pinned workers and ordinary unbound goroutines to overlap on physical cogs.

All ten final fixture/profile runs passed. Default GC completed 209 collections
and freed 1,555 objects; recovery GC completed 249 collections and freed 1,544.
Each allocated 1,651,624 bytes across eight cogs. The final memory run completed
2,288 cases while 203 collections and 47,013 timer ticks made progress.

The final machine-readable receipts are in `validation/acceptance.json`.
They include firmware SHA-256, build profile, challenge, observed output,
loader identity, and checksum acknowledgment. Local full raw records remain
under `hil/results/`; host models and simulations are not counted as hardware
acceptance. The separate `validation/hello.json` records the final demo: eight
ordinary workers ran on eight cogs, and its heartbeat continued after the serial
handle was closed and reopened. The board was left running this RAM image.

| Area | Required physical coverage |
| --- | --- |
| Language and concurrency | 64-bit multiply/divide/remainder, `math/bits.Mul64`, generics, range-over-function, maps, slices, interfaces, defers, floating point, timing, channels, atomics and mutexes; eight-cog masks and overlapping workers |
| GC | Allocation beyond hub capacity, reclamation, surviving live and interior pointers, 64-bit arithmetic during collection, all eight cogs |
| GC on unaligned C stacks | 32 rounds with a live pointer spilled in a byte-aligned C frame; the old word-stride scanner fails the negative control on round zero |
| Panic/recover | Bounds panic, panic-object identity, nested deferred-call order, and repeated recovery on every cog |
| Memory primitives | 2,288 copy/clear/memcpy/memmove/memset cases with source and guard checks, all byte alignments, both overlap directions, sizes around transfer boundaries, concurrent GC and timers |
| PSRAM | Four device IDs, 2,590 nonce/address-dependent bytes spread across the 32 MiB address space, write-all-before-read alias checks, retention, unaligned neighbor preservation, bounds and timing |
| Cgo | Actual C compilation; mixed scalar arguments, 64-bit and double returns, aggregate return, by-value aggregates, caller-copy isolation, mixed 32/64-bit field layout, and buffer guards |
| Standard library | Formatting, JSON structure/slice roundtrip and escapes, strings, sorting, endian conversions, SHA-256 and bit operations |

The PSRAM transaction maximum observed in acceptance was **214 cycles**,
**1.3375 microseconds at 160 MHz**, below the checked 1,280-cycle bound. PSRAM
coverage is a sparse addressing/alias test, not an exhaustive test of every
memory cell.

## Host and compiler checks

The following checks passed against the native P2 toolchain:

- 379 independent instruction-encoding cases.
- 32 compiler/driver integration tests and 153 LLVM P2 code-generation/MC tests.
- P2 target-triple unit test.
- 10,100 host-oracle cases for the portable 128-bit multiplication builtin.
- TinyGo P2 aggregate C ABI and type-size regressions, plus `compileopts`,
  `goenv`, and critical-atomic generator tests.
- Six runtime assembly files assembled and linked through the real P2 linker
  script; bootstrap, stack ranges, relocations and interrupt encodings checked.
- 6,048 assembly-model memory-operation cases with data, guards and ABI checks.
- Actual conservative scanner checked against an independent byte decoder for
  1,025 lengths across four heap ranges each on P2 and the ordinary aligned
  host path (8,200 cases); a protected page
  detects reads past the end.
- Six host PSRAM API failure, bounds, timing and neighbor-preservation tests.
- Ten ROM-loader unit tests, plus PowerShell argument/path forwarding, explicit
  environment overrides, build-failure handling and RAM-flash dispatch.

The complete linked compiler-builtin LUT image occupies **1,776 of 2,048
bytes**, within the P2's 512-long LUT capacity.

## P2-specific implementation choices

The runtime uses upward-growing PTRA stacks and native SETQ block transfers.
Startup establishes the stack before entering C or Go, loads the per-cog LUT,
and starts all eight cogs with a readiness handshake. The task switch preserves
the P2 ABI registers and checks the upper stack canary.

Garbage collection parks other cogs through the attention interrupt, preserving
registers without using the hub FIFO or CORDIC state. Integer register snapshots
are explicitly included as roots. Every byte offset is considered when scanning
conservatively because C callees can place saved pointers on unaligned stacks.
A cheap range check rejects values outside the exact heap interval before
calling the marking function. This preserves the marked roots while avoiding
unwinding checks for non-pointer byte windows.
The memory routines preserve the real stack and roots throughout interruptible
copies and clearing.

Hardware locks protect the scheduler, printing and atomic fallback operations.
The atomic ABI covers byte, halfword, word, doubleword and generic unaligned
operations, including updating the expected value after a failed compare-and-swap.
Timer callbacks on system stacks have a non-goroutine mutex wait path. Channel
lock ordering permits a waiting goroutine to yield without leaving interrupts
disabled.

GPIO writes and the PSRAM driver are owned by cog 0 because P2 output state
from multiple cogs is OR-combined. PSRAM is explicit storage on its four parallel
quad buses; it is not mapped into Go's address space. The driver accounts for
P2 pin-input pipeline latency and verifies the transaction timing bound.

The compiler fixes include target endianness, stack save/restore, 64-bit
division/remainder, correct boolean truncation before branches and selects,
aggregate `sret`/`byval` C ABI handling, and four-byte integer64 alignment
alongside eight-byte floating64 alignment. These are native compiler changes,
not special cases in the acceptance applications.

## Operating bounds

- `p2` and its `p2-gc` alias use eight cogs, conservative GC and halt-on-panic.
  `p2-recover` adds explicit unwinding. `p2-tasks` and `p2-minimal` are reduced
  profiles for one-cog scheduling or allocation-free applications.
- Scheduling is cooperative. A loop that remains runnable must yield, sleep,
  or block when another goroutine needs the same cog. The stress test's main
  collector uses a one-second background timer and yields after collection;
  all 96 rounds per worker and 192 forced worker collections
  and the independent correctness checks remain enabled.
- Explicit unwinding costs code space and execution time. The combined standard
  library test fits the default target but exceeds hub RAM with explicit
  unwinding. GC stress has a 300-second firmware deadline and is run with
  a 360-second host deadline.
- Go objects, pointers, stacks and heap use the 512 KiB hub. The linker reserves
  a 16 KiB primary system stack, seven 8 KiB secondary system stacks, and at least
  64 KiB for heap. Goroutine stacks default to 8 KiB and can be configured.
- The wrappers select `GOEXPERIMENT=nojsonv2` for Go 1.27's compatible compact
  JSON implementation. The language version remains Go 1.27.
- This board profile assumes the P2-EC32MB clock and pin wiring. Other P2 boards
  need matching clock/pin settings. Tested peripherals are UART, GPIO and PSRAM;
  this port does not claim a complete general-purpose OS or every TinyGo
  standard-library API.
- Acceptance covers the listed workloads and the attached board. It is not an
  exhaustive compiler proof, long-duration soak, or electrical qualification.