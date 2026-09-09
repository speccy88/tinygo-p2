# Source audit and precise implementation boundary

## 1. Locked baseline

The selected stack is TinyGo **v0.23.0**, host Go **1.18.10**, its existing pinned `tinygo.org/x/go-llvm` dependency, and ne75's P2 LLVM fork. Exact revisions are in `sources.lock.json`.

The TinyGo v0.23.0 tag resolves to `cf0b7edc78e42038a0bb522b3f1a5b76928e730e`. Its Makefile lists LLVM 14, 13, 12 and 11, and its go.mod pins the Go LLVM binding revision used here. This is stronger evidence than relying on a modern TinyGo web page to describe an archived release.

P2LLVM currently pins backend `72a9bb1ef2656d9953d1f41a8196d425ff2ab0b1` and loader `21e074cc7ee6fbd4fb12ef5352544b3457a6729c`. The backend identifies itself as 14.0.0-git, not final LLVM 14. A shared major number is an opportunity to try the integration, not proof that every C/C++ binding/API matches.

Go 1.18.10 is the selected old SDK to bound the experiment, not an assertion that it is the only possible SDK. It is downloaded locally and its archive checksum is checked against the official HTTPS Go release manifest. No old SDK is installed over the user's current one. Existing TinyGo go.mod/go.sum files are left intact and `-mod=readonly` is used.

## 2. The original proposal needed an important refinement

The earlier idea of invoking an unmodified TinyGo CLI against a P2 target skips a real dependency. In v0.23.0, `compiler.CompilePackage`:

1. obtains a loaded `runtime` SSA package;
2. looks up and predeclares `runtime.alloc`;
3. builds package initialization and all relevant members.

Consequently, a completely ordinary `tinygo build -target=p2` still needs a platform/runtime, even for an apparently trivial main program. Creating a target JSON alone does not establish that runtime.

The supplied hook is an **additional test file inside TinyGo's compiler package**. It uses `compiler.NewTargetMachine`, `compiler.Sizes`, the ordinary Go parser/typechecker and pinned SSA package, then calls the existing `newCompilerContext`, `newBuilder` and `createFunction` implementations for selected leaves. Existing compiler files are not initially changed.

It intentionally does not call `createPackage`, execute initialization, invent a runtime.alloc stub, or translate the computation by hand. Imports, globals, closures, calls and runtime-dependent SSA are prohibited; only one-block uint32 arithmetic leaves are selected. That makes omitting package initialization legitimate for this narrow probe.

This is an internal API integration harness. It can need compatibility fixes and has only been syntax-checked here, not typechecked or linked against LLVM. It is not a supported standalone TinyGo frontend or a general target implementation.

## 3. C ABI is a prerequisite, not a detail

`compiler/symbol.go` explicitly adds a hidden context parameter to non-exported functions. A Go function with two visible parameters can therefore be a three-argument LLVM function internally. Calling that arbitrarily from C is not an acceptable test.

The source uses:

```go
//export p2_add
//go:noinline
func P2Add(a, b uint32) uint32 { return a + b }
```

The hook checks TinyGo's own parsed export metadata and confirms exactly two LLVM parameters. The IR checker verifies the exported names and signatures and rejects non-C calling-convention markers. Parameter sizes and IR layout come from the actual P2 TargetMachine, not a fabricated ARM or wasm target.

The old `_ = add(10,20)` example was also a weak test: its result can disappear during optimization. Here the function is externally callable and receives fresh operands over serial after startup.

## 4. Two gates avoid unnecessary complexity

`make probe` selects only P2Add and requires a P2 object with just `p2_add`. `make probe-full` separately selects P2Add and P2Mix. P2Mix introduces bitwise instructions and an argument-order-sensitive expression:

```
x = a XOR b
mix = rotate_left_32(x,5) + a - b  (modulo 2^32)
```

This makes swapped arguments observable even though addition itself is commutative. A failure in the expanded test does not invalidate a separately preserved addition-only success.

