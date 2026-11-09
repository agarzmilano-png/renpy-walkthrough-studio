"""Benchmark RPYC decompilation only on new copies, never on --source.

--tool-only uses already-standard RPYC inputs to measure worker/batch startup.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import struct
import time
import zlib


def hashes(root, pattern):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob(pattern)) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--existing', choices=('none', 'partial', 'all'), default='none')
    parser.add_argument('--existing-source', type=Path)
    parser.add_argument('--tool-only', action='store_true')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--batch-size', type=int, default=128)
    parser.add_argument('--broken', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    game = args.output.resolve() / 'game'
    game.mkdir()
    paths = []
    for index, path in enumerate(sorted(args.source.rglob('*.rpyc'))):
        relative = path.relative_to(args.source)
        destination = game / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        paths.append(destination)
        if args.existing == 'all' or args.existing == 'partial' and index % 4 == 0:
            if args.existing_source:
                source = args.existing_source / str(relative)[:-1]
                shutil.copy2(source, str(destination)[:-1])
            else:
                Path(str(destination)[:-1]).write_text('# Existing user source: preserve verbatim\n', encoding='utf-8')
    if args.broken:
        (game / 'invalid.rpyc').write_bytes(b'not a compiled script')
        (game / 'empty.rpyc').write_bytes(b'')
        compressed = zlib.compress(b'not a pickle')
        (game / 'bad_pickle.rpyc').write_bytes(
            b'RENPY RPC2' + struct.pack('<III', 1, 34, len(compressed)) + b'\0' * 12 + compressed)
    before = hashes(game, '*.rpyc')
    existing = hashes(game, '*.rpy')
    spec = importlib.util.spec_from_file_location('renpy_walkthrough_studio', args.studio)
    studio = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = studio
    spec.loader.exec_module(studio)
    original_run = subprocess.run
    calls = []
    timings = Counter()
    counts = Counter()
    logs = []

    def run(command, *positional, **kwargs):
        started = time.perf_counter()
        record = {'command': [str(arg) for arg in command], 'timeout': kwargs.get('timeout')}
        try:
            result = original_run(command, *positional, **kwargs)
            record.update(returncode=result.returncode,
                          stdout=result.stdout, stderr=result.stderr)
            return result
        finally:
            record['seconds'] = time.perf_counter() - started
            calls.append(record)
    studio.subprocess.run = run

    def measure(name):
        original = getattr(studio, name)
        def wrapped(*positional, **kwargs):
            started = time.perf_counter()
            counts[name] += 1
            try:
                return original(*positional, **kwargs)
            finally:
                timings[name] += time.perf_counter() - started
        setattr(studio, name, wrapped)
    for name in ('convert_custom_obfuscated_rpyc', 'unlock_custom_renpy_engine',
                 'auto_repair_decompiled_scripts', 'sanitize_inline_python_recursion', 'get_unrpyc_path'):
        measure(name)
    started = time.perf_counter()
    if args.tool_only:
        tool = studio.get_unrpyc_path(log_callback=logs.append)
        for index in range(0, len(paths), args.batch_size):
            completed = run([sys.executable, tool, '-p', str(args.workers)] +
                            [str(path) for path in paths[index:index + args.batch_size]],
                            capture_output=True, text=True, timeout=180)
            assert completed.returncode == 0, completed.stderr
        count = len(hashes(game, '*.rpy'))
    else:
        count = studio.decompile_all_rpyc_in_dir(str(game), log_callback=logs.append)
    elapsed = time.perf_counter() - started
    after = hashes(game, '*.rpyc')
    outputs = hashes(game, '*.rpy')
    payload = {'seconds': elapsed, 'count': count, 'inputs': before, 'inputs_unchanged': before == after,
               'remaining_inputs': after, 'removed_inputs': sorted(set(before) - set(after)),
               'retained_inputs_unchanged': all(before.get(path) == digest for path, digest in after.items()),
               'existing': existing, 'existing_unchanged': all(outputs.get(path) == digest for path, digest in existing.items()),
               'outputs': outputs, 'timings': dict(timings), 'counts': dict(counts),
               'subprocesses': calls, 'logs': logs,
               'app_sha256': hashlib.sha256(args.studio.read_bytes()).hexdigest(),
               'temporary_files': [str(p.relative_to(game)) for p in game.rglob('*') if '.tmp_' in p.name]}
    (args.output / 'benchmark.json').write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding='utf-8')
    print(json.dumps({key: payload[key] for key in ('seconds', 'count', 'inputs_unchanged', 'existing_unchanged',
                                                  'timings', 'counts', 'temporary_files')}, indent=2), flush=True)
    print('SUBPROCESS_COUNT', len(calls), 'SUBPROCESS_SECONDS', round(sum(c['seconds'] for c in calls), 3), flush=True)
    # Existing post-repair behavior removes two stale RPYC caches in this corpus.
    # Record removals for before/after comparison; never allow altered RPYC bytes.
    assert payload['retained_inputs_unchanged'] and payload['existing_unchanged']


if __name__ == '__main__':
    main()
