"""Run isolated Both/All fixtures against explicitly supplied local engines.

Example: python tests/run_native_matrix.py --engine v813=PATH --engine v853=PATH --output NEW_DIRECTORY
No downloads or game-directory writes; all fixtures use new private copies.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', action='append', required=True, metavar='NAME=PATH')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fixtures', nargs='+', choices=('route', 'calls', 'timed', 'all', 'narrative'),
                        default=['route', 'calls', 'timed', 'all', 'narrative'])
    args = parser.parse_args()
    engines = {}
    for specification in args.engine:
        name, separator, location = specification.partition('=')
        if not separator or not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
            parser.error('Engine must be NAME=PATH; NAME uses letters, digits, _ or -')
        if name in engines or not Path(location).is_dir():
            parser.error('Duplicate engine name or missing directory: ' + specification)
        engines[name] = Path(location).resolve()
    args.output.mkdir(exist_ok=False, parents=True)
    rows = []
    for name, engine in engines.items():
        for fixture in args.fixtures:
            output = args.output.resolve() / (name + '_' + fixture)
            command = [sys.executable, '-B', str(Path(__file__).with_name('run_native_both_validation.py')),
                       '--engine', str(engine), '--fixture', fixture, '--output', str(output)]
            completed = subprocess.run(command, timeout=600)
            summary = output / 'validation_summary.json'
            data = json.loads(summary.read_text(encoding='utf-8')) if summary.exists() else {}
            cases = data.get('results', [])
            passed = completed.returncode == 0 and len(cases) == 12 and all(c['passed'] for c in cases)
            rows.append({'engine': name, 'engine_path': str(engine), 'fixture': fixture,
                         'passed': passed, 'returncode': completed.returncode,
                         'native_versions': sorted({c.get('engine', '') for c in cases}),
                         'passed_cases': len(cases) if passed else 0, 'summary': str(summary)})
            (args.output / 'matrix_summary.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    count = sum(row['passed_cases'] for row in rows)
    print('NATIVE_MATRIX', count, 'PASSED;', len(rows), 'FIXTURES', flush=True)
    if not all(row['passed'] for row in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
