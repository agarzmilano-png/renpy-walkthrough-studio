# Validation record

This is a beta, not a claim of universal Ren'Py compatibility.

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
