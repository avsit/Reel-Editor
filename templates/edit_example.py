# ═════════════ edit.py · THE EDIT for one reel (Reel Studio) ═════════════
# build.py runs this file. Every name below comes from the engine (engine/build.py):
#   wt(word, near)               start time of a spoken word (cues always come from the speaker's words)
#   seg(a, b, layout)            "face" | "split" (50/50: source on top, speaker below) | "full" | "card"
#   say(prefix, [(text, t, cls)])         words that arrive as they are spoken
#   stmt(id, a, b, html, size)   a statement below the neck (and clear of a lav-mic LED)
#   typed_words(prefix, [(text, word, near, cls)])   the hook typed out as it is said ("|" = line break)
#   shot(id, img, source, a, b, views, marks)        a real source in the top half of a split, one underline per phrase
#   takeover(id, a, b, html)     full screen; counts toward brand.rules.max_takeovers
#   driver(scene, a, b, cue)     a particle scene (templates/particles.js) as a pure function of time
#   FX + fx functions            the effects library (engine/effects/fx.py), e.g. fx.predict_keys(FX, a, b, text=...)
#   SFX.append((name, t, role, file, trim0, trim1, why))   role: ui | whoosh | hit
#   NO_CAPS, SAME, CAP_ENDS, DECISIONS, HERO
# CSS classes: .disp (display type), .lab (label), .acc (the ONE accent word), .full/.dark/.light, .stmt
#
# This starter is generic: it builds a working reel from ANY transcript so a fresh project renders end to end.
# Claude replaces it with the real edit after planning (skills/reel-editor). Keep the two hard rules:
#   1. the first 3 seconds always move (the hook types out as it is said; nothing is still for 0.5 s)
#   2. head or cover is the user's choice: reel.json "open" = "talking" (their face from frame 0) or "graphic" (a cover)

def _clean(w): return w["text"].lower().strip(".,!?;:\"'")
first = WORDS[:min(6, len(WORDS))]
G = min(3.4, max(2.2, first[-1]["end"] + 0.15))             # the hook runs until those words are said
hook_words = [w for w in first if w["end"] <= G]
accent = max(hook_words, key=lambda w: len(_clean(w)))     # the longest word carries the one accent
# lines break by width, not word count: at size px a display line holds about 920 / (0.56 * size) characters
HOOK_PX = 140 if OPEN == "graphic" else 96                 # talking open: the hook sits on the chest, below the neck
while max(len(w["text"]) for w in hook_words) > 920 / (0.56 * HOOK_PX): HOOK_PX -= 10
budget, parts, line = int(920 / (0.56 * HOOK_PX)), [], 0
for i, w in enumerate(hook_words):
    if line and line + len(w["text"]) > budget: parts.append(("|", "", 0, "")); line = 0
    parts.append((w["text"] + (" " if i < len(hook_words) - 1 else ""), _clean(w), w["start"], "acc" if w is accent else ""))
    line += len(w["text"]) + 1
HEAD = typed_words("hd", parts)
NO_CAPS.append((0.0, G))                                    # the hook IS the caption here

if OPEN == "graphic":
    # COVER OPEN: a full-bleed card, the headline typed as it's said, a particle field behind it, a slow push-in
    seg(0.0, G, "card")
    clip("open", 0.0, G, f"""<canvas id="cv-field_to_stream" width="1080" height="1920"></canvas>
      <div class="lab" style="top:1110px">{BRAND.get('handle', BRAND['name'])}</div>
      <div class="disp" style="top:1190px;font-size:{HOOK_PX}px">{HEAD}</div>""", "full dark", 4)
    js(f"tl.fromTo('#open',{{scale:1}},{{scale:1.04,duration:{G},ease:'none',immediateRender:false}},0);")
    driver("field_to_stream", 0.0, G, {"start": 0.0, "head": accent["start"], "onDark": True})
    DECISIONS.append("DECISION: cover open (reel.json open=graphic): typed headline over a particle field")
else:
    # TALKING OPEN: the speaker from frame 0, the hook typed on the chest as it's said, a slow punch-in on the face.
    # (A title above or behind the head needs a cut-out and the user's say-so: engine/tools/stylize.py cutout, logged as a DECISION.)
    seg(0.0, G, "face")
    neck = int(chin_max(0.0, G) * 1.05 - 36) + NECK_PAD       # chin after the 5% punch-in (anchored at 540,720)
    top = neck + 10
    L, lines = led_y(0.0, G), HEAD.count("<br>") + 1          # never set a line across a lav-mic LED
    if L and not (top + lines * HOOK_PX <= L - 34): top = max(top, int(L * 1.05 - 36) + 26)
    GUARD.append(("open-t", 0.0, G, top, neck))
    clip("open-t", 0.0, G, f'<div class="disp" style="top:{top}px;font-size:{HOOK_PX}px">{HEAD}</div>', "full", 6, "background:transparent")
    js(f"tl.fromTo('#video-wrap',{{x:0,y:0,scale:1}},{{x:{540 * -0.05:.1f},y:{720 * -0.05:.1f},scale:1.05,duration:{G:.2f},ease:'none',immediateRender:false}},0);")
    DECISIONS.append("DECISION: talking open (reel.json open=talking): hook typed on the chest, below the neck, as it's said")

# BODY: the speaker, with one statement on the longest sentence's key phrase, back to face, then the sign-off
seg(G, VID, "face")
sent, cur = [], []
for w in WORDS:
    if w["start"] < G + 0.5: continue
    if cur and (w["start"] - cur[-1]["end"] > 0.25 or len(cur) == 6): sent.append(cur); cur = []   # a pause or 6 words ends a phrase
    cur.append(w)
    if w["text"].endswith((".", "?", "!")): sent.append(cur); cur = []
if cur: sent.append(cur)
mid = [s for s in sent if 3 <= len(s) <= 8 and s[-1]["end"] - s[0]["start"] >= 1.0]
if mid:
    s = mid[len(mid) // 2]
    key = max(s, key=lambda w: len(_clean(w)))
    html = say("s1", [(w["text"] if w is not key else f"<span class='acc'>{w['text']}</span>", w["start"], "") for w in s])
    stmt("st1", s[0]["start"], min(VID, s[-1]["end"] + 0.4), html, 84)
    DECISIONS.append(f"DECISION: one statement on '{' '.join(w['text'] for w in s)}' (starter edit)")

# END CARD: the brand name after the last word
seg(VID, DUR, "end")
clip("end", VID, DUR, f'<div class="disp" style="top:860px;font-size:96px">{BRAND["name"]}</div>'
     f'<div class="lab" style="top:1000px">{BRAND.get("handle", "")}</div>', "full dark", 4)
rise("#end .disp", VID + 0.05)
HERO = {"t": round(accent["start"], 3), "what": "the accent word lands in the typed hook"}
