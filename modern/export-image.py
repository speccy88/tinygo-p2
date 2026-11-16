#!/usr/bin/env python3
"""Export a native P2 ELF to a flat, long-aligned RAM/flash/SD boot image."""
import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "hil"))
from p2ram import read_image


def export(source: Path, destination: Path) -> bytes:
    data, metadata = read_image(source)
    if metadata["format"] != "elf32-p2":
        raise ValueError("input must be a native P2 ELF, not a renamed binary")
    data += bytes(-len(data) % 4)
    # The ROM's SD boot path reserves the top 16 KiB of hub RAM.
    if len(data) > 496 * 1024:
        raise ValueError("image exceeds the 496 KiB SD boot limit")
    if source.resolve() == destination.resolve():
        raise ValueError("input and output paths must be different")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    data = export(args.source, args.destination)
    print(f"{args.destination}: {len(data)} bytes; sha256 {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
