"""Batch scheduling and syntax caching must not change analysis semantics."""
import ast
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import renpy_walkthrough_studio as studio
from benchmark_walkthrough import WorkerUI


def write_game(root, count=4):
    for index in range(count):
        label = 'start' if index == 0 else 'part' + str(index)
        target = 'part' + str(index + 1) if index + 1 < count else 'finish'
        source = ('default anna_points = 0\n' if index == 0 else '')
        source += (f'label {label}:\n    menu:\n        "Anna {index}":\n'
                   f'            $ anna_points += 1\n            jump {target}\n'
                   f'        "Wait {index}":\n            jump {target}\n')
        if index + 1 == count:
            source += 'label finish:\n    if anna_points >= 2:\n        "Unlocked"\n    return\n'
        (root / f'{index:02}.rpy').write_text(source, encoding='utf-8')


class AssignmentSyntaxCacheTests(unittest.TestCase):
    def setUp(self):
        studio._parse_assignment_syntax.cache_clear()

    def test_repeated_line_is_parsed_once_but_returns_fresh_results(self):
        real_parse = ast.parse
        with patch.object(studio.ast, 'parse', wraps=real_parse) as parse:
            first = studio.RenpyASTAnalyzer.get_assignment_info('$ anna_points += 2')
            first['call_args'].append('must not leak')
            second = studio.RenpyASTAnalyzer.get_assignment_info('$ anna_points += 2')
            self.assertEqual(parse.call_count, 1)
        self.assertEqual(second['value'], 2)
        self.assertEqual(second['call_args'], [])
        self.assertIsNot(first, second)

    def test_failed_syntax_is_cached_without_changing_diagnostics(self):
        real_parse = ast.parse
        with patch.object(studio.ast, 'parse', wraps=real_parse) as parse:
            first = studio.RenpyASTAnalyzer.get_assignment_info('scene room with dissolve')
            second = studio.RenpyASTAnalyzer.get_assignment_info('scene room with dissolve')
            self.assertEqual(parse.call_count, 1)
        self.assertEqual(first, second)
        self.assertFalse(first['is_ast_parsed'])
        self.assertTrue(first['parse_error'])

    def test_different_source_does_not_reuse_previous_tree(self):
        first = studio.RenpyASTAnalyzer.get_assignment_info('$ anna_points += 2')
        second = studio.RenpyASTAnalyzer.get_assignment_info('$ anna_points += 3')
        self.assertEqual((first['value'], second['value']), (2, 3))

    def test_call_resolution_is_recomputed_despite_cached_syntax(self):
        def effects(value):
            return [{'target': 'anna_points', 'op': '+=', 'value': value, 'val_type': 'number'}]
        with patch.object(studio.RenpyASTAnalyzer, 'resolve_call_to_assignment',
                          side_effect=[effects(1), effects(7)]) as resolve:
            with patch.dict(studio.STUDIO_CONFIG, enable_interprocedural_ast=True):
                first = studio.RenpyASTAnalyzer.get_assignment_info('$ award(1)')
                second = studio.RenpyASTAnalyzer.get_assignment_info('$ award(1)')
        self.assertEqual(resolve.call_count, 2)
        self.assertEqual((first['value'], second['value']), (1, 7))

    def test_nested_effect_results_are_not_shared(self):
        first = studio.RenpyASTAnalyzer.get_assignment_info('$ anna_points, luna_points = anna_points + 2, luna_points + 3')
        first['resolved_effects'][0]['value'] = 999
        second = studio.RenpyASTAnalyzer.get_assignment_info('$ anna_points, luna_points = anna_points + 2, luna_points + 3')
        self.assertEqual(second['resolved_effects'][0]['value'], 2)

    def test_large_sources_bypass_bounded_cache(self):
        studio.RenpyASTAnalyzer.get_assignment_info('$ anna_points = 2 #' + 'x' * 3000)
        self.assertEqual(studio._parse_assignment_syntax.cache_info().currsize, 0)
        self.assertEqual(studio._parse_assignment_syntax.cache_info().maxsize, 4096)


