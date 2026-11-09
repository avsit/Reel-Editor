# Reel QA process

Every reel passes two gates before the user sees it. **Gate A** measures everything that can be measured. **Gate B** is an independent reviewer (the `reel-qa` agent) who never saw the build and judges what needs eyes. Then there is **one** fix round, a re-check, and delivery to the review room.

The rule from video-director applies: *the user is never the first viewer.*

## Gate A: automated (`engine/qa_reel.py`)

```bash
python3 RS/engine/qa_reel.py reels/<name> --video "reels/<name>/<render>.mp4"
```

| ID | Check | Pass |
|---|---|---|
| H1 | Text below the neck | Every chest element and the caption band start below the neck line of their section (chin from `build/face.json` + 90 px) |
| H2 | Takeovers | ≤ 2 |
| H3 | Only the speaker's words | Every on-screen word appears in the transcript, or is a label, source, handle or date on the brand's `allow_words`. More than 6 unknown words fail |
| H4 | Fonts | Only the brand's fonts (`timeline.json` `house.fonts`, written by the build from brand.json) |
| H5 | Colours | Only the brand's colours (`house.colours`); a few greys for dimmed text are fine |
| H6 | Sound | −14 LUFS ±1, true peak ≤ −1.5 dBTP; 4–10 SFX, on graphic moments only. The bed is judged from `sound/bed_stem.wav` in Gate B, never from the mix |
| H7 | Render | 1080×1920, constant 30 fps, length = plan ±2 frames |
| H8 | Lint | `hyperframes lint`: 0 errors |
| H3b | The speaker's words, on time | Every element's words are said within 2 s of when it's on screen (catches paraphrases) |
| H9 | First 3 seconds | No static stretch ≥ 0.5 s anywhere in 0–3 s; the hook must keep moving |
| V1 | Timeline | video-director `check_timeline.py`: 0 errors. Each warning is fixed or written as a `DECISION` in `timeline.json` |
| V2 | Render QA | video-director `qa_video.py --beats timeline.json`: no FAIL. Real cuts and the speaker's own jump cuts within 1 frame, and every detected change planned. Also makes `beats_sheet`, `phone_sheet` and `hook_sheet` |

**Gate A must be PASS or WARN-with-decisions before Gate B starts.** A FAIL goes straight back to the build.

## Gate B: independent review (the `reel-qa` agent)

The agent gets only:
- the render;
- the Gate A report and sheets;
- `timeline.json`;
- the transcript;
- this file;
- the brand file (`brand/brand.json`) and the brand doc it came from;
- the audio stems in `sound/`.

It does not get the build reasoning.

**Default to reject.** Score every axis 1–10 with evidence (a timestamp and what is on screen).

| Axis | What it looks for (house + video-director) |
|---|---|
| **Hook** | The most important part of the reel. Sound off: what is this about by 3 s? Hook ≥ 84 px, typed or revealed in sync with the spoken words, motion in every 0.5 s, frame 0 not flat (a separate cover image covers the thumbnail) |
| **Face & framing** | No text on, beside or above the face. Punch-ins anchored on the face, ≤ 3. Light grade only (no LUT look) |
| **Truth** | Every word on screen is the speaker's (H3 list reviewed one by one). Sources real and labelled. No invented numbers |
| **Readability** | 360 px phone sheet: every caption and tag readable. Nothing overprinted during swaps. Caption band clear |
| **Brand** | The brand file: its display font for statements and captions, its label font for labels; one accent thing per frame; nothing on the brand's `never` list; splits full-bleed 50/50 |
| **Motion** | Per-letter reveals and caption fades are smooth (no snapping colour, no teleport). Moves ≥ 100 ms. Easing by role. No AI tells (stock gradients, everything bouncing, random scrambles) beyond the logged decisions |
| **Rhythm** | A visual change every 2–4 s. No dead stretch > 4 s on the same framing. Takeovers ≤ 2 and 2.5–5.5 s each |
| **Sync** | Pops land on the spoken word (±2 frames). SFX on picture events, never on every motion |
| **Sound** | Voice always on top. Bed ≈ 17–18 dB under the voice, measured from the bed stem. Accents on spoken words audible by band (bright, 5–9 kHz), never louder than the voice. No chimes posing as whooshes; no sub-only hits (earshot) |

**Bar: ship when every axis is ≥ 8 and there are no P0 defects.**

**Defect levels:**
- **P0:** breaks a hard rule. Text near the face, words the speaker didn't say, a takeover over the limit, a loudness fail, broken or missing media.
- **P1:** a viewer would notice. Unreadable, off-sync, off-brand, a dead stretch.
- **P2:** polish.

Each defect gets: a timestamp, the symptom, the likely mechanism, and a *measurable* fix.

