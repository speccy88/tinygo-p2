# Debugging order: investigate evidence, not hypothetical rewrites

| Symptom | First investigation | Do not do this |
|---|---|---|
| Old LLVM fails CMake under a recent CMake | Read first configuration error and policy version. The driver adds a minimum-policy compatibility setting for CMake 4. | Upgrade to LLVM 20 before trying a bounded host build fix. |
| LLVM C++ compile errors | Compare the failing source and host SDK/compiler API. Keep minimal include/signature patches with diagnostics. | Apply a large unrelated fork or suppress arbitrary errors. |
| No P2 in `llc --version` | Experimental-target configuration and generated target registration; wrong binary path. | Accept stock Homebrew LLVM as a P2 backend. |
| Go LLVM binding compile/link failure | Early LLVM 14 snapshot versus pinned final-14-era binding; matching headers/libraries; byollvm; CGO/rpath. | Run go get -u or link a different system LLVM silently. |
| Go helper package fails on newer host SDK | Exact Go 1.18.10 arm64 SDK and native Clang; current macOS SDK diagnostic. | Disable OS security or call it a P2 codegen failure before the helper runs. |
| Helper expects a missing runtime type | Ensure the source still consists of admitted scalar leaves; inspect which SSA instruction escaped the guards. | Add a fake allocator/runtime that returns null or claim runtime support. |
| C baseline compiles but Go object generation fails | Generated go.ll, verified signatures, P2 data layout and first unsupported backend operation. Compare with the C control. | Swap in C arithmetic or handwrite the purported TinyGo IR. |
| Library/header missing at link | Explicit workspace sysroot/library paths and copied libc/libp2 headers; inspect map and command. | Install over /opt or accidentally use an older user installation. |
| loadp2 make invokes FlexSpin | Confirm the requested target is `build/loadp2`, not its flash/SD-building default. Examine checked-in loader headers before regenerating. | Build or run flash helpers just to get a RAM loader. |
| ELF rejected | Actual e_machine/type/section/symbol/segment values; compare with a known output of the pinned C compiler. | Turn off architecture/memory checks without explaining and testing the correction. |
| Garbled/missing C serial output | Physical board, TCXO mode, clock, UART pins, application baud versus loader baud, reset wiring and port ownership. | Debug Go before the C-only image works. |
| Load succeeds, terminal/PTY fails | macOS loadp2 stdin/terminal behavior; retained raw log; process/PTY lifetime. | Reopen serial with a second tool and introduce an unexplained DTR reset. |
| Sum works, mix fails | Calling convention, operand order, bitwise/shift lowering and disassembly. | Claim full success based only on the sum. |
| Partial milestone only | Preserve object/disassembly/logs and report exact completed gate. | Describe it as an all-purpose TinyGo platform port. |

No compiler integration failure above was reproduced in the authoring environment: the LLVM source/toolchain was not available there. This is a diagnostic map, not a list of verified patches.
