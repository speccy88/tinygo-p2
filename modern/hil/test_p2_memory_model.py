"""Check the actual memory-helper assembly against Python's byte-copy oracle.

This is an instruction model, not a substitute for assembler or hardware tests.
"""

import argparse
import random
import re
from pathlib import Path


class MemoryMachine:
    def __init__(self, source):
        self.instructions = []
        self.labels = {}
        for line in source.splitlines():
            line = line.split("//", 1)[0].strip()
            if not line:
                continue
            if line.endswith(":"):
                self.labels[line[:-1]] = len(self.instructions)
                continue
            if line.startswith("."):
                continue
            self.instructions.append(line)

    def run(self, entry, memory, arguments):
        self.memory = memory
        self.reg = {f"r{i}": 0x80000000 + i * 4 for i in range(32)}
        self.reg.update(pa=0, pb=0, ptrb=0, ptra=0x74004)
        self.reg.update({f"${i}": 0 for i in range(128)})
        self.reg.update(zip(("r0", "r1", "r2"), arguments))
        saved = {key: self.reg[key] for key in [f"r{i}" for i in range(30)] + ["ptra"]}
        self.c = self.z = False
        self.pending = None
        pc = self.labels[entry]
        steps = 0
        while True:
            steps += 1
            assert steps < 200000, (entry, arguments, "loop")
            line = self.instructions[pc]
            pc += 1
            if line.startswith("if_"):
                condition, line = line.split(None, 1)
                if not {"if_c": self.c, "if_z": self.z}[condition]:
                    continue
            op, *rest = line.split(None, 1)
            operands = rest[0] if rest else ""
            flags = ""
            match = re.search(r"\s+(wc|wz|wcz)$", operands)
            if match:
                flags = match.group(1)
                operands = operands[:match.start()]
            args = [arg.strip() for arg in operands.split(",")] if operands else []

            def value(token):
                if token.startswith("#"):
                    return int(token.lstrip("#"))
                return self.reg[token]

            if op == "reta":
                assert self.pending is None
                assert all(self.reg[key] == val for key, val in saved.items())
                assert self.reg["r31"] == arguments[0]
                return steps
            elif op in ("jmp", "tjz", "tjnz", "djnz"):
                jump = True
                if op == "djnz":
                    self.reg[args[0]] = (value(args[0]) - 1) & 0xffffffff
                if op in ("tjz", "tjnz", "djnz"):
                    jump = (value(args[0]) == 0) == (op == "tjz")
                if jump:
                    pc = self.labels[args[-1].lstrip("#")]
            elif op == "setq":
                assert self.pending is None
                self.pending = value(args[0]) + 1
                assert 1 <= self.pending <= 128
            elif op in ("rdlong", "wrlong", "rdbyte", "wrbyte"):
                width = 4 if op.endswith("long") else 1
                count = self.pending or 1
                self.pending = None
                assert width == 4 or count == 1
                pointer = args[1]
                delta = count * width
                if pointer.startswith("--"):
                    pointer = pointer[2:]
                    self.reg[pointer] -= delta
                post_increment = pointer.endswith("++")
                if post_increment:
                    pointer = pointer[:-2]
                address = value(pointer)
                if count > 1:
                    assert address % 4 == 0, ("unaligned block", address)
                for index in range(count):
                    at = address + index * width
                    assert 0 <= at <= len(memory) - width
                    if args[0].startswith("$"):
                        target = f"${int(args[0][1:]) + index}"
                        assert int(target[1:]) < 128
                    else:
                        target = args[0]
                        assert count == 1 or target.startswith("#")
                    if op.startswith("rd"):
                        self.reg[target] = int.from_bytes(memory[at:at + width], "little")
                    else:
                        memory[at:at + width] = (value(target) & ((1 << (8 * width)) - 1)).to_bytes(width, "little")
                if post_increment:
                    self.reg[pointer] += delta
            else:
                left = value(args[0])
                right = value(args[1])
                if op == "mov":
                    result = right
                elif op == "add":
                    result = left + right
                elif op in ("sub", "cmp"):
                    result = left - right
                elif op in ("and", "test"):
                    result = left & right
                elif op == "or":
                    result = left | right
                elif op == "xor":
                    result = left ^ right
                elif op == "shl":
                    result = left << right
                elif op == "shr":
                    result = left >> right
                else:
                    raise AssertionError(("unknown instruction", line))
                if "c" in flags:
                    assert op == "cmp"
                    self.c = left < right
                result &= 0xffffffff
                if "z" in flags:
                    self.z = result == 0
                if op not in ("cmp", "test"):
                    self.reg[args[0]] = result
            # ATN can arrive at any instruction boundary outside a SETQ pair.
            # The interrupt observes real PTRA and original pointer roots.
            assert all(self.reg[key] == val for key, val in saved.items())


def check(source):
    machine = MemoryMachine(source)
    assert not re.search(r"\b(?:rdfast|wrfast|rfbyte|wfbyte|rflong|wflong|rep)\b", source)
    initial = random.Random(480019).randbytes(14000)
    lengths = list(range(18)) + [31, 32, 33, 127, 128, 129, 255, 256, 257,
                                 508, 509, 510, 511, 512, 513, 514, 515,
                                 1023, 1024, 1025, 2047, 2048, 2049, 4096]
    count = 0
    for length in lengths:
        for src_align in range(4):
            src = 6000 + src_align
            destinations = [64 + i for i in range(4)]
            destinations += [src + offset for offset in (-1024, -513, -512, -511,
                                                          -128, -127, -4, -3, -2, -1,
                                                          0, 1, 2, 3, 4, 127, 128,
                                                          511, 512, 513, 1024)]
            for dst in destinations:
                memory = bytearray(initial)
                expected = bytearray(initial)
                expected[dst:dst + length] = initial[src:src + length]
                machine.run("memmove", memory, (dst, src, length))
                assert memory == expected, ("memmove", dst, src, length)
                count += 1
            for dst_align in range(4):
                dst = 64 + dst_align
                memory = bytearray(initial)
                expected = bytearray(initial)
                expected[dst:dst + length] = initial[src:src + length]
                machine.run("memcpy", memory, (dst, src, length))
                assert memory == expected, ("memcpy", dst, src, length)
                count += 1
        for align in range(4):
            for byte in (0, 1, 127, 128, 255, 256, 0xffffffff):
                dst = 64 + align
                memory = bytearray(initial)
                expected = bytearray(initial)
                expected[dst:dst + length] = bytes([byte & 255]) * length
                machine.run("memset", memory, (dst, byte, length))
                assert memory == expected, ("memset", dst, byte, length)
                count += 1
    print(f"PASS: {count} assembly-model cases; data, guards, ABI and live stack roots checked")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", nargs="?", type=Path,
                        default=Path(__file__).parents[1] / "overlays/tinygo/src/runtime/p2_memory.S")
    check(parser.parse_args().assembly.read_text())
