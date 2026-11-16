"""Assemble P2 runtime sources and check their actual linked instructions."""

import argparse
import json
import struct
import subprocess
from pathlib import Path


SOURCES = (
    "targets/p2_boot.S",
    "src/runtime/runtime_p2.S",
    "src/internal/task/task_stack_p2.S",
    "src/runtime/gc_p2.S",
    "src/runtime/p2_memory.S",
    "src/runtime/p2_psram.S",
)


class ELF:
    def __init__(self, path):
        self.data = path.read_bytes()
        assert self.data[:7] == b"\x7fELF\x01\x01\x01"
        offset = struct.unpack_from("<I", self.data, 32)[0]
        size, count, names_index = struct.unpack_from("<HHH", self.data, 46)
        self.sections = [struct.unpack_from("<10I", self.data, offset + i * size)
                         for i in range(count)]

        def string(blob, at):
            return blob[at:blob.index(0, at)].decode()

        names = self.section_data(self.sections[names_index])
        self.names = {string(names, section[0]): section for section in self.sections}
        self.symbols = {}
        for section in self.sections:
            if section[1] != 2:
                continue
            names = self.section_data(self.sections[section[6]])
            for at in range(section[4], section[4] + section[5], section[9]):
                name, value, _, _, _, index = struct.unpack_from("<IIIBBH", self.data, at)
                if name:
                    self.symbols[string(names, name)] = (value, index)

    def section_data(self, section):
        return self.data[section[4]:section[4] + section[5]]

    def address(self, symbol):
        return self.symbols[symbol][0]

    def instruction(self, symbol, offset=0):
        value, index = self.symbols[symbol]
        section = self.sections[index]
        return struct.unpack_from("<I", self.data, section[4] + value - section[3] + offset)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--tinygo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--startup-c", action="store_true")
    parser.add_argument("--opt", default="z", choices=("0", "1", "2", "3", "s", "z"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    def run(tool, *arguments):
        result = subprocess.run([str(args.tools / tool), *map(str, arguments)],
                                capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"{tool} failed:\n{result.stdout}{result.stderr}")
        return result.stdout

    objects = []
    for name in SOURCES:
        output = args.output / (Path(name).name + ".o")
        run("llvm-mc", "-triple=p2", "-filetype=obj", args.tinygo / name, "-o", output)
        objects.append(output)
        (args.output / (output.name + ".txt")).write_text(run("llvm-objdump", "-dr", output))

    # The fixture only resolves runtime imports; it is never a bootable image.
    stub = args.output / "runtime_stubs.S"
    stub_source = """.section .text.runtime_stubs
.global tinygo_task_exit
.global tinygo_scanstack
.global tinygo_runCore
.global main
tinygo_task_exit:
    reta
tinygo_scanstack:
    reta
tinygo_runCore:
    reta
main:
    reta
"""
    if args.startup_c:
        startup = args.output / "p2_start.c.o"
        target = json.loads((args.tinygo / "targets/p2.json").read_text())
        run("clang", "--target=p2", "-O" + args.opt, *target["cflags"],
            "-gdwarf-4", "-c", args.tinygo / "targets/p2_start.c", "-o", startup)
        objects.append(startup)
        (args.output / "p2_start.c.o.txt").write_text(run("llvm-objdump", "-dr", startup))
        startup_image = ELF(startup)
        launch = startup_image.section_data(startup_image.names[".text.p2_start_core"])
        words = [word[0] for word in struct.iter_unpack("<I", launch)]
        coginit = [index for index, word in enumerate(words)
                   if word & 0x0fe00000 == 0x0ce00000]
        assert len(coginit) == 1
        index = coginit[0]
        assert words[index] & 0x100000 == 0  # Fixed IDs must not use allocation carry.
        assert words[index - 1] & 0xfffc01ff == 0xfd600028  # SETQ register parameter.
    else:
        stub_source += ".global p2_primary_entry\np2_primary_entry:\n    reta\n"
    stub.write_text(stub_source)
    stub_object = args.output / "runtime_stubs.o"
    run("llvm-mc", "-triple=p2", "-filetype=obj", stub, "-o", stub_object)
    linked = args.output / "runtime-fixture.elf"
    run("ld.lld", "-T", args.tinygo / "targets/p2.ld", *objects, stub_object, "-o", linked)
    (args.output / "runtime-fixture.disassembly.txt").write_text(run("llvm-objdump", "-dr", linked))
    image = ELF(linked)

    for caller, offset, callee in (("tinygo_startTask", 8, "tinygo_task_exit"),
                                    ("tinygo_scanCurrentStack", 12, "tinygo_scanstack")):
        instruction = image.instruction(caller, offset)
        assert instruction & 0xfff00000 == 0xfdc00000, hex(instruction)
        assert instruction & 0xfffff == image.address(callee)

    upper = image.instruction("p2_gc_install", 4)
    lower = image.instruction("p2_gc_install", 8)
    assert (upper & 0x7fffff) << 9 | (lower & 0x1ff) == image.address("p2_gc_irq")

    for caller, offset, callee in (("memmove", 4, "memcpy"),
                                    ("p2_lock_acquire_id", 4, "p2_lock_acquire_id")):
        instruction = image.instruction(caller, offset)
        assert instruction & 0x100000
        displacement = instruction & 0xfffff
        if displacement & 0x80000:
            displacement -= 0x100000
        assert image.address(caller) + offset + 4 + displacement == image.address(callee)

    assert image.instruction("p2_gc_install", 12) == 0xfd641c25  # SETINT1 #14
    assert image.instruction("p2_cog_attention") == 0xfd63a03f  # COGATN R0
    assert image.instruction("p2_irq_stall") == 0xfd604224
    assert image.instruction("p2_irq_allow") == 0xfd604024
    assert image.instruction("p2_gc_irq", 120) == 0xfb3bfff5  # RETI1
    assert image.instruction("tinygo_swapTaskP2") == 0xfd643a28  # SETQ #29
    assert image.instruction("tinygo_swapTaskP2", 4) == 0xfc67a161  # WRLONG R0,PTRA++

    globals_end = image.address("_globals_end")
    secondary = image.address("_p2_secondary_stacks")
    heap_start = image.address("_heap_start")
    assert globals_end <= secondary
    assert secondary % 8 == 0
    assert secondary + 7 * 8192 == heap_start
    assert image.names[".stack.secondary"][1] == 8  # SHT_NOBITS
    assert heap_start + 0x10000 <= image.address("_heap_end")
    assert image.address("_stack_top") - image.address("_stack_bottom") == 16384

    assert image.address("__entry") == 0
    assert image.instruction("__entry") == 0xfd800010  # Absolute cog address 16.
    assert image.address("__start0") == 0x40
    assert image.address("__start") == image.address("__start0") + 12
    assert image.address("__p2_boot_end") <= 0x200
    assert image.instruction("__start0", 8) == 0xfce801ef  # COGINIT #0,R31.

    def augmented(symbol, offset):
        return ((image.instruction(symbol, offset) & 0x7fffff) << 9 |
                (image.instruction(symbol, offset + 4) & 0x1ff))

    assert augmented("__start0", 0) == image.address("__start")
    assert image.instruction("__start", 0) == 0xfd67fe29  # SETQ2 #511.
    assert image.instruction("__start", 4) == 0xff000001  # AUGS #1.
    assert image.instruction("__start", 8) == 0xfb040000  # RDLONG $0,#0.
    assert augmented("__start", 12) == image.address("_stack_bottom")
    assert augmented("__start", 20) == image.address("p2_primary_entry")
    assert augmented("__start", 28) == image.address("tinygo_runCore")
    assert image.address("p2_primary_entry") >= 0xa00
    assert image.address("tinygo_runCore") >= 0xa00
    assert image.instruction("__start", 36) == 0xfd63a001  # COGID R0.
    assert image.instruction("__start", 40) == 0xf20fa000  # CMP R0,#0 WZ.
    assert image.instruction("__start", 44) == 0xa603f1f6  # IF_Z MOV PTRA,PA.
    assert image.instruction("__start", 48) == 0xa603dff7  # IF_Z MOV R31,PB.
    assert image.instruction("__start", 52) == 0xfd63de2c  # JMP R31.
    assert image.address("__p2_boot_end") == image.address("__start") + 56

    report = {"assembled_sources": list(SOURCES), "absolute_calls_checked": 2,
              "relative_branches_checked": 2, "gc_vector_checked": True,
              "interrupt_encodings_checked": True, "stack_layout_checked": True,
              "globals_end": globals_end, "secondary_stacks": secondary,
              "heap_start": heap_start, "hardware_execution": False}
    report.update(bootstrap_checked=True, startup_c_compiled=args.startup_c,
                  fixed_cog_launch_status_checked=args.startup_c,
                  startup_c_optimization=args.opt if args.startup_c else None,
                  bootstrap_bytes=image.address("__p2_boot_end") - image.address("__start0"))
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("PASS: six P2 assembly files, linked relocations, interrupt encodings, bootstrap and stack layout")


if __name__ == "__main__":
    main()
