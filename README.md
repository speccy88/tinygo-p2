<div align="center">

# TinyGo for Propeller 2

**Write Go. Run on eight cogs. Build something fun.**

[![Release](https://img.shields.io/github/v/release/speccy88/tinygo-p2)](https://github.com/speccy88/tinygo-p2/releases/tag/v0.1.0)
![TinyGo](https://img.shields.io/badge/TinyGo-0.44.0-00ADD8)
![Go](https://img.shields.io/badge/Go-1.27.4-00ADD8)
![P2](https://img.shields.io/badge/Propeller_2-8_cogs-7A42F4)

A native Go compiler and runtime for the **Parallax P2 Edge with 32 MiB PSRAM**.

[Try the demo](#-try-it-without-installing-a-compiler) · [Install the compiler](#-install-the-compiler) · [Learn by doing](#-your-first-go-program) · [RAM / flash / SD](#-choose-how-your-board-boots)

</div>

TinyGo brings Go's small functions, automatic memory management, and easy-to-read
concurrency to microcontrollers. This port compiles your program to **real P2
machine code**, with ordinary Go goroutines running across the P2's eight cogs.
There is no interpreter to install on the board.

If you already program in C, Python, JavaScript, or another language, you can
start here without knowing Go. First run a ready-made demo, then blink an LED,
share work between cogs, and use the board's external memory.

| What you can use | What it gives you |
| --- | --- |
| **Eight-cog concurrency** | `go` starts a task; channels carry results between tasks |
| **Garbage collection** | Ordinary Go objects, slices, maps, and interfaces in hub RAM |
| **GPIO, serial, timers** | LEDs and digital I/O, a 115200-baud console, `time.Sleep` |
| **32 MiB PSRAM** | Checked byte storage for larger buffers and datasets |
| **Modern language features** | Generics, 64-bit arithmetic, Cgo, mutexes and atomics |
| **Three boot paths** | Load into RAM, program SPI flash, or boot `_BOOT_P2.BIX` from SD |

> [!NOTE]
> This is a community port, currently **v0.1.0**. The tested board is the
> **P2-EC32MB Rev B**, using its 20 MHz TCXO at a 160 MHz system clock.
> Eleven native acceptance runs passed on real hardware, covering all eight cogs,
> GC, PSRAM, Cgo, and selected standard-library packages. RAM loading is hardware
> tested. Flash and SD procedures follow the upstream loader and board manual;
> their cold-boot behavior has not yet been physically validated for this release.
> See [exact coverage](modern/VALIDATION.md) and [release checks](modern/release/VALIDATION.md).

## 🚀 Try it without installing a compiler

You need your powered P2 Edge, its USB serial connection/Prop Plug, and the
[demo ZIP](https://github.com/speccy88/tinygo-p2/releases/download/v0.1.0/tinygo-p2-demo-v0.1.0.zip).
It includes native **Windows x64 and Linux x64 loaders**, four programs, and
ready-to-boot binary images. The Windows demo needs neither WSL nor Go.

1. Set the board's **△ switch ON and ▽ OFF** to allow serial loading.
2. Close any other application using the serial port.
3. In **PowerShell**, download and run:

```powershell
Invoke-WebRequest https://github.com/speccy88/tinygo-p2/releases/download/v0.1.0/tinygo-p2-demo-v0.1.0.zip -OutFile tinygo-p2-demo.zip
Expand-Archive .\tinygo-p2-demo.zip -DestinationPath .
Set-Location .\tinygo-p2-demo
.\tools\loadp2.exe -p COM12 -b 115200 -SINGLE .\hello.binary -t
```

**Replace `COM12` with your board's port** from Windows Device Manager. You should
see eight worker results followed by `Alive 1`, `Alive 2`, and so on. Worker order
and the cogs chosen by the scheduler can vary. Press **Ctrl+C** to leave the terminal.
The program keeps running until the board resets or loses power.

<details>
<summary><strong>Linux equivalent</strong></summary>

Extract the ZIP, enter `tinygo-p2-demo`, then run:

```sh
chmod +x tools/loadp2-linux
./tools/loadp2-linux -p /dev/ttyUSB0 -b 115200 -SINGLE hello.binary -t
```

Use your actual serial device. The bundled Linux loader targets Ubuntu 26.04 x86-64.
If access is denied, add your user to the serial group and log out/in:
`sudo usermod -aG dialout "$USER"`.

</details>

The demo also contains `blink.binary`, `channels.binary`, and `psram-store.binary`.
Replace `hello.binary` in the command to try them. For blink, turn the board's
**LED switch ON**. The PSRAM example requires the 32 MiB Edge variant.

## 🧰 Install the compiler

The compiler runs on **Ubuntu 26.04 x86-64**, including **WSL2 on Windows**. The
prebuilt SDK includes Go, TinyGo, the updated P2 LLVM compiler/linker, resource
headers, and P2 builtins. You do not need a separate Go installation.

On Windows, install WSL from an administrator PowerShell if necessary:

```powershell
wsl --install -d Ubuntu-26.04
```

Restart if prompted, open Ubuntu, and finish its first-run setup. Run the following
**inside Ubuntu** (native Linux users start here):

```sh
sudo apt update
sudo apt install -y curl ca-certificates libstdc++6 libgcc-s1 zlib1g python3
cd "$HOME"
curl -fLO https://github.com/speccy88/tinygo-p2/releases/download/v0.1.0/tinygo-p2-sdk-v0.1.0-ubuntu26.04-x86_64.tar.gz
curl -fLO https://github.com/speccy88/tinygo-p2/releases/download/v0.1.0/SHA256SUMS
grep ' tinygo-p2-sdk-' SHA256SUMS | sha256sum -c -
tar -xzf tinygo-p2-sdk-v0.1.0-ubuntu26.04-x86_64.tar.gz
export PATH="$HOME/tinygo-p2-sdk/bin:$PATH"
tinygo-p2 version
```

Add the `export PATH=...` line to `~/.bashrc` to keep the command available in new
terminals. The archive expands into `~/tinygo-p2-sdk`; use a fresh directory when
installing another version. It is built against Ubuntu 26.04's system libraries,
so the binary SDK is **not intended for older Ubuntu releases or ARM computers**.

> [!TIP]
> Want to build everything yourself? The
> [complete source archive](https://github.com/speccy88/tinygo-p2/releases/download/v0.1.0/tinygo-p2-sources-v0.1.0-full.tar.gz)
> includes the patched **P2 LLVM backend**, Clang/LLD, TinyGo, Go, module
> dependencies, support libraries, and loader sources. Follow the
> [source build guide](modern/release/SOURCE-BUILD.md).

## 👋 Your first Go program

Make a project directory in your Ubuntu terminal:

```sh
mkdir -p "$HOME/p2-hello"
cd "$HOME/p2-hello"
"$HOME/tinygo-p2-sdk/go/bin/go" mod init example.com/p2-hello
```

A *module* is simply your project's name and dependency list, stored in `go.mod`.
Create a file named **`main.go`** in that directory with this complete program:

```go
package main

import "time"

func main() {
    println("Hello, Propeller 2!")
    for count := 1; ; count++ {
        println("Tick", count)
        time.Sleep(time.Second)
    }
}
```

Build the program and create its downloadable image:

```sh
tinygo-p2 build -target=p2 -o hello.elf .
python3 "$HOME/tinygo-p2-sdk/modern/export-image.py" hello.elf hello.binary
```

`hello.elf` contains machine code plus information for development tools.
`hello.binary` contains just the bytes the P2 loads into memory. **Keep the ELF;
use the binary for the flash and SD instructions below.**

On Windows, run `explorer.exe .` from this Ubuntu directory, copy `hello.binary`
to the extracted demo folder, and repeat its PowerShell load command. Windows
owns `COM12`, so the Windows loader handles the serial port while WSL handles
compilation. On native Linux, load directly with `loadp2-linux`.

### A quick translation from other languages

| Go syntax | Meaning |
| --- | --- |
| `package main` and `func main()` | This is a runnable program and its entry point |
| `import "time"` | Use a library package |
| `count := 1` | Create a variable; Go infers its type |
| `var total uint32` | Create a 32-bit unsigned integer, initially zero |
| `for { ... }` | Repeat forever; Go uses `for` for all loops |
| `[]byte("hello")` | A slice: a variable-length view of bytes |
| `if err != nil { ... }` | Check an operation's returned error |
| `go work()` | Start a goroutine, a lightweight concurrent task |
| `ch <- value` / `<-ch` | Send / receive a value through a channel |

Go inserts statement-ending semicolons for you. Braces belong on the same line
as `func`, `if`, and `for`. Unused imports and variables are compile errors: remove
them as you experiment.

## 💡 Blink an LED

Replace `main.go` with this program, turn the board's **LED switch ON**, and
repeat the build/export/load commands above:

```go
package main

import (
    "machine"
    "time"
)

func main() {
    led := machine.Pin(38)
    led.Configure(machine.PinConfig{Mode: machine.PinOutput})
    for {
        led.High()
        println("LED on")
        time.Sleep(500 * time.Millisecond)
        led.Low()
        println("LED off")
        time.Sleep(500 * time.Millisecond)
    }
}
```

`machine` is TinyGo's hardware package. `time.Sleep` pauses this goroutine and lets
other work run. P38 and P39 are the **onboard LEDs on P2-EC32MB**. Other boards
may use different pins. [Example source](modern/examples/blink/main.go)

> [!IMPORTANT]
> On the PSRAM Edge, **P40–P57 belong to PSRAM**; P56/P57 are its clock/select,
> not LEDs. P58–P61 serve flash/SD, and P62/P63 are serial TX/RX. Use P0–P39
> for general I/O and respect the board's 3.3 V electrical limits.

## 🧵 Share work between all eight cogs

Goroutines are functions that can make progress independently. A **channel** is
a typed queue connecting them. This example starts eight workers and collects
their results without sharing a mutable counter:

```go
package main

import (
    "machine"
    "runtime"
    "time"
)

type result struct {
    core int
    sum  uint32
}

func worker(core int, done chan<- result) {
    machine.AssignCore(core)
    var sum uint32
    for i := uint32(1); i <= 10000; i++ {
        sum += i
        if i%256 == 0 {
            runtime.Gosched()
        }
    }
    done <- result{core: int(machine.CogID()), sum: sum}
}

func main() {
    done := make(chan result, 8)
    for core := 0; core < 8; core++ {
        go worker(core, done)
    }
    for i := 0; i < 8; i++ {
        r := <-done
        println("Cog", r.core, "sum", r.sum)
    }
    println("All eight workers finished!")
    for {
        time.Sleep(time.Second)
    }
}
```

You should receive one result from every cog, each with sum **50005000**. Arrival
order can vary. `make(chan result, 8)` creates room for eight results; `chan<-`
means the worker only sends through that parameter.

`machine.AssignCore(core)` pins a goroutine to a cog for this demonstration.
**It is optional**: remove it and the scheduler chooses where workers run.
You can have more goroutines than cogs, subject to available memory.
[Example source](modern/examples/channels/main.go)

The scheduler is **cooperative**. Sleeping, waiting on a channel, or calling
`runtime.Gosched()` lets another ready goroutine on that cog run. Put a yield in
long CPU loops. Protect shared mutable data with channels, `sync.Mutex`, or
`sync/atomic`; running on different cogs does not make unsynchronized access safe.

## 📦 Store bytes in 32 MiB of PSRAM

The P2 has **512 KiB of hub RAM**, shared by code, runtime, stacks, and Go objects.
External PSRAM provides much more storage, accessed explicitly by address.

```go
package main

import (
    "machine"
    "time"
)

func main() {
    if err := machine.PSRAM.Configure(); err != nil {
        panic(err)
    }
    message := []byte("Hello from 32 MiB of PSRAM!")
    const address = 1024
    if _, err := machine.PSRAM.WriteAt(message, address); err != nil {
        panic(err)
    }
    readback := make([]byte, len(message))
    if _, err := machine.PSRAM.ReadAt(readback, address); err != nil {
        panic(err)
    }
    println("External memory bytes:", machine.PSRAM.Size())
    println(string(readback))
    for {
        time.Sleep(time.Second)
    }
}
```

`WriteAt` copies bytes from hub RAM to PSRAM; `ReadAt` copies them back. The driver
checks bounds and serializes access from goroutines. The example prints
`33554432` and the original message. [Example source](modern/examples/psram-store/main.go)

PSRAM is **volatile storage**, not the Go heap: allocating a large slice still
uses hub RAM. Work in small chunks when processing large datasets. Stored bytes
are lost on power-off; Go pointers should remain in hub RAM.

## 🔌 Serial input and other building blocks

`println(...)` writes to the console on P62/P63 at **115200 baud, 8N1**. For a
small interactive program, this complete example echoes received characters:

```go
package main

import "machine"

func main() {
    if err := machine.UART0.Configure(machine.UARTConfig{BaudRate: 115200}); err != nil {
        panic(err)
    }
    println("Type something:")
    for {
        b, err := machine.UART0.ReadByte()
        if err != nil {
            panic(err)
        }
        if err := machine.UART0.WriteByte(b); err != nil {
            panic(err)
        }
    }
}
```

Use the loader's `-t` terminal. `ReadByte` waits cooperatively for input.
The current UART profile fixes the console pins and baud rate.

Standard Go packages such as `time`, `sync`, `encoding/binary`, `sort`, and
`strings` can be useful. Selected `fmt`, JSON, SHA-256, and math operations are
covered by the [stdlib example](modern/examples/stdlib/main.go). Library code
uses memory too: begin with `println` and add larger packages as needed.

## 💾 Choose how your board boots

All commands below use files in the extracted **demo folder**. For your own
application, export its ELF with `modern/export-image.py` first.

| Destination | Survives power-off? | Best for |
| --- | --- | --- |
| **Hub RAM** | No | Fast development and trying examples |
| **SPI flash** | Yes | A standalone board that starts your application on power-up |
| **SD card** | Yes | Swapping applications by replacing a boot file |

### RAM: load and run immediately

Use △ **ON**, ▽ **OFF** to enable serial loading:

```powershell
.\tools\loadp2.exe -p COM12 -b 115200 -SINGLE .\hello.binary -t
```

This resets the board and replaces its running RAM program. It leaves flash
unchanged. The repository's `modern/tinygo.ps1 flash` convenience command also
means **build and load to RAM**; its name follows TinyGo's command convention.

### Flash: run automatically after power-on

Set **FLASH ON, △ ON, ▽ OFF** while programming, then run:

```powershell
.\tools\loadp2.exe -p COM12 -b 115200 -l 115200 -f 160000000 -m 010007f7 -FLASH .\hello.binary -t
```

This **replaces the existing boot application in SPI flash**. Wait for programming
to finish. Then set **FLASH ON, △ OFF, ▽ OFF**, and reset or power-cycle the
board. The ROM briefly checks for serial loading and then boots flash.

`-FLASH` creates the P2's required boot wrapper. **`-f` sets a clock frequency;
it does not mean flash.** Keep `-PATCH` off: TinyGo already supplies its startup
layout. See [loadp2's documentation](https://github.com/totalspectrum/loadp2#loading-multiple-files).

### SD: boot `_BOOT_P2.BIX`

1. Use a **FAT32** microSD card. Back up existing files before preparing a card.
2. Copy the demo's `_BOOT_P2.BIX` into the card's **root directory**.
3. Eject the card safely and insert it into the Edge module.
4. Set **FLASH OFF, △ OFF, ▽ OFF**, then reset or power-cycle.

For example, if Windows assigned your SD card drive **`E:`**:

```powershell
# Check that E: really is your SD card before copying.
Get-Volume -DriveLetter E
Copy-Item .\_BOOT_P2.BIX E:\_BOOT_P2.BIX
```

To create the boot file for your own program, run in Ubuntu:

```sh
python3 "$HOME/tinygo-p2-sdk/modern/export-image.py" hello.elf _BOOT_P2.BIX
```

**Do not rename an ELF to `.BIX`.** BIX is a flat boot image, and the exporter
creates that format. The ROM requires a **contiguous file**, at most **496 KiB**;
copying it first onto an empty, freshly prepared FAT32 card is the easiest route.
The included `_BOOT_P2.BIX` is the same application as `hello.binary`.

<details>
<summary><strong>Board switches and troubleshooting</strong></summary>

These settings are for P2-EC32MB Rev B. Never turn both triangle switches ON.

| Mode | FLASH | △ | ▽ |
| --- | --- | --- | --- |
| Serial loading override | Either | ON | OFF |
| Flash after a short serial window | ON | OFF | OFF |
| SD, with serial fallback on failure | OFF | OFF | OFF |
| SD only, no serial window | OFF | OFF | ON |

- **No response to upload:** check the port, board power, reset connection, and
  serial override switches; close other serial terminals.
- **LED does not light:** enable the LED switch and use P38/P39 on this board.
- **Flash runs the old program:** confirm `-FLASH` completed and △ is OFF.
- **SD does not start:** check FAT32, the exact root filename, contiguous allocation,
  and FLASH OFF. Remove other boot files while diagnosing.
- **Linker reports insufficient hub RAM:** use fewer/lighter packages, fewer live
  goroutines, or smaller buffers. PSRAM does not automatically enlarge the heap.

Hardware details: [Parallax's Rev B guide, pages 5–7](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/5789/P2-EC32MB-Edge-Module-Rev-B-Guide-v2.0.pdf).
SD format details: [ROM SD boot implementation discussion](https://forums.parallax.com/discussion/170637/p2-sd-boot-code-rev-2-silicon/p1).

</details>

## ⚙️ What happens under the hood?

```mermaid
flowchart LR
    A[Your Go program] --> B[TinyGo 0.44]
    B --> C[P2 LLVM 15 backend]
    C --> D[Native P2 image]
    D --> E[RAM · Flash · SD]
    E --> F[8 cogs + shared hub RAM]
    F <--> G[32 MiB PSRAM storage]
```

The ne75 P2 backend has been updated to **LLVM 15.0.7**, a version supported by
TinyGo 0.44. Go is compiled directly for P2's 32-bit architecture. The runtime
uses P2 hardware locks, attention interrupts for garbage collection, and SETQ
block transfers for stack switching and memory operations. GPIO writes are
coordinated through cog 0 because P2 combines output signals from its cogs.

The default `p2` target enables all eight cogs and conservative GC. Each goroutine
normally has an 8 KiB stack; the linker also reserves system stacks and at least
64 KiB of heap space. Keep these costs in mind as an application grows.

| Build target | Use it when… |
| --- | --- |
| `p2` | You want the normal eight-cog runtime with garbage collection |
| `p2-recover` | You need `recover` to catch a panic; extra code must fit |
| `p2-tasks` | You want a one-cog cooperative scheduler without memory reclamation |
| `p2-minimal` | You need a small program with no scheduler or heap allocation |

Select another target with `tinygo-p2 build -target=p2-recover -o app.elf .`.
Ordinary `defer` is supported in the default profile; **recovering from a panic**
requires `p2-recover`. The wrappers default to Go's compact JSON implementation
(`GOEXPERIMENT=nojsonv2`) to conserve hub RAM.

The P2 has many hardware features beyond these examples. This release exposes
GPIO, its console UART, timing, and PSRAM; it does **not** supply a complete
high-level driver set for every smart-pin mode, USB, networking, or an SD
filesystem. Booting from SD is handled by the ROM and does not imply a Go
filesystem driver.

## Explore, build, contribute

- [Runtime design and target profiles](modern/README.md)
- [Complete source build and loader rebuild](modern/release/SOURCE-BUILD.md)
- [Hardware acceptance results](modern/VALIDATION.md) and [release validation](modern/release/VALIDATION.md)
- [Examples you can build](modern/examples) and [board test harness](modern/hil/README.md)
- [All LLVM, TinyGo, and support-library changes](modern/patches), [new runtime sources](modern/overlays/tinygo)
- [Report a problem or share what you made](https://github.com/speccy88/tinygo-p2/issues)

Built on [TinyGo](https://github.com/tinygo-org/tinygo),
[ne75's P2 LLVM](https://github.com/ne75/p2llvm),
[LLVM](https://llvm.org/), and
[Total Spectrum's loadp2](https://github.com/totalspectrum/loadp2).
Their licenses and credits travel with the source and release packages;
see [NOTICE.md](NOTICE.md).

<details>
<summary>Historical TinyGo 0.23 / LLVM 14 baseline</summary>

The earlier Phase 1 and Phase 2 sources and evidence remain in their original
directories. They describe a separate, older implementation. The original
overview is preserved in [reports/PHASE2_README.md](reports/PHASE2_README.md).
For current development and release builds, use `modern/`.

</details>
