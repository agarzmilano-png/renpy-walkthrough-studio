"""Decoder equivalence, bounded batching, and decompile failure regressions."""
import base64
import io
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import renpy_walkthrough_studio as studio


class Base32EquivalenceTests(unittest.TestCase):
    def same_as_stdlib(self, value):
        try:
            expected = base64.b32decode(value)
        except Exception as exc:
            with self.assertRaises(type(exc)) as actual:
                studio._decode_rpyc_base32(value)
            self.assertEqual(str(actual.exception), str(exc))
        else:
            self.assertEqual(studio._decode_rpyc_base32(value), expected)

    def test_all_padding_counts_and_fast_path_boundaries(self):
        rng = random.Random(2026)
        for size in list(range(12)) + list(range(2555, 2566)) + [4096, 8192, 100001]:
            with self.subTest(size=size):
                raw = bytes(rng.randrange(256) for _ in range(size))
                encoded = base64.b32encode(raw)
                self.assertEqual(studio._decode_rpyc_base32(encoded), raw)

    def test_random_large_canonical_inputs(self):
        rng = random.Random(414)
        for _ in range(80):
            raw = bytes(rng.randrange(256) for _ in range(rng.randrange(2560, 14000)))
            self.same_as_stdlib(base64.b32encode(raw))

    def test_malformed_inputs_keep_stdlib_errors(self):
        encoded = base64.b32encode(b'x' * 2561)
        for bad in (b'0', b'1', b'a', b' ', b'\xff', b'=', b'\0', b'\n'):
            for position in (0, 100, len(encoded) // 2):
                with self.subTest(bad=bad, position=position):
                    self.same_as_stdlib(encoded[:position] + bad + encoded[position + 1:])
        for value in (encoded[:-1], encoded + b'=', b'=' * 4096, b'A' * 4096 + b'=='):
            self.same_as_stdlib(value)

    def test_unused_padding_bits_match_stdlib_not_extra_restrictions(self):
        alphabet = b'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
        for size in (2561, 2562, 2563, 2564):
            encoded = base64.b32encode(b'x' * size)
            position = len(encoded.rstrip(b'=')) - 1
            for symbol in alphabet:
                changed = encoded[:position] + bytes([symbol]) + encoded[position + 1:]
                self.same_as_stdlib(changed)

    def test_other_types_use_unchanged_stdlib_behavior(self):
        encoded = base64.b32encode(b'x' * 3000)
        for value in (encoded.decode('ascii'), bytearray(encoded), None, 10, 'Türkçe'):
            with self.subTest(type=type(value)):
                self.same_as_stdlib(value)

    def test_non_reverse_codec_is_rejected_after_small_header_read(self):
        data = b'RENPY RPC2' + struct.pack('<III', 1, 46, 500000) + b'\0' * 24 + b'x' * 500000
        reads = []
        class Tracked(io.BytesIO):
            def read(self, size=-1):
                reads.append(size)
                return super().read(size)
        with patch('builtins.open', return_value=Tracked(data)):
            self.assertIsNone(studio._convert_reverse_base32_rpyc('unused.rpyc'))
        self.assertEqual(reads, [46])


class DecompileBatchTests(unittest.TestCase):
    def test_file_count_bound_and_order(self):
        paths = [f'script{i}.rpyc' for i in range(260)]
        batches = list(studio._rpyc_decompile_batches(paths, ['python', 'unrpyc.py']))
        self.assertEqual([len(batch) for batch in batches], [128, 128, 4])
        self.assertEqual([path for batch in batches for path in batch], paths)

    def test_quoted_unicode_command_length_is_bounded(self):
        prefix = ['C:\\Program Files\\Python\\python.exe', 'unrpyc.py']
        paths = ['C:\\Türkçe klasör\\' + '😀' * 12 + 'x' * 180 + str(i) + '.rpyc' for i in range(200)]
        batches = list(studio._rpyc_decompile_batches(paths, prefix, max_command_chars=2000))
        for batch in batches:
            units = len(subprocess.list2cmdline(prefix + batch).encode('utf-16-le')) // 2
            self.assertLessEqual(units, 2000)
        self.assertEqual([path for batch in batches for path in batch], paths)

    def test_empty_work_has_no_batches(self):
        self.assertEqual(list(studio._rpyc_decompile_batches([], ['python', 'unrpyc.py'])), [])


class DecompilePipelineTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.tool = self.root / 'tool.py'
        self.tool.write_text('# test double\n', encoding='utf-8')

    def source(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'original compiled bytes')
        return path

    def decompile(self, runner, custom=None):
        with patch.object(studio, 'get_unrpyc_path', return_value=str(self.tool)), \
             patch.object(studio, 'unlock_custom_renpy_engine'), \
             patch.object(studio, 'sanitize_inline_python_recursion'), \
             patch.object(studio, 'auto_repair_decompiled_scripts'), \
             patch.object(studio, 'convert_custom_obfuscated_rpyc', return_value=custom), \
             patch.object(studio.subprocess, 'run', side_effect=runner):
            result = studio.decompile_all_rpyc_in_dir(str(self.root))
        self.assertFalse([p for p in self.root.rglob('*') if '.tmp_' in p.name])
        return result

    @staticmethod
    def completed():
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    def test_existing_sources_and_ren_py_skip_tool_resolution(self):
        self.source('a.rpyc')
        self.source('b.rpyc')
        (self.root / 'a.rpy').write_bytes(b'# User source\r\n')
        (self.root / 'b_ren.py').write_bytes(b'# User ren source\n')
        with patch.object(studio, 'get_unrpyc_path') as get_tool:
            self.assertEqual(studio.decompile_all_rpyc_in_dir(str(self.root)), 0)
        get_tool.assert_not_called()
        self.assertEqual((self.root / 'a.rpy').read_bytes(), b'# User source\r\n')
        self.assertEqual((self.root / 'b_ren.py').read_bytes(), b'# User ren source\n')

    def test_standard_failure_retries_only_missing_or_empty_outputs(self):
        for name in ('good.rpyc', 'retry.rpyc', 'broken.rpyc'):
            self.source(name)
        retries = []
        def run(command, **kwargs):
            if '--try-harder' in command:
                path = Path(command[-1])
                retries.append(path.name)
                if path.name == 'retry.rpyc':
                    path.with_suffix('.rpy').write_text('# recovered\n', encoding='utf-8')
            else:
                (self.root / 'good.rpy').write_text('# good\n', encoding='utf-8')
                (self.root / 'retry.rpy').write_bytes(b'')
                return SimpleNamespace(returncode=1, stdout='', stderr='one input failed')
            return self.completed()
        self.assertEqual(self.decompile(run), 2)
        self.assertEqual(set(retries), {'retry.rpyc', 'broken.rpyc'})

    def test_custom_timeout_keeps_completed_output_and_cleans_owned_temps(self):
        original = self.source('a.rpyc')
        def run(command, **kwargs):
            Path(command[-1][:-1]).write_text('# partial batch success\n', encoding='utf-8')
            raise subprocess.TimeoutExpired(command, kwargs['timeout'])
        self.assertEqual(self.decompile(run, custom=b'normalized'), 1)
        self.assertEqual((self.root / 'a.rpy').read_text(), '# partial batch success\n')
        self.assertEqual(original.read_bytes(), b'original compiled bytes')

    def test_concurrent_custom_source_is_never_overwritten(self):
        self.source('a.rpyc')
        def run(command, **kwargs):
            Path(command[-1][:-1]).write_text('# generated\n', encoding='utf-8')
            (self.root / 'a.rpy').write_bytes(b'# concurrent user edit\r\n')
            return self.completed()
        self.assertEqual(self.decompile(run, custom=b'normalized'), 0)
        self.assertEqual((self.root / 'a.rpy').read_bytes(), b'# concurrent user edit\r\n')

    def test_empty_custom_output_is_not_counted(self):
        self.source('a.rpyc')
        def run(command, **kwargs):
            Path(command[-1][:-1]).write_bytes(b'')
            return self.completed()
        self.assertEqual(self.decompile(run, custom=b'normalized'), 0)
        self.assertFalse((self.root / 'a.rpy').exists())

    def test_timeout_budget_scales_with_original_fifty_file_batches(self):
        for index in range(60):
            self.source(f'{index:03}.rpyc')
        timeouts = []
        def run(command, **kwargs):
            timeouts.append(kwargs['timeout'])
            for path in command[2:]:
                Path(path[:-1]).write_text('# generated\n', encoding='utf-8')
            return self.completed()
        self.assertEqual(self.decompile(run, custom=b'normalized'), 60)
        self.assertEqual(timeouts, [360])

    def test_publish_refuses_existing_destination(self):
        temporary = self.root / 'source.tmp'
        destination = self.root / 'source.rpy'
        temporary.write_bytes(b'new')
        destination.write_bytes(b'user')
        self.assertFalse(studio._publish_decompiled_source(str(temporary), str(destination)))
        self.assertEqual(destination.read_bytes(), b'user')
        self.assertEqual(temporary.read_bytes(), b'new')


if __name__ == '__main__':
    unittest.main()
