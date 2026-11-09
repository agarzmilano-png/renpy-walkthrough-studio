"""End-to-end tests of generated Both code; no real game Python is executed."""
import ast
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import renpy_walkthrough_studio as studio


JUMP_GAME = '''default anna_points = 0
default luna_points = 0
default anna_path = True
default luna_path = True
label start:
    menu:
        "Visit Anna":
            jump anna_scene
        "Visit Luna":
            jump luna_scene
label anna_scene:
    scene anna_room
    "Anna scene"
    $ anna_points += 2
    $ anna_path = True
    jump together
label luna_scene:
    scene luna_room
    "Luna scene"
    $ luna_points += 2
    $ luna_path = True
    jump together
label together:
    "Common continuation"
    return
'''


def run_synthetic(files, pick='Mod:'):
    """Tiny independent runner for our trusted synthetic fixtures, not production use.

    Uses the parser only; does not use CSSolver, heuristic scores or cached deltas.
    Checks the emitted executable statements and dialogue/scene order.
    """
    prog = studio.CSProgram()
    for name, source in files.items():
        prog.add_file(name, source.splitlines(True))
    state = dict(prog.defaults)
    state.update(prog.consts)
    seen, stack = [], []
    bid, idx = prog.labels['start'], 0
    for _ in range(500):
        block = prog.blocks[bid]
        if idx >= len(block):
            if stack:
                bid, idx, _ = stack.pop()
                continue
            break
        s = block[idx]
        kind = s[0]
        idx += 1
        if kind == 'assign':
            value = eval(compile(ast.Expression(s[3]), '<synthetic>', 'eval'), {}, state)
            if s[2] == '=':
                state[s[1]] = value
            elif s[2] == '+':
                state[s[1]] += value
            else:
                raise AssertionError(s)
        elif kind == 'say':
            seen.append(s[1])
        elif kind == 'noop':
            pass
        elif kind == 'if':
            target = s[2]
            for cond, child, _ in s[1]:
                if eval(compile(ast.Expression(cond), '<synthetic>', 'eval'), {}, state):
                    target = child
                    break
            if target is not None:
                stack.append((bid, idx, False))
                bid, idx = target, 0
        elif kind == 'menu':
            available = [(cond, child, text) for _, cond, child, text, _ in s[2]
                         if cond is None or eval(compile(ast.Expression(cond), '<synthetic>', 'eval'), {}, state)]
            target = next(child for _, child, text in available if pick in text)
            stack.append((bid, idx, False))
            bid, idx = target, 0
        elif kind in ('jump', 'call'):
            if kind == 'call':
                stack.append((bid, idx, True))
            else:
                while stack and not stack[-1][2]:
                    stack.pop()
            bid, idx = prog.labels[s[1]], 0
        elif kind == 'return':
            while stack and not stack[-1][2]:
                stack.pop()
            if not stack:
                return state, seen
            bid, idx, _ = stack.pop()
        else:
            raise AssertionError('Unsupported synthetic instruction: ' + repr(s))
    raise AssertionError('Synthetic execution did not return')


