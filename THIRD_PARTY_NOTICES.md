# Third-party notices

The project MIT license applies to original project contributions, not a claim
of authorship over the components below. Original notices remain in the embedded
payloads. This file makes the corresponding notices accessible without decoding
those payloads.

## Embedded unrpyc

- Upstream: https://github.com/CensoredUsername/unrpyc
- The bundled `unrpyc.py` identifies itself as **v2.0.3**.
- License: MIT; full notice and per-file copyright statements are reproduced in
  [LICENSES/unrpyc-MIT.txt](LICENSES/unrpyc-MIT.txt).
- The exact upstream commit is not recorded; do not describe this bundle as a
  verified, unmodified upstream checkout. The application contains a local
  embedded archive and its own codec/extraction integration.

## Embedded modified Ren'Py engine script

- Upstream project: https://github.com/renpy/renpy
- Component: a modified `renpy/script.py`-derived script embedded in the application.
- Its header credits **Copyright 2004-2026 Tom Rothamel** and grants the MIT license.
- Exact notice: [LICENSES/renpy-script-MIT.txt](LICENSES/renpy-script-MIT.txt).
- The precise upstream revision and every intermediate modification are not
  independently established. The retained license is not an endorsement of this tool.
- This is not a bundled full SDK. Do not add downloaded engines, game assets,
  archives, or saves to the repository or source release.

## Optional dependencies and Windows builds

The tested GUI dependency is CustomTkinter **5.2.2**, not an untested automatic
upgrade to a newer major version. It has its own MIT notices and bundled font
licenses. darkdetect, packaging, psutil, Python, Tcl/Tk, and PyInstaller also
retain their own licenses. PyInstaller's build-tool license includes an exception
for generated applications; it does not replace this project's license.

The Windows packaging script gathers installed dependency notices and Python /
Tcl/Tk runtime license files into the portable ZIP. Review `BUILD_INFO.json` and
`licenses/runtime/` in the resulting artifact before publishing it.

### Bundled fonts and Tcl/Tk

CustomTkinter 5.2.2 includes Roboto Regular and Medium, whose font metadata states
**Copyright 2011 Google Inc. All Rights Reserved.** and Apache License 2.0.
The complete license is in [LICENSES/Roboto-Apache-2.0.txt](LICENSES/Roboto-Apache-2.0.txt).
The shapes font is retained with CustomTkinter's MIT notice. Fonts are not modified.
The Tcl/Tk fallback notices come from the official `tcltk/tcl` and `tcltk/tk`
`core-8-6-branch` license.terms files; the build prefers installed runtime notices
where present. Python's own LICENSE and installed dependency notices are also copied.
Additional notices cover the bundled OpenSSL 3.0.18 (Apache 2.0), zlib-ng 2.2.4,
XZ/liblzma 5.2.5, mpdecimal 4.0.0 and Expat 2.7.3 runtime components. Their source
URLs and text hashes are recorded in `LICENSES/RUNTIME_SOURCES.json`. Python's
LICENSE also retains bzip2, libffi, Zstandard and Microsoft runtime terms.
OpenSSL README copyright: Copyright (c) 1998-2025 The OpenSSL Project;
Copyright (c) 1995-1998 Eric A. Young, Tim J. Hudson.
The Microsoft Distributable Code restrictions apply only to those Microsoft
components, not the original MIT project code. Use this Windows build on Windows;
do not remove Microsoft notices or redistribute those components separately.

## Compatibility fixtures and names

Fixtures are reduced, hand-authored functional tests with shortened presentation;
they are not distributed game archives or complete game scripts. Compatibility
identifiers and short matching anchors do not imply affiliation with a game or
mod author. Do not contribute proprietary dialogue, artwork, audio, binaries,
saves, or authentication data as a bug reproduction.
