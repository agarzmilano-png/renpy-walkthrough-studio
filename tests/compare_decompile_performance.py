"""Sequential isolated-copy decompiler benchmarks with strict output comparison."""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--reverse', type=Path, required=True)
    parser.add_argument('--standard', type=Path, required=True)
    parser.add_argument('--mixed', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=2)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    runner = Path(__file__).with_name('benchmark_decompile.py')
    cases = [('reverse', args.reverse, 'none', args.repeats),
             ('standard', args.standard, 'none', args.repeats),
             ('mixed', args.mixed, 'none', 1),
             ('partial', args.reverse, 'partial', 1),
             ('existing', args.reverse, 'all', 1)]
    rows = []
    for case, source, existing, repeats in cases:
        for iteration in range(repeats):
            results = {}
            order = ('before', 'after') if iteration % 2 == 0 else ('after', 'before')
            for version in order:
                output = args.output / f'{case}_{iteration}_{version}'
                command = [sys.executable, '-B', str(runner), '--studio', str(getattr(args, version)),
                           '--source', str(source), '--output', str(output), '--existing', existing]
                completed = subprocess.run(command, capture_output=True, text=True, timeout=240)
                if completed.returncode:
                    raise RuntimeError(completed.stdout + completed.stderr)
                results[version] = json.loads((output / 'benchmark.json').read_text(encoding='utf-8'))
            equal = {key: results['before'][key] == results['after'][key]
                     for key in ('count', 'inputs', 'remaining_inputs', 'removed_inputs',
                                 'outputs', 'existing', 'existing_unchanged', 'temporary_files')}
            row = {'case': case, 'iteration': iteration, 'equal': equal,
                   'before_seconds': results['before']['seconds'], 'after_seconds': results['after']['seconds'],
                   'before_subprocesses': len(results['before']['subprocesses']),
                   'after_subprocesses': len(results['after']['subprocesses']),
                   'before_app_sha256': results['before']['app_sha256'],
                   'after_app_sha256': results['after']['app_sha256']}
            rows.append(row)
            print(json.dumps(row), flush=True)
            if not all(equal.values()):
                (args.output / 'mismatch.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
                raise AssertionError('Output/failure-state mismatch: ' + str(args.output))
        selected = [row for row in rows if row['case'] == case]
        before = statistics.median(row['before_seconds'] for row in selected)
        after = statistics.median(row['after_seconds'] for row in selected)
        print('MEDIAN', case, round(before, 4), '->', round(after, 4),
              'SPEEDUP', round(before / after, 2), flush=True)
    (args.output / 'comparison.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