class BatchSchedulingTests(unittest.TestCase):
    def game(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        write_game(root)
        return root

    def test_gui_decisions_are_prepared_before_first_write(self):
        root = self.game()
        ui = WorkerUI(both=True, profile='ROMANCE_ONLY')
        events = []
        real_collect = studio.RenpyMenu._collect_evidence
        real_patch = studio.RenpyWalkthroughAnalyzer.patch_file
        real_global = studio.CSSolver.run_global
        real_parse = studio.RenpyWalkthroughAnalyzer.analyze_file_menus
        profiles = []
        def collect(menu, *args, **kwargs):
            events.append('compute')
            return real_collect(menu, *args, **kwargs)
        def write(analyzer, *args, **kwargs):
            events.append('write')
            profiles.extend(m._evt_decision_cache[0][2] for m in args[2])
            return real_patch(analyzer, *args, **kwargs)
        with patch.object(studio.RenpyMenu, '_collect_evidence', collect), \
             patch.object(studio.RenpyWalkthroughAnalyzer, 'patch_file', write), \
             patch.object(studio.CSSolver, 'run_global', autospec=True, side_effect=real_global) as global_run, \
             patch.object(studio.RenpyWalkthroughAnalyzer, 'analyze_file_menus', autospec=True, side_effect=real_parse) as parse:
            studio.RenpyWalkthroughApp.run_process(ui, 'patch', str(root))
        self.assertEqual(ui.errors, [])
        self.assertIn('write', events)
        self.assertNotIn('compute', events[events.index('write'):])
        self.assertEqual(global_run.call_count, 1)
        self.assertEqual(parse.call_count, 4)  # Both reuses menus, no second pass.
        self.assertEqual(set(profiles), {'ROMANCE_ONLY'})

    def test_cli_decisions_are_prepared_before_first_write(self):
        root = self.game()
        analyzer = studio.RenpyWalkthroughAnalyzer(str(root), options={
            'enable_cheat_menu': False, 'remove_rpyc': False, 'player_profile': 'SURVIVAL_ONLY'})
        events = []
        real_collect = studio.RenpyMenu._collect_evidence
        real_patch = analyzer.patch_file
        def collect(menu, *args, **kwargs):
            events.append('compute')
            return real_collect(menu, *args, **kwargs)
        def write(*args, **kwargs):
            events.append('write')
            return real_patch(*args, **kwargs)
        with patch.object(studio.RenpyMenu, '_collect_evidence', collect), \
             patch.object(analyzer, 'patch_file', side_effect=write):
            analyzer.analyze_and_patch()
        self.assertIn('write', events)
        self.assertNotIn('compute', events[events.index('write'):])
        self.assertFalse(analyzer._in_batch_patch)

    def test_external_edit_during_analysis_aborts_before_any_write(self):
        root = self.game()
        original = (root / '00.rpy').read_bytes()
        ui = WorkerUI()
        real_parse = studio.RenpyWalkthroughAnalyzer.analyze_file_menus
        def parse(analyzer, path):
            result = real_parse(analyzer, path)
            if Path(path).name == '03.rpy':
                with open(root / '00.rpy', 'ab') as output:
                    output.write(b'\n# external edit\n')
            return result
        with patch.object(studio.RenpyWalkthroughAnalyzer, 'analyze_file_menus', parse):
            studio.RenpyWalkthroughApp.run_process(ui, 'patch', str(root))
        self.assertTrue(ui.errors)
        self.assertEqual((root / '00.rpy').read_bytes(), original + b'\n# external edit\n')
        self.assertFalse(list(root.glob('*.wtbak')))

    def test_gui_scan_remains_read_only(self):
        root = self.game()
        before = {p.name: p.read_bytes() for p in root.iterdir()}
        ui = WorkerUI(both=True)
        studio.RenpyWalkthroughApp.run_process(ui, 'scan', str(root))
        self.assertEqual(ui.errors, [])
        self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)

    def test_invalid_source_does_not_warm_unreachable_profile_evaluation(self):
        root = self.game()
        analyzer = studio.RenpyWalkthroughAnalyzer(str(root), options={'player_profile': 'ROMANCE_ONLY'})
        calls = []
        menu = SimpleNamespace(evaluate_choices=lambda **kwargs: calls.append(kwargs))
        invalid = ['label start:\n', '    python:\n', '        if\n']
        self.assertFalse(studio.validate_renpy_syntax(invalid)[0])
        analyzer._prepare_walkthrough_profile(invalid, [menu], True)
        self.assertEqual(calls, [])
        analyzer.options['allow_partial_patch'] = True
        analyzer._prepare_walkthrough_profile(invalid, [menu], True)
        self.assertEqual(calls, [{'highlight_negative': True, 'player_profile': 'ROMANCE_ONLY'}])

    def test_external_edit_between_writes_does_not_get_acknowledged_as_ours(self):
        # Filesystem enumeration is not portable. Explicitly exercise every
        # first file and edits to both the current target and a different file.
        for first in range(4):
            for edit_current in (False, True):
                with self.subTest(first=first, edit_current=edit_current):
                    root = self.game()
                    ui = WorkerUI()
                    real_write = studio.RenpyWalkthroughAnalyzer.patch_file
                    real_scan = studio.RenpyWalkthroughAnalyzer.scan_files
                    writes = []
                    changed_path = root / f'{first if edit_current else (first + 1) % 4:02}.rpy'
                    original = changed_path.read_bytes()
                    def scan(analyzer, *args, **kwargs):
                        result = real_scan(analyzer, *args, **kwargs)
                        analyzer.rpy_files.sort(key=lambda path: (
                            Path(path).name != f'{first:02}.rpy', Path(path).name))
                        return result
                    def write(analyzer, path, *args, **kwargs):
                        result = real_write(analyzer, path, *args, **kwargs)
                        writes.append(path)
                        if len(writes) == 1:
                            changed_path.write_bytes(original + b'\n# concurrent edit\n')
                        return result
                    with patch.object(studio.RenpyWalkthroughAnalyzer, 'scan_files', scan), \
                         patch.object(studio.RenpyWalkthroughAnalyzer, 'patch_file', write):
                        studio.RenpyWalkthroughApp.run_process(ui, 'patch', str(root))
                    self.assertEqual(len(writes), 1)
                    self.assertTrue(ui.errors)
                    self.assertEqual(changed_path.read_bytes(), original + b'\n# concurrent edit\n')


if __name__ == '__main__':
    unittest.main()
