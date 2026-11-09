---
name: reel-editor
description: Edit a talking-head reel (9:16, 30 fps) end to end in the user's own brand with Reel Studio. Use it for any request to edit, re-edit or version a short-form talking-head video ("edit this reel", "make a reel from this clip", "do a v2 with a cover open"). It runs intake (including the head-or-cover opening choice), transcript and clean plate, planning, build, sound and render, then the QA process (automated Gate A plus the independent reel-qa agent), one fix round, and delivery. Needs a brand file first (reel-brand) and a set-up machine (reel-setup).
---

# Reel editor

You are the user's editor. Every reel goes through the same phases, and each phase has a gate. **The user is never the first viewer:** never show a cut that hasn't passed QA.

`RS` below is the plugin root: the folder that holds `.claude-plugin/` (two levels up from this file; `${CLAUDE_PLUGIN_ROOT}` when set). Use the Python that `python3 RS/scripts/doctor.py` reports; scripts that need the engine's packages use the reel-studio venv themselves.

## Before you start
1. **Machine ready?** `python3 RS/scripts/doctor.py`. Anything required missing → run the **reel-setup** skill first.
2. **Brand ready?** Look for `brand/brand.json` in the user's working folder. None → run the **reel-brand** skill first. Never invent a brand.
3. Read `QA.md` (next to this file), especially *Recurring lessons*: they are the expensive mistakes.

## Phases

| # | Phase | Do | Gate |
|---|---|---|---|
| 0 | **Intake** | Find the rough cut (the user cuts it; you edit it). Ask **one** round, only what can't be inferred: **opening = their head (talking open) or a cover (graphic open)** (unless `brand.opening_default` says), source screenshots or B-roll they want shown, a logo to show. | Opening decided |
| 1 | **Prep** | `python3 RS/engine/prep.py <rough_cut> reels/<name> --brand brand/brand.json --open <talking\|graphic>`: plate 1080×1920/30 with a light grade, voice at −14 LUFS, word timings (`transcript.json`), face track (`build/face.json`), project layout and a starter `edit.py`. Read the transcript against the audio for misheard words and fix them in `transcript.json`. | Transcript checked |
| 2 | **Plan** | A beat sheet from their words. **The first 3 s first:** the hook types out or is revealed in sync with the spoken words, from the first word, with motion in every 0.5 s. Then: source mentions → 50/50 split with the real source and a one-phrase underline; short contrasts → statements; ≤ `max_takeovers` ideas worth a takeover; the CTA. Every element is cued to a word time with `wt()`. Real screenshots only. Show the plan to the user in a few lines before building if the reel is longer than 30 s. | ≤ max takeovers, a change every 2–4 s, nothing the speaker didn't say |
| 3 | **Build** | Write `reels/<name>/edit.py` (the starter shows every component; `templates/edit_example.py`). Run `python3 RS/engine/build.py reels/<name>`. Talking open with the title behind the head: render the cut-out first (`engine/tools/stylize.py --brand brand/brand.json cutout public/input-video.mp4 0 <G> public/pre/cut_open.webm`). Source underlines: `engine/tools/find_text.py <img> <y0> <y1> "<phrase>"` gives the boxes. Effects: `EFFECTS.md`. | Face guard all OK (the build fails otherwise), then lint 0 errors |
| 4 | **Look proof** | `hyperframes snapshot --at 0,0.3,0.6,…,3.3` for the hook, one frame of each component, each takeover and the CTA (the hyperframes binary is in `~/.cache/reel-studio/node/node_modules/.bin/`; run it inside `public/`). Look at each at full size. | Nothing near the face, nothing overprinted or cropped, one accent thing per frame, a single caret |
| 5 | **Sound** | Pick SFX for graphic moments only (4–10). With earshot installed: `earshot rank` a plain-words query, `earshot find` the clean trim, files in `~/.cache/reel-studio/sfx/` or the project. Accents on a spoken word must be bright (5–9 kHz) and sit where the voice dips. Music only if the user supplies a licensed track (`reel.json` `music`). Run `python3 RS/engine/mix.py reels/<name>` with the reel-studio venv Python (it needs numpy). | Bed ≈ 17–18 dB under the voice (from `sound/bed_stem.wav`), −14 LUFS / ≤ −1.5 dBTP |
| 6 | **Render + Gate A** | In `public/`: `hyperframes render -o "../<name> v1.mp4"`. Then `python3 RS/engine/qa_reel.py reels/<name> --video "reels/<name>/<name> v1.mp4"`. Graphic open: also export the full-headline cover still for the platform thumbnail. | No FAIL (H9, the first 3 seconds, included) |
| 7 | **Gate B** | Spawn the **reel-qa** agent with only the project folder and the render. | Every axis ≥ 8 and no P0 → ship. Otherwise **one** fix round, then report to the user; a second round needs their OK |
| 8 | **Deliver** | Give the file (and cover still) and a short report: what's in it, Gate A/B, logged DECISIONs they can overturn in one reply, what wasn't verified. Append new lessons to `QA.md` *Recurring lessons* in the user's copy if they keep one. | — |

**Variants** (e.g. both openings): build each in **its own project folder** (`reels/<name>-talking`, `reels/<name>-cover`). Rebuilding a folder Gate B is reading swaps its files mid-review.

## House rules (from the brand file's `rules`, defaults shown)
- **Text below the neck** (`text_below_neck`): nothing on, beside or above the face. A talking-open title above the head is allowed only when the user asks for it, logged as a DECISION.
- **Only the speaker's words** (`speaker_words_only`), shown when they are said: no paraphrase, no claim ahead of time. Labels, sources and handles go in `brand.allow_words`.
- **Takeovers ≤ `max_takeovers`** (2), each 2.5–5.5 s, never opening on an empty or noise frame.
- **One accent word** per frame (`accent_one_word`).
- **Captions always on** (`captions_always_on`), hidden only while the same words are on screen.
- **Avoid the lav-mic LED** (`avoid_mic_led`): a statement never crosses it.
- **50/50 splits:** source top, speaker bottom, both edge to edge, captions at the seam.
- **Light grade only** on the face. Looks (code, halftone, engraving) happen only inside takeovers.
- Tasteful and structured beats busy: one moving idea at a time.

## Never
- Leave the first 3 seconds static.
- Show a word the speaker didn't say, or show it before they say it.
- Make an SFX louder than the voice, or put a sound on every motion.
- Use music, logos or footage the user hasn't supplied or confirmed they may use. Ask before accepting any terms, spending money or credits, or downloading files.
- Report something as checked that you didn't measure or look at.
