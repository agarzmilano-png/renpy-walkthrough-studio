"""Build an isolated generated game using a supplied local Ren'Py engine.

Usage: python tests/run_native_both_validation.py --engine PATH --output PATH
The engine directory must contain renpy/, lib/, and Ripples.py or SDK renpy.py. No downloads,
game init/login scripts, or modifications of the supplied engine are needed.
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

SOURCE = '''default anna_points = 0
default luna_points = 0
default prefer_anna = False
default ticket = True
label start:
    menu:
        "Anna choice":
            $ prefer_anna = True
            $ anna_points += 2
            "Anna branch"
            jump future
        "Luna choice":
            $ prefer_anna = False
            $ luna_points += 2
            "Luna branch"
            jump future
label future:
    if prefer_anna and anna_points >= 2 and ticket:
        "Anna unlocked"
    if not prefer_anna and luna_points >= 2 and ticket:
        "Luna unlocked"
    "Done"
    return
'''

HARNESS = '''init -999 python:
    config.name = "Generated Both Native Validation"
    config.version = "1"
    config.main_menu = False
    config.save_directory = "opencode_generated_both_validation"
    config.window_title = "Both isolated test"
    config.screen_width = 640
    config.screen_height = 360
    config.developer = False
    config.autosave_on_quit = False
    config.has_autosave = False
init 999 python:
    import native_both_controller
    native_both_controller.install()
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--fixture', choices=('route', 'calls', 'timed', 'all', 'narrative'), default='route')
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(exist_ok=False)
    for name in ('renpy', 'lib'):
        shutil.copytree(args.engine / name, root / name)
    launcher = next((args.engine / name for name in ('Ripples.py', 'renpy.py')
                     if (args.engine / name).is_file()), None)
    if launcher is None:
        raise FileNotFoundError('Engine launcher missing (Ripples.py or renpy.py)')
    shutil.copy2(launcher, root / 'Ripples.py')
    shutil.copy2(Path(__file__).with_name('native_both_controller.py'), root / 'native_both_controller.py')
    game = root / 'game'
    game.mkdir()
    source_path = game / 'script.rpy'
    source = SOURCE
    if args.fixture == 'narrative':
        source = source.replace('            "Anna branch"',
                                '            "Anna branch"\n            "You died, said the actor."')
    if args.fixture == 'all':
        source = source.replace('default ticket = True', 'default ticket = True\ndefault maya_points = 0')
        source = source.replace('            $ prefer_anna = True\n', '').replace('            $ prefer_anna = False\n', '')
        source = source.replace('prefer_anna and anna_points', 'anna_points')
        source = source.replace('not prefer_anna and luna_points', 'luna_points')
        source = source.replace('label future:',
                                '        "Maya choice":\n            $ maya_points += 2\n'
                                '            "Maya branch"\n            jump future\nlabel future:')
        source = source.replace('    "Done"', '    if maya_points >= 2 and ticket:\n        "Maya unlocked"\n    "Done"')
    if args.fixture == 'timed':
        source = source.replace('            "Anna branch"', '            pause(0.01)\n            "Anna branch"')
        source = source.replace('            "Luna branch"', '            pause(.02)\n            "Luna branch"')
    if args.fixture == 'calls':
        helpers = []
        for name in ('anna', 'luna'):
            original = '            $ ' + name + '_points += 2\n            "' + name.title() + ' branch"'
            source = source.replace(original, '            call ' + name + '_chain from _call_' + name)
            helpers.append('label ' + name + '_chain:\n    jump ' + name + '_inner\n'
                           'label ' + name + '_inner:\n    $ ' + name + '_points += 2\n'
                           '    "' + name.title() + ' branch"\n    return\n')
        (game / 'helpers.rpy').write_text('\n'.join(helpers), encoding='utf-8')
        source, tail = source.split('label future:')
        (game / 'future.rpy').write_text('label future:' + tail, encoding='utf-8')
    source_path.write_text(source, encoding='utf-8')
    an = studio.RenpyWalkthroughAnalyzer(str(game), options={
        'read_only': False, 'enable_cheat_menu': False, 'remove_rpyc': False}, log_callback=lambda *_: None)
    an.scan_files(auto_extract=False, log_callback=lambda *_: None)
    an.index_labels(log_callback=lambda *_: None)
    menus = an.analyze_file_menus(str(source_path))[1]
    an.all_menus = menus
    candidates = an.detect_both_candidates(menus)
    assert len(candidates) == 1, an.both_skipped
    originals = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in game.glob('*.rpy')}
    assert an.apply_both_patch(candidates[0], log_callback=lambda *_: None)
    (game / 'native_harness.rpy').write_text(HARNESS, encoding='utf-8')
    env = os.environ.copy()
    for name in list(env):
        if name.startswith('WT_NATIVE_'):
            del env[name]
    env.update(RENPY_RENDERER='sw',
               SDL_AUDIODRIVER='dummy', RENPY_SOUND='0',
               APPDATA=str(root / 'private_appdata'), LOCALAPPDATA=str(root / 'private_localappdata'))
    if args.fixture == 'all':
        env['WT_NATIVE_PICK'] = 'Mod: All'
    for name in ('private_saves', 'private_appdata', 'private_localappdata'):
        (root / name).mkdir()
    interpreters = sorted((root / 'lib').glob('py*-windows-x86_64/python.exe'))
    if len(interpreters) != 1:
        raise RuntimeError('Expected one bundled Windows interpreter: ' + repr(interpreters))
    executable = interpreters[0]
    cases = [
        ('both', {}, (2, 2), ['Anna branch', 'Luna branch', 'Anna unlocked', 'Luna unlocked', 'Done']),
        ('anna_only', {'WT_NATIVE_PICK': 'Anna choice'}, (2, 0), ['Anna branch', 'Anna unlocked', 'Done']),
        ('luna_only', {'WT_NATIVE_PICK': 'Luna choice'}, (0, 2), ['Luna branch', 'Luna unlocked', 'Done']),
        ('ticket_false', {'WT_NATIVE_TICKET': 'False'}, (2, 2), ['Anna branch', 'Luna branch', 'Done']),
        ('anna_below_threshold', {'WT_NATIVE_ANNA': '-1'}, (1, 2),
         ['Anna branch', 'Luna branch', 'Luna unlocked', 'Done']),
        ('save_first', {}, (2, 2), None),
        ('save_second', {}, (2, 2), None),
        ('load_fresh', {}, (2, 2), None),
        ('rollback_between', {}, (2, 2), None),
        ('rollback_menu', {}, (2, 2), None),
        ('rollback_change_choice', {'WT_NATIVE_REPICK': 'Anna choice'}, (2, 0), None),
        ('save_and_rollback', {}, (2, 2), None),
    ]
    results = []
    for name, overrides, expected_points, expected_dialogue in cases:
        case_env = dict(env, WT_NATIVE_CASE=name, WT_NATIVE_RESULT=str(root / (name + '.json')),
                        WT_NATIVE_SLOT='save_first' if name == 'load_fresh' else name,
                        RENPY_PATH_TO_SAVES=str(root / 'private_saves' /
                                               ('save_first' if name == 'load_fresh' else name)))
        case_env.update(overrides)
        with open(root / (name + '_stdout.log'), 'wb') as stdout, open(root / (name + '_stderr.log'), 'wb') as stderr:
            completed = subprocess.run([str(executable), str(root / 'Ripples.py')], cwd=root,
                                       env=case_env, stdout=stdout, stderr=stderr, timeout=35)
        result_path = root / (name + '.json')
        if not result_path.exists():
            raise RuntimeError('Missing native result: ' + name + '; inspect ' + str(root / 'log.txt'))
        result = json.loads(result_path.read_text(encoding='utf-8'))
        assert completed.returncode == 0 and result['error'] is None, result
        points = (result['final']['anna_points'], result['final']['luna_points'])
        assert points == expected_points, (name, points, expected_points)
        if args.fixture == 'all':
            self_only = name in ('anna_only', 'luna_only', 'rollback_change_choice')
            assert result['final']['maya_points'] == (0 if self_only else 2), result
            if expected_dialogue is not None and not self_only:
                expected_dialogue = list(expected_dialogue)
                expected_dialogue.insert(expected_dialogue.index('Luna branch') + 1, 'Maya branch')
                if name != 'ticket_false':
                    expected_dialogue.insert(-1, 'Maya unlocked')
        if expected_dialogue is not None:
            if args.fixture == 'narrative' and 'Anna branch' in expected_dialogue:
                expected_dialogue = list(expected_dialogue)
                expected_dialogue.insert(expected_dialogue.index('Anna branch') + 1,
                                         'You died, said the actor.')
            dialogue = [e['text'] for e in result['events'] if e['kind'] == 'say']
            assert dialogue == expected_dialogue, (name, dialogue)
        if name.startswith('save_'):
            assert any(e['kind'] == 'saved' for e in result['events']), result
            assert any(e['kind'] == 'load_requested' for e in result['events']), result
        if name.startswith('rollback_') or name == 'save_and_rollback':
            assert any(e['kind'] == 'rollback_requested' for e in result['events']), result
        if name == 'load_fresh':
            assert any(e['kind'] == 'load_requested' and e.get('fresh_process') for e in result['events']), result
        events = result['events']
        load_indices = [i for i, event in enumerate(events) if event['kind'] == 'load_requested']
        if load_indices:
            resumed = [event for event in events[load_indices[0] + 1:] if event['kind'] == 'say']
            first_text, first_points = ('Luna branch', (2, 2)) if name == 'save_second' else ('Anna branch', (2, 0))
            assert resumed[0]['text'] == first_text, (name, resumed)
            assert (resumed[0]['state']['anna_points'], resumed[0]['state']['luna_points']) == first_points
        rollback_indices = [i for i, event in enumerate(events) if event['kind'] == 'rollback_requested']
        if rollback_indices:
            replay = events[rollback_indices[0] + 1:]
            if name == 'rollback_between':
                assert replay[0]['kind'] == 'say' and replay[0]['text'] == 'Luna branch', replay
            else:
                assert replay[0]['kind'] == 'menu', replay
                assert replay[0]['state']['anna_points'] == replay[0]['state']['luna_points'] == 0, replay
            replay_dialogue = [event['text'] for event in replay if event['kind'] == 'say']
            assert replay_dialogue.count('Done') == 1, replay
            assert replay_dialogue.count('Anna unlocked') == 1, replay
            assert replay_dialogue.count('Luna unlocked') == (0 if name == 'rollback_change_choice' else 1), replay
        results.append({'case': name, 'passed': True, 'engine': result['engine'], 'final_state': result['final']})
        if (root / 'log.txt').exists():
            shutil.copy2(root / 'log.txt', root / (name + '_engine.log'))
        print('NATIVE_PASS', name, points, flush=True)
    manifest = {'engine': str(args.engine), 'fixture': args.fixture,
                'app_sha256': hashlib.sha256(Path(studio.__file__).read_bytes()).hexdigest(),
                'controller_sha256': hashlib.sha256((root / 'native_both_controller.py').read_bytes()).hexdigest(),
                'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'originals_sha256': originals,
                'sources_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in game.glob('*.rpy')},
                'presentation_suppressed': True, 'results': results}
    (root / 'validation_summary.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('OUTPUT', root, flush=True)


if __name__ == '__main__':
    main()