Both stages save actual TinyGo-generated LLVM IR, assembly and an object, with hashes recorded by the hook. The checker requires P2 ELF32 little-endian machine 300, real nonempty global function symbols, and no unresolved runtime/helper dependencies in the scalar object. Those structural checks are necessary but do not prove correct machine instructions. Hardware execution remains a separate gate.

## 5. Native M2 build requirements

The host compiler executable is arm64 macOS; its output target is P2. These are different architectures and should never be conflated.

The P2LLVM wrapper `build.py` currently hardcodes an arm64 macOS configuration, `/opt/homebrew/opt/llvm/bin/clang++`, and `make -j32`. Blindly running it is undesirable on an M2 development machine. The handoff instead uses a local Ninja build, two jobs by default, the detected host Clang, the P2 experimental target and an AArch64 host target.

The TinyGo compiler package imports loader/cgo functionality, so simply producing the `llc` command is insufficient. The harness build needs custom **libLLVM and libclang**, their headers, and the matching Go bindings. The script builds shared libraries and explicitly sets CGO includes, libraries and rpath to that same P2-enabled LLVM build. It does not invoke the full TinyGo Makefile, which pulls in additional full-toolchain dependencies not needed for this leaf probe.

The pinned binding supports the `byollvm` build tag. Without this tag, its platform configuration can select a system LLVM instead. The source-side opt-out is visible in `llvm_dep.go` and the llvm_config platform files. The handoff logs the relevant CGO environment but not unrelated personal environment variables.

Plausible integration failures include early-14/final-14 C API differences, C++ header changes exposed by a modern host compiler, and macOS SDK/linker incompatibilities with the archived Go release. None was reproduced here; no speculative patches are claimed as fixes. Codex must patch demonstrated errors minimally and preserve diffs.

## 6. Reuse P2 startup, linker and libraries

The first actual image has this layout:

```
P2 ROM/loader -> existing libp2 startup -> C main / UART protocol
                                            |
                                            +-> p2_add / p2_mix from TinyGo's go.o
```

The upstream p2.ld reserves the entry header, COG/LUT sections and specific addresses used by backend relocations. Replacing it with a generic flat microcontroller linker script would add an unnecessary failure mode. The provided build uses the upstream script and existing libc/libp2 unchanged initially.

The P2 Clang driver has historical global `/opt/p2llvm` and `/opt/p2` library discovery paths. Its include sysroot is handled differently. To avoid silently linking an unrelated installed library, the firmware is linked with the **specific custom ld.lld** and explicit workspace library paths.

The backend project documents `-fno-jump-tables`; Clang's P2 driver also injects it. The Go functions receive the corresponding LLVM function attribute. The first proof uses no switches and no variable shift counts, further reducing unsupported lowering paths.

## 7. Loader and USB serial requirements

Use the pinned **ne75/loadp2** fork that is a P2LLVM submodule, rather than assuming an unrelated system `loadp2` supports the same ELF format. Its build explicitly includes loadelf.c.

Build `make build/loadp2`, not the default make target. The default also builds flash/SD board helpers through a hardcoded FlexSpin path. Those helpers are unnecessary and outside the authorized RAM-only scope.

The loader distinguishes `-b` (application terminal baud) from `-l` (download baud). Both start at 115200 here. It uses `-ZERO` for RAM clearing, an ELF filename and terminal mode. There is no flash command, no `-PATCH`, no memory-address filespec, no 9P host filesystem server and no loader script.

The runner creates a host pseudo-terminal and lets one loadp2 process own the USB serial device for loading and challenge/response. It does not close/reopen the physical serial port after upload. This avoids adding a second DTR/reset transition to the experiment. The PTY transport was exercised against a host C program; macOS loadp2 and the real USB UART still require validation.

## 8. Board and clock

Earlier user context identified P2-EC32MB Rev B with a 20 MHz TCXO. The included profile is based on that identity and a historical serial device hint; neither is a new live detection.