**Output:** `qa/review.md`, containing:
- the one-sentence message (muted test);
- the scores;
- the ranked defects;
- `SHIP` or `ONE MORE PASS`;
- the weakest moment.

## Fix round (once)

1. Fix every P0, then axes scored ≤ 7, worst first. Leave anything scored ≥ 9 alone.
2. Write each fix as a card in `qa/fixes.md`: the timecode scope, what must not change, the target.
3. Rebuild, re-render, and re-run Gate A.
4. Re-run Gate B on the changed moments only.
5. If it still fails, stop and report to the user with the remaining defects. Don't loop silently.

## Delivery

- A versioned render goes in `reels/<name>/`.
- Report:
  - what changed;
  - Gate A result;
  - Gate B scores;
  - logged decisions they can overturn in one reply;
  - what was not verified.
- The user's notes become the next take's fix cards.

## Recurring lessons (append as they happen)

These were learned the expensive way on real reels. They are built into the engine; keep them when you write an edit.

- **Frame-exact times, rounded down.** Rounding up starts a clip a frame late and leaves a 1-frame blank at a cut. A clip's length comes from its frame-exact start and end, never `round(b - a)` (`q`, `qd` in build.py).
- **Screenshot panels mount 0.2 s early and invisibly** so the image is painted before its cut.
- **Frame 0 is the thumbnail**, but it doesn't have to carry the whole headline: export a separate full-headline cover still.
- **The first 3 seconds are the most important part of a reel.** A cover that sat frozen for 1.2 s failed. The hook types or reveals in sync with the spoken words from the first word; Gate A H9 fails any static stretch ≥ 0.5 s in 0–3 s.
- **The opening is a choice on every reel:** the speaker's head (talking open) or a cover (graphic open).
- **Captions hide while the same words are on screen** (statements, takeovers, the CTA), or the screen says everything twice (`SAME`, `NO_CAPS`).
- **Elements quote the speaker's exact words**, keyed to the first one. A paraphrase ("like Google" for "similarly to Google") reads as a claim they didn't make; H3b checks a ±2 s window.
- **Underlines go on the phrase as it is said**, one stroke per line, found with `find_text.py`, never a multi-line block and never ahead of the word.
- **A takeover never opens on an empty frame**, and its lead-in line clears as the next idea arrives (left on screen, two lines can read as the opposite of what was said).
- **Line breaks go between word blocks, never inside one** (`say()` handles `<br>`).
- **Particle scenes are pure functions of reel time**, driven by a proxy tween (`driver()`): deterministic and seek-safe. Morphs sweep in x order, never a random scramble.
- **Typed letters landing on the same frame:** the caret hands over on the frame the next letter appears, or two carets show.
- **Splits are full-bleed 50/50.** Source edge to edge on top with a paper header strip for its label (it also clears the platform's top bar); the speaker edge to edge below; captions at the seam. No narrow cards, side gaps or empty bottom.
- **A logo that rolls in gets its own lane** and never crosses text that is being typed.
- **Statements avoid the lav-mic LED** (`led_y`): fully above or fully below it.
- **Never judge the music bed from the full mix.** The mix writes `sound/bed_stem.wav`, `voice_stem.wav` and `sfx_stem.wav`; measure from those. A mix-based estimate once "fixed" an approved bed 8 dB too quiet.
- **`loudnorm` outputs 192 kHz:** resample to 48 kHz straight after it, and keep a −120 dB floor on the sidechain voice, or the bed goes silent under the end card.
- **An accent on a spoken word can't be louder than the voice.** Use a bright sound (≈5–9 kHz) that cuts through by frequency. Hits in gaps can have body (~1.6 kHz). Sub-only booms vanish on phone speakers.
- **The speaker's own jump cuts** are detected from the plate (a one-frame jump in mean frame difference > max(6, 5× the median), face sections) and recorded as `plate_cuts`, so QA doesn't flag them. `scdet` at 2.4 missed two real cuts in testing. In-layout changes (statements appearing) go in `swaps`: they only *explain* detected changes.
- **Variants go in their own folders.** Rebuilding the folder a reviewer is reading swaps its files mid-review.
- **Effects declare their windows.** Each fx effect's start and end are planned swaps, and motion inside its window is that effect, not a cut (`house.fx_windows`).
- **Fonts must exist as files, not just in the CSS.** A missing font file renders in a fallback serif while the CSS still names the brand font; H4 now fails it.
- **The talking-open hook goes on the chest** (below the neck, clear of the LED) unless there's a cut-out and the user asked for a title behind the head.
- **On a dark cover, particle fields draw in the text colour** (`onDark` cue): in the ground colour they are invisible. Keep the field and the headline in separate zones.
