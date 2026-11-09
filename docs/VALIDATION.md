# Validation record

This is a beta, not a claim of universal Ren'Py compatibility.

## 0.1.0b2: Linux CI fix and rerun

The initial b1 run passed its three Windows jobs but failed the three Linux jobs
in the external-edit regression. Filesystem enumeration exposed a real batch-write
race: an external edit to the just-written target could be accepted as our own.
b2 records the temporary file's own signature before replacement and rechecks all
tracked sources immediately after each write. The existing regression now covers
four first-file orders and edits to both the current and another file (8 subcases).
The old method was also confirmed to fail all four current-target orders on Windows.
Manual checks also cover edits after the final write and no-op acknowledgement.

All **six** Windows/Linux × Python 3.12/3.13/3.14 jobs passed for the fix:
[GitHub Actions run 42701790134](https://github.com/agarzmilano-png/renpy-walkthrough-studio/actions/runs/42701790134).
The full suite remains **315 total, 263 passed, 52 unchanged legacy skips**.
No platform, test or safety requirement was removed. All **149 native scenarios**
also passed again with the b2 source hash on both tested engines.
See [validation-0.1.0b2.json](validation-0.1.0b2.json) for current evidence.

The b2 wheel installed without GUI dependencies and its CLI passed version/help/
config checks with the recorded application hash. The b2 Windows portable build
passed CLI, read-only Unicode-path scan, and visible GUI open/close checks locally.
Clean Windows VM testing and code signing remain unperformed.

The analysis/color algorithms are unchanged. This fix is not a general filesystem
locking/transaction guarantee; do not edit game sources while a patch is running.

## Historical 0.1.0b1 evidence

## Unit tests

```powershell
python -B -m unittest discover -s tests
```

The pre-publication suite contains **315 tests: 263 passing and 52 explicitly
skipped legacy API contracts**. The skipped contracts target the removed Engine
and guide API; they do not mean 52 observed failures, and are not counted as
successes. They remain visible in `tests/legacy_accuracy_contracts.py`.

The source includes 128 deterministic generated-program comparisons of projected
state against a full-state reference, conservative incoming joins, unknown effects,
type-sensitive memo keys, source-change/backup checks, and unsupported-flow guards.

## Native validation

The published beta source was exercised again on **2026-11-10** with Ren'Py
**8.1.3.23091805** and **8.5.3.26051504** in private copies. All **149** scenarios
passed and every runner's application hash matched the staged LF source:

- 120 Both/All scenarios, including actual saves, fresh-process loads, rollback,
  original choices, multiple files, and harmless fatal-sounding narration.
- 22 entry-context scenarios, including transitive assignments, bool/int differences,
  caller termination, all-hidden menus, and default-store aliases. Native quit
  callbacks observe actual terminal execution.
- 7 end-to-end official **The Question** scenarios. Original routes retain the same
  dialogue sequence; the added Both executes both scenes and the common ending once.

Presentation and choices are automated; engine execution/state/save/rollback are
native. These counts are not 149 different commercial games or exhaustive routes.
The beta source hash and checks are recorded in
[validation-0.1.0b1.json](validation-0.1.0b1.json); no engine or game assets are distributed.

Reproduce with local engines you are authorized to use:

```powershell
python tests/run_native_matrix.py --engine v813=LOCAL_ENGINE --engine v853=LOCAL_SDK --output NEW_MATRIX_DIRECTORY
python tests/run_native_context_validation.py --engine LOCAL_ENGINE --output NEW_CONTEXT_DIRECTORY
python tests/run_native_example_validation.py --sdk LOCAL_SDK --output NEW_EXAMPLE_DIRECTORY
```

Do not point tests at your only game copy. Output directories must be new.

## Real-source comparison

An earlier private 117-source corpus run completed the global model in 18,218
steps instead of aborting at 300,001, with the limit unchanged. It recovered 60
observed menus, but opaque effects still prevented complete incoming coverage.
No new definitive colors were claimed; output/backup/Both hashes remained equal.
Preparation overhead increased one diagnostic whole-worker time from about
20.3 to 25.6 seconds. This is not advertised as an end-to-end speed improvement.

Private game scripts, engine copies, local paths, and original-game reports are
intentionally not published. The small synthetic fixtures are included so the
general behavior can be tested without acquiring a commercial game.

## Platform claims

Local source/GUI checks were performed on Windows with Python 3.14.2 and
CustomTkinter 5.2.2. The GitHub Actions matrix is configured for Windows/Linux and
Python 3.12–3.14, but a configured workflow is not an already-run CI result.
Portable executable smoke tests do not replace a clean Windows VM test, antivirus
reputation review, or code signing.

The local Python 3.14.2 x64 frozen console/onedir build passed `--version`, `--help`,
`--list-config`, a read-only synthetic scan in a Unicode path, and visible GUI
open/close. The scan preserved the entire synthetic game file inventory and hashes.
A wheel was built, installed without optional dependencies in another environment,
and its CLI entry point passed version/help/config checks. A source distribution
was also built successfully. Dependency/font/runtime notices accompany the Windows
ZIP. These are local checks, not clean-machine or GitHub-hosted CI results.
