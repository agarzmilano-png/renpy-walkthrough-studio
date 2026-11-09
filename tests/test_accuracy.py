"""Accuracy checks for the current parser, ContractSim and analyzer pipeline.

Do not alias ContractSim to the removed Engine: gain/safety simulation is not a
route-preservation contract. Old route/guide tests remain explicitly skipped.
Regressions for Python boolean operand semantics are ordinary passing tests.
"""
import ast
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import renpy_walkthrough_studio as studio
from legacy_accuracy_contracts import LegacyAccuracyContractTests


GAME = (Path(__file__).parent / 'accuracy_fixtures/dalia_zero_points.rpy').read_text(encoding='utf-8')


def evaluate(expression, state=None):
    """Test helper calling the current evaluator, not a legacy compatibility API."""
    return studio.cs_ev(ast.parse(expression, mode='eval').body, {} if state is None else state)


def simulate(source, **limits):
    program = studio.CSProgram()
    program.add_file('script.rpy', source.splitlines(True))
    solver = studio.CSSolver(program, **limits)
    solver.run_global()
    return program, solver


class CurrentExpressionTests(unittest.TestCase):
    def test_literals_arithmetic_and_comparisons(self):
        cases = [('None', None), ('True', True), ('x + 2', 5),
                 ('x * 2 - 1', 5), ('x // 2', 1), ('x % 2', 1),
                 ('-x', -3), ('+x', 3), ('3 < 5 < 4', False),
                 ('x is not None', True), ('x in (1, 3)', True)]
        for expression, expected in cases:
            with self.subTest(expression=expression):
                value = evaluate(expression, {'x': 3})
                self.assertEqual(value, expected)
                self.assertIs(type(value), type(expected))

    def test_missing_variables_and_case_sensitivity(self):
        self.assertIs(evaluate('x is None'), studio.CS_UNK)
        self.assertIs(evaluate('X == 1', {'x': 1}), studio.CS_UNK)
        self.assertIs(evaluate('x is None', {'x': None}), True)

    def test_boolean_guards(self):
        for expression, expected in [('x and True', True), ('not x', False),
                                     ('x or False', True), ('False or False', False)]:
            with self.subTest(expression=expression):
                self.assertIs(evaluate(expression, {'x': True}), expected)

    def test_calls_are_not_executed(self):
        with patch('os.system', side_effect=AssertionError('must never execute')) as command:
            self.assertIs(evaluate('__import__("os").system("anything")'), studio.CS_UNK)
            self.assertIs(evaluate('unknown_call()'), studio.CS_UNK)
        command.assert_not_called()

    def test_unsupported_collections_are_unknown_not_claimed_supported(self):
        for expression in ("stats['love']", '{1, 2} == {2, 1}', '[x for x in values]'):
            with self.subTest(expression=expression):
                self.assertIs(evaluate(expression, {'stats': {'love': 4}}), studio.CS_UNK)

    def test_arithmetic_errors_are_unknown(self):
        self.assertIs(evaluate('1 // 0'), studio.CS_UNK)
        self.assertIs(evaluate('"a" - 1'), studio.CS_UNK)

    def test_conditional_expression_only_selects_known_branch(self):
        self.assertEqual(evaluate('3 if True else unsupported()'), 3)
        self.assertIs(evaluate('3 if missing else 4'), studio.CS_UNK)

    def test_boolean_operations_preserve_python_operands(self):
        value = evaluate('2 or 0')
        self.assertEqual(value, 2)
        self.assertIs(type(value), int)

    def test_unknown_left_operand_is_not_discarded(self):
        # An unknown leading operand can itself be the Python expression result.
        self.assertIs(evaluate('missing or 1'), studio.CS_UNK)


