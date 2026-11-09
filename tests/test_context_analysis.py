"""Relevant state, complete incoming contexts, and conservative joins."""
from pathlib import Path
import sys
import tempfile
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import renpy_walkthrough_studio as studio


def program(source):
    result = studio.CSProgram()
    result.add_file('script.rpy', source.splitlines(True))
    return result


def branching_source(count=14):
    lines = ['default gate = False', 'label start:']
    for index in range(count):
        lines += ['    menu:', '        "On":', f'            $ old{index} = True',
                  '        "Off":', f'            $ old{index} = False',
                  f'    if old{index}:', '        pass']
    lines += ['    menu:', '        "Safe":', '            return', '        "Terminal":',
              '            $ renpy.quit()']
    return '\n'.join(lines) + '\n'


class RelevantStateTests(unittest.TestCase):
    def test_rhs_dependencies_are_not_lost(self):
        prog = program('''default seed = True
label start:
    $ copied = seed
    $ gate = copied
    menu:
        "A":
            if gate:
                return
            $ renpy.quit()
        "B":
            $ renpy.quit()
''')
        solver = studio.CSSolver(prog)
        self.assertTrue(solver.run_global())
        visit = next(iter(solver.obs.values()))[0]
        self.assertTrue(visit['vals'][0][0])
        self.assertFalse(visit['vals'][0][4])
        self.assertTrue({'seed', 'copied', 'gate'} <= prog.consumed)

    def test_dead_history_does_not_explode_state_space(self):
        prog = program(branching_source())
        solver = studio.CSSolver(prog, max_steps=6000)
        self.assertTrue(solver.run_global())
        last = max(prog.menus, key=lambda mid: mid[1])
        self.assertEqual(studio.cs_classify_visit(solver.obs[last][0])[0], {0: 'GREEN', 1: 'RED'})
        self.assertLess(solver.steps, 6000)

    def test_projection_matches_full_state_reference(self):
        source = branching_source(5)
        projected = studio.CSSolver(program(source))
        reference = studio.CSSolver(program(source), project_state=False)
        self.assertTrue(projected.run_global())
        self.assertTrue(reference.run_global())
        for mid in reference.obs:
            expected = studio.cs_aggregate(reference.obs[mid], 2)
            actual = studio.cs_aggregate(projected.obs[mid], 2)
            for ci in expected:
                for key in ('green', 'red', 'safe_certain', 'unresolved'):
                    self.assertEqual(actual[ci][key], expected[ci][key], (mid, ci, key))
        self.assertLess(projected.steps, reference.steps)

    def test_caller_dependencies_are_kept_inside_callee(self):
        prog = program('''default seed = False
label start:
    menu:
        "A":
            $ seed = True
        "B":
            $ seed = False
    call helper
    if result:
        return
    $ renpy.quit()
label helper:
    $ result = seed
    return
''')
        solver = studio.CSSolver(prog)
        self.assertTrue(solver.run_global())
        visit = solver.obs[('script.rpy', 2)][0]
        self.assertTrue(visit['vals'][0][0])
        self.assertFalse(visit['vals'][1][1])

    def test_memo_keys_preserve_scalar_types_and_unknown_identity(self):
        self.assertNotEqual(studio.CSSolver._skey({'v': True}), studio.CSSolver._skey({'v': 1}))
        self.assertNotEqual(studio.CSSolver._skey({'v': studio.CS_UNK}), studio.CSSolver._skey({'v': '\0U'}))
        self.assertNotEqual(studio.CSSolver._skey({'v': 0.0}), studio.CSSolver._skey({'v': -0.0}))

    def test_cycle_is_not_proof_of_safe_termination(self):
        prog = program('label start:\n    menu:\n        "Again":\n            jump start\n        "Quit":\n            $ renpy.quit()\n')
        solver = studio.CSSolver(prog)
        self.assertTrue(solver.run_global())
        self.assertFalse(solver.obs[('script.rpy', 1)][-1]['vals'][0][0])

    def test_bool_and_integer_do_not_share_a_callee_result(self):
        prog = program('''label start:
    menu:
        "Bool":
            $ value = True
        "Int":
            $ value = 1
    call helper
    return
label helper:
    if value is True:
        return
    $ renpy.quit()
''')
        solver = studio.CSSolver(prog)
        self.assertTrue(solver.run_global())
        visit = solver.obs[('script.rpy', 1)][0]
        self.assertTrue(visit['vals'][0][0])
        self.assertFalse(visit['vals'][1][1])

    def test_all_hidden_menu_follows_the_real_continuation(self):
        prog = program('''label start:
    menu:
        "Hidden" if False:
            return
    $ renpy.quit()
''')
        solver = studio.CSSolver(prog)
        self.assertEqual(solver.solve(prog.labels['start'], 0, {}, (), 0), studio.CS_DEAD)

    def test_maybe_hidden_menu_cannot_prove_inevitable_death(self):
        prog = program('''label start:
    menu:
        "Conditional menu":
            menu:
                "Terminal" if missing:
                    $ renpy.quit()
            return
        "Safe":
            return
''')
        solver = studio.CSSolver(prog)
        self.assertTrue(solver.run_global())
        visit = solver.obs[('script.rpy', 1)][0]
        self.assertTrue(visit['vals'][0][1])
        self.assertEqual(studio.cs_classify_visit(visit)[0], {0: 'NONE', 1: 'NONE'})

    def test_generated_projection_equivalence_and_context_soundness(self):
        rng = random.Random(20261109)
        atoms = ('False', 'True', '0', '1', '2', '-1', '0.0', "'x'", "''")
        expressions = ('a or b', 'a and b', 'a == b', 'a is True', 'not b', 'a + b')
        for case in range(128):
            values = [rng.choice(atoms) for _ in range(4)]
            expression = rng.choice(expressions)
            source = f'''label start:
    menu:
        "First":
            $ a = {values[0]}
            $ b = {values[1]}
        "Second":
            $ a = {values[2]}
            $ b = {values[3]}
    call helper
    menu:
        "Guarded":
            if gate:
                return
            $ renpy.quit()
        "Terminal":
            $ renpy.quit()
label helper:
    $ gate = {expression}
    return
'''
            with self.subTest(case=case, expression=expression, values=values):
                prog = program(source)
                projected = studio.CSSolver(prog)
                reference = studio.CSSolver(program(source), project_state=False)
                self.assertTrue(projected.run_global())
                self.assertTrue(reference.run_global())
                self.assertEqual(set(projected.obs), set(reference.obs))
                for mid in reference.obs:
                    exact = studio.cs_aggregate(reference.obs[mid], 2)
                    actual = studio.cs_aggregate(projected.obs[mid], 2)
                    for ci in exact:
                        for key in ('green', 'red', 'safe_certain', 'unresolved'):
                            self.assertEqual(actual[ci][key], exact[ci][key], (mid, ci, key))
                    contextual = studio.cs_run_contextual(prog, mid)
                    self.assertTrue(contextual['complete'])
                    abstract = studio.cs_aggregate(contextual['visits'], 2)
                    for ci in abstract:
                        for key in ('green', 'red', 'safe_certain'):
                            if abstract[ci][key]:
                                self.assertTrue(exact[ci][key], ('unsound abstract proof', mid, ci, key))


