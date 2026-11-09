#!/usr/bin/env python3
"""Reel Studio build engine.

    python3 engine/build.py <project_dir>

A project folder holds:
  reel.json          {"name", "brand": "<path to brand.json>", "vid": <plate seconds>, "dur": <reel seconds>, "open": "graphic|talking"}
  transcript.json    word timings [{"text","start","end"}...]   (engine/prep.py)
  build/face.json    face samples [t, top, chin, left, right, ...] (engine/prep.py, OpenCV YuNet)
  edit.py            THE EDIT: the only file written per reel (see templates/edit_example.py)
  public/            input-video.mp4, broll/, fonts/, vendor/gsap.min.js, particles.js (engine/new_project.py sets this up)

The engine supplies frame-exact timing, the face guard, layouts (face / 50-50 source split / full), components (statements,
typed hooks, source shots with one-phrase underlines, takeovers, particle scene drivers), captions, the HyperFrames page and
timeline.json (the one source of truth the mix and QA read). Every look comes from the brand file; every rule from brand.rules.
All times are ABSOLUTE seconds on the reel timeline.
"""
# run inside the reel-studio venv (numpy, Pillow, OpenCV live there), whatever python3 the user called
import os as _os, sys as _sys
_VPY = _os.path.join(_os.path.expanduser(_os.environ.get("REEL_STUDIO_CACHE", "~/.cache/reel-studio")), "venv",
                     "Scripts" if _os.name == "nt" else "bin", "python.exe" if _os.name == "nt" else "python")
if _os.path.exists(_VPY) and _os.path.realpath(_sys.prefix) != _os.path.realpath(_os.path.dirname(_os.path.dirname(_VPY))):
    _os.execv(_VPY, [_VPY] + _sys.argv)

import json, math, os, sys, subprocess, re

ENGINE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
PUB = f"{ROOT}/public"
REEL = json.load(open(f"{ROOT}/reel.json"))
BRAND = json.load(open(os.path.join(ROOT, REEL["brand"]) if not os.path.isabs(REEL["brand"]) else REEL["brand"]))
RULES = {"text_below_neck": True, "max_takeovers": 2, "speaker_words_only": True, "accent_one_word": True,
         "avoid_mic_led": True, "captions_always_on": True, **BRAND.get("rules", {})}
C = BRAND["colors"]
NIGHT, BONE, FOG, PAPER, LIME, LIME_INK = C["ground"], C["text"], C["muted"], C["paper"], C["accent"], C.get("accent_ink", C["accent"])
FPS, W, H = 30, 1080, 1920
VID, DUR = float(REEL["vid"]), float(REEL["dur"])
OPEN = os.environ.get("OPEN", REEL.get("open", "graphic"))

# frame-exact times, rounded DOWN to 4 decimals (rounding up started clips a frame late -> 1-frame blanks at cuts)
q = lambda t: math.floor(round(t * FPS) / FPS * 10000) / 10000
# clip length from frame-exact start and end (rounding the length on its own drifted a frame past a cut)
qd = lambda a, b: math.floor((round(b * FPS) - round(a * FPS)) / FPS * 10000) / 10000
JS, HTML = [], []
CAP_TOP, CAP_H = 1414, 90
NECK_PAD = 90
MAX_TAKEOVERS = int(RULES["max_takeovers"])

def js(s): JS.append(s)
def hide(sel): js(f"tl.set('{sel}',{{opacity:0}},0);")
def rise(sel, t, d=0.3, dy=30):
    hide(sel); js(f"tl.fromTo('{sel}',{{opacity:0,y:{dy}}},{{opacity:1,y:0,duration:{d},ease:'power3.out',immediateRender:false}},{q(t)});")
def maskup(sel, t, d=0.35):
    js(f"tl.set('{sel}',{{clipPath:'inset(100% 0% 0% 0%)'}},0);")
    js(f"tl.fromTo('{sel}',{{clipPath:'inset(100% 0% 0% 0%)',y:24}},{{clipPath:'inset(0% 0% 0% 0%)',y:0,duration:{d},ease:'power3.out',immediateRender:false}},{q(t)});")

