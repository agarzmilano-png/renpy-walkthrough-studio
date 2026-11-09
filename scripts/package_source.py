"""Create an inspected, source-only ZIP; omit all local build environments."""
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from check_repository import ROOT, main as check_repository, source_files, version


def main():
    if check_repository():
        raise SystemExit('Repository inspection failed.')
    target = ROOT / 'dist' / f'renpy-walkthrough-studio-{version()}-source.zip'
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, 'x', ZIP_DEFLATED) as archive:
        for path in source_files():
            archive.write(path, Path('renpy-walkthrough-studio') / path.relative_to(ROOT))
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        assert all('/.venv/' not in name and '/dist/' not in name for name in archive.namelist())
    rows = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}'
            for p in sorted((ROOT / 'dist').glob('*.zip'))]
    (ROOT / 'dist/SHA256SUMS.txt').write_text('\n'.join(rows) + '\n', encoding='utf-8')
    print(f'Created {target.name}')


if __name__ == '__main__':
    main()
