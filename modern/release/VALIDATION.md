# v0.1.0 release validation

Release packaging was checked on 2026-11-16 with Windows, WSL2 Ubuntu 26.04
x86-64, and a physical P2-EC32MB Rev B. This supplements the native compiler and
runtime acceptance recorded in [../VALIDATION.md](../VALIDATION.md).

## Compiler and source packages

- The SDK's TinyGo CLI was rebuilt with `-trimpath` from the pinned, patched
  TinyGo 0.44.0 source. Go 1.27.4 and the native P2 LLVM 15.0.7 tools are included.
- The SDK was copied to a different directory whose name contains a space. With
  a new cache, all **five complete Go blocks extracted verbatim from the main
  README** compiled: hello, blink, eight-cog channels, PSRAM storage, and UART echo.
- The relocated SDK also compiled the native **Cgo aggregate/ABI acceptance
  program**, which passed on the physical board with a fresh host challenge.
  This exercises packaged libclang, Clang headers, the external compiler/linker,
  struct layout, by-value copies, return values, and mixed 64-bit alignment.
  [Cgo receipt](cgo.json)
- The full source snapshot's **148,048 source/dependency files** passed SHA-256
  verification. All three port patches passed reverse-application checks against
  those source trees, and the new TinyGo source overlays were included explicitly.
- P2 compiler builtins rebuilt from the source snapshot using the packaged LLVM
  tools. The resulting archive matches the accepted archive exactly:
  `be8a69defc7bfdfac10718be70b2d2b1f6229071cb2a1bda741ebc0b288c33ec`.
- The previously built and validated LLVM binaries are packaged; a second full
  LLVM rebuild was not performed for this packaging-only change. The complete
  LLVM source tree, CMake build command, patches, and input identities are supplied.
- The source archive includes the Go SDK archive and module cache. OS package
  prerequisites remain documented separately. The binary SDK targets Ubuntu
  26.04 x86-64 and has not been validated on other distributions or host CPUs.

## Physical release checks

[The hardware receipt](hardware.json) records **11 passing release checks**:

| Check | Acceptance |
| --- | --- |
| Demo hello | Eight worker IDs, expected checksums, consecutive heartbeats |
| Demo blink | Alternating on/off console reports; LED brightness not visually measured |
| Demo channels | Exactly cogs 0–7, each returning 50005000 |
| Demo PSRAM | Correct 32 MiB size and exact message readback |
| README hello | Greeting and consecutive ticks |
| README blink | Timed alternating console reports |
| README channels | All eight cogs and expected sums |
| README PSRAM | Exact storage round trip |
| README echo | Echoes a fresh random host challenge |
| Windows loadp2, single stage | Native executable loads the packaged binary; heartbeat received |
| Windows loadp2, two stages | Native executable uses the documented clock/baud settings; heartbeat received |

The Cgo run above is an additional physical check. These runs used **RAM only**.
No SPI flash was programmed and no SD card was modified. The board was left
running the packaged hello application in RAM, with its serial port closed.

## Boot images and host checks

- `export-image.py` exports only P2 ELF PT_LOAD file bytes, fills address gaps,
  excludes BSS/heap/system-stack reservations, aligns the image to four bytes,
  and enforces the ROM SD path's 496 KiB limit.
- The hello binary and `_BOOT_P2.BIX` are byte-identical: **18,252 bytes**, SHA-256
  `c576b992bea63d5053cbbbf323742fd208ceb52b2f2ed206e473394f81261700`.
- Ten existing ROM loader tests and three new boot-export tests pass, including
  invalid ELF, gaps/BSS, raw-input rejection, and SD reserved-memory bounds.
- The PowerShell build wrapper and RAM flash-dispatch tests pass after adding
  an explicit SDK GOROOT. The image converter works without pyserial installed.
- Native Linux and Windows x64 loadp2 binaries were built from the pinned source
  with flexspin v7.8.0. Linux help execution was checked; serial loading was
  physically tested with the Windows executable.

**Flash and SD cold boot remain untested on physical hardware in this release.**
The flash instructions use upstream loadp2's `-FLASH` boot wrapper, not a raw
write at flash address zero. SD instructions use a flat `_BOOT_P2.BIX`, FAT32,
contiguous allocation, and the board manual's switch settings. Their format and
startup contract were checked against the upstream loader/ROM documentation.

## Reproduce the focused checks

```sh
python3 -m unittest discover -s modern/hil -p test_p2ram.py
python3 -m unittest discover -s modern/release -p test_export_image.py
python3 modern/release/check-readme.py "$HOME/tinygo-p2-sdk" "$HOME/p2-readme-checks"
```

For serial tests, install `pyserial==3.5`. The first host test command also uses
pyserial in its serial-transport mocks. On Windows, point `--tutorials` to the
directory containing the README builds (a WSL UNC path works):

```powershell
python modern/release/check-board.py --port COM12 --demo .\tinygo-p2-demo --tutorials .\p2-readme-checks --output release-check.json
```

This check resets and replaces the running RAM program repeatedly. It never
invokes loadp2's `-FLASH` option.