# ───────────── words, face guard, mic LED ─────────────
WORDS = json.load(open(f"{ROOT}/transcript.json"))
def wt(word, near):
    """Start time of the spoken word closest to `near` (cues come from the speaker's words, never typed by hand)."""
    c = [w for w in WORDS if w["text"].lower().strip(".,!?") == word.lower()]
    if not c: raise SystemExit(f"edit.py: '{word}' is never said (near {near}s); only the speaker's words go on screen")
    return min(c, key=lambda w: abs(w["start"] - near))["start"]
FACE = json.load(open(f"{ROOT}/build/face.json"))["samples"]
def chin_max(a, b):
    s = [x[2] for x in FACE if x[1] is not None and a <= x[0] < b]
    return max(s) if s else 1215
GUARD = []
LED_CACHE = f"{ROOT}/build/led.json"
LED = json.load(open(LED_CACHE)) if os.path.exists(LED_CACHE) else {}
def led_y(a, b):
    """Lowest y of a lav-mic LED (small bright green dot) in this window, from 3 plate frames (cached). 0 if none."""
    if not RULES["avoid_mic_led"]: return 0
    k = f"{a:.2f}-{b:.2f}"
    if k not in LED:
        import numpy as np
        from PIL import Image
        ys = []
        for t in (a + 0.1, (a + b) / 2, b - 0.1):
            tmp = f"{ROOT}/build/_led.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", f"{PUB}/input-video.mp4", "-frames:v", "1", tmp], check=True)
            px = np.asarray(Image.open(tmp).convert("RGB")).astype(int)[900:1600]
            m = (px[..., 1] > 170) & (px[..., 0] < 120) & (px[..., 2] < 170) & (px[..., 1] - px[..., 0] > 90)
            if 10 < m.sum() < 400: ys.append(int(np.nonzero(m)[0].max()) + 900)   # a dot, not a green scene
        LED[k] = max(ys) if ys else 0
        json.dump(LED, open(LED_CACHE, "w"))
    return LED[k]

# ───────────── layouts ─────────────
FULLF = "x:0,y:0,scale:1,clipPath:'inset(0px 0px 0px 0px round 0px)'"
SR0, SR1 = 280, 1240        # 50/50 split: the speaker's half shows plate rows 280..1240 (hair to chest) at 1:1, full width
SPLIT = f"x:0,y:{960 - SR0},scale:1,clipPath:'inset({SR0}px 0px {H - SR1}px 0px round 0px)'"
SEGS = []
def seg(a, b, lay, bg=None): SEGS.append((a, b, lay, bg or NIGHT))

def clip(cid, a, b, inner, cls, track, style=""):
    HTML.append(f'<div class="clip {cls}" id="{cid}" data-start="{q(a)}" data-duration="{qd(a, b)}" data-track-index="{track}" style="{style}">{inner}</div>')

TAKEOVERS = 0
def takeover(cid, a, b, inner, cls="full dark"):
    global TAKEOVERS
    TAKEOVERS += 1
    assert TAKEOVERS <= MAX_TAKEOVERS, f"brand rule: at most {MAX_TAKEOVERS} takeovers per reel"
    clip(cid, a, b, inner, cls, 4)
    js(f"tl.fromTo('#{cid}',{{scale:1}},{{scale:1.02,duration:{b - a:.2f},ease:'none',immediateRender:false}},{q(a)});")

K = 1080 / 1290   # source screenshots are captured 1290 px wide; the split panel is 1080
def shot(pid, img, src, a, b, views, marks):
    """Source panel (top half of a 50/50 split). views: [(t, y_offset_px_in_source, scroll_dur)];
    marks: [(t, [x, y, w, h] in source px, draw_dur)] one underline per phrase the speaker says (find_text gives boxes)."""
    mk = "".join(f'<i class="mk" id="{pid}-m{i}" style="left:{r[0]*K:.1f}px;top:{r[1]*K - 2:.1f}px;height:{r[3]*K + 4:.1f}px"></i>'
                 for i, (_, r, _) in enumerate(marks))
    clip(pid, a - 0.2, b, f'<div class="inner" id="{pid}-in"><img src="broll/{img}" alt="" />{mk}</div>', "shot", 3 if int(a * 10) % 2 else 5)
    js(f"tl.set('#{pid}',{{opacity:0}},0);tl.set('#{pid}',{{opacity:1}},{q(a)});")   # mounted 0.2 s early so it paints before its cut
    clip(f"{pid}-src", a, b, f'<div class="src">Source · {src}</div>', "credit", 3)
    pv = None
    for (t, off, d) in views:
        st = f"x:0,y:{-off * K:.1f},scale:1"
        if pv is None: js(f"tl.set('#{pid}-in',{{{st}}},{q(t)});")
        else: js(f"tl.fromTo('#{pid}-in',{{{pv}}},{{{st},duration:{d},ease:'power2.inOut',immediateRender:false}},{q(t)});")
        pv = st
    for i, (t, r, d) in enumerate(marks):
        js(f"tl.fromTo('#{pid}-m{i}',{{width:0}},{{width:{round(r[2] * K + 8, 1)},duration:{d},ease:'power2.out',immediateRender:false}},{q(t)});")

