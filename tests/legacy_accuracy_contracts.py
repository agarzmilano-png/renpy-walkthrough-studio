"""Preserved contracts for the removed Engine/guide API, not ContractSim.

Imported by test_accuracy so unavailable legacy coverage is reported as skipped
rather than silently dropped or incorrectly translated into heuristic verdicts.
"""
import os
import sys
import tempfile
import unittest
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import renpy_walkthrough_studio as studio

LEGACY_API = (
    'Engine', 'UNKNOWN', 'evaluate', 'extract_guide_contracts_from_analyzer',
    'load_guide_contracts', 'match_guide_menu', 'apply_guide_to_rows', 'guide_choice_signals',
)
MISSING_LEGACY_API = tuple(name for name in LEGACY_API if not hasattr(studio, name))
globals().update({name: getattr(studio, name, None) for name in LEGACY_API})
from regression_check import load_studio


FIXTURES = os.path.join(os.path.dirname(__file__), 'accuracy_fixtures')
with open(os.path.join(FIXTURES, 'dalia_zero_points.rpy'), encoding='utf-8') as f:
    GAME = f.read()


SCREEN_GAME = '''default gym = False
label start:
    call screen gym_choice
    jump check_route

screen gym_choice():
    textbutton "Spor salonuna git":
        action [SetVariable("gym", True), Jump("gym_path")]
    textbutton "Gitme":
        action Jump("skip_path")

label gym_path:
    jump check_route

label skip_path:
    jump check_route

label check_route:
    if gym:
        jump dalia_entry
    jump ending

label dalia_entry:
    "Dalia"
    return

label ending:
    "Son"
    return
'''


@unittest.skipIf(bool(MISSING_LEGACY_API),
                 'Removed legacy API: ' + ', '.join(MISSING_LEGACY_API))
