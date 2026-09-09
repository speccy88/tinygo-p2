# Phase 2 continuation: generated-return blocker to linked CLI ELF

## Completed

- Reproduced the ordinary TinyGo CLI backend crash while emitting a linked bare-metal image: `LLVM ERROR: unable to allocate function return #1` (`logs/p2-baremetal-elf-build.log`).
- Emitted normal TinyGo IR before changing the target. The concrete failing generated declaration was `runtime.doAtomicAdd`:
  `define internal { i32, i32 } @runtime.doAtomicAdd(...)`.
- The pinned P2 `RetCC_P2` has only one scalar return register (`R31`), so LLVM lowered tuple element zero and failed allocating tuple element one. This was not an application-return failure.
- Applied the narrow no-fake fix: P2 excludes TinyGo's critical-section atomic stand-ins, which create tuple `(old,new)` returns, and uses a real P2 `LOCKNEW`/`LOCKTRY`/`LOCKREL` critical-section primitive for the mandatory `internal/task` interrupt API. Atomic API use remains unsupported on this one-cog Phase-2 target rather than being silently emulated.
- Added a direct Hub-RAM startup: establishes PTRA at `_stack_bottom` before calls, clears BSS, applies the documented 20 MHz TCXO to 160 MHz clock sequence, configures smart-pin async TX pin 62 at 115200 baud, allocates the hardware lock, and enters normal TinyGo `main -> runtime.run -> runtime.initAll -> main.main`.
- Added `//go:linkname` bindings for Go runtime hooks to the real C UART/halt/lock symbols; deleted the prior no-op P2 interrupt implementation.
- Adjusted the P2 link script to match the direct-entry layout (the old libp2 cog trampoline fixed addresses rewound the location counter).

## Verified linked result

Ordinary CLI command (inside the unchanged network-none container):

```sh
$TINYGOROOT/build/tinygo build -target=$TINYGOROOT/targets/p2.json \
  -scheduler=none -gc=none -o $ROOT/.work/phase2/out/p2goapp-phase2.elf .
```

Exit status: `0` (`logs/20260908T_phase2_cli_elf_stack_bottom.log`).

`llvm-readobj` reports `Format: elf32-p2`, `Arch: p2`, ELF32 little-endian executable, `Machine: 0x12C`, entry `0x0`, section-header entry size `40`.

The final ELF SHA-256 is:

```
3b7cacc5b6a21c484be71e966580b197eb75eaf479b953b67a3100e769dc8117
```

Inspection/disassembly: `reports/20260908T_phase2_elf_final_inspection.txt`. It contains `__entry`, `raw_p2_uart_putc`, `p2_lock_acquire`, `p2_lock_release`, and the normal runtime/main chain. The disassembly shows `PTRA` loaded from `_stack_bottom` (`0x70000`), BSS zeroing, `HUBSET`, smart-pin `WRPIN/WXPIN/DIRH`, and lock instructions.

## Preserved failures / remaining limits

- Each new unsuccessful attempt is separately retained under `logs/20260908T_*`; prior Phase-2 logs were not overwritten.
- The first startup compile failed only because TinyGo's builtin Clang frontend could not find headers. A local `tinygo/llvm-project/clang/lib/Headers` symlink points to the isolated Phase-2 LLVM Clang headers; no SDK/shared LLVM source was changed.
- The ThinLTO `invalid e_shentsize` failure was not reinterpreted or header-rewritten. This successful ordinary non-ThinLTO link produces the valid 40-byte ELF32 section-header entries.
- No serial device was opened and no load was performed. The UART/startup code is linked and instruction-inspected but not hardware validated. Atomic operations and multiword/tuple returns remain deliberately unsupported pending an ABI design; decimal integer printing was removed from this initial observable app to avoid unrelated 64-bit compiler-rt helpers.
