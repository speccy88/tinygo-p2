#!/usr/bin/env python3
"""Load a modern P2 test image into RAM and independently check nonce results."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import struct

from p2ram import P2Serial, ProtocolError, read_image

MASK = 0xFFFFFFFF
ADDRESSES = (0, 3, 63, 4093, 8191, 65533, 1048573, 8388605, 16777213, 33554173)
MEMORY_LENGTHS = (*range(10), 15, 16, 17, 127, 128, 129, 511, 512, 513, 1023, 1024, 1025)


def pattern(seed, address):
    value = seed ^ ((address * 0x9E3779B9) & MASK)
    value ^= value >> 16
    value = (value * 0x7FEB352D) & MASK
    value ^= value >> 15
    return value & 0xFF


def psram_checksum(seed):
    checksum = 0
    for address in ADDRESSES:
        for index in range(259):
            checksum = (((checksum << 5) | (checksum >> 27)) & MASK) ^ pattern(seed, address + index)
    return checksum


def language_expected(seed):
    a = (seed << 32) | (seed ^ 0xABCDEF01)
    b = (seed & 0xFFFF) + 7
    wide_mask = (1 << 64) - 1
    full = a * (((seed ^ 0x13579BDF) << 32) | ((seed + 0x2468ACE1) & MASK))
    carry = ((seed << 32) | MASK) * 0x1FFFFFFFF
    return [
        ["ARITH", a // b, a % b, (a * 37) & ((1 << 64) - 1)],
        ["MUL64", wide_mask - 1, 1, full >> 64, full & wide_mask, carry >> 64, carry & wide_mask],
        ["LANG", sum((seed + i) & MASK for i in range(32)) & MASK,
         sum(((seed + i) & MASK) ^ (i * 17) for i in range(32)) & MASK,
         (7 * seed + 21) & MASK, seed, ((seed + 13) & MASK) ^ seed],
        ["FLOAT", (seed & 255) ** 2 * 4 + 128],
        ["MATH", (seed & 255) + 1, -((seed & 255) + 2), -((seed & 255) + 1),
         -((seed & 255) + 1), 7],
    ]


def gc_checksum(seed):
    total = 0
    for core in range(8):
        for round_number in range(96):
            key = (seed ^ (core * 0x10203) ^ (round_number * 0x01010101)) & MASK
            first = (256 * key + 17 * 256 * 255 // 2) & MASK
            second = (256 * (key ^ 0x55AA55AA) + 17 * 256 * 255 // 2) & MASK
            arithmetic = 0
            for i in range(12):
                dividend = (((key + i) & MASK) << 32) | (key ^ i ^ 0xA5A5A5A5)
                quotient, remainder = divmod(dividend, (key & 0xFFFF) + i + 1)
                arithmetic = (arithmetic + ((quotient & MASK) ^ (quotient >> 32) ^ remainder)) & MASK
            total = (total + (first ^ second ^ round_number ^ arithmetic)) & MASK
    return total


def odd_gc_checksum(seed):
    total = 0
    for round_number in range(32):
        key = seed ^ ((round_number * 0x9E3779B9) & MASK)
        total += key ^ 0x13579BDF ^ ((key & 255) << 24)
    return total & MASK


def stdlib_expected(seed):
    def signed(value):
        return value if value < 0x80000000 else value - 0x100000000

    wide = (seed << 32) | (seed ^ 0xA5A5A5A5)
    formatted = f"p2:{seed:08x}:{signed(seed)}:{wide}"
    message = dict(seed=seed, label=formatted + '"\\\n', values=[signed(seed), signed(seed ^ MASK), -17],
                   ratio=(seed & 255) / 16)
    if seed & 1:
        message["enabled"] = True
    text = "/".join(sorted(["z", "go", "p2", "a", f"{seed:08x}"])).upper().replace("GO", "TINYGO")
    packed = struct.pack("<I", seed) + struct.pack(">Q", wide) + struct.pack("<Q", wide ^ 0x0123456789ABCDEF)
    trailing = (seed & -seed).bit_length() - 1 if seed else 32
    return dict(formatted=formatted, message=message, lines=[
        ["STR", text],
        ["SORT", *sorted([seed & 0xFFFF, -9, seed >> 16, 0, 42])],
        ["BIN", packed.hex()],
        ["SHA256", hashlib.sha256(packed).hexdigest()],
        ["BITS", ((seed << 13) | (seed >> 19)) & MASK, seed.bit_count(), 32 - seed.bit_length(), trailing],
    ])


def memory_expected(seed):
    checksum, operations = seed, 0

    def mix(value):
        nonlocal checksum
        checksum = (((checksum << 5) | (checksum >> 27)) & MASK) ^ value

    def byte_at(index):
        return ((seed + index * 29) ^ (index >> 3)) & 255

    def case(values):
        nonlocal operations
        mix(operations)
        operations += 1
        for value in values:
            mix(value)

    for length in MEMORY_LENGTHS:
        for source_alignment in range(4):
            for target_alignment in range(4):
                for operation in range(3):
                    case(0 if operation == 1 else byte_at(8 + source_alignment + index) for index in range(length))
    for length in MEMORY_LENGTHS:
        for distance in (1, 2, 3, 4, 127, 128, 511, 512):
            for direction in range(2):
                start = 8 + (distance if direction else 0)
                for operation in range(2):
                    case(byte_at(start + index) for index in range(length))
    for length in MEMORY_LENGTHS:
        for alignment in range(4):
            for fill in (0, 0x55, 0xFF, 0x80, 0x123456A7, seed):
                case((fill & 255) for index in range(length))
    return operations, checksum


def cgo_expected(seed):
    wide_mask = (1 << 64) - 1
    b = (seed << 32) | (seed ^ 0xA5A5A5A5)
    c = (seed * 17 + 3) & MASK
    d = ((seed ^ 0x01234567) << 32) | ((seed + 0x89ABCDEF) & MASK)
    a_out = ((seed ^ (b & MASK)) + c) & MASK
    b_out = (b >> 32) ^ (d & MASK) ^ c
    c_out = ((b + d) & wide_mask) ^ ((seed << 32) | c)
    folded = c_out ^ ((a_out << 32) | b_out) ^ (seed ^ 0xFEDCBA98)
    values = [((((seed + i * 7) & 255) ^ ((seed >> ((i & 3) * 8)) & 255)) + i * 3) & 255
              for i in range(33)]
    checksum = seed
    for value in values:
        checksum = (((checksum << 5) | (checksum >> 27)) & MASK) ^ value
    return ["CGO", a_out, b_out, c_out, folded, (seed & 1023) + 54, checksum, values[0], values[-1]]


def cgo_aggregate_expected(seed):
    _, a, b, c, *_ = cgo_expected(seed)
    salt = seed ^ 0x76543210
    changed = ((c + 0x0102030405060708) & ((1 << 64) - 1)) ^ (((a ^ salt) << 32) | ((b + 7) & MASK)) ^ salt
    head, middle, tail = seed ^ 0x22222222, (seed << 32) | ((seed + 0x11111111) & MASK), seed ^ 0x33333333
    return [["CGOCOPY", changed, a, b, c],
            ["CGOLAYOUT", 16, 4, 12, head, middle, tail, middle ^ ((head << 32) | tail)]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--port", default="COM12")
    parser.add_argument("--suite", choices=("language", "psram", "gcstress", "gcoddstack", "recovery", "stdlib", "memory", "cgo"), default="language")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--encoding", choices=("base64", "hex"), default="base64")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = args.out or Path(__file__).parent / "results" / (stamp + "-" + args.suite)
    out.mkdir(parents=True, exist_ok=False)
    image, metadata = read_image(args.elf)
    seed = secrets.randbits(32)
    result = {"status": "FAIL", "suite": args.suite, "scope": "physical-P2-modern",
              "timestamp_utc": stamp, "nonce": seed, "image": metadata, "observed": [],
              "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "loader_sha256": hashlib.sha256(Path(__file__).with_name("p2ram.py").read_bytes()).hexdigest()}
    protocol = {"language": "P2CONF1", "psram": "P2PSRAM1", "gcstress": "P2GC1",
                "recovery": "P2RECOVER1", "stdlib": "P2STDLIB1", "memory": "P2MEMORY1", "cgo": "P2CGO1",
                "gcoddstack": "P2GCODD1"}[args.suite]
    try:
        with P2Serial(args.port, raw_log=out / "serial.raw") as target:
            result["port"] = target.port_info
            result["rom"] = target.identify()
            result["download"] = target.load(image, encoding=args.encoding)

            def line():
                observed = target.line(args.timeout).decode("ascii", "backslashreplace")
                result["observed"].append(observed)
                print(observed, flush=True)
                return observed

            def expect(tokens):
                expected = " ".join(map(str, tokens))
                observed = line()
                if observed != expected:
                    raise ProtocolError(f"expected {expected!r}, observed {observed!r}")

            expect(["READY", protocol])
            target.send(f"{seed:08x}\r".encode("ascii"))
            expect(["BEGIN", seed])
            if args.suite == "language":
                for expected in language_expected(seed):
                    expect(expected)
                observed = line().split()
                if len(observed) != 2 or observed[0] != "TIME" or not 2000 <= int(observed[1]) <= 2000000:
                    raise ProtocolError("invalid elapsed time report: " + repr(observed))
                observed = line().split()
                if len(observed) != 6 or observed[0] != "CORES":
                    raise ProtocolError("invalid multicog report: " + repr(observed))
                ready, done, peak, atomic, locked = map(int, observed[1:])
                if (ready, done, atomic, locked) != (255, 255, 8000, 800) or not 2 <= peak <= 8:
                    raise ProtocolError("multicog coverage, overlap, atomic or mutex failure")
                result["cores"] = dict(ready_mask=ready, done_mask=done, overlapping_workers=peak,
                                       atomic_total=atomic, mutex_total=locked)
                observed = line().split()
                if len(observed) != 4 or observed[0] != "UNBOUND":
                    raise ProtocolError("invalid automatic multicog report: " + repr(observed))
                mask, peak, checksum = map(int, observed[1:])
                expected = sum((seed ^ (worker * 0x10203)) + i * 17
                               for worker in range(8) for i in range(64)) & MASK
                if not 0 < mask <= 255 or mask.bit_count() < 2 or not 2 <= peak <= 8 or checksum != expected:
                    raise ProtocolError("automatic multicog coverage, overlap, or checksum failure")
                result["unbound_cores"] = dict(cog_mask=mask, overlapping_workers=peak, checksum=checksum)
            elif args.suite == "psram":
                result["psram_ids"] = []
                for bank in range(4):
                    observed = line().split()
                    if len(observed) != 10 or observed[:2] != ["ID", str(bank)]:
                        raise ProtocolError("invalid PSRAM ID record")
                    chip_id = list(map(int, observed[2:]))
                    if chip_id[:2] != [13, 93] or any(not 0 <= value <= 255 for value in chip_id):
                        raise ProtocolError("unexpected PSRAM manufacturer/KGD ID")
                    result["psram_ids"].append(chip_id)
                observed = line().split()
                if len(observed) != 4 or observed[:3] != ["PSRAM", "2590", str(psram_checksum(seed))]:
                    raise ProtocolError("PSRAM count/checksum mismatch: " + repr(observed))
                ticks = int(observed[3])
                if not 0 < ticks < 1280:
                    raise ProtocolError("PSRAM transaction exceeds 8 us at 160 MHz")
                result["psram_tested_bytes"] = 2590
                result["psram_max_transaction_cycles"] = ticks
            elif args.suite == "gcstress":
                observed = line().split()
                if len(observed) != 6 or observed[:3] != ["GCSTRESS", "255", str(gc_checksum(seed))]:
                    raise ProtocolError("GC stress mask/checksum mismatch: " + repr(observed))
                cycles, allocated, frees = map(int, observed[3:])
                if cycles < 100 or allocated < 1 << 20 or frees <= 0:
                    raise ProtocolError("GC stress did not exercise collection/reclamation")
                result["gc"] = dict(collections=cycles, allocated_bytes=allocated, freed_objects=frees)
            elif args.suite == "recovery":
                expect(["RECOVER", seed, 255, 123])
            elif args.suite == "gcoddstack":
                expect(["ODDGC", odd_gc_checksum(seed), 32])
            elif args.suite == "stdlib":
                expected = stdlib_expected(seed)
                expect(["FMT", expected["formatted"]])
                observed = line()
                if not observed.startswith("JSON "):
                    raise ProtocolError("missing JSON output")
                decoded = json.loads(observed[5:])
                if decoded != expected["message"] or ("enabled" in decoded and type(decoded["enabled"]) is not bool):
                    raise ProtocolError("JSON field/value/escape mismatch: " + repr(decoded))
                for tokens in expected["lines"]:
                    expect(tokens)
            elif args.suite == "cgo":
                expect(cgo_expected(seed))
                for expected in cgo_aggregate_expected(seed):
                    expect(expected)
            else:
                operations, checksum = memory_expected(seed)
                observed = line().split()
                if len(observed) != 5 or observed[:3] != ["MEMORY", str(operations), str(checksum)]:
                    raise ProtocolError("memory helper case count/checksum mismatch: " + repr(observed))
                collections, ticks = map(int, observed[3:])
                if collections < 2 or ticks < 2:
                    raise ProtocolError("memory helpers did not run with concurrent GC and timers")
                result["memory"] = dict(operations=operations, checksum=checksum,
                                        collections_during_test=collections, timer_ticks_during_test=ticks)
            expect(["DONE", protocol, seed])
        result["status"] = "PASS"
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(result, output_directory=str(out.resolve())), indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
