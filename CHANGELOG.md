# Changelog

## 0.1.0b2 — 2026-11-10

- Fixed a batch-write race exposed by Linux CI: an external edit to the file just
  patched could be mistaken for the application's own write. The batch now records
  the temporary file's own signature before replacement and checks sources again
  immediately after each write, including the last one.
- Expanded the existing regression to cover four file orders and edits to either
  the current file or another file. No tests or CI platforms were removed.
- This is a write-safety fix, not a change to analysis/color rules. Existing beta
  artifacts remain historical; new downloads use the new version and checksums.

## 0.1.0b1 — 2026-11-10

First GitHub-oriented beta preparation.

- Single-file application with an explicit version and `--version` command.
- Conservative source-based choices and Both/All scene planning.
- Incoming-state fixed point, transitive assignments, relevant-state memoization,
  actual caller continuations, and type-sensitive scalar keys.
- Unknown effects, incomplete coverage, and unsupported constructs stay uncertain.
- Narrative/label wording and condition satisfaction do not manufacture proof.
- Source-change checks, backups, read-only scan, and optional CLI/GUI operation.
- MIT project license and retained embedded-component MIT notices.
- Standard-library unit CI plus a manual, non-publishing Windows portable workflow.
- Preserved visibility of 52 skipped contracts for the removed legacy API.

This beta does not certify every game's routes, every Ren'Py version, or all
Python/init/screen behavior. See `docs/VALIDATION.md` for scope and test evidence.
