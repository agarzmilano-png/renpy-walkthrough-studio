"""Narration and branch reachability are not proof of death or benefit."""
from pathlib import Path
from types import SimpleNamespace
from contextlib import redirect_stdout
import io
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import renpy_walkthrough_studio as studio


class EvidenceAccuracyTests(unittest.TestCase):
    def analyzer(self, source='label start:\n    return\n'):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / 'script.rpy'
        path.write_text(source, encoding='utf-8')
        analyzer = studio.RenpyWalkthroughAnalyzer(folder.name, options={
            'read_only': True, 'enable_cheat_menu': False, 'remove_rpyc': False},
            log_callback=lambda *_: None)
        analyzer.scan_files(auto_extract=False, log_callback=lambda *_: None)
        analyzer.index_labels(log_callback=lambda *_: None)
        return analyzer

    def inspect(self, body):
        choice = studio.RenpyChoice('', 0, 8, '"', 'A', '', '"A":')
        self.analyzer().inspect_code_lines(body.splitlines(True), choice)
        return choice

    def simulate(self, body, defaults=''):
        source = (defaults + 'label start:\n    menu:\n        "A":\n' +
                  ''.join('            ' + line + '\n' for line in body.splitlines()) +
                  '            return\n        "B":\n            return\n')
        program = studio.CSProgram()
        program.add_file('script.rpy', source.splitlines(True))
        solver = studio.CSSolver(program)
        self.assertTrue(solver.run_global())
        return next(iter(solver.obs.values()))[0]

    def test_narration_does_not_establish_death(self):
        for body in ('"You died"', 'npc "If you died, I would be sad."',
                     '"The film was called Game Over."', '"Öldün mü?"',
                     '"renpy.quit() is a command."', '$ caption = "you died"',
                     '$ caption = "renpy.quit()"', '$ flag = True # you died'):
            with self.subTest(body=body):
                choice = self.inspect(body)
                self.assertFalse(choice.is_death)
                self.assertFalse(any('OLUM' in str(d[0]) for d in choice.deltas_negative))

    def test_narration_does_not_establish_survival_or_reward(self):
        for body in ('"You survived!"', '"Victory! Happy ending!"',
                     '$ caption = "you survived"'):
            with self.subTest(body=body):
                choice = self.inspect(body)
                self.assertFalse(choice.is_survival)
                self.assertFalse(choice.deltas_positive)

    def test_simulator_does_not_stop_at_fatal_dialogue(self):
        visit = self.simulate('"You died, said the actor."')
        self.assertEqual(visit['vals'][0], visit['vals'][1])
        self.assertEqual(studio.cs_classify_visit(visit)[0], {0: 'NONE', 1: 'NONE'})

    def test_explicit_terminal_and_death_assignment_remain_evidence(self):
        for body in ('$ renpy.quit()', '$ renpy.full_restart()', '$ player_dead = True'):
            with self.subTest(body=body):
                self.assertTrue(self.inspect(body).is_death)

    def test_engine_call_spelling_must_be_exact(self):
        self.assertFalse(self.inspect('$ renpy.quit_mutation()').is_death)
        self.assertFalse(self.inspect('$ print("renpy.quit()")').is_death)

    def test_empty_and_harmful_conditions_are_not_gains(self):
        for body in ('if True:\n    pass',
                     'if True:\n    "Ordinary dialogue"',
                     'if True:\n    $ health -= 5',
                     'if missing:\n    pass\nelse:\n    pass'):
            with self.subTest(body=body):
                visit = self.simulate(body, 'default health = 10\n')
                self.assertEqual(visit['vals'][0][2:4], (0., 0.))
                self.assertNotIn('GREEN', studio.cs_classify_visit(visit)[0].values())

    def test_nested_conditions_do_not_manufacture_more_value(self):
        visit = self.simulate('if True:\n    if True:\n        if True:\n            pass')
        self.assertEqual(visit['vals'][0][2:4], (0., 0.))

    def test_threshold_observation_has_no_extra_reward(self):
        analyzer = self.analyzer()
        analyzer.initial_vars['love'] = 0
        analyzer.var_thresholds['love'] = [('>=', 1., '', 10)]
        choice = studio.RenpyChoice('', 0, 8, '"', 'A', '', '"A":')
        analyzer.apply_variable_delta_to_choice(choice, 'love', '+=', 1., 'test')
        self.assertEqual(choice.score, 1.)
        self.assertTrue(choice.unlocked_thresholds)

    def test_strict_threshold_equality_is_not_satisfaction(self):
        analyzer = self.analyzer()
        analyzer.initial_vars['love'] = 0
        analyzer.var_thresholds['love'] = [('>', 1., '', 10)]
        choice = studio.RenpyChoice('', 0, 8, '"', 'A', '', '"A":')
        analyzer.apply_variable_delta_to_choice(choice, 'love', '+=', 1., 'test')
        self.assertFalse(any('Esik Acildi' in text or 'Eşik sağlandı' in text
                             for _, text in choice.unlocked_thresholds))

    def test_cfg_narrative_and_quoted_code_are_not_endings(self):
        for text in ('"You died"', '"renpy.quit()"', '$ caption = "player_dead"'):
            with self.subTest(text=text):
                analyzer = self.analyzer('label start:\n    ' + text + '\n    return\n')
                cfg = analyzer.build_control_flow_graph()
                endings = list(cfg.raw_endings.values())
                self.assertTrue(endings)
                self.assertTrue(all(e['type'] != 'DEATH_BAD_ENDING' for e in endings))

    def test_dialogue_in_threshold_body_does_not_create_fatal_impact(self):
        analyzer = self.analyzer('default flag = False\nlabel start:\n    if flag:\n        "You died in my dream."\n    return\n')
        for entry in analyzer.global_condition_impact_map.get('flag', []):
            self.assertFalse(entry['has_death'])

    def test_multiline_dialogue_cannot_embed_executable_evidence(self):
        for body in ('"""A story\nrenpy.quit()\nYou died\n"""',
                     'npc happy """A story\n$ player_dead = True\n"""',
                     '$ caption = """you died\nrenpy.quit()\n"""'):
            with self.subTest(body=body):
                choice = self.inspect(body)
                self.assertFalse(choice.is_death)
                self.assertIsNone(choice.jump_target)

    def test_quoted_control_call_is_not_followed(self):
        for body in ('"renpy.jump(\'death\')"', '$ caption = "renpy.jump(\'death\')"',
                     'npc "renpy.call(\'death\')"'):
            with self.subTest(body=body):
                choice = self.inspect(body)
                self.assertIsNone(choice.jump_target)
                self.assertIsNone(choice.call_target)

    def test_no_simulation_cannot_preserve_definitive_heuristic_color(self):
        for verdict in ('GREEN', 'RED'):
            with self.subTest(verdict=verdict):
                choice = studio.RenpyChoice('', 0, 8, '"', 'A', '', '"A":')
                choice.is_death = verdict == 'RED'
                menu = SimpleNamespace(choices=[choice], analyzer=None)
                with patch.object(studio, '_cs_menu_info', return_value=None):
                    result = studio._cs_enforce(menu, {choice: studio.Decision(verdict)}, None)
                self.assertEqual(str(result[choice]), 'NONE')

    def test_unmapped_simulation_cannot_preserve_color(self):
        choice = studio.RenpyChoice('', 0, 8, '"', 'A', '', '"A":')
        menu = SimpleNamespace(choices=[choice], analyzer=None)
        with patch.object(studio, '_cs_menu_info', return_value={'mode': 'global', 'idx': {}, 'info': {}}):
            result = studio._cs_enforce(menu, {choice: studio.Decision('GREEN')}, None)
        self.assertEqual(str(result[choice]), 'NONE')

    def test_combat_wording_does_not_imply_success(self):
        choice = studio.RenpyChoice('', 0, 8, '"', 'Attack', '', '"Attack":')
        self.analyzer().inspect_code_lines(['    "You hit him!"\n'], choice)
        self.assertFalse(choice.is_combat_success)
        self.assertFalse(choice.is_combat_failure)
        self.assertFalse(choice.deltas_positive)

    def test_unknown_call_names_are_not_safe_prefixes(self):
        analyzer = self.analyzer()
        self.assertTrue(analyzer.is_irrelevant_call('print'))
        self.assertFalse(analyzer.is_irrelevant_call('print_mutation'))
        self.assertFalse(analyzer.is_irrelevant_call('renpy.pause_mutation'))

    def test_branch_jump_does_not_establish_route_benefit(self):
        analyzer = self.analyzer('default flag = False\nlabel start:\n    if flag:\n        jump ordinary\n    return\nlabel ordinary:\n    return\n')
        entry = analyzer.global_flag_impact['flag']
        self.assertFalse(entry['enables_route'])
        self.assertFalse(entry['true_enables_route'])

    def test_multiline_narrative_cannot_create_cfg_terminal(self):
        analyzer = self.analyzer('label start:\n    """Text\nrenpy.quit()\n"""\n    return\n')
        cfg = analyzer.build_control_flow_graph()
        self.assertTrue(all(e['type'] != 'DEATH_BAD_ENDING' for e in cfg.raw_endings.values()))

    def test_cli_help_and_missing_tkinter_are_handled(self):
        with redirect_stdout(io.StringIO()), patch.object(sys, 'argv', ['studio', '--help']):
            with self.assertRaises(SystemExit) as exit_status:
                studio.main()
        self.assertEqual(exit_status.exception.code, 0)
        with redirect_stdout(io.StringIO()), patch.object(sys, 'argv', ['studio']), patch.object(studio, 'HAS_CUSTOMTKINTER', False), patch.object(studio, 'HAS_TKINTER', False):
            studio.main()  # No AttributeError from tk=None.

    def test_report_counts_canonical_decisions_without_alias_hash_confusion(self):
        analyzer = self.analyzer('label start:\n    menu:\n        "A":\n            return\n        "B":\n            return\n        "C":\n            return\n')
        _, menus = analyzer.analyze_file_menus(analyzer.rpy_files[0])
        analyzer.menus = menus
        for choice, verdict in zip(menus[0].choices, ('GREEN', 'RED', 'NONE')):
            choice.verdict = studio.Decision(verdict)
        report = analyzer.export_analysis_report()
        self.assertEqual(report['summary']['decisions'], {'BEST': 1, 'WORST': 1, 'NEUTRAL': 1})
        self.assertFalse(report['analysis_policy']['condition_satisfaction_is_reward'])
        self.assertFalse(report['analysis_policy']['narrative_is_terminal_proof'])

    def test_unavailable_verdict_exposes_uncertainty_without_erasing_code_delta(self):
        choice = self.inspect('$ love += 1')
        before = list(choice.deltas_positive)
        menu = SimpleNamespace(choices=[choice], analyzer=None)
        with patch.object(studio, '_cs_menu_info', return_value=None):
            studio._cs_enforce(menu, {choice: studio.Decision('GREEN')}, None)
        self.assertFalse(choice.decision_verified)
        self.assertTrue(choice.uncertainty_reasons)
        self.assertEqual(choice.deltas_positive, before)

    def test_direct_numeric_threshold_has_no_extra_reward(self):
        analyzer = self.analyzer()
        analyzer.initial_vars['love'] = 0
        analyzer.var_thresholds['love'] = [('>=', 1., '', 10)]
        choice = studio.RenpyChoice('', 0, 8, '"', 'A', '', '"A":')
        analyzer.inspect_code_lines(['    $ love += 1\n'], choice)
        self.assertEqual(choice.score, 1.)
        self.assertTrue(choice.unlocked_thresholds)

    def test_label_name_is_not_a_terminal(self):
        for name in ('death', 'bad_end', 'good_end', 'safe_ending'):
            with self.subTest(name=name):
                program = studio.CSProgram()
                source = ('label start:\n    menu:\n        "A":\n            call ' + name +
                          '\n        "B":\n            pass\n    return\nlabel ' + name + ':\n    return\n')
                program.add_file('script.rpy', source.splitlines(True))
                solver = studio.CSSolver(program)
                self.assertTrue(solver.run_global())
                visit = solver.obs[('script.rpy', 1)][0]
                self.assertEqual(visit['vals'][0], visit['vals'][1])
                self.assertEqual(studio.cs_classify_visit(visit)[0], {0: 'NONE', 1: 'NONE'})

    def test_label_spelling_does_not_establish_heuristic_death_or_survival(self):
        for target in ('death', 'bad_end', 'good_end', 'safe_ending'):
            choice = self.inspect('jump ' + target)
            self.assertFalse(choice.is_death)
            self.assertFalse(choice.is_survival)

    def test_fatal_dialogue_does_not_hide_real_following_terminal(self):
        visit = self.simulate('"You died, said the actor."\n$ renpy.quit()')
        self.assertFalse(visit['vals'][0][1])
        self.assertEqual(studio.cs_classify_visit(visit)[0], {0: 'RED', 1: 'GREEN'})


if __name__ == '__main__':
    unittest.main()
