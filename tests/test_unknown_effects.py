"""Unknown Python effects must not establish terminal safety or death."""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import renpy_walkthrough_studio as studio


def simulate(body='', prefix='', ending='jump death'):
    source = ('label start:\n' + prefix + '    menu:\n        "Unknown":\n' +
              ''.join('            ' + line + '\n' for line in body.splitlines()) +
              '            ' + ending + '\n        "Safe":\n            return\n'
              'label death:\n    $ renpy.quit()\n')
    program = studio.CSProgram()
    program.add_file('script.rpy', source.splitlines(True))
    solver = studio.CSSolver(program)
    assert solver.run_global()
    mid = next(iter(program.menus))
    return program, solver, mid, solver.obs[mid][0]


class UnknownEffectsTests(unittest.TestCase):
    def assert_unknown(self, value):
        self.assertEqual(value, (False, True, 0., studio.CS_INF, True))

    def test_unknown_statement_before_death_is_not_red(self):
        _, _, _, visit = simulate('$ external_change()')
        self.assert_unknown(visit['vals'][0])
        self.assertEqual(studio.cs_classify_visit(visit)[0], {0: 'NONE', 1: 'NONE'})

    def test_unknown_statement_before_return_is_not_safe(self):
        _, _, _, visit = simulate('$ external_change()', ending='return')
        self.assert_unknown(visit['vals'][0])

    def test_all_terminal_paths_respect_taint(self):
        for ending in ('return', 'jump death', '$ renpy.quit()', '"You died"',
                       'jump expression destination', 'call death'):
            with self.subTest(ending=ending):
                self.assert_unknown(simulate('$ external_change()', ending=ending)[3]['vals'][0])

    def test_call_return_and_nested_menu_preserve_effects(self):
        source = '''label start:
    menu:
        "A":
            call helper
            menu:
                "Inner A":
                    jump death
                "Inner B":
                    return
        "B":
            return
label helper:
    $ external_change()
    return
label death:
    $ renpy.quit()
'''
        program = studio.CSProgram()
        program.add_file('script.rpy', source.splitlines(True))
        solver = studio.CSSolver(program)
        self.assertTrue(solver.run_global())
        self.assert_unknown(solver.obs[('script.rpy', 1)][0]['vals'][0])
        for value in solver.obs[('script.rpy', 4)][0]['vals'].values():
            self.assert_unknown(value)

    def test_unknown_before_menu_reaches_both_choices(self):
        _, _, _, visit = simulate(prefix='    $ external_change()\n')
        for value in visit['vals'].values():
            self.assert_unknown(value)

    def test_unused_rhs_and_noop_arguments_are_not_ignored(self):
        for body in ('$ unused = external_change()', '$ print(external_change())',
                     '$ renpy.notify(message=external_change())', '$ print_mutation()',
                     '$ renpy.pause_mutation()', '$ renpy.jump("death", external_change())',
                     '$ renpy.quit(external_change())'):
            with self.subTest(body=body):
                self.assert_unknown(simulate(body)[3]['vals'][0])

    def test_condition_effects_are_unknown(self):
        for body in ('if external_change():\n    pass',
                     'if missing and external_change():\n    pass',
                     'if 0 < 1 < external_change():\n    pass'):
            with self.subTest(body=body):
                self.assert_unknown(simulate(body)[3]['vals'][0])

    def test_unexecuted_calls_do_not_taint(self):
        for body in ('$ unused = 2 or external_change()',
                     '$ unused = False and external_change()',
                     '$ unused = 1 if True else external_change()',
                     'if False and external_change():\n    pass',
                     'if 2 < 1 < external_change():\n    pass',
                     '$ print(2 or external_change())', '$ renpy.pause(0)'):
            with self.subTest(body=body):
                self.assertEqual(simulate(body)[3]['vals'][0], studio.CS_DEAD)

    def test_clean_death_retains_classification(self):
        _, _, _, visit = simulate()
        self.assertEqual(studio.cs_classify_visit(visit)[0], {0: 'RED', 1: 'GREEN'})

    def test_local_return_is_not_proven_safe_in_unseen_caller(self):
        program, _, mid, _ = simulate()
        visits = studio.cs_run_local(program, mid)
        self.assert_unknown(visits[0]['vals'][1])
        self.assertEqual(studio.cs_classify_visit(visits[0])[0], {0: 'NONE', 1: 'NONE'})

    def test_unknown_syntax_remains_uncertain(self):
        for body in ('$ invalid python !', 'python:\n    while flag:\n        external_change()'):
            self.assert_unknown(simulate(body)[3]['vals'][0])

    def test_fallthrough_to_death_respects_taint(self):
        program = studio.CSProgram()
        program.add_file('script.rpy', 'label start:\n    $ external_change()\nlabel death:\n    $ renpy.quit()\n'.splitlines(True))
        solver = studio.CSSolver(program)
        self.assert_unknown(solver.solve(program.labels['start'], 0, {}, (), 0))

    def test_unreachable_statements_and_elif_do_not_taint(self):
        visit = simulate('if True:\n    jump death\nelif external_change():\n    pass\n$ external_change()')[3]
        self.assertEqual(visit['vals'][0][:2], (False, False))
        self.assertFalse(visit['vals'][0][4])
        # Existing condition-gain accounting is deliberately a separate task.

    def test_effect_checker_short_circuit_and_unknown_guards(self):
        for expression, expected in (
                ('True or external()', False), ('False and external()', False),
                ('missing or external()', True), ('external() if missing else 0', True),
                ('0 if True else external()', False), ('3 < 2 < external()', False),
                ('missing < 2 < external()', True), ('(changed := 1)', True)):
            with self.subTest(expression=expression):
                node = ast.parse(expression, mode='eval').body
                self.assertIs(studio._cs_expr_effect(node, {}), expected)

    def test_missing_scalar_is_not_arbitrary_python_effect(self):
        visit = simulate('$ unused = missing')[3]
        self.assertEqual(visit['vals'][0], studio.CS_DEAD)

    def test_unknown_pure_condition_can_still_prove_all_paths_dead(self):
        visit = simulate('if missing:\n    jump death\nelse:\n    jump death')[3]
        self.assertFalse(visit['vals'][0][1])
        self.assertEqual(studio.cs_classify_visit(visit)[0][0], 'RED')

    def test_no_game_callable_is_executed(self):
        with patch('os.system', side_effect=AssertionError('game code executed')) as command:
            self.assert_unknown(simulate('$ unused = __import__("os").system("anything")')[3]['vals'][0])
        command.assert_not_called()

    def test_taint_survives_call_return_and_memo(self):
        program, solver, _, _ = simulate('$ external_change()')
        state = {studio._CS_TAINT: True}
        bid = program.labels['death']
        self.assertEqual(solver.solve(bid, 0, {}, (), 0), studio.CS_DEAD)
        for _ in range(2):
            self.assert_unknown(solver.solve(bid, 0, state, (), 0))
        key = (bid, 0, solver._skey(state), ())
        solver.memo.pop(key)
        solver.inprog.add(key)
        self.assert_unknown(solver.solve(bid, 0, state, (), 0))

    def test_visibility_effect_applies_to_all_choices(self):
        source = ('label start:\n    menu:\n        "A" if external_change():\n'
                  '            jump death\n        "B":\n            return\n'
                  'label death:\n    return\n')
        program = studio.CSProgram()
        program.add_file('script.rpy', source.splitlines(True))
        solver = studio.CSSolver(program)
        self.assertTrue(solver.run_global())
        for value in solver.obs[('script.rpy', 1)][0]['vals'].values():
            self.assert_unknown(value)


