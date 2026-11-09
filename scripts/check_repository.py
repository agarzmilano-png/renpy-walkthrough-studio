"""Fail closed on accidental private/generated content in the source tree."""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', '.venv', 'build', 'dist', '__pycache__', '.pytest_cache'}


def source_files():
    for path in sorted(ROOT.rglob('*')):
        parts = path.relative_to(ROOT).parts
        if any(p in SKIP or p.endswith('.egg-info') for p in parts):
            continue
        if path.is_symlink():
            raise ValueError(f'Symlink not permitted: {path.relative_to(ROOT)}')
        if path.is_file():
            yield path


def version():
    tree = ast.parse((ROOT / 'renpy_walkthrough_studio.py').read_text(encoding='utf-8'))
    return next(ast.literal_eval(n.value) for n in tree.body
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and
                    t.id == '__version__' for t in n.targets))


def main():
    errors = []
    forbidden = {'.rpa', '.rpyc', '.exe', '.dll', '.zip', '.7z', '.rar', '.wtbak',
                 '.bak', '.save', '.log', '.pem', '.key', '.pfx'}
    private_path = re.compile(r'(?i)(?:[a-z]:[\\/]+Users[\\/]+|[/]home[/]|[/]Users[/]|'
                              r'\.gemini[\\/]|antigravity[\\/]scratch)')
    secret = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|'
                        r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)')
    files = list(source_files())
    for path in files:
        rel = path.relative_to(ROOT)
        if path.suffix.lower() in forbidden or path.name.startswith('.env'):
            errors.append(f'Forbidden file: {rel}')
        if rel.parts[0] in {'private', 'validation-runs', 'game', 'games'}:
            errors.append(f'Private/generated directory: {rel}')
        if path.name.endswith('.latest.json') or 'baselines' in rel.parts:
            errors.append(f'Generated/old baseline: {rel}')
        raw = path.read_bytes()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            errors.append(f'Unexpected binary file: {rel}')
            continue
        if b'\r' in raw:
            errors.append(f'Non-LF line endings: {rel}')
        if private_path.search(text):
            errors.append(f'Private local path: {rel}')
        if secret.search(text):
            errors.append(f'Potential credential: {rel}')
        if path.suffix == '.rpy' and not rel.is_relative_to('tests'):
            errors.append(f'Unexpected game source: {rel}')
    v = version()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:(?:b|rc)\d+)?', v):
        errors.append('Invalid application version')
    for name in ('README.md', 'CHANGELOG.md', 'docs/RELEASING.md'):
        if v not in (ROOT / name).read_text(encoding='utf-8'):
            errors.append(f'Missing current version: {name}')
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    if project['project']['license'] != 'MIT':
        errors.append('Project license must match the selected MIT license')
    for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'LICENSES/unrpyc-MIT.txt',
                 'LICENSES/renpy-script-MIT.txt', 'LICENSES/Roboto-Apache-2.0.txt'):
        if not (ROOT / name).is_file():
            errors.append(f'Missing license: {name}')
    sources = ROOT / 'LICENSES/RUNTIME_SOURCES.json'
    if sources.is_file():
        for name, record in json.loads(sources.read_text(encoding='utf-8')).items():
            path = ROOT / 'LICENSES' / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
                errors.append(f'Runtime license hash mismatch: {name}')
    manifest = ROOT / 'docs' / f'validation-{v}.json'
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding='utf-8'))
        sha = hashlib.sha256((ROOT / 'renpy_walkthrough_studio.py').read_bytes()).hexdigest()
        if data['version'] != v or data['app_sha256'] != sha:
            errors.append('Validation record is stale; rerun checks for this source hash')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Repository checks passed: {len(files)} files, version {v}.')
    print('Automated checks do not replace manual privacy and license review.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
