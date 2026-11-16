# TinyGo for Propeller 2 v0.1.0

Write Go programs that run natively across the P2's eight cogs. This release
brings TinyGo **0.44.0**, Go **1.27.4**, and the P2 LLVM backend updated to
**LLVM 15.0.7**, with a ready-to-use compiler and a friendly, copy-paste tutorial.

**Start here: [the main README](https://github.com/speccy88/tinygo-p2/tree/v0.1.0)**

## Choose your download

| Asset | Use it for |
| --- | --- |
| `tinygo-p2-demo-v0.1.0.zip` | Try four programs with native Windows/Linux serial loaders; no compiler required |
| `tinygo-p2-sdk-v0.1.0-ubuntu26.04-x86_64.tar.gz` | Compile your own programs on Ubuntu 26.04 x86-64 or Windows WSL2 |
| `tinygo-p2-sources-v0.1.0-full.tar.gz` | Build from complete patched LLVM, TinyGo, P2 support, Go, module, and loader inputs |
| `SHA256SUMS` | Verify the three downloads |

GitHub's automatic “Source code” archives contain the repository's patches and
overlays. Choose the **`sources-...-full.tar.gz` asset** for all resolved toolchain
sources and build dependencies. OS build prerequisites are listed in the
[source guide](https://github.com/speccy88/tinygo-p2/blob/v0.1.0/modern/release/SOURCE-BUILD.md).

## Included

- Eight-cog goroutine scheduling, channels, mutexes, atomics, timers, and optional affinity.
- Conservative garbage collection with coordinated multicog root scanning.
- GPIO, console UART, explicit 32 MiB PSRAM storage, and native Cgo support.
- Optional panic recovery using the `p2-recover` target.
- Hello, onboard LED, eight-cog channels, PSRAM, and serial-echo tutorials.
- RAM loading, SPI flash programming instructions, and a ready-made SD `_BOOT_P2.BIX`.
- Complete port patches, pinned source revisions, build scripts, licenses, and test receipts.

## Tested scope

The target board is **P2-EC32MB Rev B**, 20 MHz TCXO, running at **160 MHz** with
P62/P63 serial at **115200 baud**. Eleven prior native acceptance runs covered
the language/runtime, multicog GC, PSRAM, Cgo, memory helpers, and selected
standard-library packages. Release testing additionally passed all five README
programs on the board, all four demo binaries, both Windows loadp2 loading paths,
and a Cgo program built with a relocated SDK.

**RAM operation is hardware tested. Flash and SD cold boot have not yet been
physically validated for this release.** Their documented procedures follow
upstream loadp2 and Parallax's board/ROM boot specifications. The flash command
replaces the existing flash boot application; the RAM command leaves it intact.

The scheduler is cooperative. Go objects and stacks use hub RAM; PSRAM is explicit
byte storage, not an enlarged Go heap. The binary SDK requires Ubuntu 26.04 x86-64
libraries. High-level drivers for all P2 peripherals and an SD filesystem are not
included. See the [validation record](https://github.com/speccy88/tinygo-p2/blob/v0.1.0/modern/release/VALIDATION.md)
for exact coverage and reproducible checks.

Thanks to the TinyGo, Go, LLVM, ne75/p2llvm, Total Spectrum, and Parallax communities
whose work makes this port possible.
