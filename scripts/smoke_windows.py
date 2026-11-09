"""Exercise the frozen CLI and optionally open/close only its own GUI window."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from check_repository import ROOT, version


def run(exe, *args):
    result = subprocess.run([str(exe), *map(str, args)], capture_output=True,
                            timeout=90, encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}): {args}\n{result.stdout}\n{result.stderr}')
    return result.stdout


def gui_smoke(exe):
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    proc = subprocess.Popen([str(exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        found = []
        @callback_type
        def visit(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            title = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, title, len(title))
            if pid.value == proc.pid and user32.IsWindowVisible(hwnd) and version() in title.value:
                found.append(hwnd)
            return True
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline and not found:
            if proc.poll() is not None:
                raise RuntimeError('GUI exited before its window appeared')
            user32.EnumWindows(visit, 0)
            time.sleep(0.2)
        if not found:
            raise RuntimeError('No visible application window found')
        time.sleep(2)
        for hwnd in found:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE, exact launched PID only
        if proc.wait(timeout=20) != 0:
            raise RuntimeError('GUI did not close successfully')
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--cli-only', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'win32':
        raise SystemExit('Frozen smoke tests require Windows.')
    exe = args.exe or ROOT / 'dist' / f'RenpyWalkthroughStudio-{version()}-windows-x64/RenpyWalkthroughStudio.exe'
    assert version() in run(exe, '--version')
    assert '--scan' in run(exe, '--help')
    config = json.loads(run(exe, '--list-config'))
    assert isinstance(config, dict) and 'weight_direct_score' in config
    with tempfile.TemporaryDirectory(prefix='studio-smoke-') as tmp:
        root = Path(tmp)
        game = root / 'Sentetik Türkçe' / 'game'
        game.mkdir(parents=True)
        source = game / 'script.rpy'
        source.write_text('default luna_points = 0\nlabel start:\n    menu:\n'
                          '        "Support":\n            $ luna_points += 1\n'
                          '        "Wait":\n            pass\n    return\n', encoding='utf-8')
        before = {str(p.relative_to(game)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in game.rglob('*') if p.is_file()}
        report = root / 'analysis.json'
        run(exe, game.parent, '--cli', '--scan', '--skip-rpa', '--no-cheat-menu', '--report', report)
        assert report.is_file()
        json.loads(report.read_text(encoding='utf-8'))
        after = {str(p.relative_to(game)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in game.rglob('*') if p.is_file()}
        assert before == after, 'Read-only scan changed synthetic game files'
    if not args.cli_only:
        gui_smoke(exe)
    print('Frozen smoke passed: version/help/config/read-only scan' +
          ('' if args.cli_only else '/GUI open-close'))


if __name__ == '__main__':
    main()
