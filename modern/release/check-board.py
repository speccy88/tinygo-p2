#!/usr/bin/env python3
"""Check release demos and README examples on a P2 through RAM loading only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hil"))
from p2ram import P2Serial, read_image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--port", required=True)
parser.add_argument("--demo", type=Path, required=True)
parser.add_argument("--tutorials", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
receipt = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
           "scope": "release-RAM-only", "checks": []}


def check(name, path, validator):
    raw, _ = read_image(path)
    record = {"name": name, "image": path.name,
              "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "lines": []}
    with P2Serial(args.port) as board:
        record["rom"] = board.identify()
        record["download"] = board.load(raw)

        def line():
            value = board.line(8).decode("ascii")
            record["lines"].append(value)
            return value

        validator(board, line)
    record["status"] = "PASS"
    receipt["checks"].append(record)
    print(f"PASS {name}", flush=True)


def hello(board, line):
    assert line() == "TinyGo 0.44.0 on Propeller 2"
    assert line() == "Available cogs: 8"
    workers = set()
    for _ in range(8):
        match = re.fullmatch(r"Worker (\d) ran on cog (\d) checksum (\d+)", line())
        assert match is not None
        worker, cog, checksum = map(int, match.groups())
        assert worker not in workers and 0 <= cog < 8 and checksum == 1068819344
        workers.add(worker)
    assert workers == set(range(8))
    assert line() == "Alive 1"
    assert line() == "Alive 2"


def channels(board, line):
    cogs = set()
    for _ in range(8):
        match = re.fullmatch(r"Cog (\d) sum 50005000", line())
        assert match is not None
        cogs.add(int(match[1]))
    assert cogs == set(range(8))
    assert line() == "All eight workers finished!"


def psram(board, line):
    assert line() == "External memory bytes: 33554432"
    assert line() == "Hello from 32 MiB of PSRAM!"


def blink(board, line):
    assert [line() for _ in range(4)] == ["LED on", "LED off"] * 2


def echo(board, line):
    assert line() == "Type something:"
    challenge = secrets.token_hex(16)
    board.send(challenge.encode() + b"\r")
    assert line() == challenge


def first_program(board, line):
    assert line() == "Hello, Propeller 2!"
    assert line() == "Tick 1"
    assert line() == "Tick 2"


try:
    for name, validator in (("hello", hello), ("blink", blink), ("channels", channels), ("psram-store", psram)):
        check(f"demo-{name}", args.demo / f"{name}.binary", validator)
    for name, validator in (("hello", first_program), ("blink", blink), ("channels", channels), ("psram", psram), ("echo", echo)):
        check(f"README-{name}", args.tutorials / name / "app.elf", validator)
    if sys.platform == "win32":
        loader = args.demo / "tools/loadp2.exe"
        for mode in ("single-stage", "two-stage"):
            options = ["-SINGLE"] if mode == "single-stage" else ["-l", "115200", "-f", "160000000", "-m", "010007f7"]
            completed = subprocess.run([str(loader), "-p", args.port, "-b", "115200", *options,
                                        str(args.demo / "hello.binary")], capture_output=True, timeout=30, check=True)
            with P2Serial(args.port) as board:
                lines = []
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    value = board.line(5).decode("ascii")
                    lines.append(value)
                    if value.startswith("Alive "):
                        break
                assert any(value.startswith("Alive ") for value in lines)
            receipt["checks"].append({"name": f"Windows-loadp2-{mode}", "status": "PASS",
                                       "loader_sha256": hashlib.sha256(loader.read_bytes()).hexdigest(),
                                       "output": completed.stdout.decode("utf-8", "replace"), "lines": lines})
            print(f"PASS Windows loadp2 {mode}", flush=True)
    receipt["status"] = "PASS"
except Exception as error:
    receipt["status"] = "FAIL"
    receipt["error"] = f"{type(error).__name__}: {error}"
    raise
finally:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(receipt, indent=2) + "\n").encode("utf-8"))
