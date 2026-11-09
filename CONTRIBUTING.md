# Contributing

Use Python 3.12+ and keep the application logic in `renpy_walkthrough_studio.py`.
Optional build/test scripts do not turn the runtime into a multi-module dependency.

Run `python -B -m unittest discover -s tests` and
`python scripts/check_repository.py` before proposing a change. Reproduce bugs
with small synthetic sources. Do not add game archives, copied proprietary
scripts, screenshots with private information, SDK binaries, or saves.

Preserve unknown effects and complete-coverage requirements. More colored options
are not by themselves a correctness improvement. Do not lower budgets, remove
negative effects, or translate missing legacy APIs into fake passing adapters.
Explain decision/source/backup differences. Do not silently replace old baselines
to make a correctness test green.

Native tests require an explicitly supplied local engine and a new private output
directory. They must not modify the supplied engine or original game. CI unit
tests must not download or launch games. Explain any new dependency/license and
preserve all embedded copyright notices.
