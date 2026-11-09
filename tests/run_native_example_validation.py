"""Validate generated Both end-to-end in the SDK's unmodded The Question.

Runs only new private copies. Requires an explicit local Ren'Py 8.5 SDK path.
The real game's scripts/assets run unchanged except the generated Both and an
isolated presentation controller. This does not certify commercial game routes.
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


HARNESS = '''init -999 python:
    config.main_menu = False
    config.language = None
    config.autosave_on_quit = False
    config.has_autosave = False
init 999 python:
    import example_controller
    example_controller.install()
'''

CONTROLLER = '''import json
import os
import traceback
import renpy

dialogs = []
menus = []

def finish(error=None):
    with open(os.environ['WT_EXAMPLE_RESULT'], 'w', encoding='utf-8') as output:
        json.dump({'engine': str(renpy.version), 'case': os.environ['WT_EXAMPLE_CASE'],
                   'dialogs': dialogs, 'menus': menus, 'book': renpy.store.book,
                   'error': error}, output, indent=2)
    os._exit(1 if error else 0)

def choose(items, *args, **kwargs):
    case = os.environ['WT_EXAMPLE_CASE']
    captions = [(str(caption), index) for caption, cond, index in items
                if index is not None and renpy.python.py_eval(cond)]
    if not menus:
        requested = 'To ask her later.' if case == 'later' else 'To ask her right away.'
    else:
        requested = {'game': "It's a videogame.", 'book': "It's an interactive book.",
                     'both': 'Mod: Both'}[case]
    matches = [index for caption, index in captions if requested in caption]
    if len(matches) != 1:
        finish('Choice not unique: ' + repr((requested, captions)))
    menus.append({'requested': requested, 'available': captions})
    renpy.game.log.did_interaction = True
    renpy.exports.checkpoint(matches[0])
    return matches[0]

def say(who, what, *args, **kwargs):
    text = str(what)
    dialogs.append(text)
    renpy.game.log.did_interaction = True
    renpy.exports.checkpoint()
    if text in ('{b}Good Ending{/b}.', '{b}Bad Ending{/b}.'):
        finish()

def install():
    renpy.exports.menu = choose
    renpy.exports.say = say
    renpy.config.exception_handler = lambda *args: finish(traceback.format_exc())
'''


def hashes(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*.rpy')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(exist_ok=False, parents=True)
    original_game = args.sdk / 'the_question/game'
    originals = hashes(original_game)
    results = {}
    candidate_report = None
    for version in ('baseline', 'patched'):
        target = root / version
        target.mkdir()
        for name in ('renpy', 'lib'):
            shutil.copytree(args.sdk / name, target / name)
        shutil.copy2(args.sdk / 'renpy.py', target / 'example.py')
        shutil.copytree(original_game, target / 'game')
        game = target / 'game'
        if version == 'patched':
            analyzer = studio.RenpyWalkthroughAnalyzer(str(game), options={
                'read_only': False, 'enable_cheat_menu': False, 'remove_rpyc': False},
                log_callback=lambda *_: None)
            analyzer.scan_files(auto_extract=False, log_callback=lambda *_: None)
            analyzer.index_labels(log_callback=lambda *_: None)
            menus = analyzer.analyze_file_menus(str(game / 'script.rpy'))[1]
            analyzer.all_menus = menus
            candidates = analyzer.detect_both_candidates(menus)
            assert len(candidates) == 1, analyzer.export_both_report()
            assert analyzer.apply_both_patch(candidates[0], log_callback=lambda *_: None)
            candidate_report = analyzer.export_both_report()
        (game / 'native_validation.rpy').write_text(HARNESS, encoding='utf-8')
        (target / 'example_controller.py').write_text(CONTROLLER, encoding='utf-8')
        executable, = (target / 'lib').glob('py*-windows-x86_64/python.exe')
        for case in ('game', 'book', 'later') + (('both',) if version == 'patched' else ()):
            env = os.environ.copy()
            env.update(WT_EXAMPLE_CASE=case, WT_EXAMPLE_RESULT=str(target / (case + '.json')),
                       RENPY_SKIP_MAIN_MENU='1',
                       RENPY_RENDERER='sw', SDL_AUDIODRIVER='dummy', RENPY_SOUND='0',
                       APPDATA=str(target / ('appdata_' + case)), LOCALAPPDATA=str(target / ('local_' + case)),
                       RENPY_PATH_TO_SAVES=str(target / ('saves_' + case)))
            with (target / (case + '_stdout.log')).open('wb') as stdout, (target / (case + '_stderr.log')).open('wb') as stderr:
                completed = subprocess.run([str(executable), str(target / 'example.py')], cwd=target,
                                           env=env, stdout=stdout, stderr=stderr, timeout=60)
            result_path = target / (case + '.json')
            assert result_path.exists(), (version, case, 'Missing native result; see logs')
            data = json.loads(result_path.read_text(encoding='utf-8'))
            assert completed.returncode == 0 and data['error'] is None, data
            expected_ending = '{b}Bad Ending{/b}.' if case == 'later' else '{b}Good Ending{/b}.'
            assert data['dialogs'][-1] == expected_ending, data
            assert data['book'] is (case in ('book', 'both')), data
            results[version + '_' + case] = data
            print('NATIVE_EXAMPLE_PASS', version, case, data['engine'], flush=True)
    for case in ('game', 'book', 'later'):
        assert results['baseline_' + case]['dialogs'] == results['patched_' + case]['dialogs'], case
    both = results['patched_both']['dialogs']
    for line in ("It's a kind of videogame you can play on your computer or a console.",
                 "It's like an interactive book that you can read on a computer or a console.",
                 'And so, we become a visual novel creating duo.', '{b}Good Ending{/b}.'):
        assert both.count(line) == 1, (line, both.count(line))
    assert hashes(original_game) == originals, 'Original SDK example was modified'
    summary = {'app_sha256': hashlib.sha256(Path(studio.__file__).read_bytes()).hexdigest(),
               'game': 'The Question (official SDK, unmodded input)', 'sdk': str(args.sdk),
               'original_source_hashes': originals, 'original_sources_unchanged': True,
               'presentation_suppressed': True, 'candidates': candidate_report,
               'passed_cases': list(results), 'original_option_dialogue_equal': True,
               'both_scenes_and_common_ending_once': True}
    (root / 'example_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print('NATIVE_EXAMPLE', len(results), 'PASSED', flush=True)


if __name__ == '__main__':
    main()
