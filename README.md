# Ren'Py Walkthrough Studio

**0.1.0b1 — beta.** A single-file Python application for source-based Ren'Py
choice analysis, conservative Both/All scene composition, and optional in-game
walkthrough hints. The current GUI and generated hints are primarily Turkish.

[Türkçe kullanım](docs/README_TR.md) · [Analysis limits](docs/ANALYSIS.md) ·
[Validation](docs/VALIDATION.md) · [Release instructions](docs/RELEASING.md)

> Always work on a separate copy of a game you own or are authorized to modify.
> A neutral option means **not proven**, not necessarily harmless or ineffective.
> This project is not affiliated with or endorsed by the Ren'Py project or game authors.

## Run from source

Use Python **3.12 or newer**. The command-line interface uses the standard
library; the GUI requires Tkinter and the optional GUI dependencies.

```powershell
python -m pip install -r requirements-gui.txt
python renpy_walkthrough_studio.py
```

Tkinter is supplied with the usual Windows Python installer. Linux users may
need their distribution's Tkinter package. `psutil` is optional for additional
process detection; it is included in the optional Windows portable build.

Alternatively, install the local project with its console entry point:

```powershell
python -m pip install ".[gui]"
renpy-walkthrough-studio --version
```

There is no mandatory guide, LLM, account, or API key.

## Scan first, then patch a copy

Create the report directory first. A scan does not patch game sources:

```powershell
python renpy_walkthrough_studio.py "C:\GameCopy" --cli --scan --detect-both --report "C:\Reports\analysis.json" --both-report "C:\Reports\both.json"
```

Apply only to the copy after reviewing the report:

```powershell
python renpy_walkthrough_studio.py "C:\GameCopy" --cli --apply-both --no-cheat-menu
```

Leave backups enabled. `--skip-rpa` skips archive extraction when source scripts
are already available. Use `--help` to see all options and `--version` when
reporting a problem. Do not enable container executable extraction for untrusted games.

## Windows portable application

Windows builds are **portable ZIPs**, not installers. Extract the entire ZIP;
keep the executable and `_internal` directory together. No system Python is
required for a frozen build. The console is retained so CLI commands and error
messages remain available; a console window may remain visible behind the GUI.

The manual `Windows portable build` GitHub Actions workflow produces an artifact
and checksums. It **does not create or publish a GitHub Release**. Maintainers
review the artifact before uploading it to Releases. Local building is also
documented in [RELEASING.md](docs/RELEASING.md).

Unsigned builds can trigger reputation or antivirus warnings. Do not disable
security software or add broad exclusions; verify the checksum, use source
instead, and report a suspected false positive to the security vendor.

## What the analysis does not promise

- It is a bounded source model, not a complete Python/Ren'Py interpreter.
- Dialogue, label names, or opening an `if` condition do not prove death or benefit.
- Unknown effects, incomplete entry coverage, and unsupported control flow remain
  uncertain. A completed solver is not automatically complete game-route coverage.
- Both copies supported scene bodies and runs a common continuation once. It does
  not guarantee every ending in every commercial game.
- 52 preserved tests target a removed Engine/guide API and are explicitly skipped,
  not counted as passing. See [VALIDATION.md](docs/VALIDATION.md).

## Development

```powershell
python -B -m unittest discover -s tests
python scripts/check_repository.py
```

Native validation is opt-in, requires an explicitly supplied local engine, and
runs only private copies. No Ren'Py SDK, commercial game, game archive, or save is
included in this repository. Unit tests do not download or run a game executable.

## License

Original project code is licensed under [MIT](LICENSE). Embedded unrpyc and
modified Ren'Py engine-script components retain their own MIT notices; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [LICENSES](LICENSES).
Optional build dependencies and bundled runtimes retain their separate licenses.
This license does not grant rights to distribute or modify someone else's game.
