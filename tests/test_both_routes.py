"""Route-gate adaptation and hand-authored Ripples reference contracts."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import test_both_scenes as scenes
studio = scenes.studio


EXCLUSION_GAME = '''default anna_points = 0
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
    return
'''


class BothRouteTests(unittest.TestCase):
    analyze = scenes.BothSceneTests.analyze
    sources = staticmethod(scenes.BothSceneTests.sources)
    apply = scenes.BothSceneTests.apply
    assert_rejected = scenes.BothSceneTests.assert_rejected

    def test_automatic_gate_union_preserves_both_paths_and_original_choices(self):
        an, candidates = self.analyze(EXCLUSION_GAME)
        self.assertEqual(len(candidates), 1, an.both_skipped)
        plan = candidates[0].scene_plan
        self.assertEqual(set(plan['selectors']), {'prefer_anna'})
        self.assertEqual(len(plan['condition_adaptations']), 2)
        files = self.apply(an, candidates)
        state, seen = scenes.run_synthetic(files)
        self.assertEqual(seen, ['"Anna branch"', '"Luna branch"', '"Anna unlocked"', '"Luna unlocked"'])
        self.assertEqual((state['anna_points'], state['luna_points']), (2, 2))
        # All original source conditions/labels remain byte-for-byte unchanged.
        self.assertEqual(files['script.rpy'].split('label future:')[1], EXCLUSION_GAME.split('label future:')[1])
        for pick in ('Anna choice', 'Luna choice'):
            self.assertEqual(scenes.run_synthetic(files, pick),
                             scenes.run_synthetic({'script.rpy': EXCLUSION_GAME}, pick))
        self.assertTrue(candidates[0].scene_plan['verification']['source_reparsed'])

    def test_thresholds_and_external_requirements_not_bypassed(self):
        for ticket in ('True', 'False'):
            for threshold in (2, 3, 10):
                with self.subTest(ticket=ticket, threshold=threshold):
                    source = EXCLUSION_GAME.replace('ticket = True', 'ticket = ' + ticket)
                    source = source.replace('>= 2', '>= ' + str(threshold))
                    an, cands = self.analyze(source)
                    _, seen = scenes.run_synthetic(self.apply(an, cands))
                    expected = ticket == 'True' and threshold <= 2
                    self.assertEqual('"Anna unlocked"' in seen, expected)
                    self.assertEqual('"Luna unlocked"' in seen, expected)

    def test_differential_union_over_multiple_initial_point_states(self):
        for anna in (0, 1, 3):
            for luna in (0, 1, 3):
                source = EXCLUSION_GAME.replace('anna_points = 0', 'anna_points = ' + str(anna))
                source = source.replace('luna_points = 0', 'luna_points = ' + str(luna))
                an, cands = self.analyze(source)
                combined = self.apply(an, cands)
                state, seen = scenes.run_synthetic(combined)
                _, a_seen = scenes.run_synthetic({'script.rpy': source}, 'Anna choice')
                _, b_seen = scenes.run_synthetic({'script.rpy': source}, 'Luna choice')
                self.assertLessEqual(set(a_seen) | set(b_seen), set(seen))
                self.assertEqual((state['anna_points'], state['luna_points']), (anna + 2, luna + 2))

    def test_cross_file_future_gates_are_cloned_not_globally_rewritten(self):
        head, tail = EXCLUSION_GAME.split('label future:')
        an, cands = self.analyze(head, {'future.rpy': 'label future:' + tail})
        files = self.apply(an, cands)
        self.assertEqual(files['future.rpy'], 'label future:' + tail)
        self.assertEqual(len(scenes.run_synthetic(files)[1]), 4)
        self.assertTrue(all(a['file'].endswith('future.rpy') for a in cands[0].scene_plan['condition_adaptations']))

    def test_route_union_matrix_preserves_thresholds_and_external_requirements(self):
        for ticket in (False, True):
            for threshold in (2, 5):
                for anna in (-1, 0, 3):
                    for luna in (-1, 0, 3):
                        with self.subTest(ticket=ticket, threshold=threshold, anna=anna, luna=luna):
                            source = EXCLUSION_GAME.replace('ticket = True', 'ticket = ' + str(ticket))
                            source = source.replace('>= 2', '>= ' + str(threshold))
                            source = source.replace('anna_points = 0', 'anna_points = ' + str(anna))
                            source = source.replace('luna_points = 0', 'luna_points = ' + str(luna))
                            an, cands = self.analyze(source)
                            state, seen = scenes.run_synthetic(self.apply(an, cands))
                            self.assertEqual((state['anna_points'], state['luna_points']), (anna + 2, luna + 2))
                            self.assertEqual('"Anna unlocked"' in seen, ticket and anna + 2 >= threshold)
                            self.assertEqual('"Luna unlocked"' in seen, ticket and luna + 2 >= threshold)
                            self.assertEqual(seen.count('"Anna branch"'), 1)
                            self.assertEqual(seen.count('"Luna branch"'), 1)

    def test_impossible_correlated_condition_does_not_become_true(self):
        source = EXCLUSION_GAME.replace('    return',
                                       '    if prefer_anna and not prefer_anna:\n'
                                       '        "Impossible scene"\n    return')
        an, cands = self.analyze(source)
        _, seen = scenes.run_synthetic(self.apply(an, cands))
        self.assertNotIn('"Impossible scene"', seen)

    def test_opt_out_of_route_adaptation(self):
        an, cands = self.analyze(EXCLUSION_GAME, both_route_adaptation=False)
        self.assertEqual(cands, [])
        self.assertIn('route_adaptation_disabled', an.both_skipped[0]['reason'])

    def test_missing_opposite_path_requires_review(self):
        source = EXCLUSION_GAME.replace('    if not prefer_anna and luna_points >= 2 and ticket:\n        "Luna unlocked"\n', '')
        self.assert_rejected(source)

    def test_else_chain_not_silently_opened_by_or(self):
        self.assert_rejected(EXCLUSION_GAME.replace('    if not prefer_anna and luna_points >= 2 and ticket:',
                                                  '    elif not prefer_anna and luna_points >= 2 and ticket:'))

    def test_selector_rewritten_later_requires_review(self):
        self.assert_rejected(EXCLUSION_GAME.replace('label future:', 'label future:\n    $ prefer_anna = True'))

    def test_selector_read_outside_proven_continuation_requires_review(self):
        self.assert_rejected(EXCLUSION_GAME + '\nlabel other:\n    if prefer_anna:\n        "Unknown later context"\n    return\n')

    def test_selector_interpolation_requires_review(self):
        self.assert_rejected(EXCLUSION_GAME.replace('    return', '    "State [prefer_anna]"\n    return'))

    def test_selector_comparison_requires_review_not_guessed(self):
        self.assert_rejected(EXCLUSION_GAME.replace('if prefer_anna and', 'if prefer_anna == True and'))

    def test_real_route_loss_is_still_rejected(self):
        source = EXCLUSION_GAME.replace('label start:', 'default anna_path = True\nlabel start:')
        self.assert_rejected(source.replace('"Luna branch"', '$ anna_path = False\n            "Luna branch"'))

    def test_persistent_selector_is_not_automatically_repaired(self):
        self.assert_rejected(EXCLUSION_GAME.replace('prefer_anna', 'persistent.prefer_anna'))

    def test_unsupported_future_call_cannot_prove_gate_union(self):
        self.assert_rejected(EXCLUSION_GAME.replace('    return', '    $ unknown_effect()\n    return'))

    def test_route_report_has_sources_proof_and_manual_proposal(self):
        an, cands = self.analyze(EXCLUSION_GAME, read_only=True)
        report = an.export_both_report()
        self.assertEqual(report['entries'][0]['status'], 'verified_candidate')
        entry = report['entries'][0]
        self.assertEqual(len(entry['condition_adaptations']), 2)
        self.assertTrue(all(row['line'] > 0 and row['file'] for row in entry['dependencies']))
        self.assertEqual(self.sources(an)['script.rpy'], EXCLUSION_GAME)
        path = os.path.join(an.game_dir, 'wt_both_analysis.json')
        an.export_both_report(path)
        with open(path, encoding='utf-8') as f:
            self.assertEqual(json.load(f)['schema'], 1)
        with self.assertRaises(studio.BothPlanError):
            an.export_both_report(cands[0].file_path)
        failed, _ = self.analyze(EXCLUSION_GAME.replace('    return', '    $ unknown_effect()\n    return'))
        proposal = failed.export_both_report()['entries'][0]
        self.assertEqual(proposal['status'], 'manual_review')
        self.assertFalse(proposal['proposal']['automatic_write'])
        self.assertTrue(proposal['proposal']['source_conditions'])

    def test_unknown_report_does_not_claim_a_romantic_route(self):
        an, _ = self.analyze(EXCLUSION_GAME.replace('    return', '    call screen missing\n    return'))
        self.assertEqual(an.export_both_report()['semantics'], 'source_dependencies_not_inferred_romantic_routes')

    def test_existing_both_is_reported_without_duplicate_insertion(self):
        an, cands = self.analyze(EXCLUSION_GAME)
        files = self.apply(an, cands)
        an.detect_both_candidates()
        report = an.export_both_report()
        self.assertTrue(any(e['status'] == 'existing_both_not_modified' for e in report['entries']))
        self.assertEqual(self.sources(an), files)

    def test_modified_generated_body_rejected_before_write(self):
        an, cands = self.analyze(EXCLUSION_GAME)
        generate = an.generate_both_patch
        def tamper(candidate):
            result = generate(candidate)
            result['menu_choice_code'] += '\n            $ anna_points += 100'
            return result
        with patch.object(an, 'generate_both_patch', side_effect=tamper):
            self.assertFalse(an.apply_both_patch(cands[0]))
        self.assertEqual(self.sources(an)['script.rpy'], EXCLUSION_GAME)

    def test_removed_visibility_guard_rejected_before_write(self):
        source = EXCLUSION_GAME.replace('"Anna choice":', '"Anna choice" if ticket:')
        an, cands = self.analyze(source)
        generate = an.generate_both_patch
        def tamper(candidate):
            result = generate(candidate)
            result['menu_choice_code'] = result['menu_choice_code'].replace(' if (ticket):', ':')
            return result
        with patch.object(an, 'generate_both_patch', side_effect=tamper):
            self.assertFalse(an.apply_both_patch(cands[0]))
        self.assertEqual(self.sources(an)['script.rpy'], source)

    def test_dependency_budget_exhaustion_refuses_adaptation(self):
        with patch.object(studio.BothDependencyIndex, 'LIMIT', 1):
            an, cands = self.analyze(EXCLUSION_GAME)
        self.assertEqual(cands, [])
        self.assertIn('dependency_index_budget_exceeded', an.both_skipped[0]['reason'])

    def test_negative_point_gate_not_bypassed(self):
        self.assert_rejected(EXCLUSION_GAME.replace('luna_points >= 2', 'luna_points < 2'))

    def test_reference_contracts_from_hand_authored_ripples_mod(self):
        cases = [
            ('jessica_skylar', {'jessica': 1, 'skylar': 1, 'skylarL': 1},
             ['"Jessica branch"', '"Skylar branch"', '"Later Jessica branch"', '"Later Skylar branch"']),
            ('outfits', {'shelbyS': 1, 'shelbyD': 1},
             ['"Playful branch"', '"Sexy branch"', '"Shared continuation"']),
            ('tori_valerie', {'tori': 1, 'valerie': 1},
             ['"Tori branch"', '"Valerie branch"', '"Shared continuation"']),
        ]
        for name, scores, order in cases:
            with self.subTest(reference=name):
                path = os.path.join(os.path.dirname(__file__), 'accuracy_fixtures',
                                    'ripples_both_' + name + '_reference.rpy')
                with open(path, encoding='utf-8') as source:
                    state, seen = scenes.run_synthetic({'script.rpy': source.read()})
                self.assertEqual({key: state[key] for key in scores}, scores)
                self.assertEqual(seen, order)
                if name == 'jessica_skylar':
                    self.assertFalse(state['jessicaRisk'])
                    self.assertTrue(state['mod_skylar_jess'])
                    self.assertEqual(state['persistent.relationshipSkylar'], 'More Than Friends')

    def test_legacy_ripples_spin_does_not_preaward_scene_points(self):
        original = '''default tori = 0
default valerie = 0
default mod_toriVal_nips = False
label start:
    menu:
        "Spin Right":
            $ tori += 1
            $ toriNip = True
            $ persistent.toriNip = True
            sc "Haha.... I love this game!"
        "Spin Left":
            $ valerie += 1
            $ valNip = True
            $ persistent.valNip = True
            "Valerie branch"
    return
'''
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, 'e8s1.rpy')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(original)
            studio.RipplesGameProfile.apply(root)
            with open(path, encoding='utf-8') as f:
                generated = f.read()
            self.assertEqual(generated.count('$ tori += 1'), 1)
            self.assertEqual(generated.count('$ valerie += 1'), 1)
            entry = generated.split('Mod: Both', 1)[1].split('"Spin Right"', 1)[0]
            self.assertIn('$ mod_toriVal_nips = True', entry)
            self.assertNotIn('+=', entry)
            # Running the original scene reward sites once matches the supplied mod.
            self.assertIn('jump mod_tori_spin', entry)
            self.assertIn('jump mod_valerie_spin', generated)

    def test_persistent_dependencies_reported_without_automatic_write(self):
        source = EXCLUSION_GAME.replace('prefer_anna', 'persistent.prefer_anna')
        an, cands = self.analyze(source, read_only=True)
        self.assertEqual(cands, [])
        entry = an.export_both_report()['entries'][0]
        self.assertIn('persistent.prefer_anna', entry['candidate_variables'])
        self.assertTrue(any('persistent.prefer_anna' in row.get('reads', [])
                            for row in entry['dependencies'] if row['kind'] == 'condition'))
        self.assertEqual(self.sources(an)['script.rpy'], source)

    def test_stale_plan_report_requires_rescan(self):
        an, cands = self.analyze(EXCLUSION_GAME)
        with open(cands[0].file_path, 'a', encoding='utf-8') as f:
            f.write('# external edit\n')
        entry = an.export_both_report()['entries'][0]
        self.assertEqual(entry['status'], 'stale_requires_rescan')
        self.assertFalse(entry['eligible_for_automatic_apply'])

    def test_applied_report_tracks_post_write_hashes(self):
        an, cands = self.analyze(EXCLUSION_GAME)
        self.apply(an, cands)
        entry = an.export_both_report()['entries'][0]
        self.assertEqual(entry['status'], 'applied')
        self.assertTrue(entry['verification']['current_source_matches_expected'])
        self.assertTrue(entry['verification']['emitted_body_matches_plan'])

    def test_legacy_missing_mod_flag_initialized_with_backup(self):
        source = '''label start:
    menu:
        "Spin Right":
            $ tori += 1
            sc "Haha.... I love this game!"
        "Spin Left":
            $ valerie += 1
    return
'''
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, 'e8s1.rpy')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(source)
            studio.RipplesGameProfile.apply(root)
            with open(path, encoding='utf-8') as f:
                generated = f.read()
            self.assertEqual(generated.count('default mod_toriVal_nips = False'), 1)
            with open(path + '.wtbak', encoding='utf-8') as f:
                self.assertEqual(f.read(), source)
            studio.RipplesGameProfile.apply(root)
            with open(path, encoding='utf-8') as f:
                self.assertEqual(f.read(), generated)

    def test_legacy_missing_bridge_anchor_does_not_write_partial_option(self):
        source = 'label start:\n    menu:\n        "Spin Right":\n            pass\n        "Spin Left":\n            pass\n    return\n'
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, 'e8s1.rpy')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(source)
            studio.RipplesGameProfile.apply(root)
            with open(path, encoding='utf-8') as f:
                self.assertEqual(f.read(), source)
            self.assertFalse(os.path.exists(path + '.wtbak'))

    def test_legacy_reuses_flag_default_from_mod_additions(self):
        source = 'label start:\n    menu:\n        "Spin Right":\n            sc "Haha.... I love this game!"\n        "Spin Left":\n            pass\n    return\n'
        with tempfile.TemporaryDirectory() as root:
            scripts, additions = os.path.join(root, 'scripts'), os.path.join(root, 'mod_additions')
            os.mkdir(scripts)
            os.mkdir(additions)
            path = os.path.join(scripts, 'e8s1.rpy')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(source)
            with open(os.path.join(additions, 'options.rpy'), 'w', encoding='utf-8') as f:
                f.write('default mod_toriVal_nips = False\n')
            studio.RipplesGameProfile.apply(scripts)
            with open(path, encoding='utf-8') as f:
                self.assertNotIn('default mod_toriVal_nips', f.read())

    def test_numeric_truthiness_is_not_assumed_monotone(self):
        # A alone: -4 + 2 is truthy; A+B: -4 + 2 + 2 is zero/false.
        # Replacing a route gate while treating that as monotone would LOSE A.
        source = EXCLUSION_GAME.replace('anna_points = 0', 'anna_points = -4')
        source = source.replace('$ luna_points += 2', '$ luna_points += 2\n            $ anna_points += 2')
        source = source.replace('anna_points >= 2', 'anna_points')
        self.assert_rejected(source)

    def test_point_updates_not_treated_as_boolean_even_with_boolean_default(self):
        source = EXCLUSION_GAME.replace('anna_points = 0', 'anna_points = False')
        source = source.replace('label start:', 'label start:\n    $ anna_points = -4')
        source = source.replace('$ luna_points += 2', '$ luna_points += 2\n            $ anna_points += 2')
        source = source.replace('anna_points >= 2', 'anna_points')
        self.assert_rejected(source)


if __name__ == '__main__':
    unittest.main()
