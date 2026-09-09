"""Independent read-only replay of recorded P2 hardware evidence.

Does not open a serial port, import the supplied oracle, or generate fixtures.
A valid replay checks recorded evidence; it does not itself prove physical origin.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

MASK = (1 << 32) - 1
EDGES = [(0, 0), (1, 2), (MASK, 1), (MASK, MASK),
         (0x7fffffff, 1), (0x80000000, 0x80000000), (0, MASK),
         (0x12345678, 0x87654321), (0xaaaaaaaa, 0x55555555), (7, 3)]
REPLY = re.compile(rb"R ([CG]) ([0-9a-fA-F]{8}) ([0-9a-fA-F]{8}) ([0-9a-fA-F]{8})")
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def expected(a, b):
    xor = a ^ b
    rotation = ((xor * 32) | (xor // (1 << 27))) & MASK
    return (a + b) & MASK, (rotation + a - b) & MASK


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_run(directory):
    errors = []

    def require(condition, reason):
        if not condition:
            errors.append(reason)

    transport = json.loads((directory / "transport.json").read_text())
    hardware_path = directory / "hardware.json"
    hardware = json.loads(hardware_path.read_text()) if hardware_path.is_file() else {}
    vectors = json.loads((directory / "vectors.json").read_text())
    command = json.loads((directory / "command.json").read_text())
    raw = (directory / "terminal.raw").read_bytes()
    response_path = directory / "responses.jsonl"
    responses = [json.loads(line) for line in response_path.read_text().splitlines() if line] if response_path.is_file() else []
    mode = transport["expected_mode"]
    require(mode in ("C", "G"), "invalid mode")
    require(len(vectors) >= len(EDGES) + 128, "fewer than edge cases + 128 random pairs")
    require([(v["a"], v["b"]) for v in vectors[:len(EDGES)]] == EDGES, "edge sequence mismatch")
    require(len({v["id"] for v in vectors}) == len(vectors), "duplicate request nonce")
    for v in vectors:
        require(all(isinstance(v[k], int) and 0 <= v[k] <= MASK for k in ("id", "a", "b", "sum", "mix")), "non-word vector field")
        require((v["sum"], v["mix"]) == expected(v["a"], v["b"]), "supplied vector oracle mismatch")
    require(command and Path(command[0]).name == "loadp2", "not a loadp2 invocation")
    require(not any(x in command for x in ("-9", "-PATCH")), "forbidden loader option")
    require(not any("@" in x or "," in x or "flash" in x.lower() for x in command), "unexpected multi-file/address/flash command")
    for flag, value in (("-p", "/dev/ttyUSB0"), ("-b", "115200"), ("-l", "115200")):
        require(command.count(flag) == 1, "missing/duplicate " + flag)
        if flag in command:
            i = command.index(flag)
            require(i + 1 < len(command) and command[i + 1] == value, "unexpected value for " + flag)
    require(all(flag in command for flag in ("-ZERO", "-v", "-t")), "RAM/verbose/terminal flags missing")
    require(Path(command[-1]).suffix == ".elf", "loader did not receive ELF")
    raw_lines = [line.strip() for line in raw.splitlines()]
    raw_responses = []
    for line in raw_lines:
        match = REPLY.fullmatch(line)
        if match:
            raw_responses.append({"mode": match[1].decode(), "id": int(match[2], 16),
                                  "sum": int(match[3], 16), "mix": int(match[4], 16)})
    require(transport["passed"] == len(responses), "transport passed count differs from response JSONL")
    require(transport["total"] == len(vectors), "transport total differs from vectors")
    for i, response in enumerate(responses):
        require(i < len(vectors), "excess response JSONL")
        if i >= len(vectors):
            continue
        v = vectors[i]
        require(response == {"mode": mode, "id": v["id"], "sum": v["sum"], "mix": v["mix"]}, "JSONL nonce/order/result mismatch")
        require(i < len(raw_responses) and raw_responses[i] == response, "JSONL differs from raw serial record")
    mismatches = []
    for i, response in enumerate(raw_responses):
        if i >= len(vectors):
            mismatches.append({"index": i, "error": "extra raw response"})
            continue
        v = vectors[i]
        wanted = {"mode": mode, "id": v["id"], "sum": v["sum"], "mix": v["mix"]}
        if response != wanted:
            mismatches.append({"index": i, "observed": response, "expected": wanted})
    for key in ("elf_sha256", "loader_sha256", "profile_sha256"):
        # These are replay identities, not a claim that replay recreated bytes.
        # A missing/empty/noncanonical value must never collapse to a shared None.
        require(isinstance(hardware.get(key), str) and DIGEST.fullmatch(hardware[key]),
                "missing or noncanonical " + key)
    if transport["status"] == "PASS":
        require(hardware.get("status") == "PASS", "missing physical PASS metadata")
        require(hardware.get("scope") == "physical-P2-via-USB-serial", "wrong physical scope")
        require(hardware.get("port") == "/dev/ttyUSB0", "wrong physical port")
        require(hardware.get("mode") == ("c" if mode == "C" else "go"), "physical mode mismatch")
        require(hardware.get("passed") == len(vectors) == hardware.get("total"), "hardware counts mismatch")
        require(len(responses) == len(vectors) == len(raw_responses), "PASS missing/extra raw responses")
        require(not mismatches, "PASS contains wrong arithmetic")
        require(f"READY {mode} 1".encode() in raw_lines, "missing actual READY line")
        require(any(re.search(rb"chksum: [0-9a-fA-F]+ OK", line) or b"Checksum validated" in line for line in raw_lines), "missing loader checksum success")
        require(not any(line.startswith((b"ERR ", b"ERROR:")) for line in raw_lines), "PASS raw log contains errors")
    return {
        "directory": str(directory), "declared_status": transport["status"], "mode": mode,
        "vectors": len(vectors), "jsonl_responses": len(responses), "raw_responses": len(raw_responses),
        "raw_sha256": sha(directory / "terminal.raw"), "vectors_sha256": sha(directory / "vectors.json"),
        "elf_sha256": hardware.get("elf_sha256"), "loader_sha256": hardware.get("loader_sha256"),
        "profile_sha256": hardware.get("profile_sha256"), "errors": errors,
        "actual_arithmetic_mismatches": mismatches,
        "random_input_digest": hashlib.sha256(json.dumps([(v["id"], v["a"], v["b"]) for v in vectors[len(EDGES):]]).encode()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--require-full", action="store_true")
    args = parser.parse_args()
    runs = []
    for path in sorted((args.root / ".work" / "hil").glob("*/transport.json")):
        try:
            runs.append(inspect_run(path.parent))
        except Exception as exc:
            runs.append({"directory": str(path.parent), "errors": [f"{type(exc).__name__}: {exc}"]})
    passed = [r for r in runs if r.get("declared_status") == "PASS" and not r["errors"]]
    c_runs = [r for r in passed if r["mode"] == "C"]
    go_runs = [r for r in passed if r["mode"] == "G"]
    checks = {
        "all_available_records_consistent": all(not r["errors"] for r in runs),
        "physical_c_baseline": bool(c_runs),
        "three_fresh_go_downloads": len(go_runs) >= 3 and len({r["random_input_digest"] for r in go_runs}) == len(go_runs),
        "shared_go_image": bool(go_runs) and len({r["elf_sha256"] for r in go_runs}) == 1,
        "shared_loader_and_profile": bool(passed) and len({r["loader_sha256"] for r in passed}) == 1 and len({r["profile_sha256"] for r in passed}) == 1,
    }
    result = {"scope": "independent-offline-replay-NOT-new-hardware-execution",
              "recorded_runs": len(runs), "c_passes": len(c_runs), "go_passes": len(go_runs),
              "checks": checks, "runs": runs}
    print(json.dumps(result, indent=2))
    return 0 if (all(checks.values()) if args.require_full else checks["all_available_records_consistent"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
