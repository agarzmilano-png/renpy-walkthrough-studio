"""Opt-in real-engine test controller. Never imported by the application.

Runs only in an isolated generated test game. Presentation is replaced with
deterministic choices; Ren'Py's execution loop, saves and rollback stay native.
"""
import json
import os
import traceback

import renpy

events = []
phase = 'initial'
slot = 'both_' + os.environ.get('WT_NATIVE_SLOT', os.environ['WT_NATIVE_CASE'])


def state():
    names = ['anna_points', 'luna_points', 'prefer_anna', 'ticket']
    if hasattr(renpy.store, 'maya_points'):
        names.append('maya_points')
    return {name: getattr(renpy.store, name) for name in names}


def record(kind, **details):
    events.append(dict(kind=kind, state=state(), **details))


def finish(error=None):
    result = {'engine': str(renpy.version), 'case': os.environ['WT_NATIVE_CASE'],
              'presentation_suppressed': True, 'native_execution_loop': True,
              'events': events, 'final': state(), 'error': error}
    with open(os.environ['WT_NATIVE_RESULT'], 'w', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
    os._exit(1 if error else 0)


def choose(items, *args, **kwargs):
    global phase
    case = os.environ['WT_NATIVE_CASE']
    if case == 'load_fresh' and phase == 'initial':
        phase = 'load_requested'
        record('load_requested', fresh_process=True)
        renpy.loadsave.load(slot)
        finish('Native load unexpectedly returned')
    if phase == 'initial' and not any(e['kind'] == 'menu' for e in events):
        renpy.store.ticket = os.environ.get('WT_NATIVE_TICKET', 'True') == 'True'
        renpy.store.anna_points = int(os.environ.get('WT_NATIVE_ANNA', '0'))
        renpy.store.luna_points = int(os.environ.get('WT_NATIVE_LUNA', '0'))
    valid = [(caption, index) for caption, cond, index in items
             if index is not None and renpy.python.py_eval(cond)]
    pick = os.environ.get('WT_NATIVE_PICK', 'Mod: Both')
    if phase == 'rollback_requested':
        pick = os.environ.get('WT_NATIVE_REPICK', pick)
        phase = 'replaying'
    matches = [index for caption, index in valid if pick in caption]
    if len(matches) != 1:
        finish('Requested choice not uniquely available: ' + repr(valid))
    record('menu', picked=pick)
    renpy.game.log.did_interaction = True
    renpy.exports.checkpoint(matches[0])
    return matches[0]


def say(who, what, *args, **kwargs):
    global phase
    text = str(what)
    record('say', text=text, phase=phase)
    # A deterministic interaction/checkpoint without renderer/user input.
    renpy.game.log.did_interaction = True
    renpy.exports.checkpoint()
    case = os.environ['WT_NATIVE_CASE']
    save_at = {'save_first': 'Anna branch', 'save_second': 'Luna branch',
               'save_and_rollback': 'Anna branch'}.get(case)
    if text == save_at and phase == 'initial':
        renpy.loadsave.save(slot)
        phase = 'saved'
        record('saved', at=text)
    if text == 'Done':
        if phase == 'saved':
            phase = 'load_requested'
            record('load_requested', fresh_process=False)
            renpy.loadsave.load(slot)
            finish('Native load unexpectedly returned')
        rollback_case = case.startswith('rollback_') or case == 'save_and_rollback'
        if rollback_case and phase in ('initial', 'load_requested'):
            record('rollback_log', entries=[
                {'node': str(entry.context.current),
                 'type': type(renpy.game.script.lookup(entry.context.current)).__name__,
                 'line': renpy.game.script.lookup(entry.context.current).linenumber,
                 'what': str(getattr(renpy.game.script.lookup(entry.context.current), 'what', '')),
                 'checkpoint': entry.hard_checkpoint}
                for entry in renpy.game.log.log])
            target_kind = 'Say' if case == 'rollback_between' else 'Menu'
            # Ren'Py 8.5 represents dialogue as TranslateSay, unlike 8.1's Say.
            dialogue_types = ('Say', 'TranslateSay')
            checkpoints = 0
            for entry in reversed(renpy.game.log.log):
                checkpoints += bool(entry.hard_checkpoint)
                node = renpy.game.script.lookup(entry.context.current)
                if target_kind == 'Say':
                    # Ren'Py groups assignments before a dialogue into the same
                    # checkpoint. Find the checkpoint that leads to scene two.
                    for _ in range(12):
                        if type(node).__name__ in dialogue_types or node.next is None:
                            break
                        node = node.next
                matches_type = (type(node).__name__ in dialogue_types if target_kind == 'Say'
                                else type(node).__name__ == target_kind)
                if matches_type and (target_kind != 'Say' or node.what == 'Luna branch'):
                    break
            else:
                finish('Native rollback target not found')
            phase = 'rollback_requested'
            record('rollback_requested', checkpoints=checkpoints, target=target_kind)
            renpy.exports.rollback(force=True, checkpoints=checkpoints, greedy=False)
            finish('Native rollback unexpectedly returned')
        finish()


def install():
    renpy.exports.menu = choose
    renpy.exports.say = say
    renpy.config.exception_handler = lambda *args: finish(traceback.format_exc())
