# Build TinyGo/P2 from the complete source release

The `tinygo-p2-sources-v0.1.0-full.tar.gz` asset contains the patched TinyGo
0.44.0 sources, the complete patched LLVM 15.0.7 tree (including Clang and LLD),
the P2 support libraries and builtins, TinyGo's `src/net` submodule, the verified
Go 1.27.4 Linux toolchain archive, Go module build dependencies, loadp2, and
flexspin's sources. Upstream licenses are kept alongside their code.

The sources match `modern/toolchain.lock.json`, `modern/source-manifest.json`,
and `modern/release/loaders.lock.json`. `prepared-source-manifest.json` records
every prepared source and module-cache input by SHA-256. No upstream Git
checkout is needed to build this archive. Operating-system packages below are
still prerequisites; they are not bundled.

## Ubuntu 26.04 / WSL2

Keep the build in your Linux home directory, rather than `/mnt/c`. Allow at
least 20 GiB free disk space and 8 GiB RAM. Building LLVM takes substantially
longer than installing the prebuilt SDK.

```sh
sudo apt update
sudo apt install -y build-essential git curl python3 cmake ninja-build clang lld zlib1g-dev
tar -xzf tinygo-p2-sources-v0.1.0-full.tar.gz
cd tinygo-p2-sources
P2_BUILD_JOBS=3 bash modern/build-toolchain.sh "$PWD"
export TINYGO_P2_WORK="$PWD"
bash modern/tinygo.sh version
bash modern/tinygo.sh build -target=p2 -o hello.elf ./modern/examples/hello/main.go
python3 modern/export-image.py hello.elf hello.binary
```

Once the OS packages are installed, `GOPROXY=off GOSUMDB=off` can be set when
running the build to require the supplied module cache. The source verifier
deliberately rejects changed prepared inputs. For development, first keep a
copy of the manifest as provenance, then rename it out of the way and work in
normal Git checkouts using the Git-based bootstrap below; do not bypass a
failed verification on an untrusted download.

## Build from Git instead

This is the smaller download when you already have network access. Git contains
all port changes as complete patches and new source files. The bootstrap fetches
the exact public upstream revisions and applies them, including the P2 LLVM
backend. It is not dependent on a maintainer's unpublished branch.

```sh
git clone --branch v0.1.0 https://github.com/speccy88/tinygo-p2.git
cd tinygo-p2
bash modern/build-toolchain.sh "$HOME/tinygo-p2-work"
bash modern/verify-host.sh "$HOME/tinygo-p2-work"
```

## Rebuild the Windows and Linux loaders

The complete source archive supplies the two source directories used here.
The Windows executable is a native x86-64 application; it uses the Windows
serial port directly. Flexspin is used only to assemble loadp2's loader stubs.

```sh
sudo apt install -y bison xxd gcc-mingw-w64-x86-64
bash modern/release/build-loaders.sh "$PWD"
./loadp2/build/loadp2 -?
# Windows executable: loadp2/build-win32/loadp2.exe
```

The upstream help command exits with status 1 after displaying usage.
For source revisions and licenses, see `modern/release/loaders.lock.json`,
`loadp2/LICENSE`, and `spin2cpp/COPYING`.

## Maintainer packaging

`modern/release/package.py stage` takes `--work`, `--output`, `--loadp2`, and
`--spin2cpp` paths. It copies only tracked sources and the declared TinyGo
overlays, rebuilds the CLI with `-trimpath`, includes Clang resource headers,
and sets relative ELF library search paths. It requires `patchelf` in addition
to the build prerequisites. Use a new empty output directory.

Run the same command with `demo` in place of `stage` to compile the demo images
and collect loaders, instructions, and licenses. Validate the relocated SDK and
the demo, then run it with `archives` in place of `stage`. It produces the SDK,
complete source and demo assets plus `SHA256SUMS`. Release checks and physical
board coverage are recorded in `modern/release/VALIDATION.md`.
