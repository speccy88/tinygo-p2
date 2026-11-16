# P2 hardware checks

The portable loader uses the P2 ROM serial protocol, verifies its download
checksum, and keeps one serial handle open for loading and test traffic. It
loads **hub RAM only**. It does not program SPI flash. Loading resets the P2;
the current volatile application is replaced until the next reset.

Downloads use the ROM's `Prop_Txt` Base64 encoding by default. The checksum
word is appended before encoding, and a positive ROM checksum acknowledgement
is required before checking application output. `--encoding hex` selects the
equivalent `Prop_Hex` protocol in either Python command for diagnostics.

Install the one runtime dependency in an isolated environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux/macOS can use the same scripts, with the relevant serial device and
`.venv/bin/python`. Supply the actual connected port explicitly. Example
commands from this directory:

```powershell
# Identify the P2 ROM after a reset.
.\.venv\Scripts\python.exe p2ram.py --port COM12

# Load an ELF and check an exact sequence of boot lines.
.\.venv\Scripts\python.exe p2ram.py --port COM12 application.elf --expect 'hello'

# Verify current TinyGo language/runtime/concurrency on physical hardware.
.\.venv\Scripts\python.exe conformance.py --port COM12 --suite language conformance.elf
.\.venv\Scripts\python.exe conformance.py --port COM12 --suite stdlib stdlib.elf
.\.venv\Scripts\python.exe conformance.py --port COM12 --suite cgo cgo.elf

# Verify on-module PSRAM identification, addressing, data, and transfer timing.
.\.venv\Scripts\python.exe conformance.py --port COM12 --suite psram psram.elf

# These profiles exercise concurrent collection and explicit panic unwinding.
.\.venv\Scripts\python.exe conformance.py --port COM12 --suite gcstress --timeout 360 gcstress.elf
# Explicit panic unwinding adds overhead; allow its full bounded stress run.
.\.venv\Scripts\python.exe conformance.py --port COM12 --suite gcstress --timeout 360 gcstress-recover.elf
.\.venv\Scripts\python.exe conformance.py --port COM12 --suite gcoddstack gcoddstack.elf
.\.venv\Scripts\python.exe conformance.py --port COM12 --suite recovery recovery.elf
.\.venv\Scripts\python.exe conformance.py --port COM12 --suite memory --timeout 180 memory.elf

# Check loader framing and rejection of malformed/unsafe ELF layouts.
.\.venv\Scripts\python.exe -m unittest -v test_p2ram
.\test_wrapper.ps1
.\test_flash.ps1
```

From the repository root, the Windows wrapper builds through WSL and uploads
the resulting ELF through the Windows serial port:

```powershell
.\modern\tinygo.ps1 flash -target=p2 -port=COM12 .\modern\examples\conformance\main.go
# Opt in to a timed, receive-only UART monitor after loading.
.\modern\tinygo.ps1 flash -target=p2 -port=COM12 -monitor 10 .\app
# Keep the compiled ELF instead of using an automatically removed temporary file.
.\modern\tinygo.ps1 flash -target=p2 -port=COM12 -o .\application.elf .\app
```

`flash` here always means a ROM download to hub RAM. Build options pass through
to TinyGo; `-port` and `-monitor` are handled by Windows. A failed build prevents
the upload. Without `-monitor`, the command exits after the ROM acknowledges the
download. `modern/flash.ps1` is also directly callable with these same options.
The loader defaults to `modern/hil/.venv/Scripts/python.exe`; `P2_FLASH_PYTHON`
can select another Python installation containing the requirements above.

The Windows wrapper defaults to `GOEXPERIMENT=nojsonv2` so Go 1.27 uses the
smaller standard JSON implementation within the P2's 512 KiB hub memory.
This selects the implementation behind the same `encoding/json` API; the Go
language version remains 1.27. An explicitly defined Windows `GOEXPERIMENT`
environment variable, including an empty value, overrides this default.

`conformance.py` expects the corresponding application under
`modern/examples/conformance` or `modern/examples/psram`. It generates a fresh
32-bit nonce after every RAM download. The host independently calculates the
integer, language-feature, floating-point, and PSRAM checksums.
Wide multiplication checks include the maximum 64-bit operands, a nonce-derived
full-width product, and a product with carries across 32-bit limbs.
The multicog test requires all eight physical cog IDs and overlapping busy workers, with
separate channel, atomic, and mutex checks. It does not infer parallelism from
goroutine creation alone.

