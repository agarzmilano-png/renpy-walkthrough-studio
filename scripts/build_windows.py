"""Build a console/onedir portable ZIP. Never publishes or downloads engines."""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tkinter
from datetime import datetime, timezone
from zipfile import ZIP_DEFLATED, ZipFile

from check_repository import ROOT, main as check_repository, version


def copy_notices(destination):
    destination.mkdir(parents=True)
    packages = {}
    for name in ('customtkinter', 'darkdetect', 'packaging', 'psutil', 'pyinstaller',
                 'pyinstaller-hooks-contrib', 'altgraph', 'pefile', 'pywin32-ctypes', 'setuptools'):
        dist = metadata.distribution(name)
        packages[name] = dist.version
        found = []
        for entry in dist.files or ():
            if any(token in entry.name.lower() for token in ('license', 'copying', 'notice')):
                source = Path(dist.locate_file(entry))
                if not source.is_file():
                    continue
                target = destination / name / Path(str(entry))
                # Distribution records may contain relative paths outside site-packages.
                if '..' in target.parts:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                found.append(str(entry))
        if not found:
            raise RuntimeError(f'No installed license notice found for {name}')
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    shutil.copyfile(python_license, destination / 'Python-LICENSE.txt')
    interp = tkinter.Tcl()
    tcl_library = Path(interp.eval('info library'))
    tcl_version = interp.eval('info patchlevel')
    tk_library = tcl_library.parent / ('tk' + '.'.join(tcl_version.split('.')[:2]))
    for name, library in (('Tcl', tcl_library), ('Tk', tk_library)):
        local = library / 'license.terms'
        if local.is_file():
            shutil.copyfile(local, destination / f'{name}-license.terms')
        else:
            # Official upstream license retained in the repository; reviewed separately.
            shutil.copyfile(ROOT / 'LICENSES' / f'{name}-license.terms.txt',
                            destination / f'{name}-license.terms')
    return packages, tcl_version


def main():
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise SystemExit('Use Windows x64 Python for this portable build.')
    if platform.python_version() != '3.14.2':
        raise SystemExit('Portable runtime notices were reviewed for Python 3.14.2; '
                         'review/update runtime licenses before changing the build interpreter.')
    if check_repository():
        raise SystemExit('Repository inspection failed.')
    v = version()
    name = f'RenpyWalkthroughStudio-{v}-windows-x64'
    bundle = ROOT / 'dist' / name
    archive = ROOT / 'dist' / (name + '.zip')
    if bundle.exists() or archive.exists():
        raise SystemExit('Output exists; move it aside before building a fresh artifact.')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir',
                    '--console', '--name', name, '--distpath', str(ROOT / 'dist'),
                    '--workpath', str(ROOT / 'build/pyinstaller'),
                    '--specpath', str(ROOT / 'build'), '--collect-data', 'customtkinter',
                    '--collect-all', 'psutil', '--exclude-module', 'PIL',
                    str(ROOT / 'renpy_walkthrough_studio.py')], check=True, cwd=ROOT)
    (bundle / (name + '.exe')).rename(bundle / 'RenpyWalkthroughStudio.exe')
    for file in ('README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'CHANGELOG.md'):
        shutil.copyfile(ROOT / file, bundle / file)
    shutil.copytree(ROOT / 'docs', bundle / 'docs')
    shutil.copytree(ROOT / 'LICENSES', bundle / 'licenses/project')
    packages, tcl_version = copy_notices(bundle / 'licenses/runtime')
    files = {str(p.relative_to(bundle)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(bundle.rglob('*')) if p.is_file()}
    info = {'version': v, 'built_utc': datetime.now(timezone.utc).isoformat(),
            'python': platform.python_version(), 'platform': 'Windows x64',
            'tcl': tcl_version, 'dependencies': packages,
            'app_sha256': hashlib.sha256((ROOT / 'renpy_walkthrough_studio.py').read_bytes()).hexdigest(),
            'mode': 'onedir-console', 'signed': False, 'files_sha256': files}
    (bundle / 'BUILD_INFO.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    # Test the exact directory which is archived; do not ship a failed smoke build.
    subprocess.run([sys.executable, str(ROOT / 'scripts/smoke_windows.py'),
                    '--cli-only', '--exe', str(bundle / 'RenpyWalkthroughStudio.exe')], check=True)
    with ZipFile(archive, 'x', ZIP_DEFLATED) as zf:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                zf.write(path, path.relative_to(bundle.parent))
    checksums = ROOT / 'dist/SHA256SUMS.txt'
    rows = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}'
            for p in sorted((ROOT / 'dist').glob('*.zip'))]
    checksums.write_text('\n'.join(rows) + '\n', encoding='utf-8')
    print(f'Built {archive.name}; review notices before publication.')


if __name__ == '__main__':
    main()
