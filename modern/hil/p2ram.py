#!/usr/bin/env python3
"""Portable P2 ROM RAM loader and serial transport (never writes SPI flash).

Protocol reference: totalspectrum/loadp2, loadfilesingle/checkp2_and_init,
commit c20afedd4253d09da449fa740f8d4304481fc560. This implementation sends
ELF PT_LOAD file contents; the firmware startup must initialize its own BSS.
All serial operations share one open handle so capture does not reset the P2.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None  # Image conversion works without the optional serial package.

HUB_SIZE = 512 * 1024


class ProtocolError(RuntimeError):
    pass


def read_image(path: Path) -> tuple[bytes, dict]:
    """Flatten an ELF32 little-endian P2 load image; reject unsafe layouts."""
    source = path.read_bytes()
    metadata = {"file": str(path.resolve()), "sha256": hashlib.sha256(source).hexdigest()}
    if not source.startswith(b"\x7fELF"):
        if not source or len(source) > HUB_SIZE - 4:
            raise ValueError("raw image is empty or exceeds hub RAM")
        return source, dict(metadata, format="binary", file_bytes=len(source))
    if len(source) < 52 or source[4:7] != b"\x01\x01\x01":
        raise ValueError("requires ELF32 little-endian version 1")
    hdr = struct.unpack_from("<16sHHIIIIIHHHHHH", source)
    _, elf_type, machine, _, entry, phoff, _, _, _, phentsize, phnum, *_ = hdr
    if elf_type != 2 or machine != 300 or entry != 0 or phentsize != 32:
        raise ValueError("requires executable P2 ELF, entry address 0, 32-byte program headers")
    if phoff + phnum * phentsize > len(source):
        raise ValueError("truncated ELF program headers")
    segments = []
    high = 0
    for index in range(phnum):
        kind, offset, vaddr, paddr, filesz, memsz, flags, alignment = struct.unpack_from(
            "<IIIIIIII", source, phoff + index * phentsize
        )
        if kind != 1:
            continue
        if filesz > memsz or offset + filesz > len(source) or paddr + memsz > HUB_SIZE:
            raise ValueError("invalid/truncated PT_LOAD or segment outside P2 hub RAM")
        if filesz:
            for previous in segments:
                if paddr < previous["address"] + previous["file_bytes"] and previous["address"] < paddr + filesz:
                    raise ValueError("overlapping PT_LOAD file ranges")
            high = max(high, paddr + filesz)
        segments.append({"offset": offset, "address": paddr, "file_bytes": filesz, "memory_bytes": memsz})
    if not segments or not high or not any(s["address"] == 0 and s["file_bytes"] for s in segments):
        raise ValueError("ELF has no loadable reset image at address zero")
    if high > HUB_SIZE - 4:
        raise ValueError("no room for ROM checksum word")
    image = bytearray(high)
    for segment in segments:
        start, length = segment["address"], segment["file_bytes"]
        image[start:start + length] = source[segment["offset"]:segment["offset"] + length]
    return bytes(image), dict(metadata, format="elf32-p2", file_bytes=high, segments=segments,
                              bss_policy="firmware-startup")


class P2Serial:
    def __init__(self, port: str, baud: int = 115200, raw_log: Path | None = None):
        if serial is None:
            raise RuntimeError("Install pyserial first: python -m pip install pyserial==3.5")
        self.serial = serial.Serial(port=None, baudrate=baud, timeout=.05, write_timeout=5)
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.port = port
        self.serial.open()
        self.buffer = bytearray()
        self.raw = raw_log.open("wb") if raw_log else None
        self.port_info = next((dict(device=p.device, description=p.description, hwid=p.hwid)
                               for p in list_ports.comports() if p.device.lower() == port.lower()), {})

    def close(self):
        self.serial.close()
        if self.raw:
            self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def send(self, data: bytes):
        if self.serial.write(data) != len(data):
            raise ProtocolError("short serial write")
        self.serial.flush()

    def read(self, count=4096) -> bytes:
        data = self.serial.read(min(count, max(1, self.serial.in_waiting)))
        if self.raw and data:
            self.raw.write(data)
            self.raw.flush()
        return data

    def line(self, timeout: float = 10) -> bytes:
        deadline = time.monotonic() + timeout
        while True:
            for index, value in enumerate(self.buffer):
                if value in (10, 13):
                    line = bytes(self.buffer[:index])
                    del self.buffer[:index + 1]
                    if line:
                        return line
                    break
            else:
                if time.monotonic() >= deadline:
                    raise ProtocolError("timeout waiting for output; buffered=" + repr(bytes(self.buffer)))
                self.buffer.extend(self.read())
                if len(self.buffer) > 65536:
                    raise ProtocolError("unterminated output exceeds 64 KiB")

    def identify(self) -> str:
        self.serial.dtr = True
        time.sleep(.002)
        self.serial.dtr = False
        time.sleep(.025)
        self.serial.reset_input_buffer()
        self.buffer.clear()
        for _ in range(3):
            self.send(b"> Prop_Chk 0 0 0 0  ")
            try:
                line = self.line(.4)
            except ProtocolError:
                continue
            if line.startswith(b"Prop_Ver ") and len(line) == 10:
                return line.decode("ascii")
        raise ProtocolError("P2 ROM identification failed")

    def load(self, image: bytes, encoding: str = "base64") -> dict:
        if not image or len(image) > HUB_SIZE - 4:
            raise ValueError("RAM image is empty or too large")
        if encoding not in ("base64", "hex"):
            raise ValueError("RAM encoding must be base64 or hex")
        image += bytes((-len(image)) % 4)
        checksum = (0x706F7250 - sum(word[0] for word in struct.iter_unpack("<I", image))) & 0xFFFFFFFF
        self.buffer.clear()
        self.serial.reset_input_buffer()
        if encoding == "base64":
            self.send(b"> Prop_Txt 0 0 0 0 ")
            encoded = base64.b64encode(image + struct.pack("<I", checksum)).rstrip(b"=")
            for offset in range(0, len(encoded), 1024):
                self.send(encoded[offset:offset + 1024] + b"\n")
            self.send(b" ?")
        else:
            self.send(b"> Prop_Hex 0 0 0 0 ")
            for offset in range(0, len(image), 128):
                block = image[offset:offset + 128]
                self.send(b" " + block.hex(" ").encode("ascii") + b" > ")
            self.send(b" " + struct.pack("<I", checksum).hex(" ").encode("ascii") + b"?")
        deadline = time.monotonic() + 2
        reply = b""
        prefix = bytearray()
        while time.monotonic() < deadline:
            reply = self.read(1)
            if reply in (b"\r", b"\n", b" ", b"\t") and len(prefix) < 64:
                prefix.extend(reply)
                continue
            if reply:
                break
        if reply != b".":
            raise ProtocolError("ROM download checksum failed: " + repr(reply))
        return {"loaded_bytes": len(image), "checksum": f"{checksum:08x}", "checksum_ack": ".",
                "checksum_prefix": prefix.decode("ascii"),
                "load_mode": f"ROM-{encoding}-RAM-only"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?", type=Path)
    parser.add_argument("--port", default="COM12")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--encoding", choices=("base64", "hex"), default="base64")
    parser.add_argument("--expect", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--monitor", type=float, default=0, metavar="SECONDS")
    args = parser.parse_args()
    if not 0 <= args.monitor <= 3600:
        parser.error("--monitor must be between 0 and 3600 seconds")
    if args.monitor and not args.image:
        parser.error("--monitor requires an image to load")
    prepared = read_image(args.image) if args.image else None
    with P2Serial(args.port, args.baud) as target:
        result = {"port": target.port_info, "rom": target.identify()}
        if prepared:
            data, metadata = prepared
            result["image"] = metadata
            result["download"] = target.load(data, encoding=args.encoding)
            result["output"] = []
            for expected in args.expect:
                observed = target.line(args.timeout).decode("utf-8", "backslashreplace")
                result["output"].append(observed)
                if observed != expected:
                    raise ProtocolError(f"expected {expected!r}; received {observed!r}")
        print(json.dumps(result, indent=2), flush=True)
        if args.monitor:
            if target.buffer:
                sys.stdout.buffer.write(target.buffer)
                target.buffer.clear()
            deadline = time.monotonic() + args.monitor
            while time.monotonic() < deadline:
                sys.stdout.buffer.write(target.read())
                sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
