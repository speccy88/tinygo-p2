# TinyGo/P2 v0.1.0 — try it on your board

This package is for the **P2-EC32MB Rev B**, with its 20 MHz TCXO. Programs run at
160 MHz and use the serial console on P62/P63 at **115200 baud, 8N1**.
No compiler is needed to run these images. The Windows x64 loader runs directly
on Windows; the Linux x64 loader targets Ubuntu 26.04.

## Pick a program

| Image | What to expect |
| --- | --- |
| `hello.binary` | Eight worker results, then an `Alive` heartbeat |
| `blink.binary` | P38 onboard LED blinking; enable the board's LED switch |
| `channels.binary` | One result from every cog, each with sum 50005000 |
| `psram-store.binary` | 33554432 memory bytes and a message read back from PSRAM |
| `_BOOT_P2.BIX` | The hello application, prepared for ROM SD boot |

Source programs are included in `examples/`. The `.elf` files retain development
metadata. The `.binary` and `.BIX` files are flat, long-aligned P2 boot images.

## Load into RAM (Windows PowerShell)

Set **△ ON, ▽ OFF** for serial override. Close other serial terminals, open
PowerShell in this directory, and replace `COM12` with your board's port:

```powershell
.\tools\loadp2.exe -p COM12 -b 115200 -SINGLE .\hello.binary -t
```

Press Ctrl+C to close the terminal. The program keeps running until reset or
power-off. This command does not write flash.

Linux equivalent:

```sh
chmod +x tools/loadp2-linux
./tools/loadp2-linux -p /dev/ttyUSB0 -b 115200 -SINGLE hello.binary -t
```

## Program SPI flash

This replaces the boot program already stored in flash. Set **FLASH ON, △ ON,
▽ OFF** while programming:

```powershell
.\tools\loadp2.exe -p COM12 -b 115200 -l 115200 -f 160000000 -m 010007f7 -FLASH .\hello.binary -t
```

Wait until programming finishes. Set **FLASH ON, △ OFF, ▽ OFF**, then reset or
power-cycle. `-FLASH` supplies the ROM-compatible flash boot wrapper. Do not add
`-PATCH`, and do not confuse `-f` (frequency) with `-FLASH`.

On Linux, use `./tools/loadp2-linux` and your `/dev/ttyUSB...` port with the same
options and filename.

## Boot from SD

Use a **FAT32** card. Copy `_BOOT_P2.BIX` to the root directory, eject safely,
insert into the board, select **FLASH OFF, △ OFF, ▽ OFF**, and reset.

Example for a card assigned drive `E:` (check the drive first):

```powershell
Get-Volume -DriveLetter E
Copy-Item .\_BOOT_P2.BIX E:\_BOOT_P2.BIX
```

The ROM needs a contiguous file, no larger than 496 KiB. Back up your files before
preparing a card; an empty, freshly prepared FAT32 card with the boot file copied
first is the easiest approach. Do not rename an ELF file to BIX.

For an application built with the SDK, the included pure-Python converter works
without additional packages:

```powershell
python .\tools\export-image.py .\app.elf .\_BOOT_P2.BIX
```

## Optional Python RAM loader

The native loadp2 executables above do not need Python. If you prefer the
project's checksum-verifying RAM loader:

```powershell
python -m pip install pyserial==3.5
python .\tools\hil\p2ram.py .\hello.elf --port COM12 --monitor 10
```

## More to explore

- [Friendly Go tutorial and compiler installation](https://github.com/speccy88/tinygo-p2/tree/v0.1.0)
- [Complete source/build inputs and SDK downloads](https://github.com/speccy88/tinygo-p2/releases/tag/v0.1.0)
- [Hardware and release validation](https://github.com/speccy88/tinygo-p2/blob/v0.1.0/modern/release/VALIDATION.md)
- [Parallax Rev B guide](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/5789/P2-EC32MB-Edge-Module-Rev-B-Guide-v2.0.pdf)

RAM operation is physically tested. Flash/SD cold boot has not yet been physically
validated for this release; the documented paths follow loadp2 and the board ROM.
Never enable both triangle switches together. On this board P38/P39 are LEDs;
P40–P57 belong to PSRAM. Component copyright and license notices are in `licenses/`.
