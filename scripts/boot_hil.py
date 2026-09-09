#!/usr/bin/env python3
"""RAM-only Phase2 Go boot-marker capture through one loadp2-owned PTY."""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.hil import ProtocolError, Terminal

WORK = ROOT / ".work"
PHASE2 = WORK / "phase2"
PORT = "/dev/ttyUSB0"
ELF = PHASE2 / "out" / "p2goapp-phase2.elf"
LOADER = WORK / "bin" / "loadp2"
PROFILE = ROOT / "firmware" / "p2-edge-tcxo.json"
EXPECTED = [b"P2 PHASE2 IMPORT INIT", b"P2 PHASE2 INIT", b"READY P2GO"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = PHASE2 / "hil" / (stamp + "-go-init-main")
    out.mkdir(parents=True, exist_ok=False)
    command = [str(LOADER), "-p", PORT, "-b", "115200", "-l", "115200", "-ZERO", "-v", "-t", str(ELF)]
    provenance = {
        "scope": "physical-P2-via-USB-serial",
        "mode": "phase2-go-init-main",
        "port": PORT,
        "command": command,
        "elf_sha256": sha256(ELF),
        "loader_sha256": sha256(LOADER),
        "profile_sha256": sha256(PROFILE),
        "expected_markers": [x.decode() for x in EXPECTED],
    }
    (out / "command.json").write_text(json.dumps(command, indent=2) + "\n")
    terminal = None
    lines = []
    result = dict(provenance, status="FAIL", markers=[])
    try:
        terminal = Terminal(command, out / "terminal.raw")
        deadline = time.monotonic() + 60
        index = 0
        while index < len(EXPECTED):
            line = terminal.line(deadline).strip()
            lines.append(line.decode("utf-8", "backslashreplace"))
            if line == EXPECTED[index]:
                result["markers"].append(lines[-1])
                index += 1
            elif line in EXPECTED:
                raise ProtocolError("out-of-order Go boot marker: " + repr(line))
        result["status"] = "PASS"
        result["observed_lines"] = lines
        (out / "hardware.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0
    except BaseException as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["observed_lines"] = lines
        (out / "hardware.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2), file=sys.stderr)
        return 1
    finally:
        if terminal is not None:
            terminal.close()


if __name__ == "__main__":
    raise SystemExit(main())
