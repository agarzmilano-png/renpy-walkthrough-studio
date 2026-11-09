"""Check incoming state/caller proofs against an explicit local Ren'Py engine.

Only new private copies are run. The harness automates presentation/choices and
observes native quit callbacks; source assignments and calls remain native.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import renpy_walkthrough_studio as studio


SOURCE = '''default seed = False
default copied = False
default gate = False
label start:
PREFIX
    call helper from _call_helper
CALLER
label helper:
HIDDEN
    $ copied = seed
    $ gate = copied
    menu:
        "Conditional return":
            if gate is True:
                return
            $ renpy.quit()
        "Terminal":
            $ renpy.quit()
'''

HARNESS = '''init -999 python:
    config.name = "Context validation"
    config.main_menu = False
    config.autosave_on_quit = False
    config.has_autosave = False
init 999 python:
    import context_controller
    context_controller.install()
'''

CONTROLLER = '''import json
import os
import traceback
import renpy

events = []
written = False

def state():
    return {name: getattr(renpy.store, name) for name in ('seed', 'copied', 'gate')}

def write(outcome, error=None):
    global written
    if written:
        return
    written = True
    with open(os.environ['WT_CONTEXT_RESULT'], 'w', encoding='utf-8') as output:
        json.dump({'engine': str(renpy.version), 'outcome': outcome, 'error': error,
                   'state': state(), 'events': events}, output, indent=2)

def choose(items, *args, **kwargs):
    valid = [(str(text), index) for text, cond, index in items
             if index is not None and renpy.python.py_eval(cond)]
    events.append({'kind': 'menu', 'state': state(), 'choices': [text for text, _ in valid]})
    if not valid:
        return None
    if any(text.startswith('First ') for text, _ in valid):
        requested = os.environ.get('WT_CONTEXT_FIRST', 'First true')
    else:
        requested = os.environ['WT_CONTEXT_PICK']
    matches = [index for text, index in valid if text == requested]
    if len(matches) != 1:
        write('error', repr((requested, valid)))
        os._exit(1)
    renpy.game.log.did_interaction = True
    renpy.exports.checkpoint(matches[0])
    return matches[0]

def say(who, what, *args, **kwargs):
    events.append({'kind': 'say', 'text': str(what), 'state': state()})
    if str(what) == 'After helper':
        write('returned')
        os._exit(0)

def error(*args):
    write('error', traceback.format_exc())
    os._exit(1)

def install():
    renpy.exports.menu = choose
    renpy.exports.say = say
    renpy.config.quit_callbacks.append(lambda: write('terminal'))
    renpy.config.exception_handler = error
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False, parents=True)
    summaries = []
    for fixture in ('known', 'mixed', 'hidden', 'caller', 'aliases'):
        root = args.output.resolve() / fixture
        root.mkdir()
        for name in ('renpy', 'lib'):
            shutil.copytree(args.engine / name, root / name)
        launcher = next(args.engine / name for name in ('Ripples.py', 'renpy.py') if (args.engine / name).is_file())
        shutil.copy2(launcher, root / 'context.py')
        game = root / 'game'
        game.mkdir()
        prefix = '    $ seed = True'
        if fixture == 'mixed':
            prefix = '''    menu:
        "First true":
            $ seed = True
        "First int":
            $ seed = 1
        "First false":
            $ seed = False'''
        caller = '    "After helper"\n    return' if fixture != 'caller' else '    $ renpy.quit()'
        hidden = ('    menu:\n        "Never" if False:\n            $ renpy.quit()'
                  if fixture == 'hidden' else '')
        source = SOURCE.replace('PREFIX', prefix).replace('CALLER', caller).replace('HIDDEN', hidden)
        if fixture == 'aliases':
            source = source.replace('$ copied = seed', '$ store.copied = renpy.store.seed')
            source = source.replace('$ gate = copied', '$ gate = store.copied')
        (game / 'script.rpy').write_text(source, encoding='utf-8')
        (game / 'native_context.rpy').write_text(HARNESS, encoding='utf-8')
        (root / 'context_controller.py').write_text(CONTROLLER, encoding='utf-8')
        prog = studio.CSProgram()
        prog.add_file('script.rpy', source.splitlines(True))
        mid = max(prog.menus, key=lambda key: key[1])
        proof = studio.cs_run_contextual(prog, mid)
        assert proof['complete'], proof
        info = studio.cs_aggregate(proof['visits'], 2)
        if fixture in ('known', 'hidden', 'aliases'):
            assert info[0]['green'] and info[1]['red'], info
        else:
            assert not any(row['green'] or row['red'] for row in info.values()), info
        cases = [('conditional', 'First true', 'Conditional return', 'returned'),
                 ('terminal', 'First true', 'Terminal', 'terminal')]
        if fixture == 'mixed':
            cases = [('true', 'First true', 'Conditional return', 'returned'),
                     ('int', 'First int', 'Conditional return', 'terminal'),
                     ('false', 'First false', 'Conditional return', 'terminal')]
        if fixture == 'caller':
            cases = [(name, first, pick, 'terminal') for name, first, pick, _ in cases]
        executable, = (root / 'lib').glob('py*-windows-x86_64/python.exe')
        for name, first, pick, outcome in cases:
            env = os.environ.copy()
            env.update(WT_CONTEXT_FIRST=first, WT_CONTEXT_PICK=pick, WT_CONTEXT_RESULT=str(root / (name + '.json')),
                       RENPY_SKIP_MAIN_MENU='1', RENPY_RENDERER='sw', SDL_AUDIODRIVER='dummy', RENPY_SOUND='0',
                       APPDATA=str(root / ('appdata_' + name)), LOCALAPPDATA=str(root / ('local_' + name)),
                       RENPY_PATH_TO_SAVES=str(root / ('saves_' + name)))
            with (root / (name + '_stdout.log')).open('wb') as stdout, (root / (name + '_stderr.log')).open('wb') as stderr:
                completed = subprocess.run([str(executable), str(root / 'context.py')], cwd=root,
                                           env=env, stdout=stdout, stderr=stderr, timeout=60)
            data = json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
            assert completed.returncode == 0 and data['error'] is None and data['outcome'] == outcome, data
            observed = [e for e in data['events'] if e['kind'] == 'menu' and 'Conditional return' in e['choices']]
            assert len(observed) == 1, data
            for visit in proof['visits']:
                for variable, value in visit['state'].items():
                    if variable in observed[0]['state'] and value is not studio.CS_UNK:
                        assert studio._cs_scalar_key(value) == studio._cs_scalar_key(observed[0]['state'][variable]), data
            summaries.append({'fixture': fixture, 'case': name, 'engine': data['engine'], 'passed': True,
                              'outcome': outcome, 'abstract_entry_contains_native_state': True,
                              'proof': info, 'coverage': proof['coverage']})
            print('NATIVE_CONTEXT_PASS', fixture, name, outcome, data['engine'], flush=True)
    (args.output / 'context_summary.json').write_text(json.dumps({
        'app_sha256': hashlib.sha256(Path(studio.__file__).read_bytes()).hexdigest(),
        'presentation_suppressed': True, 'native_quit_callback': True, 'results': summaries}, indent=2), encoding='utf-8')
    print('NATIVE_CONTEXT', len(summaries), 'PASSED', flush=True)


if __name__ == '__main__':
    main()