class LegacyAccuracyContractTests(unittest.TestCase):
    def screen_analyze(self, source=SCREEN_GAME, routes=None, **kwargs):
        engine = Engine({'script.rpy': source.splitlines(True)},
                        {'dalia': ['dalia_entry']} if routes is None else routes, **kwargs)
        lines = source.splitlines()
        screen_line = next(i for i, s in enumerate(lines) if s.startswith('screen '))
        button_lines = [i for i, s in enumerate(lines)
                        if s.strip().startswith('textbutton ') and i > screen_line]
        return engine, engine.analyze_menu('script.rpy', screen_line, button_lines)['choices']

    def test_screen_jump_and_set_variable(self):
        _, rows = self.screen_analyze()
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])

    def test_screen_source_function_action(self):
        source = '''init python:
    def set_gym(value):
        store.gym = value
''' + SCREEN_GAME.replace(
            'action [SetVariable("gym", True), Jump("gym_path")]',
            'action [Function("set_gym", True), Jump("gym_path")]')
        _, rows = self.screen_analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])

    def test_screen_unsupported_action_is_unknown(self):
        source = SCREEN_GAME.replace(
            'action [SetVariable("gym", True), Jump("gym_path")]',
            'action [Function("unmodeled_external"), Jump("gym_path")]')
        _, rows = self.screen_analyze(source)
        self.assertTrue(all(r['verdict'] == 'NONE' for r in rows))
        self.assertFalse(rows[0]['complete'])

    def test_screen_multiple_call_sites_unknown(self):
        source = SCREEN_GAME.replace('label ending:',
                                     'label other:\n    call screen gym_choice\n    return\n\nlabel ending:')
        _, rows = self.screen_analyze(source)
        self.assertTrue(all(r['verdict'] == 'NONE' for r in rows))
        self.assertTrue(any('multiple_screen_call_sites' in r['reasons'] for r in rows))

    def test_screen_button_guard_used(self):
        source = SCREEN_GAME.replace('    textbutton "Gitme":\n        action Jump("skip_path")',
                                     '    if gym:\n        textbutton "Gitme" action Jump("skip_path")')
        _, rows = self.screen_analyze(source)
        self.assertTrue(all(r['verdict'] == 'NONE' for r in rows))
        self.assertFalse(rows[1]['complete'])
        self.assertTrue(any('menu_or_choice_unreachable' in r['reasons'] for r in rows))

    def test_route_dependency_candidates_are_reported_not_proven(self):
        engine, _ = self.analyze(GAME)
        report = engine.route_dependencies()
        self.assertIn('condition', ' '.join(report).lower())
        self.assertTrue(report['conditions'])
        self.assertTrue(all(c['routes'] == ['dalia'] for c in report['conditions']))
        self.assertIn('unverified', report['semantics'])

    def object_game(self):
        return '''init python:
    class RouteState:
        def __init__(self, points):
            self.points = points
            self.gym = False
        def add(self, amount):
            self.points += amount
        def set_gym(self, value):
            self.gym = value
        def eligible(self):
            return self.gym and self.points >= 2
default dalia = RouteState(2)
''' + GAME.replace('$ gym = True', '$ dalia.set_gym(True)').replace('$ gym = False', '$ dalia.set_gym(False)').replace('if gym:', 'if dalia.eligible():')

    def test_object_methods_zero_point_route(self):
        _, rows = self.analyze(self.object_game())
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])

    def test_object_alias_shares_state(self):
        source = self.object_game().replace('    call check_route', '    $ alias = dalia\n    $ alias.set_gym(False)\n    call check_route')
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['NONE', 'NONE'])

    def test_object_states_isolated_across_choices(self):
        source = self.object_game().replace('default dalia = RouteState(2)', 'default dalia = RouteState(0)').replace('$ dalia.set_gym(True)', '$ dalia.set_gym(True)\n            $ dalia.add(2)')
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])

    def test_property_class_not_assumed_safe(self):
        source = self.object_game().replace('        def eligible(self):', '        @property\n        def eligible(self):')
        _, rows = self.analyze(source)
        self.assertTrue(all(r['verdict'] == 'NONE' for r in rows))

    def test_method_condition_side_effect_unknown(self):
        source = self.object_game().replace('            return self.gym and', '            self.points += 1\n            return self.gym and')
        _, rows = self.analyze(source)
        self.assertTrue(all(r['verdict'] == 'NONE' for r in rows))

    def test_source_predicate_in_route_condition(self):
        source = '''init python:
    def eligible(value):
        return value == True
''' + GAME.replace('if gym:', 'if eligible(gym):')
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])

    def test_compound_predicate_short_circuit(self):
        source = '''init python:
    def eligible(value):
        return value
''' + GAME.replace('if gym:', 'if eligible(gym) and (True or unknown_call()):')
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])

    def test_mutating_predicate_cannot_prove_route(self):
        source = '''init python:
    def eligible(value):
        store.other_flag = True
        return value
''' + GAME.replace('if gym:', 'if eligible(gym):')
        _, rows = self.analyze(source)
        self.assertTrue(all(r['verdict'] == 'NONE' for r in rows))

    def test_nested_numeric_function_threshold(self):
        source = '''init python:
    def points(value):
        return value + 1
''' + GAME.replace('$ gym = True', '$ gym = points(1) + points(2)').replace('$ gym = False', '$ gym = points(0)').replace('if gym:', 'if points(gym) >= 6:')
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])

    def test_function_condition_recovery_path(self):
        source = '''init python:
    def eligible(value):
        return value
''' + GAME.replace('    call check_route', '    $ gym = True\n    call check_route').replace('if gym:', 'if eligible(gym):')
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['NONE', 'NONE'])

    def test_transition_is_not_new_content(self):
        source = GAME.replace('$ gym = True', 'scene cg_room\n            scene cg_room with dissolve').replace('$ gym = False', 'scene cg_room')
        _, rows = self.analyze(source, routes={})
        self.assertTrue(all(row['verdict'] == 'NONE' for row in rows))

    def test_scene_and_show_same_content(self):
        source = GAME.replace('$ gym = True', 'scene cg_room').replace('$ gym = False', 'show cg_room')
        _, rows = self.analyze(source, routes={})
        self.assertTrue(all(row['verdict'] == 'NONE' for row in rows))

    def test_transform_side_effect_blocks_proof(self):
        source = '''init python:
    def close_route():
        store.gym = False
        return Transform()
''' + GAME.replace('$ gym = True', '$ gym = True\n            show cg_room at close_route()')
        _, rows = self.analyze(source)
        self.assertTrue(all(row['verdict'] == 'NONE' for row in rows))
        self.assertFalse(rows[0]['complete'])

    def test_source_python_function_route_effect(self):
        source = '''init python:
    def set_gym(value):
        store.gym = value
''' + GAME.replace('$ gym = True', '$ set_gym(True)').replace('$ gym = False', '$ set_gym(False)')
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])

    def test_python_return_and_local_scope(self):
        source = '''init python:
    def route_allowed(value):
        gym = False
        if value >= 2:
            return True
        return False
''' + GAME.replace('$ gym = True', '$ gym = route_allowed(2)').replace('$ gym = False', '$ gym = route_allowed(1)')
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])

    def test_python_unknown_effect_not_ignored(self):
        source = '''init python:
    def set_gym(value):
        store.gym = value
        external_mutation()
''' + GAME.replace('$ gym = True', '$ set_gym(True)')
        _, rows = self.analyze(source)
        self.assertTrue(all(row['verdict'] == 'NONE' for row in rows))

    def test_python_recursion_bounded(self):
        source = '''init python:
    def recursive():
        recursive()
''' + GAME.replace('$ gym = True', '$ recursive()')
        _, rows = self.analyze(source)
        self.assertTrue(all(row['verdict'] == 'NONE' for row in rows))

    def analyze(self, source=GAME, routes=None, **kwargs):
        engine = Engine({'script.rpy': source.splitlines(True)},
                        {'dalia': ['dalia_entry']} if routes is None else routes, **kwargs)
        lines = source.splitlines()
        menu = next(i for i, s in enumerate(lines) if s.strip() == 'menu:')
        choices = [i for i, s in enumerate(lines) if s.strip().endswith('":')]
        return engine, engine.analyze_menu('script.rpy', menu, choices)['choices']

    def test_conditions(self):
        self.assertIs(evaluate('x is None', {'x': None}), True)
        self.assertIs(evaluate('x is None', {}), UNKNOWN)
        self.assertEqual(evaluate('0 and missing', {}), 0)
        self.assertEqual(evaluate('1 or missing', {}), 1)
        self.assertIs(evaluate('3 < 5 < 4', {}), False)
        self.assertIs(evaluate('X == 1', {'x': 1}), UNKNOWN)
        self.assertIs(evaluate('__import__("os")', {}), UNKNOWN)
        self.assertEqual(evaluate('x + 2', {'x': 3}), 5)
        self.assertIs(evaluate('missing or 1', {}), UNKNOWN)
        self.assertIs(evaluate('missing and 0', {}), UNKNOWN)
        self.assertIs(evaluate('{1, 2} == {2, 1}', {}), True)
        self.assertEqual(evaluate("stats['love']", {'stats': {'love': 4}}), 4)

    def test_zero_point_route(self):
        _, rows = self.analyze()
        with open(os.path.join(FIXTURES, 'dalia_zero_points.expected.json'), encoding='utf-8') as f:
            expected = json.load(f)
        self.assertEqual([r['verdict'] for r in rows], expected['verdicts'])
        self.assertEqual([r['preserved'] for r in rows], expected['preserved'])
        self.assertEqual([r['lost'] for r in rows], expected['lost'])

    def test_return_continuation(self):
        source = GAME.replace('    call check_route', '    call helper\n    call check_route')
        source += '\nlabel helper:\n    $ gym = False\n    return\n'
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['NONE', 'NONE'])

    def test_return_value_overwrites_previous_return(self):
        source = GAME.replace('    call check_route', '    $ _return = True\n    call helper\n    if _return:\n        call check_route')
        source += '\nlabel helper:\n    return False\n'
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['NONE', 'NONE'])

    def test_bounded_while_and_scc(self):
        source = GAME.replace('    call check_route', '    $ counter = 0\n    while counter < 3:\n        $ counter += 1\n    call check_route')
        engine, rows = self.analyze(source)
        self.assertGreater(engine.metrics['cyclic_nodes'], 0)
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])

    def test_infinite_loop_widens_without_false_proof(self):
        source = GAME.replace('    call check_route', '    $ counter = 0\n    while True:\n        $ counter += 1\n    call check_route')
        engine, rows = self.analyze(source)
        self.assertGreater(engine.metrics['widenings'], 0)
        self.assertTrue(all(r['verdict'] == 'NONE' for r in rows))

    def test_resolved_dynamic_jump(self):
        source = GAME.replace('        jump dalia_entry', '        $ destination = "dalia_entry"\n        jump expression destination')
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])

    def test_future_route_recovery(self):
        source = GAME.replace('    call check_route', '''    menu:
        "Recover":
            $ gym = True
        "Continue":
            pass
    call check_route''')
        engine = Engine({'script.rpy': source.splitlines(True)}, {'dalia': ['dalia_entry']})
        rows = engine.analyze_menu('script.rpy', 2, [3, 5])['choices']
        self.assertEqual([r['verdict'] for r in rows], ['NONE', 'NONE'])

    def test_numeric_threshold_not_raw_points(self):
        source = GAME.replace('default gym = False', 'default gym = 0').replace('$ gym = True', '$ gym += 2').replace('$ gym = False', '$ gym += 1').replace('if gym:', 'if gym >= 2:')
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])
        self.assertEqual(rows[0]['terminal_intervals']['gym'], [2, 2])
        _, rows = self.analyze(source.replace('gym >= 2', 'gym >= 1'))
        self.assertEqual([r['verdict'] for r in rows], ['NONE', 'NONE'])

    def test_mutually_exclusive_routes(self):
        source = GAME.replace('    if gym:\n        jump dalia_entry\n    return', '    if gym:\n        jump dalia_entry\n    else:\n        jump other_entry')
        source += '\nlabel other_entry:\n    "Other route"\n    return\n'
        _, rows = self.analyze(source, routes={'dalia': ['dalia_entry'], 'other': ['other_entry']})
        self.assertEqual([r['verdict'] for r in rows], ['NONE', 'NONE'])

    def test_content_access_without_route_contract(self):
        source = GAME.replace('    "Dalia route"', '    scene cg_dalia')
        _, rows = self.analyze(source, routes={})
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'NONE'])

    def test_nested_elif_and_branch_exclusivity(self):
        source = GAME.replace('    if gym:\n        jump dalia_entry', '''    if gym:
        if gym == True:
            $ score = 3
        else:
            $ score = -100
    elif gym == False:
        $ score = -2
    else:
        $ score = -200
    if score > 0:
        jump dalia_entry''')
        _, rows = self.analyze(source)
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])
        self.assertEqual(rows[0]['terminal_intervals']['score'], [3, 3])

    def test_loop_is_bounded(self):
        source = GAME.replace('    call check_route', '    jump forever')
        source += '\nlabel forever:\n    $ gym += 1\n    jump forever\n'
        engine, rows = self.analyze(source, budget=50)
        self.assertLessEqual(engine.metrics['states'], 50)
        self.assertTrue(all(r['verdict'] == 'NONE' for r in rows))

    def test_harmful_route_never_green(self):
        _, rows = self.analyze(harmful_labels=['dalia_entry'])
        self.assertEqual([r['verdict'] for r in rows], ['RED', 'NONE'])

    def test_store_alias_preserves_case(self):
        _, rows = self.analyze(GAME.replace('$ gym =', '$ store.gym ='))
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])
        _, rows = self.analyze(GAME.replace('$ gym =', '$ Gym ='))
        self.assertEqual([r['verdict'] for r in rows], ['NONE', 'NONE'])

    def test_unknown_init_does_not_reuse_default(self):
        source = 'init python:\n    gym = True\n' + GAME.replace('$ gym = True', 'pass').replace('$ gym = False', 'pass')
        _, rows = self.analyze(source)
        self.assertTrue(all(r['verdict'] == 'NONE' for r in rows))

    def test_missing_contract_label(self):
        _, rows = self.analyze(routes={'dalia': ['not_in_source']})
        self.assertTrue(all(r['verdict'] == 'NONE' for r in rows))
        self.assertTrue(any('contract_label_missing:not_in_source' in r['reasons'] for r in rows))

    def test_distinct_entry_contexts_compared_separately(self):
        source = GAME.replace('label start:', '''label start:
    menu:
        "First":
            $ state = 1
        "Second":
            $ state = 2''')
        lines = source.splitlines()
        engine = Engine({'script.rpy': source.splitlines(True)}, {'dalia': ['dalia_entry']})
        menu = next(i for i, s in enumerate(lines) if 'Dalia ile' in s) - 1
        rows = engine.analyze_menu('script.rpy', menu, [menu + 1, menu + 3])['choices']
        self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])

    def test_overwrite_removes_causal_gain(self):
        _, rows = self.analyze(GAME.replace('    call check_route', '    $ gym = True\n    call check_route'))
        self.assertEqual([r['verdict'] for r in rows], ['NONE', 'NONE'])

    def test_no_name_based_route_claim(self):
        _, rows = self.analyze(routes={})
        self.assertEqual([r['verdict'] for r in rows], ['NONE', 'NONE'])

    def test_unknown_condition_not_proof(self):
        _, rows = self.analyze(GAME.replace('if gym:', 'if gym and missing:'))
        self.assertEqual([r['verdict'] for r in rows], ['NONE', 'NONE'])

    def test_unsupported_side_effect_blocks(self):
        _, rows = self.analyze(GAME.replace('    call check_route', '    $ mutate_flags()\n    call check_route'))
        self.assertTrue(all(not r['complete'] for r in rows))
        self.assertTrue(all(r['verdict'] == 'NONE' for r in rows))

    def test_budget(self):
        _, rows = self.analyze(budget=1)
        self.assertTrue(all(r['verdict'] == 'NONE' for r in rows))

    def test_cache_invalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cache.json')
            engine, rows = self.analyze(cache_path=path)
            engine.save_cache()
            warm, cached = self.analyze(cache_path=path)
            self.assertEqual(rows, cached)
            self.assertEqual(warm.metrics['cache_hits'], 1)
            changed, _ = self.analyze(GAME.replace('$ gym = False', '$ gym = True'), cache_path=path)
            self.assertEqual(changed.metrics['cache_hits'], 0)

    def test_guide_marker_signals(self):
        self.assertEqual(guide_choice_signals('[gr]Go with her')['verdict'], 'GREEN')
        self.assertEqual(guide_choice_signals('[red]Go away')['verdict'], 'RED')
        self.assertEqual(guide_choice_signals('[pink]Nova +1')['verdict'], 'NONE')
        self.assertTrue(guide_choice_signals('[pink]Nova +1')['points'])
        closes = guide_choice_signals("Don't go (Closes Dalia's path)")
        self.assertEqual(closes['verdict'], 'RED')
        self.assertEqual(closes['marker'], 'closes')
        self.assertEqual(guide_choice_signals('[gr]Stay (Closes side path)')['verdict'], 'NONE')
        self.assertEqual(guide_choice_signals('[gr][red]Confused')['verdict'], 'NONE')

    def guide_source(self):
        return GAME.replace('"Dalia ile spor salonuna git"',
                            '"[gr]Dalia ile spor salonuna git"').replace(
            '"Evde kal"', '"Evde kal [red][mt](Closes Dalia\'s path)"')

    def test_guide_extraction_match_and_application(self):
        studio = load_studio()
        source = self.guide_source()
        with tempfile.TemporaryDirectory() as root:
            game = os.path.join(root, 'game')
            os.mkdir(game)
            source_path = os.path.join(game, 'script.rpy')
            with open(source_path, 'w', encoding='utf-8') as f:
                f.write(source)
            analyzer = studio.RenpyWalkthroughAnalyzer(root, options={'read_only': True})
            analyzer.scan_files(auto_extract=False)
            payload = extract_guide_contracts_from_analyzer(analyzer)
            self.assertEqual(len(payload['menus']), 1)
            self.assertEqual(payload['menus'][0]['line'], 3)
            self.assertEqual([c['guide'] for c in payload['menus'][0]['choices']],
                             ['GREEN', 'RED'])

            guide_path = os.path.join(root, 'guide.json')
            with open(guide_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f)
            contracts = load_guide_contracts(guide_path)
            choice_texts = ['[gr]Dalia ile spor salonuna git',
                            "Evde kal [red][mt](Closes Dalia's path)"]
            matched = match_guide_menu(contracts, source_path, 3, choice_texts)
            self.assertIsNotNone(matched)
            self.assertEqual([c['guide'] for c in matched['choices']], ['GREEN', 'RED'])

            rows = [
                {'verdict': 'GREEN', 'proof_kind': 'proven_opportunity_preservation',
                 'reasons': []},
                {'verdict': 'RED', 'proof_kind': 'proven_route_access_loss', 'reasons': []},
            ]
            stats, conflicts = apply_guide_to_rows(rows, matched, choice_texts)
            self.assertEqual([r['verdict'] for r in rows], ['GREEN', 'RED'])
            self.assertEqual(stats['agreed'], 2)
            self.assertEqual(stats['conflicts'], 0)
            self.assertFalse(conflicts)

    def test_guide_engine_conflict_becomes_none(self):
        menu = {'choices': [
            {'text': 'A', 'guide': 'GREEN', 'marker': '[gr]'},
            {'text': 'B', 'guide': 'RED', 'marker': '[red]'},
        ]}
        rows = [
            {'verdict': 'RED', 'proof_kind': 'proven_harm', 'reasons': ['engine']},
            {'verdict': 'GREEN', 'proof_kind': 'proven_opportunity_preservation',
             'reasons': ['engine']},
        ]
        stats, conflicts = apply_guide_to_rows(rows, menu, ['A', 'B'], 'script.rpy', 7)
        self.assertEqual([r['verdict'] for r in rows], ['NONE', 'NONE'])
        self.assertEqual([r['proof_kind'] for r in rows],
                         ['guide_engine_conflict', 'guide_engine_conflict'])
        self.assertEqual(stats['conflicts'], 2)
        self.assertEqual(len(conflicts), 2)
        self.assertEqual(conflicts[0]['engine_proof_kind'], 'proven_harm')

    def test_guide_pipeline_via_analyzer(self):
        studio = load_studio()
        source = self.guide_source()
        with tempfile.TemporaryDirectory() as root:
            game = os.path.join(root, 'game')
            os.mkdir(game)
            source_path = os.path.join(game, 'script.rpy')
            with open(source_path, 'w', encoding='utf-8') as f:
                f.write(source)
            extractor = studio.RenpyWalkthroughAnalyzer(root, options={'read_only': True})
            extractor.scan_files(auto_extract=False)
            payload = extract_guide_contracts_from_analyzer(extractor)
            guide_path = os.path.join(root, 'guide.json')
            with open(guide_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f)
            analyzer = studio.RenpyWalkthroughAnalyzer(root, options={
                'accuracy_mode': True, 'read_only': True,
                'route_contracts': {'dalia': ['dalia_entry']},
                'guide_contracts': load_guide_contracts(guide_path)})
            analyzer.scan_files(auto_extract=False)
            _, menus = analyzer.analyze_file_menus(source_path)
            result = menus[0].evaluate_choices()
            self.assertEqual([str(v) for v in result.values()], ['GREEN', 'RED'])
            self.assertEqual([c.proof_kind for c in menus[0].choices],
                             ['guide_marker_engine_agree', 'guide_marker_engine_agree'])
            self.assertEqual(analyzer._guide_stats['conflicts'], 0)
            cached = list(analyzer._accuracy_engine.cache.values())[-1]
            self.assertTrue(all('guide_verdict' not in row for row in cached['choices']))

    def test_full_pipeline_and_repeat(self):
        studio = load_studio()
        with tempfile.TemporaryDirectory() as root:
            game = os.path.join(root, 'game')
            os.mkdir(game)
            path = os.path.join(game, 'script.rpy')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(GAME)
            analyzer = studio.RenpyWalkthroughAnalyzer(root, options={
                'accuracy_mode': True, 'read_only': True,
                'route_contracts': {'dalia': ['dalia_entry']}})
            analyzer.scan_files(auto_extract=False)
            _, menus = analyzer.analyze_file_menus(path)
            self.assertEqual(len(menus), 1)
            result = menus[0].evaluate_choices()
            self.assertEqual([str(v) for v in result.values()], ['GREEN', 'RED'])
            first = list(analyzer.decision_log)
            menus[0].evaluate_choices()
            self.assertEqual(first, analyzer.decision_log)


if __name__ == '__main__':
    unittest.main()