NO_CAPS = []    # windows where captions are hidden (the words are on screen already: cover lines, takeovers)
SAME = []       # (from, to, "words on screen"): caption chunks overlapping this window that share a content word are hidden
CAP_LOW = []    # (a, b, top[, class]) caption band overrides
STMT_WIN, STMT_FIRST, SAY_T0 = [], [], []

def say(prefix, parts):
    """Words that arrive on their spoken times: [(text, time, extra_class)]; '<br>' at the start of a text breaks the line."""
    SAY_T0.append(parts[0][1]); out = []
    for i, (txt, t, cls) in enumerate(parts):
        sid = f"{prefix}{i}"
        if txt.startswith("<br>"): out.append("<br>"); txt = txt[4:]
        out.append(f'<span class="wd {cls}" id="{sid}">{txt}</span>')
        js(f"tl.set('#{sid}',{{clipPath:'inset(0% 0% 100% 0%)'}},0);tl.fromTo('#{sid}',{{clipPath:'inset(0% 0% 100% 0%)',y:22}},{{clipPath:'inset(0% 0% -20% 0%)',y:0,duration:0.26,ease:'power2.out',immediateRender:false}},{q(t)});")
    return " ".join(out).replace("<br> ", "<br>").replace(" <br>", "<br>")

def stmt(cid, a, b, html, size=96, captions=False):
    """A statement below the neck (and clear of a mic LED). Captions hide under it unless captions=True (e.g. the CTA)."""
    if not captions: STMT_WIN.append((a, b))
    STMT_FIRST.append(SAY_T0[-1])
    neck = chin_max(a, b) + NECK_PAD; top = neck + 10; hgt = size * (html.count("<br>") + 1); L = led_y(a, b)
    if L and not (top + hgt <= L - 34): top = max(top, L + 26)
    if RULES["text_below_neck"]: GUARD.append((cid, a, b, top, neck))
    clip(cid, a, b, f'<div class="stmt" style="font-size:{size}px">{html}</div>', "ov chest", 6, f"top:{top}px")
    return top

def typed_words(prefix, parts, first_at_zero=True):
    """A hook typed out letter by letter across each word's spoken duration, led by one accent caret.
    parts: [(text, spoken_word, near_time, css_class)] with ("|", "", 0, "") for a line break."""
    out, chars = [], []
    for txt, word, near, cls in parts:
        if txt == "|": out.append("<br>"); continue
        w = next(x for x in WORDS if x["text"].lower().strip(".,!?") == word.lower() and abs(x["start"] - near) < 0.4)
        t0, t1 = (0.0 if (first_at_zero and not chars) else w["start"]), w["end"]
        step = max(1 / 60, min(0.07, (t1 - t0) / max(1, len(txt))))
        spans = []
        for i, ch in enumerate(txt):
            sid = f"{prefix}{len(chars)}"; chars.append((sid, t0 + i * step))
            spans.append(f'<span class="tc {cls}" id="{sid}">{"&nbsp;" if ch == " " else ch}</span>')
        out.append("".join(spans))
    for n, (sid, t) in enumerate(chars):
        off = chars[n + 1][1] if n + 1 < len(chars) else t + 0.35
        js(f"tl.set('#{sid}',{{opacity:0}},0);tl.set('#{sid}',{{opacity:1,boxShadow:'7px 0 0 {LIME}'}},{q(t)});"
           f"tl.set('#{sid}',{{boxShadow:'0 0 0 rgba(0,0,0,0)'}},{q(off)});")
    return "".join(out)

