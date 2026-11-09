"""Sequential before/after benchmarks; never overwrite sources or baselines."""
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
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=2)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    runner = Path(__file__).with_name('benchmark_walkthrough.py')
    checks = []
    configurations = [('gui_both', 'gui', 'ALL_CONTENT', True, args.repeats),
                      ('cli', 'cli', 'ALL_CONTENT', False, 1),
                      ('gui_romance', 'gui', 'ROMANCE_ONLY', True, 1)]
    for case, entry, profile, both, repeats in configurations:
        times = {'before': [], 'after': []}
        for index in range(repeats):
            results = {}
            # Reverse order on alternate iterations to reduce warm-cache bias.
            order = ('before', 'after') if index % 2 == 0 else ('after', 'before')
            for version in order:
                output = args.output / f'{case}_{index}_{version}'
                command = [sys.executable, '-B', str(runner), '--studio', str(getattr(args, version)),
                           '--source', str(args.source), '--output', str(output),
                           '--entry', entry, '--profile', profile]
                if both:
                    command.append('--both')
                completed = subprocess.run(command, capture_output=True, text=True, timeout=240)
                if completed.returncode:
                    raise RuntimeError(completed.stdout + completed.stderr)
                results[version] = json.loads((output / 'benchmark.json').read_text(encoding='utf-8'))
                times[version].append(results[version]['seconds'])
            equal = {key: results['before'][key] == results['after'][key]
                     for key in ('inputs', 'outputs', 'backups', 'decisions', 'both', 'stats', 'characters')}
            row = {'case': case, 'iteration': index, 'equal': equal,
                   'before_seconds': results['before']['seconds'], 'after_seconds': results['after']['seconds'],
                   'before_counts': results['before']['counts'], 'after_counts': results['after']['counts']}
            checks.append(row)
            print(json.dumps(row), flush=True)
            if not all(equal.values()):
                (args.output / 'mismatch.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
                raise AssertionError('Output/decision mismatch: inspect ' + str(args.output))
        before = statistics.median(times['before'])
        after = statistics.median(times['after'])
        print('MEDIAN', case, round(before, 3), '->', round(after, 3), 'SPEEDUP', round(before / after, 2), flush=True)
    (args.output / 'comparison.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
