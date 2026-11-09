# Effects library

21 motion effects for HyperFrames reels, drawn in the user's brand (colours and display font come from brand.json).
Code: `RS/engine/effects/fx.py` (one function per effect) and `fx.css`. Pre-render looks: `RS/engine/tools/stylize.py`.

## Rules every effect keeps
1. **Text is below the neck.** Effects that carry words place them at y ≥ 1240 by default; check each against the face guard.
2. **Nothing on screen the speaker didn't say.** No function hard-codes copy: every word comes from the edit, i.e. the transcript.
3. **Takeovers count.** Effects marked **TAKEOVER** replace the frame: call `takeover_used()` in edit.py for each one so the brand's limit holds.
4. **Captions band** is y 1414–1504: chest effects default to top ≈ 1250–1300; hide captions (`NO_CAPS`) where they would clash.

## How to use in edit.py
The build gives you `FX`, a Comp already wired into the reel's page and timeline, and puts `fx` on the import path.
```python
import fx
fx.predict_keys(FX, wt("ship", 12.0), wt("it", 13.2) + 0.4, text="ship it")
fx.impact_frame(FX, 20.3, 21.0, word="huge"); takeover_used()
```
Cut-out effects need a person matte for the same window (source seconds = reel seconds when the plate plays 1:1):
```bash
python3 RS/engine/tools/stylize.py --brand brand/brand.json cutout   public/input-video.mp4 A B public/pre/cut.webm
python3 RS/engine/tools/stylize.py --brand brand/brand.json code     public/input-video.mp4 A B public/pre/code.mp4
python3 RS/engine/tools/stylize.py --brand brand/brand.json engrave  public/input-video.mp4 A B public/pre/engrave.mp4
python3 RS/engine/tools/stylize.py --brand brand/brand.json halftone public/input-video.mp4 A B public/pre/halftone.mp4
python3 RS/engine/tools/stylize.py --brand brand/brand.json blowaway public/input-video.mp4 A B public/pre/blow.webm
```
Run these with the reel-studio venv Python (numpy, Pillow). Mattes: Apple Vision on a Mac, MediaPipe elsewhere; all local.

## The 21 effects

| # | Effect | Type | Needs | What it does / how it's built |
|---|---|---|---|---|
| 01 | `live_cursor` | overlay | — | A Figma-style multiplayer cursor drags an accent selection box round the speaker. It adds handles, a size tag and the cursor name tag at the bottom-right (below the neck). |
| 02 | `clone_row` | overlay | cutout | Cut-out copies slide out to both sides, receding in scale and brightness, then slide back. |
| 03 | `day_dial` | overlay | cutout | A conic-gradient mask sweeps a paper world in like a clock hand. A tick-only dial turns behind the cut-out, then it sweeps out. |
| 04 | `predict_keys` | overlay | — | A phone keyboard slides up under the neck and types the speaker's phrase; each key flashes in the accent. |
| 05 | `orbit_ring` | overlay | cutout | 3D letters orbit the chest. The front half is drawn over the cut-out and the back half behind it, with per-letter visibility computed from rotation (seek-safe). |
| 06 | `code_body` | **TAKEOVER** | pre: code | The speaker is redrawn in code characters (accent highlights, paper mids, faint room) with a scan wipe in and out. |
| 07 | `post_wall` | overlay | — | A contribution-style tile wall fills in on the chest while a counter climbs. **Only use a number the speaker says.** |
| 08 | `letter_dive` | **TAKEOVER** (transition) | — | A paper card where the display letters are windows onto the live video. The camera dives through the full stop (`origin`) back into the shot. |
| 09 | `comment_drop` | overlay | — | Comment cards drop onto a stack under the neck. Built for the comment-keyword CTA . |
| 10 | `layer_explode` | **TAKEOVER** | — | The frame tilts into 3D and splits into glass layers (video, accent frame, waveform, label), then snaps back. |
| 11 | `sketch_words` | overlay | cutout | The room becomes ruled paper. A display word draws itself in hatching across the chest, with a mono note and an accent-ink underline. |
| 12 | `blade_slice` | transition | — | A white blade swipes diagonally; the two halves slide apart along the cut and rejoin (0.8 s). |
| 13 | `chest_stack` | overlay | — | Paper tags fly in with motion blur and pile up on the chest, then fly off. |
| 14 | `rack_focus` | overlay | cutout | Focus pulls to the room (background blurs), then to nothing (speaker softens), then back. |
| 15 | `banknote` | **TAKEOVER** | pre: engrave | A paper banknote with an engraved portrait in an oval and the speaker's phrase typed digit by digit beneath it. Corner marks are bottom only. |
| 16 | `voice_note` | overlay | — | An accent voice-message bubble pops in under the neck and its waveform fills as it plays. |
| 17 | `impact_frame` | **TAKEOVER** | — | Comic panel: the shot crushed to black-and-white ink, radial speed lines, a heavy word low on the frame and two invert flashes. |
| 18 | `dolly_zoom` | overlay | cutout | Vertigo: the room shrinks away while the speaker holds or grows slightly. A blurred fill covers the edges, so no clean plate is needed. |
| 19 | `press_front` | **TAKEOVER** | pre: halftone | A newspaper front: a live halftone photo on top, then masthead, headline, standfirst and greyed column rules. The columns are placeholder bars, not invented text. |
| 20 | `paper_tear` | transition | — | Paper strips with interlocking torn edges hang for `hold` seconds, then fall and rotate away to reveal the shot. |
| 21 | `blow_away` | **TAKEOVER** (ending) | pre: blowaway | The speaker disintegrates left to right into particles over a brand background. |

Also available: `chapter(c, a, b, n, total, name)`, an "07 / 21 · Name" pill for list-style reels.

## Picking effects for a reel
- **Per reel:** 3–5 overlays at most, takeovers within the brand limit, at most 1 transition between sections. Tasteful beats busy: many reels need none.
- **Land on the word:** start each effect on the spoken word it illustrates (`wt()`).
- **Sound:** a whoosh on takeover in/out, a UI tick on pops and typing, an impact hit on `impact_frame`; never louder than the voice.
- **Grade:** stylised looks happen only inside takeovers. The face keeps the light grade.

## Known limits
- The cut-out edge shows where the speaker meets a desk on full-frame paper backgrounds (`day_dial`, `sketch_words`). Frame tighter, or accept it as a paper-cut look.
- `orbit_ring` letters behind the body hide on dark clothing; the ring reads as a front arc.
- `code_body` follows the plate's brightness: on a dark plate the room is mostly empty.
- Alpha WebM cut-outs render in HyperFrames' Chrome: check a snapshot before the final render.
