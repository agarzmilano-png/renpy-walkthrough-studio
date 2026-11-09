"""Measure the real GUI worker without Tk, only on a newly created test copy.

Never calls the worker on --source. No executables/media are copied or run.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class WorkerUI:
    def __init__(self, both=False, profile='ALL_CONTENT'):
        for name, value in {
            'hint_style': 'Sayı ve İsim', 'green_color': 'Yeşil',
            'highlight_neg': True, 'show_hints': True, 'clear_rpyc': False,
            'auto_backup': True, 'deep_jump': True, 'cheat_menu': False,
            'verify_lint': False, 'player_profile': profile, 'both_routes': both,
            'export_cfg': False, 'export_report': False, 'runtime_hook': False,
        }.items():
            setattr(self, 'var_' + name, Value(value))
        self.errors = []
        self.messages = []
        self.stats = []

    def log(self, message):
        self.messages.append(message)

    def set_ui_state(self, state):
        pass

    def update_progress(self, value):
        pass

    def update_stats(self, **stats):
        self.stats.append(stats)

    def set_selected_folder(self, path):
        pass

    def show_error(self, title, message):
        self.errors.append(message)

    def show_info(self, title, message):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--both', action='store_true')
    parser.add_argument('--cheat', action='store_true')
    parser.add_argument('--profile', default='ALL_CONTENT')
    parser.add_argument('--entry', choices=('gui', 'cli'), default='gui')
    parser.add_argument('--mode', choices=('patch', 'scan'), default='patch')
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    game = args.output.resolve() / 'game'
    game.mkdir()
    originals = {}
    for source in sorted(args.source.rglob('*.rpy')):
        relative = source.relative_to(args.source)
        target = game / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        originals[str(relative)] = hashlib.sha256(source.read_bytes()).hexdigest()
    if not originals:
        raise RuntimeError('No source scripts')
    spec = importlib.util.spec_from_file_location('renpy_walkthrough_studio', args.studio)
    studio = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = studio
    spec.loader.exec_module(studio)
    timings = Counter()
    counts = Counter()
    decisions = {}
    instances = []
    original_init = studio.RenpyWalkthroughAnalyzer.__init__

    def initialize(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        instances.append(self)
    studio.RenpyWalkthroughAnalyzer.__init__ = initialize

    def measure(owner, name):
        original = getattr(owner, name)
        def wrapped(*args, **kwargs):
            counts[name] += 1
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                timings[name] += time.perf_counter() - start
        setattr(owner, name, wrapped)

    for owner, names in (
        (studio.RenpyWalkthroughAnalyzer, ('scan_files', 'analyze_file_menus', 'patch_file', 'detect_both_candidates')),
        (studio.CSSolver, ('run_global',)),
        (studio, ('cs_run_local', 'build_both_scene_plan')),
    ):
        for name in names:
            measure(owner, name)
    original_evaluate = studio.RenpyMenu.evaluate_choices

    def evaluate(self, *args, **kwargs):
        start = time.perf_counter()
        result = original_evaluate(self, *args, **kwargs)
        timings['evaluate_choices'] += time.perf_counter() - start
        counts['evaluate_choices'] += 1
        relative = str(Path(self.file_path).relative_to(game))
        decisions[relative + ':' + str(self.line_num)] = [
            {'text': choice.text, 'verdict': str(verdict),
             'rule': getattr(choice, 'decision_rule', ''), 'score': choice.score,
             'evidence': getattr(choice, 'evidence_level', '')}
            for choice, verdict in result.items() if not isinstance(choice, str)]
        return result
    studio.RenpyMenu.evaluate_choices = evaluate
    ui = WorkerUI(args.both, args.profile)
    ui.var_cheat_menu = Value(args.cheat)
    start = time.perf_counter()
    if args.entry == 'gui':
        studio.RenpyWalkthroughApp.run_process(ui, args.mode, str(game))
    else:
        if args.mode != 'patch':
            raise ValueError('Use GUI entry for read-only scans')
        analyzer = studio.RenpyWalkthroughAnalyzer(str(game), options={
            'enable_cheat_menu': args.cheat, 'remove_rpyc': False, 'player_profile': args.profile,
            'enable_both_route': args.both}, log_callback=ui.log)
        ui.stats.append(analyzer.analyze_and_patch(log_callback=ui.log))
    elapsed = time.perf_counter() - start
    outputs = {str(p.relative_to(game)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(game.rglob('*.rpy'))}
    payload = {'seconds': elapsed, 'counts': dict(counts), 'timings': dict(timings),
               'app_sha256': hashlib.sha256(args.studio.read_bytes()).hexdigest(),
               'inputs': originals, 'outputs': outputs, 'decisions': decisions,
               'backups': {str(p.relative_to(game)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(game.rglob('*.wtbak'))},
               'errors': ui.errors, 'stats': ui.stats, 'messages': ui.messages,
               'entry': args.entry, 'mode': args.mode, 'profile': args.profile, 'cheat': args.cheat,
               'characters': dict(studio.DYNAMIC_CHARACTERS),
               'both': [{'file': str(Path(c.file_path).relative_to(game)), 'line': c.line_num,
                         'kind': c.bridge_kind} for c in getattr(instances[0], 'both_candidates', [])]}
    (args.output / 'benchmark.json').write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding='utf-8')
    print(json.dumps({key: payload[key] for key in ('seconds', 'counts', 'timings', 'errors')}, indent=2), flush=True)
    if ui.errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