class BothSceneTests(unittest.TestCase):
    def analyze(self, source=JUMP_GAME, extra=None, **options):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        files = {'script.rpy': source, **(extra or {})}
        for name, text in files.items():
            with open(os.path.join(temp.name, name), 'w', encoding='utf-8', newline='') as f:
                f.write(text)
        opts = {'read_only': False, 'enable_cheat_menu': False, 'remove_rpyc': False}
        opts.update(options)
        an = studio.RenpyWalkthroughAnalyzer(temp.name, options=opts, log_callback=lambda *_: None)
        an.scan_files(auto_extract=False, log_callback=lambda *_: None)
        an.index_labels(log_callback=lambda *_: None)
        menus = []
        for path in an.rpy_files:
            menus.extend(an.analyze_file_menus(path)[1])
        an.all_menus = menus
        return an, an.detect_both_candidates(menus)

    def test_existing_localized_both_is_not_duplicated(self):
        for caption in ('Mod: İkiside', '[gr]Mod: Her İkiside'):
            source = JUMP_GAME.replace('        "Visit Luna":',
                                       '        "' + caption + '":')
            with self.subTest(caption=caption):
                an, candidates = self.analyze(source, read_only=True)
                self.assertEqual(candidates, [])
                self.assertTrue(any(s['reason'] == 'already_patched' for s in an.both_skipped))

    @staticmethod
    def sources(an):
        result = {}
        for path in an.rpy_files:
            with open(path, encoding='utf-8') as f:
                result[os.path.basename(path)] = f.read()
        return result

    def apply(self, an, candidates):
        self.assertEqual(len(candidates), 1, getattr(an, 'both_skipped', []))
        self.assertTrue(an.apply_both_patch(candidates[0], log_callback=lambda *_: None))
        return self.sources(an)

    def assert_rejected(self, source):
        an, candidates = self.analyze(source)
        self.assertEqual(candidates, [], getattr(an, 'both_skipped', []))
        self.assertTrue(an.both_skipped)
        self.assertEqual(self.sources(an)['script.rpy'], source)

    def test_jump_scenes_points_routes_and_common_tail_once(self):
        an, candidates = self.analyze()
        files = self.apply(an, candidates)
        state, seen = run_synthetic(files)
        self.assertEqual(seen, ['"Anna scene"', '"Luna scene"', '"Common continuation"'])
        self.assertEqual((state['anna_points'], state['luna_points']), (2, 2))
        self.assertTrue(state['anna_path'] and state['luna_path'])
        self.assertEqual(files['script.rpy'].split('label anna_scene:')[1], JUMP_GAME.split('label anna_scene:')[1])

    def test_original_choices_still_only_play_their_scene(self):
        an, candidates = self.analyze()
        files = self.apply(an, candidates)
        for pick in ('Visit Anna', 'Visit Luna'):
            self.assertEqual(run_synthetic(files, pick), run_synthetic({'script.rpy': JUMP_GAME}, pick))

    def test_inline_scenes_are_not_reduced_to_assignments(self):
        source = '''default anna_points = 0
default luna_points = 0
label start:
    menu:
        "Visit Anna":
            "Anna scene"
            $ anna_points += 2
        "Visit Luna":
            "Luna scene"
            $ luna_points += 2
    "Common continuation"
    return
'''
        an, cands = self.analyze(source)
        state, seen = run_synthetic(self.apply(an, cands))
        self.assertEqual((state['anna_points'], state['luna_points']), (2, 2))
        self.assertEqual(len(seen), 3)

    def test_points_before_jump_not_awarded_twice(self):
        source = JUMP_GAME.replace('            jump anna_scene', '            $ anna_points += 3\n            jump anna_scene')
        an, cands = self.analyze(source)
        state, _ = run_synthetic(self.apply(an, cands))
        self.assertEqual(state['anna_points'], 5)
        self.assertEqual(state['luna_points'], 2)

    def test_identical_reward_lines_in_different_scenes_are_not_deduplicated(self):
        source = JUMP_GAME.replace('luna_points += 2', 'anna_points += 2')
        an, cands = self.analyze(source)
        state, _ = run_synthetic(self.apply(an, cands))
        self.assertEqual(state['anna_points'], 4)

    def test_cross_file_scenes_leave_original_files_untouched(self):
        head, rest = JUMP_GAME.split('label anna_scene:')
        an, cands = self.analyze(head, {'scenes.rpy': 'label anna_scene:' + rest})
        files = self.apply(an, cands)
        self.assertEqual(files['scenes.rpy'], 'label anna_scene:' + rest)
        self.assertEqual(len(run_synthetic(files)[1]), 3)

    def test_called_scenes_return_before_common_continuation(self):
        source = JUMP_GAME.replace('jump anna_scene', 'call anna_scene').replace('jump luna_scene', 'call luna_scene')
        source = source.replace('label anna_scene:', '    jump together\nlabel anna_scene:')
        source = source.replace('    jump together\nlabel luna_scene:', '    return\nlabel luna_scene:')
        source = source.replace('    jump together\nlabel together:', '    return\nlabel together:')
        an, cands = self.analyze(source)
        state, seen = run_synthetic(self.apply(an, cands))
        self.assertEqual((state['anna_points'], state['luna_points']), (2, 2))
        self.assertEqual(len(seen), 3)

    def test_three_scenes_all_not_just_first_two(self):
        source = JUMP_GAME.replace('label start:', 'default maya_points = 0\nlabel start:')
        source = source.replace('label anna_scene:', '        "Visit Maya":\n            jump maya_scene\nlabel anna_scene:')
        source = source.replace('label together:', 'label maya_scene:\n    "Maya scene"\n    $ maya_points += 2\n    jump together\nlabel together:')
        an, cands = self.analyze(source)
        self.assertEqual(cands[0].bridge_kind, 'all')
        files = self.apply(an, cands)
        state, seen = run_synthetic(files)
        self.assertIn('Mod: All', files['script.rpy'])
        self.assertEqual([state[k + '_points'] for k in ('anna', 'luna', 'maya')], [2, 2, 2])
        self.assertEqual(len(seen), 4)

    def test_decompiled_static_call_from_is_inlined(self):
        source = JUMP_GAME.replace('jump anna_scene', 'call anna_scene from _call_anna')
        source = source.replace('jump luna_scene', 'call luna_scene from _call_luna')
        source = source.replace('label anna_scene:', '    jump together\nlabel anna_scene:')
        source = source.replace('    jump together\nlabel luna_scene:', '    return\nlabel luna_scene:')
        source = source.replace('    jump together\nlabel together:', '    return\nlabel together:')
        an, cands = self.analyze(source)
        code = an.generate_both_patch(cands[0])['menu_choice_code']
        self.assertNotIn('call anna_scene', code)
        self.assertEqual(run_synthetic(self.apply(an, cands))[0]['anna_points'], 2)

    def test_literal_decompiled_pauses_preserved(self):
        for pause in ('pause', 'pause(.5)', 'pause(0)', 'pause ( 1.25 )', 'pause .5', 'pause 1.'):
            with self.subTest(pause=pause):
                source = JUMP_GAME.replace('    "Luna scene"', '    ' + pause + '\n    "Luna scene"')
                an, cands = self.analyze(source)
                self.assertEqual(len(cands), 1, an.both_skipped)
                self.assertIn(pause, an.generate_both_patch(cands[0])['menu_choice_code'])

    def test_pause_and_call_expressions_still_rejected(self):
        for pause in ('pause(change_route())', 'pause(wait_time)', 'pause(-1)',
                      'pause(1, hard=True)', 'pause(float("inf"))', 'pause0.5'):
            with self.subTest(pause=pause):
                self.assert_rejected(JUMP_GAME.replace('    "Luna scene"', '    ' + pause + '\n    "Luna scene"'))
        for call in ('call luna_scene(value)', 'call expression target',
                     'call luna_scene from expression target'):
            with self.subTest(call=call):
                self.assert_rejected(JUMP_GAME.replace('jump luna_scene', call))

    def test_conditional_points_are_not_hoisted(self):
        source = JUMP_GAME.replace('label start:', 'default bonus = False\nlabel start:')
        source = source.replace('    $ anna_points += 2', '    if bonus:\n        $ anna_points += 2')
        an, cands = self.analyze(source)
        code = an.generate_both_patch(cands[0])['menu_choice_code']
        self.assertNotIn('Anna +2', code)
        state, _ = run_synthetic(self.apply(an, cands))
        self.assertEqual(state['anna_points'], 0)
        self.assertEqual(state['luna_points'], 2)

    def test_visibility_guards_preserved(self):
        source = JUMP_GAME.replace('label start:', 'default available = True\nlabel start:')
        source = source.replace('"Visit Anna":', '"Visit Anna" if available:')
        an, cands = self.analyze(source)
        self.assertIn('if (available):', an.generate_both_patch(cands[0])['menu_choice_code'])

    def test_hints_respect_all_styles_and_hide_switch(self):
        an, cands = self.analyze()
        for style, expected in [('number_and_name', '+2 Anna'), ('name_and_number', 'Anna +2'), ('number_only', '(+2, +2)'), ('none', None)]:
            an.options['hint_style'] = style
            code = an.generate_both_patch(cands[0])['menu_choice_code'].splitlines()[0]
            if expected:
                self.assertIn(expected, code)
            else:
                self.assertNotIn('+2', code)
        an.options.update(hint_style='number_and_name', show_hints=False)
        self.assertNotIn('+2', an.generate_both_patch(cands[0])['menu_choice_code'].splitlines()[0])

    def test_reapply_is_idempotent(self):
        an, cands = self.analyze()
        once = self.apply(an, cands)
        self.assertFalse(an.apply_both_patch(cands[0]))
        self.assertEqual(self.sources(an), once)
        self.assertEqual(an.detect_both_candidates(), [])

    def test_read_only_and_backup(self):
        an, cands = self.analyze(read_only=True)
        self.assertFalse(an.apply_both_patch(cands[0]))
        self.assertFalse(os.path.exists(cands[0].file_path + '.wtbak'))
        self.assertEqual(self.sources(an)['script.rpy'], JUMP_GAME)
        an.options['read_only'] = False
        self.apply(an, cands)
        with open(cands[0].file_path + '.wtbak', encoding='utf-8') as f:
            self.assertEqual(f.read(), JUMP_GAME)

    def test_crlf_is_preserved(self):
        an, cands = self.analyze(JUMP_GAME.replace('\n', '\r\n'))
        self.apply(an, cands)
        with open(cands[0].file_path, 'rb') as f:
            data = f.read()
        self.assertNotIn(b'\r\r\n', data)
        self.assertNotIn(b'\n', data.replace(b'\r\n', b''))

    def test_route_closure_is_not_overwritten_to_fake_safety(self):
        self.assert_rejected(JUMP_GAME.replace('$ luna_path = True', '$ anna_path = False'))

    def test_negative_points_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('$ luna_points += 2', '$ luna_points -= 2'))

    def test_unknown_python_rejected_even_if_contractsim_disabled(self):
        source = JUMP_GAME.replace('$ luna_points += 2', '$ unknown_function()')
        an, cands = self.analyze(source, contract_enforcement=False)
        self.assertEqual(cands, [])

    def test_screen_actions_are_not_noops(self):
        self.assert_rejected(JUMP_GAME.replace('scene luna_room', 'show screen unknown_ui'))

    def test_dynamic_control_flow_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('jump luna_scene', 'jump expression next_label'))

    def test_cross_scene_conditions_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('    $ luna_points += 2', '    if anna_points < 2:\n        $ luna_points += 2'))

    def test_future_route_loss_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('    "Common continuation"', '    if anna_points >= 2 and luna_points >= 2:\n        $ anna_path = False'))

    def test_non_monotone_future_scene_gates_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('    "Common continuation"', '    if anna_points == 2:\n        "Anna route"'))

    def test_future_inverse_route_content_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('    "Common continuation"', '    if anna_points >= 2:\n        "Anna route"\n    else:\n        "Other route"'))

    def test_unknown_future_flow_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('    "Common continuation"', '    call screen next_choice'))

    def test_parameterized_scene_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('label luna_scene:', 'label luna_scene(value=1):'))

    def test_recursive_scene_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('    $ luna_points += 2', '    call luna_scene'))

    def test_conditional_early_exit_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('    $ luna_points += 2', '    if anna_path:\n        jump together\n    $ luna_points += 2'))

    def test_executable_dialogue_interpolation_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('"Luna scene"', '"Luna [change_route()]"'))

    def test_duplicate_scene_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('jump luna_scene', 'jump anna_scene'))

    def test_stale_menu_rejected_without_touching_user_edits(self):
        an, cands = self.analyze()
        path = cands[0].file_path
        with open(path, 'w', encoding='utf-8') as f:
            f.write('# user edit\n' + JUMP_GAME)
        self.assertFalse(an.apply_both_patch(cands[0]))
        self.assertEqual(self.sources(an)['script.rpy'], '# user edit\n' + JUMP_GAME)

    def test_simulated_effects_do_not_inject_extra_points(self):
        an, cands = self.analyze()
        cands[0].choice_a.deltas_positive.append(('luna_points', 10000))
        state, _ = run_synthetic(self.apply(an, cands))
        self.assertEqual(state['luna_points'], 2)

    def test_no_analyzer_is_not_a_bridge_proof(self):
        dummy = type('Menu', (), {'analyzer': None})()
        self.assertFalse(studio._cs_bridge_ok(dummy, {'subset': []}))

    def test_source_change_between_plan_and_commit_aborts(self):
        an, cands = self.analyze()
        original_generate = an.generate_both_patch
        path = cands[0].file_path

        def changed(candidate):
            result = original_generate(candidate)
            with open(path, 'a', encoding='utf-8') as f:
                f.write('# external edit\n')
            return result

        with patch.object(an, 'generate_both_patch', side_effect=changed):
            self.assertFalse(an.apply_both_patch(cands[0]))
        self.assertEqual(self.sources(an)['script.rpy'], JUMP_GAME + '# external edit\n')
        self.assertFalse(os.path.exists(path + '.wtbak'))

    def test_changed_visibility_guard_does_not_unlock_choice(self):
        source = JUMP_GAME.replace('"Visit Anna":', '"Visit Anna" if available:')
        an, cands = self.analyze(source)
        path = cands[0].file_path
        edited = source.replace('if available:', 'if disabled:')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(edited)
        self.assertFalse(an.apply_both_patch(cands[0]))
        self.assertEqual(self.sources(an)['script.rpy'], edited)

    def test_post_point_thresholds_still_unlock_both_routes(self):
        source = JUMP_GAME.replace('    "Common continuation"',
                                  '    if anna_points >= 2:\n        "Anna unlocked"\n'
                                  '    if luna_points >= 2:\n        "Luna unlocked"')
        an, cands = self.analyze(source)
        _, seen = run_synthetic(self.apply(an, cands))
        self.assertEqual(seen[-2:], ['"Anna unlocked"', '"Luna unlocked"'])

    def test_shared_continuation_points_awarded_once(self):
        source = JUMP_GAME.replace('    "Common continuation"', '    $ anna_points += 1\n    "Common continuation"')
        an, cands = self.analyze(source)
        state, seen = run_synthetic(self.apply(an, cands))
        self.assertEqual(state['anna_points'], 3)
        self.assertEqual(state['luna_points'], 2)
        self.assertEqual(len(seen), 3)

    def test_scene_chain_preserves_middle_scene(self):
        source = JUMP_GAME.replace('    jump together\nlabel luna_scene:',
                                  '    jump anna_extra\nlabel anna_extra:\n'
                                  '    "Anna extra scene"\n    $ anna_points += 1\n'
                                  '    jump together\nlabel luna_scene:')
        an, cands = self.analyze(source)
        state, seen = run_synthetic(self.apply(an, cands))
        self.assertEqual(state['anna_points'], 3)
        self.assertEqual(seen, ['"Anna scene"', '"Anna extra scene"', '"Luna scene"', '"Common continuation"'])

    def test_return_context_dependency_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('    "Common continuation"', '    if _return is None:\n        "A scene"'))

    def test_no_points_needed_for_two_distinct_scenes(self):
        source = JUMP_GAME.replace('    $ anna_points += 2\n', '').replace('    $ luna_points += 2\n', '')
        an, cands = self.analyze(source)
        state, seen = run_synthetic(self.apply(an, cands))
        self.assertEqual(len(seen), 3)
        self.assertEqual(state['anna_points'], 0)

    def test_budget_exhaustion_fails_closed(self):
        an, _ = self.analyze()
        with patch.object(studio.BothScenePlanner, 'LIMIT', 1):
            self.assertEqual(an.detect_both_candidates(), [])

    def test_incompatible_choice_does_not_block_safe_subset(self):
        source = JUMP_GAME.replace('label anna_scene:', '        "Close Anna route":\n            $ anna_path = False\nlabel anna_scene:')
        an, cands = self.analyze(source)
        self.assertEqual(len(cands), 1, an.both_skipped)
        self.assertEqual(len(cands[0].choices), 2)
        state, _ = run_synthetic(self.apply(an, cands))
        self.assertTrue(state['anna_path'])

    def test_bom_preserved(self):
        an, cands = self.analyze('\ufeff' + JUMP_GAME)
        self.apply(an, cands)
        with open(cands[0].file_path, 'rb') as f:
            self.assertTrue(f.read().startswith(b'\xef\xbb\xbf'))

    def test_return_to_unknown_menu_caller_is_not_treated_as_game_end(self):
        source = JUMP_GAME.replace('label start:',
                                  'label start:\n    call choice_hub\n'
                                  '    if anna_points >= 2 and luna_points >= 2:\n'
                                  '        $ anna_path = False\n    return\nlabel choice_hub:')
        self.assert_rejected(source)

    def test_menu_reached_by_jump_from_called_label_also_rejected(self):
        source = JUMP_GAME.replace('label start:',
                                  'label start:\n    call wrapper\n    return\n'
                                  'label wrapper:\n    jump choice_hub\nlabel choice_hub:')
        self.assert_rejected(source)

    def test_menu_history_set_is_not_silently_dropped(self):
        source = JUMP_GAME.replace('    menu:', '    menu:\n        set visited_choices')
        self.assert_rejected(source)

    def test_menu_arguments_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('    menu:', '    menu (custom=True):'))

    def test_choice_arguments_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('"Visit Anna":', '"Visit Anna" (custom=True):'))

    def test_nested_dialogue_interpolation_cannot_hide_python_call(self):
        self.assert_rejected(JUMP_GAME.replace('"Luna scene"', '"Luna [change_route([1])]"'))

    def test_escaped_dialogue_interpolation_cannot_hide_python_call(self):
        self.assert_rejected(JUMP_GAME.replace('"Luna scene"', r'"Luna \x5bchange_route()]"'))

    def test_escaped_literal_brackets_are_not_treated_as_python(self):
        source = JUMP_GAME.replace('"Luna scene"', '"Luna [[literal bracket]"')
        an, cands = self.analyze(source)
        self.assertEqual(len(cands), 1, an.both_skipped)

    def test_point_variable_cannot_be_overwritten_with_true(self):
        self.assert_rejected(JUMP_GAME.replace('$ anna_points += 2', '$ anna_points = True'))

    def test_character_object_cannot_be_overwritten_with_true(self):
        source = JUMP_GAME.replace('label start:', 'define anna = Character("Anna")\nlabel start:')
        source = source.replace('$ anna_path = True', '$ anna = True')
        source = source.replace('"Luna scene"', 'anna "Luna scene"')
        self.assert_rejected(source)

    def test_shared_continuation_indirect_point_gate_is_checked(self):
        source = JUMP_GAME.replace('label start:', 'default maya_points = 0\nlabel start:')
        source = source.replace('    "Common continuation"',
                                '    if anna_points >= 2:\n        $ maya_points += 1\n'
                                '    if luna_points >= 2:\n        $ maya_points += 1\n'
                                '    if maya_points == 1:\n        "Maya route"')
        self.assert_rejected(source)

    def test_shared_continuation_indirect_inverse_flag_gate_is_checked(self):
        source = JUMP_GAME.replace('label start:', 'default extra_scene = False\nlabel start:')
        source = source.replace('    "Common continuation"',
                                '    if anna_points >= 2:\n        $ extra_scene = True\n'
                                '    if not extra_scene:\n        "Another route"')
        self.assert_rejected(source)

    def test_write_success_is_not_reported_as_failure_on_cache_error(self):
        an, cands = self.analyze()
        with patch.object(an, '_cache_file_meta', side_effect=RuntimeError('cache refresh failed')):
            self.assertTrue(an.apply_both_patch(cands[0]))
        self.assertIn('wt_scene_bridge:', self.sources(an)['script.rpy'])

    def test_numeric_nonpoint_variable_cannot_be_overwritten_with_true(self):
        source = JUMP_GAME.replace('label start:', 'default season = 4\nlabel start:')
        self.assert_rejected(source.replace('$ anna_path = True', '$ season = True'))

    def test_unknown_variable_is_not_assumed_to_be_boolean_route_flag(self):
        self.assert_rejected(JUMP_GAME.replace('$ anna_path = True', '$ unknown_state = True'))

    def test_flat_dialogue_interpolation_is_preserved(self):
        source = JUMP_GAME.replace('label start:', 'default player_name = "Player"\nlabel start:')
        source = source.replace('"Luna scene"', '"Luna greets [player_name]"')
        an, cands = self.analyze(source)
        self.assertEqual(len(cands), 1, an.both_skipped)
        self.assertIn('[player_name]', an.generate_both_patch(cands[0])['menu_choice_code'])

    def test_unclosed_dialogue_interpolation_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('"Luna scene"', '"Luna [unknown_state"'))

    def test_unicode_escaped_dialogue_interpolation_rejected(self):
        self.assert_rejected(JUMP_GAME.replace('"Luna scene"', r'"Luna \u005bchange_route()]"'))

    def test_python_jump_from_called_label_preserves_unknown_return_context(self):
        source = JUMP_GAME.replace('label start:',
                                  'label start:\n    call wrapper\n    return\n'
                                  'label wrapper:\n    $ renpy.jump("choice_hub")\nlabel choice_hub:')
        self.assert_rejected(source)

    def test_dynamic_jump_from_called_label_has_no_return_safety_proof(self):
        source = JUMP_GAME.replace('label start:',
                                  'label start:\n    call wrapper\n    return\n'
                                  'label wrapper:\n    jump expression "choice_hub"\nlabel choice_hub:')
        self.assert_rejected(source)


if __name__ == '__main__':
    unittest.main()
