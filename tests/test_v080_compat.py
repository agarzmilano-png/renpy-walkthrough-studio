"""Side-effect-free codec and localized existing-mod regressions."""
import base64
import os
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import renpy_walkthrough_studio as studio


class CompatibilityTests(unittest.TestCase):
    def test_localized_markers(self):
        for caption in ('Mod: Both', 'Mod: All', 'Mod: İkiside',
                        '[gr]Mod: Her İkiside', 'Mod: İkisi de',
                        '{wt_best}Mod: Both{/wt_best}'):
            with self.subTest(caption=caption):
                self.assertTrue(studio.has_existing_both_marker(caption))
        for caption in ('Both scenes', 'Mod: Ally', 'Mod: Brotherhood', 'İkiside'):
            self.assertFalse(studio.has_existing_both_marker(caption))

    def make_codec(self):
        raw = [b'\x80\x02N.', b'\x80\x02K\x01.']
        payloads = [zlib.compress(base64.b32encode(p))[::-1] for p in raw]
        result = bytearray(b'RENPY RPC2')
        offset = 46
        for slot, payload in enumerate(payloads, 1):
            result.extend(struct.pack('<III', slot, offset + 91, len(payload)))
            offset += len(payload)
        result.extend(b'\0' * 12)
        return bytes(result) + b''.join(payloads), raw

    def convert(self, data, **kwargs):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'test.rpyc')
            with open(path, 'wb') as f:
                f.write(data)
            result = studio._convert_reverse_base32_rpyc(path, **kwargs)
            with open(path, 'rb') as f:
                self.assertEqual(f.read(), data)
            return result

    def test_codec_slots_and_public_entry(self):
        data, raw = self.make_codec()
        result = self.convert(data)
        self.assertIsNotNone(result)
        for index, expected in enumerate(raw):
            slot, start, length = struct.unpack_from('<III', result, 10 + index * 12)
            self.assertEqual(slot, index + 1)
            self.assertEqual(zlib.decompress(result[start:start + length]), expected)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'test.rpyc')
            with open(path, 'wb') as f:
                f.write(data)
            self.assertEqual(studio.convert_custom_obfuscated_rpyc(path), result)
            with open(path, 'wb') as f:
                f.write(result)
            self.assertIsNone(studio.convert_custom_obfuscated_rpyc(path))

    def test_codec_rejects_bad_bounds_and_budget(self):
        data, _ = self.make_codec()
        self.assertIsNone(self.convert(data, max_bytes=8))
        self.assertIsNone(self.convert(data[:-1]))
        broken = bytearray(data)
        struct.pack_into('<I', broken, 14, 138)
        self.assertIsNone(self.convert(broken))


if __name__ == '__main__':
    unittest.main()
