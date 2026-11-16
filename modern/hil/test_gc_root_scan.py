#!/usr/bin/env python3
"""Test the actual conservative scanner against byte oracles and a guard page.

Run on Linux/WSL: python3 test_gc_root_scan.py --tinygo /path/to/tinygo
"""

import argparse
import pathlib
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tinygo", type=pathlib.Path, required=True)
    parser.add_argument("--go", default="go")
    args = parser.parse_args()
    source = (args.tinygo / "src/runtime/gc_blocks.go").read_text()
    start = source.index("func scanConservative(addr, len uintptr) {")
    scanner = source[start : source.index("\n}\n", start) + 2]
    harness = r'''
package roots

import (
    "encoding/binary"
    "syscall"
    "testing"
    "unsafe"
)

type rootSlot struct { address, value uintptr }
var roots []rootSlot
var heapStart uintptr
var metadataStart unsafe.Pointer
func markRoot(address, value uintptr) {
    if value >= heapStart && value < uintptr(metadataStart) {
        roots = append(roots, rootSlot{address, value})
    }
}

func TestGuardedScanner(t *testing.T) {
    page := syscall.Getpagesize()
    memory, err := syscall.Mmap(-1, 0, page*2, syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_PRIVATE|syscall.MAP_ANON)
    if err != nil { t.Fatal(err) }
    defer syscall.Munmap(memory)
    if err := syscall.Mprotect(memory[page:], syscall.PROT_NONE); err != nil { t.Fatal(err) }
    boundaryValues := [...]uint32{0, 0x1ffff, 0x20000, 0x20001, 0x2ffff, 0x30000, 0x30001, 0xffffffff}
    for i := 0; i < page/4; i++ { binary.LittleEndian.PutUint32(memory[i*4:i*4+4], boundaryValues[i%len(boundaryValues)]) }
    bounds := [][2]uintptr{{0, ^uintptr(0)}, {0x20000, 0x30000}, {0, 1}, {0xffffffff, 0x100000000}}
    for _, bound := range bounds {
    heapStart, metadataStart = bound[0], unsafe.Pointer(bound[1])
    for size := 0; size <= 1024; size++ {
        begin := page-size
        step, width := 1, 4
        if GOARCH != "p2" {
            step = int(unsafe.Alignof(uintptr(0)))
            width = int(unsafe.Sizeof(uintptr(0)))
            begin &^= step-1
        }
        address := uintptr(unsafe.Pointer(&memory[begin]))
        roots = nil
        scanConservative(address, uintptr(size))
        var expected []rootSlot
        for offset := begin; offset+width <= begin+size; offset += step {
            want := uintptr(binary.LittleEndian.Uint32(memory[offset:offset+4]))
            if width == 8 { want = uintptr(binary.LittleEndian.Uint64(memory[offset:offset+8])) }
            if want >= bound[0] && want < bound[1] { expected = append(expected, rootSlot{address+uintptr(offset-begin), want}) }
        }
        if len(roots) != len(expected) { t.Fatalf("range %#v size %d: got %d roots, want %d", bound, size, len(roots), len(expected)) }
        for i, root := range roots {
            if root != expected[i] { t.Fatalf("range %#v size %d root %d: got %#v, want %#v", bound, size, i, root, expected[i]) }
        }
    }
    }
}
'''
    for architecture in ("p2", "amd64"):
        with tempfile.TemporaryDirectory(prefix="tinygo-gc-roots-") as directory:
            work = pathlib.Path(directory)
            (work / "go.mod").write_text("module roots\n\ngo 1.22\n")
            (work / "roots_test.go").write_text(
                harness + f'\nconst GOARCH = "{architecture}"\n\n' + scanner + "\n"
            )
            subprocess.run([args.go, "test", "-count=1", "-v", "."], cwd=work, check=True)
        print(f"PASS {architecture}: 1,025 lengths x 4 heap ranges, exact roots, guarded upper bound")


if __name__ == "__main__":
    main()