class IncomingContextTests(unittest.TestCase):
    def collect(self, source, **limits):
        prog = program(source)
        incoming = studio.CSIncoming(prog, **limits)
        incoming.run()
        return prog, incoming

    def test_prior_assignments_and_transitive_rhs_reach_menu(self):
        prog, incoming = self.collect('''default seed = True
label start:
    $ copied = seed
    $ gate = copied
    menu:
        "A" if gate:
            return
        "B":
            $ renpy.quit()
''')
        self.assertTrue(incoming.complete)
        mid = next(iter(prog.menus))
        contexts = incoming.contexts(mid)
        self.assertEqual(len(contexts), 1)
        self.assertIs(contexts[0]['state']['gate'], True)

    def test_all_previous_player_choices_are_joined_not_sampled(self):
        prog, incoming = self.collect('''label start:
    menu:
        "A":
            $ gate = True
        "B":
            $ gate = False
    menu:
        "Guarded" if gate:
            return
        "Other":
            $ renpy.quit()
''')
        self.assertTrue(incoming.complete)
        mid = max(prog.menus, key=lambda key: key[1])
        contexts = incoming.contexts(mid)
        self.assertEqual(len(contexts), 1)
        self.assertIs(contexts[0]['state'].get('gate', studio.CS_UNK), studio.CS_UNK)

    def test_caller_return_context_is_not_invented(self):
        prog, incoming = self.collect('''label start:
    $ gate = True
    call helper
    $ renpy.quit()
label helper:
    menu:
        "A":
            return
        "B":
            return
''')
        self.assertTrue(incoming.complete)
        mid = next(iter(prog.menus))
        self.assertTrue(incoming.contexts(mid)[0]['cont'])
        result = studio.cs_run_contextual(prog, mid)
        self.assertTrue(result['complete'])
        self.assertTrue(all(not val[1] for visit in result['visits'] for val in visit['vals'].values()))

    def test_two_callers_keep_distinct_continuations(self):
        prog, incoming = self.collect('''label start:
    menu:
        "Safe caller":
            call helper
            return
        "Terminal caller":
            call helper
            $ renpy.quit()
label helper:
    menu:
        "A":
            return
        "B":
            return
''')
        mid = max(prog.menus, key=lambda key: key[1])
        self.assertEqual(len(incoming.contexts(mid)), 2)
        result = studio.cs_run_contextual(prog, mid)
        self.assertTrue(result['complete'])
        info = studio.cs_aggregate(result['visits'], 2)
        self.assertFalse(any(row['green'] or row['red'] or row['safe_certain'] for row in info.values()))

    def test_loop_converges_to_unknown_instead_of_unrolling_forever(self):
        prog, incoming = self.collect('''default n = 0
label start:
    $ n += 1
    menu:
        "Again":
            jump start
        "Exit" if n > 2:
            return
''', max_steps=1000)
        self.assertTrue(incoming.complete)
        mid = next(iter(prog.menus))
        self.assertIs(incoming.contexts(mid)[0]['state'].get('n', studio.CS_UNK), studio.CS_UNK)

    def test_budget_or_opaque_effect_cannot_certify_incoming_coverage(self):
        for source, limits in ((branching_source(5), {'max_steps': 1}),
                               ('label start:\n    $ external()\n    menu:\n        "A":\n            return\n        "B":\n            return\n', {}),
                               ('label start:\n    jump expression target\n', {})):
            with self.subTest(source=source):
                _, incoming = self.collect(source, **limits)
                self.assertFalse(incoming.complete)

    def test_unknown_initial_input_is_not_replaced_with_default_zero(self):
        prog, incoming = self.collect('''label start:
    menu:
        "A" if missing:
            return
        "B":
            return
''')
        self.assertTrue(incoming.complete)
        result = studio.cs_run_contextual(prog, next(iter(prog.menus)))
        self.assertFalse(result['visits'][0]['sure'][0])

    def test_partial_results_are_not_promoted_after_continuation_abort(self):
        prog = program(branching_source(5))
        result = studio.cs_run_contextual(prog, next(iter(prog.menus)), max_steps=1)
        self.assertFalse(result['complete'])
        self.assertFalse(result['visits'])

    def test_context_cache_invalidates_when_another_file_is_added(self):
        prog = program('label start:\n    menu:\n        "A":\n            return\n        "B":\n            return\n')
        first = studio.cs_run_contextual(prog, next(iter(prog.menus)))
        self.assertTrue(first['complete'])
        old = prog._context_entry
        prog.add_file('extra.rpy', ['label extra:\n', '    return\n'])
        studio.cs_run_contextual(prog, next(iter(prog.menus)))
        self.assertIsNot(prog._context_entry, old)

    def test_all_hidden_possibility_reaches_a_later_menu(self):
        prog, incoming = self.collect('''label start:
    $ known = True
    menu:
        "Maybe visible" if missing:
            return
    menu:
        "A" if known:
            return
        "B":
            return
''')
        self.assertTrue(incoming.complete)
        mid = max(prog.menus, key=lambda key: key[1])
        self.assertIs(incoming.contexts(mid)[0]['state']['known'], True)

    def test_hidden_menu_is_a_complete_unavailable_context_not_a_fake_choice(self):
        prog = program('label start:\n    menu:\n        "Hidden" if False:\n            return\n    return\n')
        result = studio.cs_run_contextual(prog, next(iter(prog.menus)))
        self.assertTrue(result['complete'])
        self.assertEqual(result['visits'][0]['vals'], {})

    def test_unknown_initialization_and_unsupported_signatures_block_coverage(self):
        sources = (
            'init python:\n    external()\nlabel start:\n    return\n',
            'label start(value=True):\n    return\n',
            'label start:\n    call helper(1)\n    return\nlabel helper(value):\n    return\n',
            'label start:\n    return external()\n',
            'label start:\n    menu:\n        set seen\n        "A":\n            return\n',
        )
        for source in sources:
            with self.subTest(source=source):
                _, incoming = self.collect(source)
                self.assertFalse(incoming.complete)

    def test_pure_function_declaration_does_not_execute_its_body(self):
        _, incoming = self.collect('init python:\n    def unused():\n        external()\nlabel start:\n    return\n')
        self.assertTrue(incoming.complete)

    def test_lost_correlations_reduce_precision_not_create_proof(self):
        prog = program('''label start:
    menu:
        "First":
            $ a = True
            $ b = False
        "Second":
            $ a = False
            $ b = True
    menu:
        "A":
            if a and b:
                $ renpy.quit()
            return
        "B":
            $ renpy.quit()
''')
        mid = max(prog.menus, key=lambda key: key[1])
        result = studio.cs_run_contextual(prog, mid)
        self.assertTrue(result['complete'])
        info = studio.cs_aggregate(result['visits'], 2)
        self.assertFalse(info[0]['green'])
        self.assertFalse(info[0]['red'])

    def test_opaque_path_after_observed_menu_is_not_ignored(self):
        _, incoming = self.collect('label start:\n    menu:\n        "A":\n            pass\n        "B":\n            pass\n    $ external()\n')
        self.assertFalse(incoming.complete)

    def test_recursion_and_global_recursion_limit_are_bounded(self):
        previous = sys.getrecursionlimit()
        prog = program('label start:\n    call start\n')
        incoming = studio.CSIncoming(prog, max_steps=100, max_depth=10)
        incoming.run()
        self.assertFalse(incoming.complete)
        self.assertEqual(incoming.reason, 'context_depth')
        self.assertEqual(sys.getrecursionlimit(), previous)

    def test_contextual_result_can_replace_missing_global_not_missing_proof(self):
        source = 'label start:\n    $ gate = True\n    menu:\n        "A":\n            if gate:\n                return\n            $ renpy.quit()\n        "B":\n            $ renpy.quit()\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'script.rpy'
            path.write_text(source, encoding='utf-8')
            analyzer = studio.RenpyWalkthroughAnalyzer(directory, options={'read_only': True})
            analyzer.rpy_files = [str(path)]
            menu = analyzer.analyze_file_menus(str(path))[1][0]
            prog = studio.CSProgram()
            prog.add_file(studio._cs_norm(path), source.splitlines(True))
            failed = studio.CSSolver(prog)
            failed.aborted = True
            with patch.object(studio, '_cs_get', return_value=(prog, failed)):
                info = studio._cs_menu_info(menu)
            self.assertEqual(info['origin'], 'incoming_contexts')
            self.assertEqual(info['mode'], 'global')
            self.assertTrue(info['coverage']['complete'])
            self.assertTrue(info['info'][0]['green'])
            self.assertTrue(info['info'][1]['red'])

    def test_completed_global_with_opaque_reentry_does_not_certify_coverage(self):
        source = '''label start:
    menu:
        "Known":
            jump target
        "Opaque":
            $ external()
            return
label target:
    menu:
        "Safe":
            return
        "Terminal":
            $ renpy.quit()
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'script.rpy'
            path.write_text(source, encoding='utf-8')
            analyzer = studio.RenpyWalkthroughAnalyzer(directory, options={'read_only': True})
            analyzer.rpy_files = [str(path)]
            menu = analyzer.analyze_file_menus(str(path))[1][-1]
            info = studio._cs_menu_info(menu)
            self.assertEqual(info['mode'], 'partial')
            self.assertFalse(info['coverage']['complete'])
            result = studio._cs_enforce(menu, dict.fromkeys(menu.choices, studio.Decision('NONE')), None)
            self.assertTrue(all(str(value) == 'NONE' for value in result.values()))

    def test_global_result_cannot_keep_a_heuristic_without_safe_alternative(self):
        choices = [studio.RenpyChoice('', i, 8, '"', str(i), '', '') for i in range(2)]
        for choice in choices:
            choice.is_death = True
        visit = {'vals': {0: studio.CS_DEAD, 1: studio.CS_DEAD}, 'sure': {0: True, 1: True}}
        info = {'mode': 'global', 'idx': dict(zip(choices, range(2))), 'info': studio.cs_aggregate([visit], 2)}
        menu = SimpleNamespace(choices=choices, analyzer=None)
        with patch.object(studio, '_cs_menu_info', return_value=info):
            result = studio._cs_enforce(menu, dict.fromkeys(choices, studio.Decision('RED')), None)
        self.assertTrue(all(str(value) == 'NONE' for value in result.values()))
        self.assertTrue(all(choice.decision_rule == 'CS_SIM_NOT_PROVEN' for choice in choices))

    def test_rebound_noop_and_display_calls_do_not_gain_false_certainty(self):
        for prefix in ('$ print = external', '$ renpy.notify = external', '$ renpy.quit = external',
                       'show expression external()', 'with external()', 'pause external()'):
            with self.subTest(prefix=prefix):
                source = 'label start:\n    ' + prefix + '\n    menu:\n        "A":\n            return\n        "B":\n            $ renpy.quit()\n'
                prog, incoming = self.collect(source)
                self.assertFalse(incoming.complete)
                solver = studio.CSSolver(prog)
                self.assertTrue(solver.run_global())
                self.assertTrue(all(not value[0] for visits in solver.obs.values()
                                    for visit in visits for value in visit['vals'].values()))

    def test_literal_pause_remains_supported_without_executing_game_python(self):
        _, incoming = self.collect('label start:\n    pause(.01)\n    pause 0.1\n    return\n')
        self.assertTrue(incoming.complete)

    def test_default_store_alias_reads_and_writes_share_the_same_state(self):
        for write, read in (('store.gate', 'gate'), ('renpy.store.gate', 'gate'),
                            ('gate', 'store.gate'), ('gate', 'renpy.store.gate')):
            source = f'''default gate = False
