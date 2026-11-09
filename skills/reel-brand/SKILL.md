---
name: reel-brand
description: Turn the user's brand doc (a markdown file about their look, fonts, colours, rules and sound) into the brand.json every Reel Studio edit is drawn from, validate it for phone legibility, fetch the fonts with permission, and show a still style board for approval. Use after reel-setup, when the user uploads or pastes a brand md, or says "change my brand / colours / fonts".
---

# Reel Studio brand

`RS` is the plugin root (two levels up from this file; `${CLAUDE_PLUGIN_ROOT}` when set). The brand lives in the user's working folder: `brand/brand.md` (theirs, human-written) → `brand/brand.json` (yours, machine-read). Every edit reads only brand.json.

## 1. Get the brand doc
Ask the user to upload or paste their brand doc. If they don't have one, give them `RS/brand/brand.template.md` to fill in (or ask its questions in one short round). `RS/brand/example.brand.md` shows a finished one. Save theirs as `brand/brand.md`.

## 2. Write brand.json
Map the doc onto `RS/brand/schema.json` (example: `RS/brand/example.brand.json`):
- `colors`: `ground` (background), `text`, `muted`, `paper` (light panels), `accent` (the ONE highlight), `accent_ink` (a deeper accent for underlines on paper). Hex only.
- `fonts`: `display` (statements, hooks, captions), `body`, `label` (small caps/mono labels): family, weight, tracking.
- `rules`: keep the defaults unless the doc says otherwise; never loosen `text_below_neck` or `speaker_words_only` without the user saying so in plain words.
- `allow_words`: their name, handle, tagline words and recurring source names (words allowed on screen that they don't say).
- `sound`: `music` stays `null` unless they give a file they're licensed to use; `bed_db_under_voice` default 18.
- `never`: their "never want to see" list, verbatim.
- `opening_default`: "talking", "graphic" or "ask".
Fill gaps from the doc's spirit, and list every value you inferred so they can correct it.

## 3. Validate
`python3 RS/engine/brand.py validate brand/brand.json`. It checks contrast for phone legibility (text/ground ≥ 7:1, accent/ground ≥ 4.5:1) and the schema. A failure → propose the nearest passing colour, show both, let them pick.

## 4. Fonts (ask first)
Say which families will be downloaded from Google Fonts (free, OFL), then on a yes: `python3 RS/engine/brand.py fonts brand/brand.json ~/.cache/reel-studio/fonts/brand`. A family that isn't on Google Fonts: ask the user for the font file (woff2/ttf) and confirm they hold a licence that covers video. prep.py copies the fonts into each project.

## 5. Style board (stills)
`python3 RS/engine/style_board.py brand/brand.json brand/style_board.html` renders one page of stills in their brand: a typed hook frame, a statement below a placeholder head, a 50/50 split, a takeover with particles, captions and the end card. Screenshot it (`hyperframes snapshot` or the browser) and show it. Iterate on their notes until they approve; only then is the brand ready for **reel-editor**.