class EnforcementUnknownTests(unittest.TestCase):
    def enforce(self, visits, mode, old='RED'):
        choice = studio.RenpyChoice('script.rpy', 2, 8, '"', 'A', '', '"A":')
        choice.is_death = True
        menu = SimpleNamespace(choices=[choice], analyzer=None)
        info = {'idx': {choice: 0}, 'info': studio.cs_aggregate(visits, 2), 'mode': mode}
        with patch.object(studio, '_cs_menu_info', return_value=info):
            result = studio._cs_enforce(menu, {choice: studio.Decision(old)}, None)
        return str(result[choice]), choice

    def test_unknown_effect_overrides_old_fatal_red(self):
        visit = simulate('$ external_change()')[3]
        result, choice = self.enforce([visit], 'global')
        self.assertEqual(result, 'NONE')
        self.assertEqual(choice.decision_rule, 'CS_SIM_UNRESOLVED')
        self.assertTrue(choice.is_death)  # Retain risk evidence, not a proven verdict.

    def test_local_simulation_cannot_establish_global_red(self):
        result, _ = self.enforce([simulate()[3]], 'local')
        self.assertEqual(result, 'NONE')

    def test_clean_global_death_remains_red(self):
        self.assertEqual(self.enforce([simulate()[3]], 'global')[0], 'RED')

    def test_mixed_visits_do_not_keep_old_fatal_red(self):
        visits = [simulate()[3], simulate('$ external_change()')[3]]
        self.assertEqual(self.enforce(visits, 'global')[0], 'NONE')

    def test_unknown_safe_option_does_not_keep_heuristic_green(self):
        visit = simulate('$ external_change()', ending='return')[3]
        choice = studio.RenpyChoice('script.rpy', 2, 8, '"', 'A', '', '"A":')
        menu = SimpleNamespace(choices=[choice], analyzer=None)
        info = {'idx': {choice: 0}, 'info': studio.cs_aggregate([visit], 2), 'mode': 'global'}
        with patch.object(studio, '_cs_menu_info', return_value=info):
            self.assertEqual(str(studio._cs_enforce(menu, {choice: studio.Decision('GREEN')}, None)[choice]), 'NONE')


if __name__ == '__main__':
    unittest.main()