label start:
    $ {write} = True
    menu:
        "A":
            if {read}:
                return
            $ renpy.quit()
        "B":
            $ renpy.quit()
'''
            with self.subTest(write=write, read=read):
                prog = program(source)
                solver = studio.CSSolver(prog)
                self.assertTrue(solver.run_global())
                visit = next(iter(solver.obs.values()))[0]
                self.assertTrue(visit['vals'][0][0])
                contextual = studio.cs_run_contextual(prog, next(iter(prog.menus)))
                self.assertTrue(contextual['complete'])
                self.assertTrue(contextual['visits'][0]['vals'][0][0])

    def test_store_alias_rhs_dependency_is_transitive(self):
        prog = program('''default seed = True
label start:
    $ store.copied = renpy.store.seed
    $ gate = store.copied
    menu:
        "A":
            if gate:
                return
            $ renpy.quit()
        "B":
            $ renpy.quit()
''')
        contextual = studio.cs_run_contextual(prog, next(iter(prog.menus)))
        self.assertTrue(contextual['complete'])
        self.assertTrue(contextual['visits'][0]['vals'][0][0])

    def test_unmodelled_local_labels_and_named_python_stores_block_coverage(self):
        for source in ('label start:\n    pass\nlabel .local:\n    $ renpy.quit()\n',
                       'label start:\n    python in other:\n        gate = True\n    return\n'):
            with self.subTest(source=source):
                _, incoming = self.collect(source)
                self.assertFalse(incoming.complete)

    def test_unknown_default_initializer_is_not_a_known_starting_state(self):
        for declaration in ('default gate = external()', 'define gate = external()',
                            'define speaker = Character("Name", callback=external)'):
            with self.subTest(declaration=declaration):
                _, incoming = self.collect(declaration + '\nlabel start:\n    return\n')
                self.assertFalse(incoming.complete)

    def test_plain_native_character_declaration_remains_supported(self):
        _, incoming = self.collect('define s = Character(_("Name"), color="#fff")\nlabel start:\n    s "Text"\n    return\n')
        self.assertTrue(incoming.complete)

    def test_persistent_default_is_not_assumed_to_reset_on_new_game(self):
        prog = program('''default persistent.gate = True
label start:
    menu:
        "A":
            if persistent.gate:
                return
            $ renpy.quit()
        "B":
            $ renpy.quit()
''')
        result = studio.cs_run_contextual(prog, next(iter(prog.menus)))
        self.assertTrue(result['complete'])
        self.assertFalse(result['visits'][0]['vals'][0][0])
        self.assertFalse(studio.cs_aggregate(result['visits'], 2)[0]['green'])


if __name__ == '__main__':
    unittest.main()
