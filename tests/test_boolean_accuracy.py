"""Exact Python and/or values, short-circuiting and conservative unknowns."""
import ast
from itertools import product
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import renpy_walkthrough_studio as studio


def evaluate(expression, state=None):
    return studio.cs_ev(ast.parse(expression, mode='eval').body, {} if state is None else state)


class BooleanOperandAccuracyTests(unittest.TestCase):
    def assert_matches_python(self, expression, state=None):
        state = {} if state is None else state
        expected = eval(compile(expression, '<trusted-test>', 'eval'), {'__builtins__': {}}, state)
        actual = evaluate(expression, state)
        self.assertEqual(actual, expected, expression)
        self.assertIs(type(actual), type(expected), expression)

    def test_known_scalar_operand_matrix(self):
        literals = ('None', 'False', 'True', '0', '1', '2', '-3', '0.0', '-0.0',
                    '2.5', "''", "'route'", "'other'")
        for left, right, operator in product(literals, literals, ('and', 'or')):
            expression = f'({left}) {operator} ({right})'
            with self.subTest(expression=expression):
                self.assert_matches_python(expression)

    def test_nested_generated_expressions_match_python(self):
        rng = random.Random(20261109)
        atoms = ('a', 'b', 'c', 'None', 'False', 'True', '0', '2', "''", "'route'")
        state = {'a': -2, 'b': 0.0, 'c': 'luna'}
        for _ in range(300):
            expression = rng.choice(atoms)
            for _ in range(rng.randrange(1, 5)):
                expression = f'({expression}) {rng.choice(("and", "or"))} ({rng.choice(atoms)})'
            with self.subTest(expression=expression):
                self.assert_matches_python(expression, state)

    def test_values_feed_arithmetic_and_comparisons_correctly(self):
        for expression in ('(2 or 0) + 3', '(2 and 7) >= 5', '(0 and 7) is False',
                           '(None or 2) * 3', "('' or 'route') == 'route'",
                           '(None and 1) is None', 'not (0 or 2)',
                           '(2 or 0) if True else unsupported()'):
            with self.subTest(expression=expression):
                self.assert_matches_python(expression)

    def test_unknowns_are_not_replaced_by_later_known_operands(self):
        for expression in ('missing or 1', 'missing and 0', 'missing or True',
                           'missing and False', '0 or missing or 7',
                           '2 and missing and 0', '(missing or 2) >= 1',
                           '(missing and 0) is False'):
            with self.subTest(expression=expression):
                self.assertIs(evaluate(expression), studio.CS_UNK)

    def test_unreachable_operands_are_not_evaluated(self):
        for expression, expected in (('2 or unsupported()', 2), ('0 and unsupported()', 0),
                                     ('True or missing', True), ('None and missing', None)):
            with self.subTest(expression=expression):
                root = ast.parse(expression, mode='eval').body
                real = studio.cs_ev
                with patch.object(studio, 'cs_ev', wraps=real) as evaluate_node:
                    result = studio.cs_ev(root, {})
                self.assertEqual(result, expected)
                self.assertIs(type(result), type(expected))
                self.assertEqual(evaluate_node.call_count, 2)  # BoolOp and first constant only.

    def test_tainted_variables_stay_unknown(self):
        state = {'points': 2, studio._CS_TAINT: True}
        self.assertIs(evaluate('points or 1', state), studio.CS_UNK)
        self.assertEqual(evaluate('7 or points', state), 7)

    def test_failed_truth_test_is_unknown_not_an_exception(self):
        class InvalidTruth:
            def __bool__(self):
                raise ValueError('cannot determine truth')
        self.assertIs(evaluate('value or 1', {'value': InvalidTruth()}), studio.CS_UNK)

    def test_unknown_operand_does_not_evaluate_suffix(self):
        root = ast.parse('missing or unsupported()', mode='eval').body
        real = studio.cs_ev
        with patch.object(studio, 'cs_ev', wraps=real) as evaluate_node:
            self.assertIs(studio.cs_ev(root, {}), studio.CS_UNK)
        self.assertEqual(evaluate_node.call_count, 2)


class BooleanSimulationAccuracyTests(unittest.TestCase):
    SOURCE = '''default points = 0
label start:
    menu:
        "First":
            $ points = VALUE
        "Second":
            $ points = 0
    if points >= 2:
        "Unlocked"
    return
'''

    def visit(self, value, source=None):
        program = studio.CSProgram()
        program.add_file('script.rpy', (self.SOURCE if source is None else source).replace('VALUE', value).splitlines(True))
        solver = studio.CSSolver(program)
        self.assertTrue(solver.run_global())
        return solver.obs[('script.rpy', 2)][0]

    def test_numeric_boolean_result_reaches_real_threshold(self):
        source = self.SOURCE.replace('        "Unlocked"', '        return\n    else:\n        $ renpy.quit()')
        visit = self.visit('2 or 0', source)
        self.assertTrue(visit['vals'][0][0])
        self.assertFalse(visit['vals'][1][1])
        self.assertEqual(visit['vals'][0][2:4], (0., 0.))
        self.assertEqual(visit['vals'][1][2:4], (0., 0.))
        self.assertFalse(visit['vals'][0][4])
        # Safety follows executable terminals, not an arbitrary condition bonus.
        self.assertEqual(studio.cs_classify_visit(visit)[0], {0: 'GREEN', 1: 'RED'})

    def test_unknown_boolean_result_cannot_prove_threshold_gain(self):
        visit = self.visit('missing or 2')
        self.assertTrue(visit['vals'][0][4])
        self.assertEqual(studio.cs_classify_visit(visit)[0], {0: 'NONE', 1: 'NONE'})


if __name__ == '__main__':
    unittest.main()
