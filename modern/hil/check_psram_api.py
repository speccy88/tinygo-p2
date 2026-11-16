#!/usr/bin/env python3
"""Run the actual PSRAM Go API on a host with mocked raw pin transactions.

Only target tags, external declarations, and interrupt imports are adapted in
a disposable copy. This checks API error counts and byte preservation; it is
not a hardware, timing, scheduler, or PSRAM electrical test.
"""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

MOCKS = r'''
package machine

import "unsafe"

var mockWords [8]uint32
var mockReads, mockWrites, mockFailRead, mockFailWrite int
var mockTicks uint32 = 100

func CPUFrequency() uint32 { return 160000000 }
func AssignCore(int) {}
func psramInit(ids *uint32) {
    view := unsafe.Slice(ids, 8)
    view[0], view[1] = 0x0d0d0d0d, 0x5d5d5d5d
}
func psramReadWord(address uint32) uint64 {
    mockReads++
    ticks := mockTicks
    if mockReads == mockFailRead { ticks = 1280 }
    return uint64(ticks)<<32 | uint64(mockWords[address])
}
func psramWriteWord(address, word uint32) uint32 {
    mockWrites++
    mockWords[address] = word
    if mockWrites == mockFailWrite { return 1280 }
    return mockTicks
}
'''

TESTS = r'''
package machine

import (
    "bytes"
    "testing"
)

func setup(t *testing.T) *psramDevice {
    mockWords = [8]uint32{0x04030201, 0x08070605, 0x0c0b0a09}
    mockReads, mockWrites, mockFailRead, mockFailWrite = 0, 0, 0, 0
    mockTicks = 100
    p := new(psramDevice)
    t.Cleanup(func() { if p.requests != nil { close(p.requests) } })
    return p
}

func TestReadReportsCompletedPrefix(t *testing.T) {
    p := setup(t)
    mockFailRead = 2
    buffer := bytes.Repeat([]byte{0xcc}, 9)
    n, err := p.ReadAt(buffer, 1)
    if n != 3 || err != ErrPSRAMTiming { t.Fatalf("got (%d, %v)", n, err) }
    if !bytes.Equal(buffer, []byte{2,3,4,0xcc,0xcc,0xcc,0xcc,0xcc,0xcc}) {
        t.Fatalf("read modified unconfirmed bytes: %x", buffer)
    }
}

func TestWriteReportsCompletedPrefix(t *testing.T) {
    p := setup(t)
    mockFailWrite = 2
    n, err := p.WriteAt([]byte{10,11,12,13,14,15,16,17,18}, 1)
    if n != 3 || err != ErrPSRAMTiming { t.Fatalf("got (%d, %v)", n, err) }
    if mockWords[0] != 0x0c0b0a01 { t.Fatalf("first word/guard mismatch: %x", mockWords[0]) }
}

func TestRMWReadFailureDoesNotWrite(t *testing.T) {
    p := setup(t)
    mockFailRead = 1
    n, err := p.WriteAt([]byte{10,11}, 1)
    if n != 0 || err != ErrPSRAMTiming || mockWrites != 0 { t.Fatalf("(%d,%v), writes=%d", n, err, mockWrites) }
}

func TestUnalignedRoundtripPreservesNeighbors(t *testing.T) {
    p := setup(t)
    want := []byte{10,11,12,13,14,15,16,17,18}
    n, err := p.WriteAt(want, 1)
    if n != 9 || err != nil { t.Fatalf("write (%d,%v)", n, err) }
    got := make([]byte, 9)
    n, err = p.ReadAt(got, 1)
    if n != 9 || err != nil || !bytes.Equal(got, want) { t.Fatalf("read (%d,%v) %x", n, err, got) }
    if mockWords[0]&0xff != 1 || mockWords[2]&0xffff0000 != 0x0c0b0000 { t.Fatal("neighbor changed") }
}

func TestBoundsRejectWithoutAccess(t *testing.T) {
    p := setup(t)
    for _, offset := range []int64{-1, PSRAMSize, PSRAMSize+1, 1<<62} {
        n, err := p.ReadAt(make([]byte, 1), offset)
        if n != 0 || err != ErrPSRAMBounds { t.Fatalf("offset %d got (%d,%v)", offset, n, err) }
    }
    if mockReads != 0 || mockWrites != 0 { t.Fatal("out-of-range request touched raw driver") }
    n, err := p.ReadAt(nil, PSRAMSize)
    if n != 0 || err != nil { t.Fatalf("empty end read (%d,%v)", n, err) }
}

func TestTimingLimitIsExclusive(t *testing.T) {
    p := setup(t)
    mockTicks = 1279
    if n, err := p.ReadAt(make([]byte, 4), 0); n != 4 || err != nil { t.Fatalf("1279 cycles: (%d,%v)", n, err) }
    mockTicks = 1280
    if n, err := p.ReadAt(make([]byte, 4), 0); n != 0 || err != ErrPSRAMTiming { t.Fatalf("1280 cycles: (%d,%v)", n, err) }
    if p.MaxTransactionCycles() != 1280 { t.Fatal("failed duration not recorded") }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tinygo-root", required=True, type=Path)
    parser.add_argument("--go", default="go")
    args = parser.parse_args()
    source = (args.tinygo_root / "src/machine/machine_p2_psram.go").read_text()
    source = re.sub(r"^//go:build .*\n", "", source, count=1)
    source = source.replace('"runtime/interrupt"', '"p2-api-check/interrupt"')
    for function in ("psramInit", "psramReadWord", "psramWriteWord"):
        source, count = re.subn(r"//export \w+\nfunc " + function + r"\([^\n]+\n", "", source)
        if count != 1:
            raise RuntimeError("raw declaration changed: " + function)
    with tempfile.TemporaryDirectory(prefix="p2-psram-api-") as directory:
        root = Path(directory)
        (root / "go.mod").write_text("module p2-api-check\n\ngo 1.25.0\n")
        (root / "psram.go").write_text(source)
        (root / "raw_mock.go").write_text(MOCKS)
        (root / "psram_test.go").write_text(TESTS)
        (root / "interrupt").mkdir()
        (root / "interrupt/interrupt.go").write_text(
            "package interrupt\ntype State uintptr\nfunc Disable() State { return 0 }\nfunc Restore(State) {}\n"
        )
        return subprocess.run([args.go, "test", "-count=1", "-v", "."], cwd=root).returncode


if __name__ == "__main__":
    raise SystemExit(main())
