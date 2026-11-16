import base64
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import p2ram

from p2ram import HUB_SIZE, P2Serial, ProtocolError, read_image


def elf(segments, entry=0, machine=300):
    image = bytearray(0x200)
    ident = b"\x7fELF\x01\x01\x01" + bytes(9)
    struct.pack_into("<16sHHIIIIIHHHHHH", image, 0, ident, 2, machine, 1, entry, 52, 0, 0,
                     52, 32, len(segments), 0, 0, 0)
    for index, (offset, address, payload, memory_size) in enumerate(segments):
        struct.pack_into("<IIIIIIII", image, 52 + index * 32, 1, offset, address, address,
                         len(payload), memory_size, 7, 4)
        image[offset:offset + len(payload)] = payload
    return image


class Images(unittest.TestCase):
    def read(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.elf"
            path.write_bytes(data)
            return read_image(path)

    def test_flatten_gaps_and_keep_bss_out_of_upload(self):
        data = elf([(0x100, 0, b"boot", 8), (0x110, 16, b"data", HUB_SIZE - 16)])
        image, metadata = self.read(data)
        self.assertEqual(image, b"boot" + bytes(12) + b"data")
        self.assertEqual(metadata["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(metadata["bss_policy"], "firmware-startup")

    def test_reject_overlapping_file_segments(self):
        with self.assertRaisesRegex(ValueError, "overlapping"):
            self.read(elf([(0x100, 0, b"boot", 8), (0x110, 2, b"data", 4)]))

    def test_reject_bad_arch_and_entry(self):
        for kwargs in ({"machine": 3}, {"entry": 4}):
            with self.assertRaises(ValueError):
                self.read(elf([(0x100, 0, b"boot", 4)], **kwargs))

    def test_cli_validates_image_before_opening_serial(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "host.elf"
            path.write_bytes(elf([(0x100, 0, b"boot", 4)], machine=3))
            with mock.patch("sys.argv", ["p2ram.py", str(path)]), mock.patch("p2ram.P2Serial") as transport:
                with self.assertRaises(ValueError):
                    p2ram.main()
                transport.assert_not_called()

    def test_reject_outside_hub_and_truncated_file(self):
        for image in (elf([(0x100, 0, b"boot", HUB_SIZE + 1)]),
                      elf([(0x100, 0, b"boot", 4)])[:0x102]):
            with self.assertRaises(ValueError):
                self.read(image)


class FakeSerial:
    def reset_input_buffer(self):
        pass


class Transport(unittest.TestCase):
    def target(self, response):
        target = P2Serial.__new__(P2Serial)
        target.serial = FakeSerial()
        target.buffer = bytearray()
        target.sent = []
        target.send = target.sent.append
        target.read = lambda count=4096: response
        return target

    def test_checksum_matches_rom_word_sum_and_ack(self):
        target = self.target(b".")
        result = target.load(b"12345", encoding="hex")
        stream = b"".join(target.sent)
        payload = stream.split(b"0 0 0 0 ", 1)[1].replace(b">", b"").replace(b"?", b"")
        decoded = bytes.fromhex(payload.decode())
        self.assertEqual(decoded[:8], b"12345\0\0\0")
        total = sum(x[0] for x in struct.iter_unpack("<I", decoded)) & 0xFFFFFFFF
        self.assertEqual(total, 0x706F7250)
        self.assertEqual(result["loaded_bytes"], 8)

    def test_base64_payload_alignment_chunking_and_checksum(self):
        for length in (1, 2, 3, 4, 5, 1023, 1024, 1025, 325684):
            with self.subTest(length=length):
                source = bytes(index % 251 for index in range(length))
                target = self.target(b".")
                result = target.load(source)
                stream = b"".join(target.sent)
                self.assertTrue(stream.startswith(b"> Prop_Txt 0 0 0 0 "))
                encoded = b"".join(stream.split(b"0 0 0 0 ", 1)[1][:-1].split())
                self.assertNotIn(b"=", encoded)
                decoded = base64.b64decode(encoded + b"=" * (-len(encoded) % 4), validate=True)
                padded = source + bytes(-length % 4)
                self.assertEqual(decoded[:-4], padded)
                self.assertEqual(sum(x[0] for x in struct.iter_unpack("<I", decoded)) & 0xFFFFFFFF, 0x706F7250)
                self.assertEqual(result["load_mode"], "ROM-base64-RAM-only")

    def test_reject_checksum_error(self):
        with self.assertRaises(ProtocolError):
            self.target(b"!").load(b"1234")

    def test_late_rom_line_ending_does_not_replace_checksum_ack(self):
        target = self.target(b".")
        replies = iter([b"\r", b"\n", b"."])
        target.read = lambda count=4096: next(replies, b"")
        result = target.load(b"1234")
        self.assertEqual(result["checksum_prefix"], "\r\n")
        self.assertEqual(result["checksum_ack"], ".")

    def test_coalesced_lines_keep_unconsumed_bytes(self):
        target = self.target(b"\r\nfirst\r\nsecond\n")
        self.assertEqual(target.line(), b"first")
        self.assertEqual(target.line(), b"second")


if __name__ == "__main__":
    unittest.main()