A second phase starts ordinary goroutines without `machine.AssignCore`.
It requires at least two observed cog IDs, overlapping non-yielding busy
intervals, and an independently computed nonce checksum. This checks automatic
multicore scheduling separately from explicit affinity.

`stdlib` checks formatted signed/unsigned integers, JSON structure/slice
roundtrips and escapes, string transforms, sorting, mixed-endian 32/64-bit
encoding, SHA-256, and bit operations. Python's JSON parser, `struct`, and
`hashlib` provide independent expected results for the fresh nonce.

`gcstress` requires conservative GC (`p2` or `p2-gc`) and checks allocation beyond total hub
capacity, reclamation, pointer survival, and a host-computed checksum across
all cogs. `recovery` requires `p2-recover` and checks panic recovery, deferred
call order, bounds-panic recovery, and recovery on every cog. Use the matching
image/profile; passing one suite does not imply the others have passed.

`gcoddstack` retains a Go allocation through an unaligned C stack frame while
a C-to-Go callback forces collection and subsequent allocation. Its 32-round
nonce checksum checks the P2 collector's byte-aligned root scanning.

`cgo` compiles an actual C preamble using standard C headers. Non-inlined C
helpers exercise a 16-byte structure return, a structure passed by value, mixed
32/64-bit arguments, a 64-bit return, a double return, and mutation through a
Go buffer pointer. Both guard bytes and nonce-dependent results are checked.
Volatile writes to a by-value C argument must preserve the caller's original
structure. A mixed 32/64-bit structure also checks C/Go size, field offsets,
return values, and argument passing against the P2's four-byte alignment.

`memory` also requires conservative GC. It checks 2,288 Go `copy`/`clear` and C ABI
`memcpy`/`memmove`/`memset` operations with full source and guard-byte checks.
Lengths cover 0–9 and both sides of 16, 128, 512, and 1,024-byte boundaries,
all byte alignments, both overlap directions, and several nonzero fill values.
A fresh host nonce determines the data and final host-computed digest. GC on
cog 7 and timer work on cog 6 must make progress during the memory operations.

The `p2-recover` profile can run the same GC stress workload. Its explicit
unwinding code needs a longer limit: the firmware watchdog is 300 seconds;
use `--timeout 360` on the host. The number of rounds, reclamation checks,
pointer-survival checks, and expected checksum remain the same.

The PSRAM test writes 2,590 address-dependent bytes before reading them back,
including unaligned, physical-page, high-address, and end-of-memory locations.
It also checks preservation of neighboring bytes and rejection of invalid
addresses. This is a representative addressing test, not a full 32 MiB sweep.
The raw PSRAM transfer measures its own clock-counter duration; the host
requires the conservative bound to stay below 1,280 cycles (8 us at 160 MHz).

Each run records the ELF hash, loader/harness hashes, USB serial identity,
ROM response, fresh nonce, raw receive bytes, decoded results, and failure
details in a new `results/` directory. A missing test, timeout, malformed
output, wrong nonce, or mismatch fails the process. Source and firmware
identities are separate: retain the compiler build receipt beside these
hardware results when publishing a release.

`legacy_challenge.py` runs the archived Phase 2 stateful challenge application.
Its results are labeled `physical-P2-legacy-baseline`; they establish the
serial/reset/clock baseline and do not establish support for the new compiler.

The ELF loader transfers PT_LOAD **file bytes**, preserving load addresses and
zero-filling gaps in that image. It intentionally does not transfer potentially
large NOBITS stack/heap reservations. Firmware startup must initialize BSS.

Protocol implementation reference:
[loadp2](https://github.com/totalspectrum/loadp2/tree/c20afedd4253d09da449fa740f8d4304481fc560).
Base64 command and checksum format:
[P2 serial boot documentation](https://p2docs.github.io/boot.html).
PSRAM hardware references:
[Parallax P2-EC32MB product guide](https://www.parallax.com/package/p2-edge-module-with-32mb-ram-product-guide/)
and [AP Memory APS6404L datasheet](https://www.pjrc.com/store/APS6404L_3SQR.pdf).
