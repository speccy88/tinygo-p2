#!/usr/bin/env python3
"""Fresh, nonce-checked hardware replay of the archived Phase 2 application.

This establishes serial, clock and reset baselines, not modern compiler support.
The independent integer oracle matches scripts/gate2f_hil.py.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets

from p2ram import P2Serial, ProtocolError, read_image

MASK = 0xFFFFFFFF
EDGES = [(0, 0, 0), (MASK, 1, 15), (0x80000000, 0x7FFFFFFF, 16),
         (0x7FFFFFFF, MASK, 3), (19, 0xDEADBEEF, 31), (MASK, MASK, MASK),
         (0x13, 0, 1), (0xFFFFFFED, 4, 2), (0x12345678, 0x87654321, 7),
         (0xAAAAAAAA, 0x55555555, 8)]


def oracle(a, b, limit, state):
    words = (0x13579BDF, 0x2468ACE0, 0xF00DCAFE, 0x10203040)
    local = (a + words[(a ^ b) & 3]) & MASK
    fold = state["fold"] ^ state["seed"]
    for i in range(4):
        fold = (((fold << 3) | (fold >> 29)) ^ words[(local + i) & 3]) & MASK
    signed_a = a if a < 0x80000000 else a - 0x100000000
    if signed_a < -19:
        local ^= (-19) & MASK
    elif a > ((-19) & MASK):
        local = (local + b) & MASK
    else:
        local ^= 0xA5A5A5A5
    for i in range((limit & 15) + 1):
        local = (((local << 5) | (local >> 27)) ^ fold ^ i) & MASK
        fold = (fold + words[(i + state["count"]) & 3]) & MASK
    state["sum"] = (state["sum"] + local) & MASK
    state["count"] = (state["count"] + 1) & MASK
    state["fold"] = fold ^ local
    state["seed"] = (state["seed"] + local + b + limit) & MASK
    return local ^ state["sum"] ^ state["fold"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--port", default="COM12")
    parser.add_argument("--random", type=int, default=128)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not 0 <= args.random <= 4096:
        parser.error("--random must be in 0..4096")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = args.out or Path(__file__).parent / "results" / (stamp + "-legacy-baseline")
    out.mkdir(parents=True, exist_ok=False)
    image, metadata = read_image(args.elf)
    result = {"status": "FAIL", "scope": "physical-P2-legacy-baseline", "timestamp_utc": stamp,
              "image": metadata, "passed": 0, "malformed_passed": 0,
              "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "loader_sha256": hashlib.sha256(Path(__file__).with_name("p2ram.py").read_bytes()).hexdigest()}
    vectors = EDGES + [(secrets.randbits(32), secrets.randbits(32), secrets.randbits(32))
                       for _ in range(args.random)]
    ids = set()
    state = dict(sum=0, count=0, fold=0, seed=0x91E10DA5)
    try:
        with P2Serial(args.port, raw_log=out / "serial.raw") as target:
            result["port"] = target.port_info
            result["rom"] = target.identify()
            result["download"] = target.load(image)
            result["boot"] = []
            for expected in (b"P2 PHASE2 IMPORT INIT", b"P2 PHASE2 INIT", b"READY P2E 1"):
                observed = target.line()
                result["boot"].append(observed.decode("ascii", "backslashreplace"))
                if observed != expected:
                    raise ProtocolError("unexpected boot marker: " + repr(observed))
            for malformed in (b"?", b"C 00000000 00000000", b"C zzzzzzzz 00000000 00000000 00000000", b"X" * 65):
                target.send(malformed + b"\r")
                if target.line(3) != b"ERR INPUT":
                    raise ProtocolError("malformed input was not rejected")
                result["malformed_passed"] += 1
            with (out / "challenges.jsonl").open("w") as log:
                for a, b, n in vectors:
                    nonce = secrets.randbits(32)
                    while nonce in ids:
                        nonce = secrets.randbits(32)
                    ids.add(nonce)
                    expected = [nonce, oracle(a, b, n, state), state["sum"], state["count"]]
                    target.send(f"C {nonce:08x} {a:08x} {b:08x} {n:08x}\r".encode("ascii"))
                    line = target.line(3)
                    words = line.split()
                    if len(words) != 6 or words[:2] != [b"R", b"E"] or any(
                        len(word) != 8 or any(c not in b"0123456789abcdefABCDEF" for c in word) for word in words[2:]
                    ):
                        raise ProtocolError("malformed response: " + repr(line))
                    observed = [int(word, 16) for word in words[2:]]
                    log.write(json.dumps(dict(nonce=nonce, a=a, b=b, n=n, expected=expected, observed=observed)) + "\n")
                    log.flush()
                    if observed != expected:
                        raise ProtocolError(f"challenge mismatch: {observed} != {expected}")
                    result["passed"] += 1
        result["total"] = len(vectors)
        result["status"] = "PASS"
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(result, output_directory=str(out.resolve())), indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
