---
name: reel-setup
description: Set up Reel Studio on this machine (macOS, Windows or Linux) - checks FFmpeg, Node, Python and the engine's packages, installs what's missing one step at a time with the user's OK, then hands over to reel-brand so the user uploads their brand doc. Use on first install, when the user says "set up reel studio", or when another Reel Studio skill finds something missing.
---

# Reel Studio setup

`RS` is the plugin root (the folder holding `.claude-plugin/`, two levels up from this file; `${CLAUDE_PLUGIN_ROOT}` when set). Everything the engine installs goes in one cache folder, `~/.cache/reel-studio` (override with `REEL_STUDIO_CACHE`): a Python venv, the Node packages, models, compiled helpers and SFX. Nothing is installed globally except the three system tools, and those only with the user's OK.

## 1. Check
Run `python3 RS/scripts/doctor.py` (Windows: `py -3 RS\scripts\doctor.py`). Show the user the report as a short list: what's ready, what's missing.

## 2. Install, one step at a time, asking first
For each missing item, tell the user in one line what it installs, from where and roughly how big, then wait for a yes before running it.

| Item | How | What it is |
|---|---|---|
| python / ffmpeg / node | the `install:` command doctor prints for this OS (Homebrew, winget or apt) | system tools; may ask for an admin password, so the **user** runs the command if it needs one |
| node-deps | `python3 RS/scripts/setup.py node-deps` | HyperFrames (renderer, Apache-2.0) and GSAP 3 from npm, into the cache (~150 MB) |
| browser | `python3 RS/scripts/setup.py browser` | the headless Chrome HyperFrames renders with (~170 MB) |
| python-deps | `python3 RS/scripts/setup.py python-deps` | a venv with numpy, Pillow, OpenCV (headless) and faster-whisper (~400 MB) |
| models | `python3 RS/scripts/setup.py models` | OpenCV's YuNet face detector (0.2 MB, GitHub). faster-whisper fetches its speech model (~150 MB) on first use |
| matte (optional) | Mac: `setup.py xcode-clt` (Apple's Command Line Tools for the Vision cut-out); else `setup.py matte` (MediaPipe) | person cut-outs for the talking open and cut-out effects |
| ocr (optional) | Mac: same Command Line Tools; else `setup.py ocr` (RapidOCR) | finds a phrase in a screenshot for the underline |
| earshot (optional) | `python3 RS/scripts/setup.py earshot` | listen-and-pick sound effects (MIT, pinned commit) |

Some installs show licence terms (e.g. Xcode Command Line Tools): the user accepts those themselves. Never accept terms for them.

## 3. Re-check
Run doctor again. Required items all ✓ → done. Anything still failing → show the exact error and the fix; don't loop.

## 4. Hand over
Tell the user setup is complete and that the next step is their brand: run the **reel-brand** skill, which asks them to upload or write their brand doc (`RS/brand/brand.template.md` is the fill-in template; `RS/brand/example.brand.md` is a finished example).