class CurrentSimulationTests(unittest.TestCase):
    def test_literal_defaults_labels_and_menu_locations(self):
        program, solver = simulate(GAME)
        self.assertEqual(program.defaults['gym'], False)
        self.assertEqual(set(program.labels), {'start', 'check_route', 'dalia_entry'})
        self.assertEqual(list(program.menus), [('script.rpy', 2)])
        self.assertIn(('script.rpy', 2), solver.obs)
        self.assertFalse(solver.aborted)

    def test_choices_have_separate_initial_states(self):
        # Use executable, different terminal outcomes to observe state isolation;
        # opening a branch is no longer an artificial reward.
        source = GAME.replace('    if gym:\n        jump dalia_entry\n    return',
                              '    if gym:\n        jump dalia_entry\n    $ renpy.quit()')
        _, solver = simulate(source)
        visit = solver.obs[('script.rpy', 2)][0]
        self.assertEqual(set(visit['vals']), {0, 1})
        self.assertTrue(all(visit['sure'].values()))
        # A conservative menu fall-through edge may retain the literal default;
        # a proven-dead incoming value may instead be omitted by projection.
        self.assertIs(visit['state'].get('gym', False), False)
        self.assertTrue(visit['vals'][0][0])
        self.assertFalse(visit['vals'][1][1])

    def test_call_continuation_overwrites_previous_flag(self):
        source = GAME.replace('    call check_route', '    call helper\n    call check_route')
        source += '\nlabel helper:\n    $ gym = False\n    return\n'
        _, solver = simulate(source)
        visit = solver.obs[('script.rpy', 2)][0]
        self.assertEqual(visit['vals'][0], visit['vals'][1])
        decisions, _ = studio.cs_classify_visit(visit)
        self.assertEqual(decisions, {0: 'NONE', 1: 'NONE'})

    def test_unknown_python_taints_continuation(self):
        source = GAME.replace('    call check_route', '    $ unknown_effect()\n    call check_route')
        _, solver = simulate(source)
        visit = solver.obs[('script.rpy', 2)][0]
        self.assertTrue(all(value[4] for value in visit['vals'].values()))
        self.assertEqual(studio.cs_classify_visit(visit)[0], {0: 'NONE', 1: 'NONE'})

    def test_unknown_control_flow_cannot_prove_safe_choice(self):
        source = GAME.replace('    call check_route', '    jump expression target')
        _, solver = simulate(source)
        visit = solver.obs[('script.rpy', 2)][0]
        self.assertTrue(all(value[4] for value in visit['vals'].values()))
        self.assertFalse(any(value[0] for value in visit['vals'].values()))

    def test_budget_exhaustion_clears_partial_observations(self):
        _, solver = simulate(GAME, max_steps=1)
        self.assertTrue(solver.aborted)
        self.assertEqual(solver.obs, {})

    def test_missing_start_aborts(self):
        _, solver = simulate('label elsewhere:\n    return\n')
        self.assertTrue(solver.aborted)
        self.assertEqual(solver.obs, {})

    def test_global_recursion_limit_is_restored(self):
        previous = sys.getrecursionlimit()
        simulate(GAME, max_steps=1)
        self.assertEqual(sys.getrecursionlimit(), previous)

    def test_single_available_choice_gets_no_competitive_verdict(self):
        visit = {'vals': {0: (True, True, 1.0, 1.0, False)}, 'sure': {0: True}}
        self.assertEqual(studio.cs_classify_visit(visit)[0], {0: 'NONE'})

    def test_conflicting_visit_classifications_are_not_universal(self):
        visits = [
            {'vals': {0: (True, True, 1., 1., False), 1: (True, True, 0., 0., False)},
             'sure': {0: True, 1: True}},
            {'vals': {0: (True, True, 0., 0., False), 1: (True, True, 1., 1., False)},
             'sure': {0: True, 1: True}},
        ]
        info = studio.cs_aggregate(visits, 2)
        self.assertFalse(any(row['green'] or row['red'] for row in info.values()))


class CurrentPipelineTests(unittest.TestCase):
    def analyze(self, source=GAME, extra=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for name, text in {'script.rpy': source, **(extra or {})}.items():
            (root / name).write_text(text, encoding='utf-8')
        analyzer = studio.RenpyWalkthroughAnalyzer(str(root), options={
            'read_only': True, 'enable_cheat_menu': False, 'remove_rpyc': False}, log_callback=lambda *_: None)
        analyzer.scan_files(auto_extract=False, log_callback=lambda *_: None)
        analyzer.index_labels(log_callback=lambda *_: None)
        menus = []
        for path in analyzer.rpy_files:
            menus.extend(analyzer.analyze_file_menus(path)[1])
        analyzer.all_menus = menus
        analyzer.project_ctx = {'consumed_vars': analyzer.get_all_consumed_variables()}
        for menu in menus:
            menu.project_ctx = analyzer.project_ctx
        analyzer.build_alias_map(log_callback=lambda *_: None)
        cfg = analyzer.build_control_flow_graph()
        analyzer.cfg_unreachable_labels = analyzer.filter_cfg_unreachable(set(cfg.get_unreachable_labels()))
        return analyzer, menus

    def test_read_only_pipeline_returns_current_decisions_without_writing(self):
        analyzer, menus = self.analyze()
        root = Path(analyzer.game_dir)
        def hashes():
            return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in root.rglob('*') if p.is_file()}
        before = hashes()
        self.assertEqual(len(menus), 1)
        result = menus[0].evaluate_choices()
        self.assertEqual(set(result), set(menus[0].choices))
        self.assertTrue(all(isinstance(value, studio.Decision) for value in result.values()))
        self.assertEqual(hashes(), before)

    def test_repeat_uses_current_decision_cache_without_duplicate_log(self):
        analyzer, menus = self.analyze()
        first = menus[0].evaluate_choices()
        log = list(analyzer.decision_log)
        self.assertEqual(menus[0].evaluate_choices(), first)
        self.assertTrue(log)
        self.assertEqual(analyzer.decision_log, log)

    def test_simulation_cache_invalidated_by_source_change(self):
        analyzer, _ = self.analyze()
        first_program, first_solver = studio._cs_get(analyzer)
        self.assertIs(studio._cs_get(analyzer)[1], first_solver)
        path = Path(analyzer.game_dir) / 'script.rpy'
        previous = path.stat()
        path.write_text(GAME.replace('default gym = False', 'default gym = True'), encoding='utf-8')
        os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1_000_000_000))
        program, solver = studio._cs_get(analyzer)
        self.assertIsNot(program, first_program)
        self.assertIsNot(solver, first_solver)
        self.assertIs(program.defaults['gym'], True)

    def test_cross_file_call_target_is_indexed_and_simulated(self):
        source, tail = GAME.split('label check_route:')
        analyzer, _ = self.analyze(source, {'future.rpy': 'label check_route:' + tail})
        program, solver = studio._cs_get(analyzer)
        self.assertIn('check_route', analyzer.labels)
        self.assertIn('dalia_entry', program.labels)
        self.assertFalse(solver.aborted)
        self.assertTrue(solver.obs)

    def test_current_both_dependency_report_does_not_claim_romantic_route_proof(self):
        analyzer, menus = self.analyze()
        analyzer.detect_both_candidates(menus)
        report = analyzer.export_both_report()
        self.assertEqual(report['semantics'], 'source_dependencies_not_inferred_romantic_routes')
        self.assertEqual((Path(analyzer.game_dir) / 'script.rpy').read_text(encoding='utf-8'), GAME)


if __name__ == '__main__':
    unittest.main()