def driver(fn, a, b, cue=None):
    """Particle scenes are pure functions of reel time: a proxy tween calls PART.<fn>(t, cue) every frame (seek-safe).
    cue: the scene's cue times from the speaker's words, e.g. {"light": wt("ad", 1.2)} (see templates/particles.js)."""
    cj = json.dumps(cue or {})
    js(f"(function(){{const o={{t:{a}}},c={cj};tl.fromTo(o,{{t:{a}}},{{t:{b},duration:{b - a:.3f},ease:'none',immediateRender:false,onUpdate:()=>window.PART&&PART.{fn}(o.t,c)}},{q(a)});}})();")

# the edit may set these
SFX, TEXTS, TERMS, DECISIONS, HERO, CAP_ENDS = [], [], [], [], None, set()

# ───────────── effects library (engine/effects/fx.py), wired into this page and drawn in the brand ─────────────
sys.path.insert(0, os.path.join(ENGINE, "effects"))
import fx as _fx
_fx.set_brand(BRAND)
FX = _fx.Comp(plate="input-video.mp4")
FX.html, FX.js, FX.q = HTML, JS, q
def takeover_used(n=1):
    """Count an fx effect marked TAKEOVER (letter_dive, layer_explode, impact_frame, banknote, press_front, code_body, blow_away)."""
    global TAKEOVERS
    TAKEOVERS += n
    assert TAKEOVERS <= MAX_TAKEOVERS, f"brand rule: at most {MAX_TAKEOVERS} takeovers per reel"

# ═════════════ THE EDIT (project edit.py) ═════════════
exec(compile(open(f"{ROOT}/edit.py").read(), f"{ROOT}/edit.py", "exec"))

for _a, _b, _lay, _ in SEGS:
    if _lay == "split": CAP_LOW.append((_a, _b, 846, "seam"))
for a, b, lay, bg in sorted(SEGS):
    js(f"tl.set('#bg',{{backgroundColor:'{bg}'}},{q(a)});")
    js(f"tl.set('#video-wrap',{{{SPLIT if lay == 'split' else FULLF}}},{q(a)});")

# ───────────── captions: one line, 2–4 words; spoken words full, upcoming dim; never under a statement ─────────────
inside = lambda t: any(a - 0.05 <= t < b for a, b in NO_CAPS)
STOP = {"the", "a", "an", "and", "of", "to", "be", "is", "in", "on", "it", "it's", "this", "that", "what", "what's"}
cw = lambda s: {x.strip(".,?!").lower() for x in s.split()} - STOP
def repeats(c):
    a, b = c[0]["start"], c[-1]["end"]
    return any(a < y and b > x and cw(" ".join(w["text"] for w in c)) & cw(t) for x, y, t in SAME)
chunks, cur = [], []
for w in WORDS:
    if inside(w["start"]): continue
    if cur and (len(" ".join(x["text"] for x in cur + [w])) > 24 or w["start"] - cur[-1]["end"] > 0.3 or len(cur) == 4):
        chunks.append(cur); cur = []
    cur.append(w)
    if w["text"].lower().strip(".,") in CAP_ENDS or w["text"].endswith((".", "?", "!")):
        chunks.append(cur); cur = []
if cur: chunks.append(cur)
merged = []
for c in chunks:   # a lone word under 0.7 s joins the chunk before it (read-time)
    dur = c[-1]["end"] - c[0]["start"]
    if merged and len(c) == 1 and dur < 0.7 and len(" ".join(x["text"] for x in merged[-1] + c)) <= 28 \
            and c[0]["start"] - merged[-1][-1]["end"] < 0.3:
        merged[-1] = merged[-1] + c
    else:
        merged.append(c)
chunks = [c for c in merged if not repeats(c) and not any(
    max(0, min(b, c[-1]["end"]) - max(a, c[0]["start"])) > 0.5 * (c[-1]["end"] - c[0]["start"]) for a, b in STMT_WIN)]