The generic example's p2es_clock.h hardcodes `_XOSC = 2` (crystal capacitance). It is not blindly reused for a TCXO. The harness supplies `_XTALFREQ = 20000000` and `_XOSC = 1` (external oscillator) to the upstream generic clock macros, selecting 160 MHz. This proposed profile must be checked against the actual connected board and proven by the C serial baseline. Do not claim clock validation from source inspection alone.

The first proof uses no external PSRAM and does not need the advertised 32 MB expansion. Stack, code and data stay in internal HUB RAM; load segments are checked against the linker script's usable 0x7c000 boundary.

## 9. What remains after a successful leaf proof

Only after a separate decision to expand scope would a normal TinyGo port need target/architecture configuration, runtime entry and memory layout, package initialization, panic/exit behavior, UART/timer implementations, allocation policy, machine support and tests. Goroutines add scheduler/context-switch and stack work. Multicog execution adds synchronization, cross-cog memory/ownership rules and multicore-safe runtime/GC design.

None of those is needed to answer the highlighted arithmetic-function question. Eight hardware cogs do not automatically map to Go goroutines.

## Primary source references

All repository paths below were inspected for this handoff; revisions are pinned rather than moving branches.

- TinyGo compiler initialization, Config, NewTargetMachine and CompilePackage: https://github.com/tinygo-org/tinygo/blob/cf0b7edc78e42038a0bb522b3f1a5b76928e730e/compiler/compiler.go
- TinyGo exported versus hidden-context functions: https://github.com/tinygo-org/tinygo/blob/cf0b7edc78e42038a0bb522b3f1a5b76928e730e/compiler/symbol.go
- Existing package compiler tests and SSA setup: https://github.com/tinygo-org/tinygo/blob/cf0b7edc78e42038a0bb522b3f1a5b76928e730e/compiler/compiler_test.go
- Archived dependencies and build configuration: https://github.com/tinygo-org/tinygo/blob/cf0b7edc78e42038a0bb522b3f1a5b76928e730e/go.mod and https://github.com/tinygo-org/tinygo/blob/cf0b7edc78e42038a0bb522b3f1a5b76928e730e/Makefile
- Go LLVM target bindings: https://github.com/tinygo-org/go-llvm/blob/512c94c1e71f46c07311e34e8dff3210fb08daa4/target.go
- Custom LLVM opt-out: https://github.com/tinygo-org/go-llvm/blob/512c94c1e71f46c07311e34e8dff3210fb08daa4/llvm_dep.go
- P2LLVM wrapper/build and submodules: https://github.com/ne75/p2llvm/blob/bdcefcce7860b2232c06f35726fea679a3a7309c/build.py
- P2 Clang driver and linker paths: https://github.com/ne75/llvm-project/blob/72a9bb1ef2656d9953d1f41a8196d425ff2ab0b1/clang/lib/Driver/ToolChains/P2.cpp
- Upstream P2 linker layout: https://github.com/ne75/p2llvm/blob/bdcefcce7860b2232c06f35726fea679a3a7309c/libp2/p2.ld
- Serial initialization example: https://github.com/ne75/p2llvm/blob/bdcefcce7860b2232c06f35726fea679a3a7309c/examples/3_serial/serial.cpp
- Crystal-specific and generic clocks: https://github.com/ne75/p2llvm/blob/bdcefcce7860b2232c06f35726fea679a3a7309c/libp2/include/sys/p2es_clock.h and https://github.com/ne75/p2llvm/blob/bdcefcce7860b2232c06f35726fea679a3a7309c/libp2/include/sys/p2_clock.h
- ELF-capable loader build: https://github.com/ne75/loadp2/blob/21e074cc7ee6fbd4fb12ef5352544b3457a6729c/Makefile
- Loader arguments and reset/terminal behavior contract: https://github.com/ne75/loadp2/blob/21e074cc7ee6fbd4fb12ef5352544b3457a6729c/README.md
