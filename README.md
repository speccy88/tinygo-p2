# TinyGo for Propeller 2

A native TinyGo 0.44.0 port for the Parallax P2 Edge with 32 MiB PSRAM.
The modern toolchain uses Go 1.27.4 and updates the ne75 P2 LLVM backend to
LLVM 15.0.7, the minimum LLVM version supported by TinyGo 0.44.

The implementation and reproducible source bundle are in **[modern/](modern/README.md)**.
It includes an eight-cog goroutine scheduler, conservative garbage collection,
panic/recover, channels, timers, atomics, mutexes, GPIO/UART, Cgo, and an explicit
PSRAM storage API. The build and hardware acceptance results are documented in
[modern/VALIDATION.md](modern/VALIDATION.md).

## Get started

The compiler runs in Linux x86-64, including WSL2. Build the pinned toolchain:

```sh
bash modern/build-toolchain.sh "$HOME/tinygo-p2-work"
```

On Windows, install the serial-loader dependency once:

```powershell
python -m venv modern/hil/.venv
./modern/hil/.venv/Scripts/python.exe -m pip install -r modern/hil/requirements.txt
```

Then build and run a Go application on the board:

```powershell
./modern/tinygo.ps1 version
./modern/tinygo.ps1 flash -target=p2 -port=COM12 -monitor 10 ./modern/examples/hello/main.go
```

This command resets the board and downloads to hub RAM. It does not program
SPI flash. The hello example prints worker results and a heartbeat. See the
[test harness](modern/hil/README.md) for automated hardware checks.

The default target uses all eight cogs and garbage collection. The `p2-recover`
profile adds explicit panic unwinding when the application fits in hub RAM. Goroutines run concurrently on the available cogs; optional affinity
is exposed through `machine.AssignCore`. The scheduler is cooperative. Go
objects and stacks live in hub RAM; `machine.PSRAM` provides checked byte access
to external memory. See the [runtime design and profiles](modern/README.md).

## Historical baseline

The original TinyGo 0.23 / LLVM 14 Phase 1 and Phase 2 sources, immutable
archive, and historical evidence remain in their original directories. They
are separate from the modern port. The old root documentation is preserved as
[reports/PHASE2_README.md](reports/PHASE2_README.md); its capability limitations
and publication status describe that historical baseline.

See [NOTICE.md](NOTICE.md) for upstream license boundaries. The modern bundle
contains source patches and new source files; it does not redistribute a
prebuilt Go or LLVM installation.