caps = []
for i, c in enumerate(chunks):
    st = c[0]["start"] - 0.03
    for a0, b0 in STMT_WIN:
        if a0 <= st < b0: st = b0
    en = chunks[i + 1][0]["start"] - 0.03 if i + 1 < len(chunks) else VID
    en = min(en, c[-1]["end"] + 0.5, VID)
    for a, b in NO_CAPS + STMT_WIN:
        if st < a < en: en = a
    if en <= st: continue
    spans = []
    for k, w in enumerate(c):
        wid = f"cw{i}_{k}"
        spans.append(f'<span class="w" id="{wid}">{w["text"]}</span>')
        js(f"tl.set('#{wid}',{{opacity:.45}},0);tl.fromTo('#{wid}',{{opacity:.45}},{{opacity:1,duration:0.12,ease:'power1.out',immediateRender:false}},{q(max(st, w['start'] - 0.033))});")
    low = next((t for a, b, t, *_ in CAP_LOW if a - 0.05 <= st < b), None)
    seam = next((x[3] for x in CAP_LOW if len(x) > 3 and x[0] - 0.05 <= st < x[1]), "")
    caps.append(f'<div class="cap {seam}" id="cap{i}"' + (f' style="top:{low}px"' if low else "") + f'><span class="box">{" ".join(spans)}</span></div>')
    js(f"tl.set('#cap{i}',{{visibility:'visible'}},{q(st)});")
    js(f"tl.set('#cap{i}',{{visibility:'hidden'}},{q(en)});")

# effects (fx.*) change the picture where they start and end: declare those as planned swaps for render QA
FX_SWAPS = [t for m in re.finditer(r'class="clip fx[^"]*" id="[^"]*" data-start="([\d.]+)" data-duration="([\d.]+)"', "\n".join(HTML))
            for t in (float(m.group(1)), float(m.group(1)) + float(m.group(2)))]

# ───────────── face guard (fails the build on a violation) ─────────────
bad = []
if RULES["text_below_neck"]:
    print("face guard: text must start below the neck")
    for cid, a, b, top, neck in GUARD:
        ok = top > neck; print(f"  {cid:8s} {a:6.2f}-{b:6.2f}  neck {neck:5d}  text top {top:5d}  {'OK' if ok else 'FAIL'}")
        if not ok: bad.append(cid)
    for a, b, lay, _ in SEGS:
        if lay == "face" and not CAP_TOP > chin_max(a, b) + NECK_PAD: bad.append(f"captions {a}-{b}")
assert not bad, f"face guard failed: {bad}"

# ───────────── page ─────────────
sys.path.insert(0, ENGINE)
from brand import css_for
CSS = css_for(BRAND, open(f"{ENGINE}/templates/reel.css").read() + "\n" + open(f"{ENGINE}/effects/fx.css").read()).replace("__CAP_TOP__", str(CAP_TOP)).replace("__CAP_H__", str(CAP_H))
PRELOAD = "".join(f'<img src="broll/{f}" alt="" style="width:4px;height:4px" />'
                  for f in sorted(os.listdir(f"{PUB}/broll")) if f.lower().endswith((".png", ".jpg", ".jpeg"))) if os.path.isdir(f"{PUB}/broll") else ""
