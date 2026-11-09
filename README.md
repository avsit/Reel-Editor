# Reel Studio

A Claude Code plugin that edits talking-head reels (9:16, 30 fps) in **your** brand, and checks every cut before you see it.

You film and rough-cut. Reel Studio does the rest: word-synced captions, a hook that types out as you say it, 50/50 source splits with the real article and an underline on the phrase you say, statements that stay below your neck, up to two full-screen takeovers with particle illustrations, a 21-effect library, sound design and a mastered mix. Then two QA gates: an automated one (face guard, only your words, brand fonts and colours, loudness, render spec, the first 3 seconds) and an independent reviewer agent that scores the cut and lists defects with timestamps.

Works on macOS, Windows and Linux. Everything runs locally.

## Install

In Claude Code:
```
/plugin marketplace add avsit/Reel-Editor
/plugin install reel-studio@reel-studio
```
Then:
```
/reel-setup
```
Setup checks your machine and installs what's missing **one step at a time, asking first**: FFmpeg, Node 18+ and Python 3.10+ (via Homebrew, winget or apt), then HyperFrames + GSAP, a Python venv (numpy, Pillow, OpenCV, faster-whisper), the YuNet face model, and optional extras (cut-outs, OCR, earshot). Everything except the three system tools lives in `~/.cache/reel-studio`.

Setup ends by asking for your **brand doc**.

## Your brand

Fill in [`brand/brand.template.md`](brand/brand.template.md) (or let Claude ask you its questions): colours, fonts, rules, sound, what you never want to see. [`brand/example.brand.md`](brand/example.brand.md) is a finished example for a fictional creator.

```
/reel-brand path/to/my-brand.md
```
Claude turns it into `brand/brand.json`, checks the colours are legible on a phone, fetches your fonts (with your OK) and shows a style board of stills for you to approve. Every reel is drawn from that file.

## Edit a reel

```
/reel-edit path/to/rough-cut.mp4 talking
```
`talking` opens on your face from frame 0 with the hook typed above you; `graphic` opens on a cover card. Claude asks if you don't say.

Each reel gets a folder in `reels/<name>/` with the plate, transcript, `edit.py` (the edit, as code), `timeline.json` (the plan), the render and a `qa/` report.

```
/reel-qa reels/<name>
```
re-runs both QA gates on any render.

## How it's built

| Part | What |
|---|---|
| `engine/prep.py` | rough cut → plate, cleaned voice (−14 LUFS), word timings, face track, project |
| `engine/build.py` | `edit.py` → HyperFrames page + `timeline.json`; frame-exact timing, face guard, layouts, captions |
| `engine/mix.py` | voice + optional ducked music + SFX, with stems for QA |
| `engine/qa_reel.py` | Gate A: every rule that can be measured |
| `engine/effects/` | the 21-effect library, in your brand |
| `engine/tools/` | cut-outs, code/engraving/halftone looks, phrase finder (OCR) |
| `skills/` | reel-setup, reel-brand, reel-editor (+ QA.md, EFFECTS.md) |
| `agents/reel-qa.md` | Gate B: the independent reviewer |

## Rules it keeps (change them in your brand file)
- Text never on, beside or above your face.
- Only words you say, shown when you say them.
- At most two takeovers per reel; one accent word per frame; captions always on.
- The first 3 seconds always move.
- Light grade on your face; stylised looks only inside takeovers.

## Licence
MIT, © 2026 Inneraktive. Third-party code and packages: see [CREDITS.md](CREDITS.md).