CID = re.sub(r"[^a-z0-9-]", "-", REEL["name"].lower())
open(f"{PUB}/index.html", "w").write(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" /><title>{REEL['name']}</title><style>
{CSS}
</style></head><body>
<div id="stage" data-composition-id="{CID}" data-start="0" data-duration="{DUR}" data-fps="{FPS}" data-width="{W}" data-height="{H}">
  <div id="bg"></div>
  <div id="video-wrap"><video id="bg-video" src="input-video.mp4" playsinline muted data-start="0" data-duration="{VID}" data-track-index="1"></video></div>
  <div id="preload" class="clip" data-start="0" data-duration="{DUR}" data-track-index="9" style="left:0;top:0;width:4px;height:4px;overflow:hidden;opacity:0.01;z-index:0">{PRELOAD}</div>
  <audio id="mix" src="mix.m4a" data-start="0" data-duration="{DUR}" data-track-index="10" data-volume="1"></audio>
{chr(10).join(HTML)}
  <div id="captions" class="clip" data-start="0" data-duration="{VID}" data-track-index="7">
{chr(10).join(caps)}
  </div>
  <script>window.BRAND = {json.dumps({**C, "labelFont": BRAND["fonts"]["label"]["family"]})};</script>
  <script src="vendor/gsap.min.js"></script>
  <script src="particles.js"></script>
  <script>(function () {{
    const tl = window.gsap.timeline({{ paused: true, defaults: {{ lazy: false }} }});
{chr(10).join('    ' + l for l in JS)}
    tl.set({{}}, {{}}, {DUR});
    window.__timelines = window.__timelines || {{}}; window.__timelines["{CID}"] = tl;
  }})();</script>
</div></body></html>
""")
print(f"{len(HTML)} visual elements, {TAKEOVERS} takeovers, {len(caps)} captions, {len(JS)} timeline lines")

# ───────────── timeline.json (the one source of truth: the mix and QA read it) ─────────────
scenes = []
WHY = {"split": "the speaker names a source: show the real source", "face": "back to the speaker",
       "full": "a takeover carries the idea", "end": "sign-off", "card": "cover"}
for i, (a, b, lay, _) in enumerate(sorted(SEGS)):
    sc = {"id": f"s{i:02d}_{lay}", "start": round(a, 3), "end": round(b, 3), "beats": {}}
    nxt = sorted(SEGS)[i + 1][2] if i + 1 < len(SEGS) else None
    if nxt: sc["transitionOut"] = {"type": "hard cut", "dur": 0, "why": WHY.get(nxt, "next beat")}
    for name, t, *_ in SFX:
        if a <= t < b: sc["beats"][name] = t
    scenes.append(sc)
beat_scene = {name: sc["id"] for sc in scenes for name in sc["beats"]}
PC = f"{ROOT}/build/plate_cuts.json"   # the speaker's own jump cuts (detected once from the plate): planned, not defects
if not os.path.exists(PC):
    # a jump cut is a single-frame jump in the plate: mean frame difference > max(6, 5x the median) on a 90x160 grey proxy
    # (scdet at 2.4 missed two of the speaker's cuts in testing; this measure separates them from motion cleanly)
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f"{PUB}/input-video.mp4", "-vf", "scale=90:160,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, 160, 90).astype(np.float32)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2)); thr = max(6.0, 5 * float(np.median(d)))
    json.dump([round((i + 1) / FPS, 3) for i in np.nonzero(d > thr)[0]], open(PC, "w"))
PLATE_CUTS = [t for t in json.load(open(PC)) if any(a0 + 0.05 < t < b0 - 0.05 and lay == "face" for a0, b0, lay, _ in SEGS)]
fonts = sorted({f["family"].lower() for f in BRAND["fonts"].values()})
TL = {
    "meta": {"w": W, "h": H, "fps": FPS, "dur": DUR, "clock": "voice", "register": "clean", "loop": False, "grid": "none",
             "hookWaiver": "talking-head reel: the CTA is a spoken comment keyword at the end, not a by-3 s ad CTA",
             "vo": {"status": "RENDERED", "file": "public/mix.m4a", "rateWps": None}},
    "vo": [{"id": "L1", "text": " ".join(w["text"] for w in WORDS), "from": WORDS[0]["start"], "to": WORDS[-1]["end"],
            "words": [{"w": w["text"], "t": w["start"]} for w in WORDS]}],
    "scenes": scenes,
    "cuts": sorted({round(round(a * FPS) / FPS, 3) for a, b, _, _ in SEGS if a > 0}),
    "swaps": sorted({round(round(t * FPS) / FPS, 3) for t in STMT_FIRST + FX_SWAPS}),
    "plate_cuts": PLATE_CUTS,
    "hero": HERO or {"t": 0, "what": "unset"},
    "sfx": [{"at": f"{beat_scene[n]}.{n}", "offset": 0.0, "src": f, "role": r, "trim": [s0, s1], "why": why}
            for n, t, r, f, s0, s1, why in SFX],
    "captions": [{"from": round(c[0]["start"] - 0.03, 3), "to": round(c[-1]["end"], 3), "text": " ".join(x["text"] for x in c), "src": "vo:L1"} for c in chunks],
    "texts": TEXTS, "terms": TERMS,
    "decisions": ["DECISION: captions follow the speaking rate (karaoke) because they transcribe the voice", *DECISIONS],
    "house": {"takeovers": TAKEOVERS, "max_takeovers": MAX_TAKEOVERS, "guard": [list(g) for g in GUARD],
              "no_caption_windows": NO_CAPS, "fx_windows": [[round(a, 3), round(b, 3)] for a, b in zip(FX_SWAPS[::2], FX_SWAPS[1::2])], "caption_band": [CAP_TOP, CAP_H], "fonts": fonts,
              "colours": sorted({v.lower() for v in C.values()}), "allow_words": BRAND.get("allow_words", []) + [BRAND["name"], BRAND.get("handle", "")]},
}
json.dump(TL, open(f"{ROOT}/timeline.json", "w"), indent=1)
print("wrote timeline.json:", len(scenes), "scenes,", len(SFX), "sfx,", len(TL["captions"]), "captions")
