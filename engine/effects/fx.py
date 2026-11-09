"""Reel Studio effects library: 21 effects for HyperFrames reels, drawn in the user's brand.

Rules every effect keeps:
  - text never on, beside or above the face: anything with words sits below the neck (`neck`, default 1240);
  - nothing on screen the speaker didn't say: every text argument is supplied by the edit, nothing is hard-coded copy;
  - full-screen effects marked TAKEOVER count toward the brand's takeover limit (call takeover_used() in edit.py);
  - the brand accent goes on ONE thing per effect.

Use inside edit.py (build.py provides FX, a Comp wired into the reel's page and timeline, already in the brand):
    from fx import predict_keys, comment_drop, blade_slice
    predict_keys(FX, 12.4, 14.0, text="ship it")

Every function takes (c, a, b, ...) with a/b = start/end in seconds on the reel timeline. Effects that need a
person cut-out take `cut=` (an alpha .webm from engine/tools/stylize.py cutout covering the SAME a..b window);
pre-rendered looks take their .mp4 from engine/tools/stylize.py.
"""
import json, os, math

W, H, FPS = 1080, 1920, 30
# brand tokens (set_brand() overwrites these from brand.json colors: ground, text, muted, paper, accent, accent_ink)
LIME, INK, CREAM, GREEN = "#E5FF1F", "#0E1110", "#ECE7DC", "#0E1110"   # accent, ground, paper, engraving ink
BONE, FOG, LIME_INK = "#EFEADF", "#8A8F86", "#C8E000"                  # text, muted, accent ink
DISPLAY = "Geist"

def set_brand(brand):
    """Point every effect at the user's brand (build.py calls this before edit.py runs)."""
    global LIME, INK, CREAM, GREEN, BONE, FOG, LIME_INK, DISPLAY
    c = brand["colors"]
    LIME, INK, CREAM, GREEN = c["accent"], c["ground"], c["paper"], c["ground"]
    BONE, FOG, LIME_INK = c["text"], c["muted"], c.get("accent_ink", c["accent"])
    DISPLAY = brand["fonts"]["display"]["family"]


class Comp:
    def __init__(self, plate="input-video.mp4", plate_dur=None, audio=True, fonts_dir="fonts"):
        self.plate, self.plate_dur, self.audio, self.fonts = plate, plate_dur, audio, fonts_dir
        self.html, self.js, self._n = [], [], 0

    # ── helpers ──
    q = staticmethod(lambda t: round(round(t * FPS) / FPS, 4))
    def uid(self, p): self._n += 1; return f"{p}{self._n}"
    def add(self, s): self.html.append(s)
    def j(self, s): self.js.append(s)
    def clip(self, cid, a, b, inner, cls="", z=5, style="", track=3):
        self.add(f'<div class="clip fx {cls}" id="{cid}" data-start="{self.q(a)}" data-duration="{self.q(b - a)}" '
                 f'data-track-index="{track}" style="z-index:{z};{style}">{inner}</div>')
    def vtag(self, vid, src, a, b, media_start=None, cls="", style="", z=None, track=2):
        ms = f' data-media-start="{self.q(media_start)}"' if media_start is not None else ""
        zs = f"z-index:{z};" if z is not None else ""
        return (f'<video id="{vid}" class="clip {cls}" src="{src}" muted playsinline data-start="{self.q(a)}" '
                f'data-duration="{self.q(b - a)}"{ms} data-track-index="{track}" style="{zs}{style}"></video>')
    def video(self, vid, src, a, b, media_start=None, cls="", style="", z=None):
        self._v = getattr(self, "_v", 10) + 1          # each overlapping video gets its own track
        self.add(self.vtag(vid, src, a, b, media_start, cls, style, z, track=self._v))
    def plate_copy(self, vid, a, b, cls="", style="", z=None):
        """A second, frame-synced copy of the main plate (for slices, layers, masks)."""
        self.video(vid, self.plate, a, b, media_start=a, cls=cls, style=style, z=z)
    def fromto(self, sel, frm, to, t, d=0.3, ease="power3.out", extra=""):
        self.j(f"tl.fromTo('{sel}',{frm},{{...{to},duration:{d},ease:'{ease}',immediateRender:false{extra}}},{self.q(t)});")
    def hide_until(self, sel, prop="opacity:0"): self.j(f"tl.set('{sel}',{{{prop}}},0);")
    def pop(self, sel, t, d=0.25, s0=0.85):
        self.hide_until(sel); self.fromto(sel, f"{{opacity:0,scale:{s0}}}", "{opacity:1,scale:1}", t, d)
    def rise(self, sel, t, d=0.3, dy=40):
        self.hide_until(sel); self.fromto(sel, f"{{opacity:0,y:{dy}}}", "{opacity:1,y:0}", t, d)
    def out(self, sel, t, d=0.2, extra="{}"):
        self.j(f"tl.to('{sel}',{{opacity:0,duration:{d},ease:'power2.in',...{extra}}},{self.q(t)});")

    def write(self, path, duration, title="fx demo"):
        css = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fx.css")).read()
        aud = ' data-has-audio="true"' if self.audio else " muted"
        pd = self.plate_dur or duration
        html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"/><title>{title}</title><style>{css}</style></head><body>
<div id="stage" data-composition-id="fx" data-start="0" data-duration="{duration}" data-fps="{FPS}" data-width="{W}" data-height="{H}">
  <div id="video-wrap"><video id="bg-video" src="{self.plate}" playsinline{aud} data-start="0" data-duration="{pd}" data-track-index="1"></video></div>
{chr(10).join(self.html)}
  <script src="vendor/gsap.min.js"></script>
  <script>(function(){{
    const tl = window.gsap.timeline({{ paused: true, defaults: {{ lazy: false }} }});
{chr(10).join('    ' + l for l in self.js)}
    tl.set({{}}, {{}}, {duration});
    window.__timelines = window.__timelines || {{}}; window.__timelines["fx"] = tl;
  }})();</script>
</div></body></html>"""
        open(path, "w").write(html)


# ═══════════════════════════ 01 · LIVE CURSOR (overlay) ═══════════════════════════
def live_cursor(c, a, b, box=(150, 250, 780, 1240), label="Claude", size_tag=True):
    """A multiplayer cursor drags a Figma-style selection around the speaker; handles, a size tag below the box,
    the cursor's name tag appears at the bottom-right corner (below the neck)."""
    i = c.uid("cur"); x, y, w, h = box
    hs = "".join(f'<i class="h" style="left:{px - 9}px;top:{py - 9}px"></i>' for px, py in
                 [(0, 0), (w / 2, 0), (w, 0), (0, h / 2), (w, h / 2), (0, h), (w / 2, h), (w, h)])
    tag = f'<div class="sz" id="{i}-sz">{int(w)} × {int(h)}</div>' if size_tag else ""
    c.clip(i, a, b, f"""<div class="sel" id="{i}-box" style="left:{x}px;top:{y}px;width:0;height:0">{hs}</div>{tag.replace('class="sz"', f'class="sz" style="left:{x + w / 2}px;top:{y + h + 18}px"')}
      <div class="cursor" id="{i}-c"><svg width="44" height="54" viewBox="0 0 44 54"><path d="M3 3 L3 44 L14 33 L22 51 L30 47 L22 30 L38 30 Z" fill="{LIME}" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/></svg>
      <span class="ctag" id="{i}-t">{label}</span></div>""", cls="ov")
    d = b - a
    c.j(f"tl.set('#{i}-c',{{x:{x + w + 260},y:{y + h + 300}}},{c.q(a)});")
    c.fromto(f"#{i}-c", f"{{x:{x + w + 260},y:{y + h + 300}}}", f"{{x:{x},y:{y}}}", a + 0.05, 0.35, "power2.inOut")
    c.hide_until(f"#{i}-box .h"); c.hide_until(f"#{i}-t")
    c.fromto(f"#{i}-box", "{width:0,height:0}", f"{{width:{w},height:{h}}}", a + 0.45, 0.5, "power2.inOut")
    c.fromto(f"#{i}-c", f"{{x:{x},y:{y}}}", f"{{x:{x + w},y:{y + h}}}", a + 0.45, 0.5, "power2.inOut")
    c.j(f"tl.fromTo('#{i}-box .h',{{opacity:0,scale:.4}},{{opacity:1,scale:1,duration:.18,stagger:.02,immediateRender:false}},{c.q(a + 0.95)});")
    c.pop(f"#{i}-t", a + 0.95, 0.2)
    if size_tag: c.pop(f"#{i}-sz", a + 1.0, 0.2)
    c.out(f"#{i}", b - 0.2, 0.2)


# ═══════════════════════════ 02 · CLONE ROW (overlay, cut-out) ═══════════════════════════
def clone_row(c, a, b, cut, n=2):
    """Copies of the speaker slide out from behind them to both sides, receding in size, then slide back."""
    i = c.uid("clo"); els = []
    for k in range(1, n + 1):
        for side in (-1, 1):
            vid = f"{i}-{k}{'l' if side < 0 else 'r'}"
            els.append((vid, k, side))
            c.video(vid, cut, a, b, cls="cutv clone", style=f"filter:brightness({1 - 0.12 * k})", z=6 - k)
    c.video(f"{i}-main", cut, a, b, cls="cutv", z=7)
    for vid, k, side in els:
        s = 1 - 0.13 * k; dx = side * 250 * k
        c.fromto(f"#{vid}", "{x:0,scale:1}", f"{{x:{dx},scale:{s}}}", a + 0.08 * k, 0.45, "power3.out")
        c.fromto(f"#{vid}", f"{{x:{dx},scale:{s}}}", "{x:0,scale:1}", b - 0.45, 0.4, "power3.in")


# ═══════════════════════════ 03 · DAY DIAL (overlay, cut-out) ═══════════════════════════
def day_dial(c, a, b, cut):
    """A cream world sweeps in like a clock hand; a slow engraved dial turns behind the speaker; sweeps out."""
    i = c.uid("dial")
    ticks = "".join(f'<line x1="540" y1="{90 if t % 5 else 60}" x2="540" y2="120" transform="rotate({t * 6} 540 540)"/>' for t in range(60))
    rings = "".join(f'<circle cx="540" cy="540" r="{r}" />' for r in (470, 420, 300, 180))
    c.clip(i, a, b, f"""<div class="dialbg" id="{i}-bg"><svg class="dial" id="{i}-d" width="1080" height="1080" viewBox="0 0 1080 1080"><g fill="none" stroke="{INK}" stroke-opacity=".55" stroke-width="2">{rings}{ticks}</g>
      <path d="M540 540 L540 90" stroke="{LIME}" stroke-width="8" stroke-linecap="round"/></svg></div>""", cls="ov", z=5)
    c.video(f"{i}-cut", cut, a, b, cls="cutv", z=7)
    c.j(f"tl.fromTo('#{i}',{{'--a':'0deg'}},{{'--a':'360deg',duration:.45,ease:'power2.inOut',immediateRender:false}},{c.q(a)});")
    c.j(f"tl.fromTo('#{i}-d',{{rotation:0}},{{rotation:40,duration:{b - a:.2f},ease:'none',immediateRender:false}},{c.q(a)});")
    c.j(f"tl.fromTo('#{i}',{{'--a':'360deg'}},{{'--a':'0deg',duration:.4,ease:'power2.inOut',immediateRender:false}},{c.q(b - 0.4)});")


# ═══════════════════════════ 04 · PREDICT KEYS (overlay) ═══════════════════════════
def predict_keys(c, a, b, text, top=1300):
    """A phone keyboard slides up under the neck and types `text` into its field, keys lighting up."""
    i = c.uid("kb")
    rows = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
    keys = "".join(f'<div class="krow">{"".join(f"<b id={i}-k{ch}>{ch}</b>" for ch in r)}</div>' for r in rows)
    field = "".join(f'<span id="{i}-c{n}">{ch if ch != " " else "&nbsp;"}</span>' for n, ch in enumerate(text))
    c.clip(i, a, b, f"""<div class="kb" id="{i}-kb" style="top:{top}px"><div class="kfield"><i>⌕</i>{field}<u id="{i}-caret"></u></div>{keys}
      <div class="krow"><b class="wide">space</b><b class="go">go</b></div></div>""", cls="ov", z=8)
    c.fromto(f"#{i}-kb", "{y:700}", "{y:0}", a, 0.35, "power3.out")
    step = min(0.09, (b - a - 0.9) / max(1, len(text)))
    for n, ch in enumerate(text):
        t = a + 0.4 + n * step
        c.hide_until(f"#{i}-c{n}"); c.j(f"tl.set('#{i}-c{n}',{{opacity:1}},{c.q(t)});")
        if ch.upper() in "".join(rows):
            c.j(f"tl.fromTo('#{i}-k{ch.upper()}',{{backgroundColor:'{LIME}'}},{{backgroundColor:'rgba(255,255,255,.08)',duration:.16,immediateRender:false}},{c.q(t)});")
    c.fromto(f"#{i}-kb", "{y:0}", "{y:700}", b - 0.35, 0.3, "power3.in")


# ═══════════════════════════ 05 · ORBIT RING (overlay, cut-out) ═══════════════════════════
def orbit_ring(c, a, b, cut, text="ORBIT RING · ", cy=1330, r=360, turns=0.6):
    """Letters orbit the speaker's chest in 3D: the near half passes in front, the far half behind the body."""
    i = c.uid("orb"); letters = list(text * 2)
    n = len(letters)
    def ring(layer):
        return "".join(f'<span class="ol" data-a="{360 * k / n:.2f}" style="transform:rotateY({360 * k / n:.2f}deg) translateZ({r}px)">{ch}</span>' for k, ch in enumerate(letters))
    for layer, z in (("back", 5), ("front", 8)):
        c.clip(f"{i}-{layer}", a, b, f'<div class="orbit" style="top:{cy}px"><div class="oring" id="{i}-{layer}-r">{ring(layer)}</div></div>', cls="ov", z=z)
    c.video(f"{i}-cut", cut, a, b, cls="cutv", z=7)
    c.j(f"""(function(){{const st={{v:0}};const fr=[...document.querySelectorAll('#{i}-front .ol')],bk=[...document.querySelectorAll('#{i}-back .ol')];
      tl.fromTo(st,{{v:0}},{{v:{360 * turns},duration:{b - a:.2f},ease:'none',immediateRender:false,onUpdate:()=>{{
        document.getElementById('{i}-front-r').style.transform=document.getElementById('{i}-back-r').style.transform='rotateX(-14deg) rotateY('+(-st.v)+'deg)';
        fr.forEach((e,k)=>{{const ang=(parseFloat(e.dataset.a)-st.v)*Math.PI/180;const front=Math.cos(ang)>0;e.style.opacity=front?1:0;bk[k].style.opacity=front?0:.55;}});
      }}}},{c.q(a)});}})();""")
    for layer in ("front", "back"):
        c.pop(f"#{i}-{layer}", a, 0.3, 0.6); c.out(f"#{i}-{layer}", b - 0.25, 0.25)


# ═══════════════════════════ 06 · CODE BODY (TAKEOVER, pre-render) ═══════════════════════════
def code_body(c, a, b, src):
    """The speaker redrawn in code characters (tools/stylize.py code). Scanline wipe in, wipe out."""
    i = c.uid("code")
    c.video(f"{i}", src, a, b, cls="full scan", z=9)
    c.fromto(f"#{i}", "{clipPath:'inset(0% 0% 100% 0%)'}", "{clipPath:'inset(0% 0% 0% 0%)'}", a, 0.25, "power2.out")
    c.fromto(f"#{i}", "{clipPath:'inset(0% 0% 0% 0%)'}", "{clipPath:'inset(100% 0% 0% 0%)'}", b - 0.2, 0.2, "power2.in")


# ═══════════════════════════ 07 · POST WALL (overlay) ═══════════════════════════
def post_wall(c, a, b, count_to, label="posts", top=1270, cols=16, rows=4):
    """A contribution-style wall of tiles fills in under the neck while a counter climbs to `count_to`."""
    i = c.uid("wall"); tiles = []
    import random; rnd = random.Random(3)
    for k in range(cols * rows):
        lvl = rnd.choice([1, 2, 2, 3, 3, 4])
        tiles.append(f'<i class="t{lvl}" style="--d:{k}"></i>')
    c.clip(i, a, b, f"""<div class="wall" style="top:{top}px"><div class="tiles" style="grid-template-columns:repeat({cols},1fr)">{''.join(tiles)}</div>
      <div class="wcount"><b id="{i}-n">0</b> {label}</div></div>""", cls="ov", z=8)
    c.rise(f"#{i} .wall", a, 0.3, 30)
    c.j(f"tl.fromTo('#{i} .tiles i',{{opacity:0,scale:.3}},{{opacity:1,scale:1,duration:.18,stagger:{{each:{(b - a - 0.8) / (cols * rows):.4f},from:'start'}},immediateRender:false}},{c.q(a + 0.2)});")
    c.j(f"(function(){{const o={{v:0}};tl.fromTo(o,{{v:0}},{{v:{count_to},duration:{b - a - 0.6:.2f},ease:'power2.out',immediateRender:false,onUpdate:()=>{{document.getElementById('{i}-n').textContent=Math.round(o.v).toLocaleString('en-US');}}}},{c.q(a + 0.2)});}})();")
    c.out(f"#{i}", b - 0.2, 0.2)


# ═══════════════════════════ 08 · LETTER DIVE (TAKEOVER → transition) ═══════════════════════════
def letter_dive(c, a, b, word="ads.", origin=(812, 1050), size=330, baseline=1080):
    """A cream card where serif letters are windows onto the video; the camera dives through `origin`
    (pick a point inside a letter or the full stop) back into the shot. Text sits below the neck (baseline ~1080+)."""
    i = c.uid("dive"); ox, oy = origin
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='1080' height='1920' viewBox='0 0 1080 1920'><text x='540' y='{baseline}' "
           f"text-anchor='middle' font-family='{DISPLAY},Arial,sans-serif' font-weight='700' font-size='{size}' fill='white'>{word}</text></svg>")
    from urllib.parse import quote
    mask = "url('data:image/svg+xml;utf8," + quote(svg, safe="") + "')"
    c.clip(i, a, b, f'<div class="divezoom" id="{i}-z" style="transform-origin:{ox}px {oy}px"><div class="cream full"></div></div>', z=9)
    c.plate_copy(f"{i}-v", a, b, cls="full masked", style=f"-webkit-mask-image:{mask};mask-image:{mask};-webkit-mask-size:100% 100%;mask-size:100% 100%;transform-origin:{ox}px {oy}px", z=10)
    for sel in (f"#{i}-z", f"#{i}-v"):
        c.fromto(sel, "{scale:1}", "{scale:1.08}", a, b - a - 0.55, "none")
        c.fromto(sel, "{scale:1.08}", "{scale:70}", b - 0.55, 0.55, "power3.in")


# ═══════════════════════════ 09 · COMMENT DROP (overlay) ═══════════════════════════
def comment_drop(c, a, b, comments, top=1250, gap=108):
    """Comment cards drop in at the top of a stack under the neck; each new one pushes the older ones down."""
    i = c.uid("cmt"); cards = ""
    for k, (name, text) in enumerate(comments):
        cards += f'<div class="cmt" id="{i}-{k}"><i></i><div><b>{name}</b><span>{text}</span></div><em>♡</em></div>'
    c.clip(i, a, b, f'<div class="cstack" style="top:{top}px">{cards}</div>', cls="ov", z=8)
    step = (b - a - 0.6) / max(1, len(comments))
    for j in range(len(comments)):
        t = a + 0.1 + j * step
        c.hide_until(f"#{i}-{j}")
        c.fromto(f"#{i}-{j}", "{opacity:0,y:-40,scale:.9}", "{opacity:1,y:0,scale:1}", t, 0.32, "power3.out")
        for k in range(j):
            c.fromto(f"#{i}-{k}", f"{{y:{(j - 1 - k) * gap}}}", f"{{y:{(j - k) * gap}}}", t, 0.32, "power3.out")
    c.out(f"#{i}", b - 0.2, 0.2)


# ═══════════════════════════ 10 · LAYER EXPLODE (TAKEOVER) ═══════════════════════════
def layer_explode(c, a, b, label="layer explode"):
    """The frame tilts into 3D and splits into stacked glass layers (video, lime frame, waveform, label), then snaps back."""
    i = c.uid("lay")
    bars = "".join(f'<i style="height:{20 + 70 * abs(math.sin(k * 0.7)) * abs(math.cos(k * 0.23))}px"></i>' for k in range(48))
    c.clip(f"{i}-bg", a, b, "", cls="ink full", z=8)
    c.plate_copy(f"{i}-v", a, b, cls="lvideo", z=9, style="transform-origin:540px 960px")
    c.clip(i, a, b, f"""<div class="lscene"><div class="lstack" id="{i}-s">
        <div class="layer l1 glass" id="{i}-l1"><div class="lframe"></div></div>
        <div class="layer l2 glass" id="{i}-l2"><div class="wave">{bars}</div></div>
        <div class="layer l3 glass" id="{i}-l3"><div class="lname">{label}</div></div></div></div>""", cls="full", z=10)
    flat, tilt = "rotationY:0,rotationX:0,scale:1", "rotationY:-38,rotationX:12,scale:.72"
    for sel, extra in ((f"#{i}-s", ""), (f"#{i}-v", ",transformPerspective:1800")):
        c.fromto(sel, f"{{{flat}{extra}}}", f"{{{tilt}{extra}}}", a, 0.45, "power3.inOut")
        c.fromto(sel, f"{{{tilt}{extra}}}", f"{{{flat}{extra}}}", b - 0.4, 0.4, "power3.inOut")
    for k in range(1, 4):
        c.fromto(f"#{i}-l{k}", "{z:0}", f"{{z:{k * 100}}}", a + 0.35, 0.45, "power3.out")
        c.fromto(f"#{i}-l{k}", f"{{z:{k * 100}}}", "{z:0}", b - 0.55, 0.35, "power3.in")


# ═══════════════════════════ 11 · SKETCH WORDS (overlay, cut-out) ═══════════════════════════
def sketch_words(c, a, b, cut, word, note="sketch", top=1235):
    """The room turns to cream paper; a word draws itself in pencil with red hatching across the chest, under the neck."""
    i = c.uid("skw")
    c.clip(i, a, b, f"""<svg class="skw" style="top:{top}px" width="1080" height="320" viewBox="0 0 1080 320">
        <defs><pattern id="{i}-h" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(35)"><line x1="0" y1="0" x2="0" y2="9" stroke="{BONE}" stroke-width="2.6"/></pattern></defs>
        <text id="{i}-fill" x="540" y="245" text-anchor="middle" font-family="{DISPLAY}, sans-serif" font-weight="700" letter-spacing="-10" font-size="250" fill="url(#{i}-h)">{word}</text>
        <text id="{i}-ln" x="540" y="245" text-anchor="middle" font-family="{DISPLAY}, sans-serif" font-weight="700" letter-spacing="-10" font-size="250" fill="none" stroke="{BONE}" stroke-width="3">{word}</text>
        <path id="{i}-u" d="M150 285 C 380 270, 700 300, 930 278" stroke="{LIME_INK}" stroke-width="9" fill="none" stroke-linecap="round"/></svg>
      <div class="note" style="top:{top - 10}px">{note}</div>""", cls="ov", z=8)
    c.clip(f"{i}-p", a, b, '<div class="paper full"></div>', z=5)
    c.video(f"{i}-cut", cut, a, b, cls="cutv", z=7)
    c.j(f"(function(){{const L=3000;tl.fromTo('#{i}-ln',{{strokeDasharray:L,strokeDashoffset:L}},{{strokeDashoffset:0,duration:.7,ease:'power1.inOut',immediateRender:false}},{c.q(a + 0.15)});"
        f"const u=document.getElementById('{i}-u');const U=u.getTotalLength();tl.fromTo(u,{{strokeDasharray:U,strokeDashoffset:U}},{{strokeDashoffset:0,duration:.35,ease:'power2.out',immediateRender:false}},{c.q(a + 0.9)});}})();")
    c.hide_until(f"#{i}-fill"); c.fromto(f"#{i}-fill", "{opacity:0}", "{opacity:1}", a + 0.6, 0.4, "power1.out")
    c.rise(f"#{i} .note", a + 0.2, 0.3, 10)


# ═══════════════════════════ 12 · BLADE SLICE (transition) ═══════════════════════════
def blade_slice(c, a, b, angle_drop=380):
    """A blade swipes diagonally; the two halves slide apart along the cut and settle back."""
    i = c.uid("cut")
    top = "polygon(0 0,100% 0,100% 30%,0 50%)"; bot = "polygon(0 50%,100% 30%,100% 100%,0 100%)"
    c.plate_copy(f"{i}-a", a, b, cls="full", style=f"clip-path:{top}", z=9)
    c.plate_copy(f"{i}-b", a, b, cls="full", style=f"clip-path:{bot}", z=9)
    c.clip(i, a, b, '<div class="blade"></div>', cls="ov", z=10)
    m = (b - a) / 2
    c.fromto(f"#{i} .blade", "{scaleX:0,opacity:1}", "{scaleX:1,opacity:1}", a, 0.15, "power2.out")
    c.out(f"#{i} .blade", a + 0.2, 0.15)
    c.fromto(f"#{i}-a", "{x:0,y:0}", "{x:-40,y:-24}", a + 0.1, 0.25, "power3.out")
    c.fromto(f"#{i}-b", "{x:0,y:0}", "{x:40,y:24}", a + 0.1, 0.25, "power3.out")
    c.fromto(f"#{i}-a", "{x:-40,y:-24}", "{x:0,y:0}", b - 0.25, 0.22, "power3.in")
    c.fromto(f"#{i}-b", "{x:40,y:24}", "{x:0,y:0}", b - 0.25, 0.22, "power3.in")


# ═══════════════════════════ 13 · CHEST STACK (overlay; the reference's 'Head stack', moved below the neck) ═══════════════════════════
def chest_stack(c, a, b, labels, top=1260):
    """Paper tags fly in from the top with motion blur and pile up on the chest, then fly off."""
    i = c.uid("tag"); tags = ""
    for k, t in enumerate(labels):
        rot = 0; x = [180, 400, 260, 470, 220, 430][k % 6]; y = top + 84 * (k % 4)   # style A: no tilted cards
        tags += f'<div class="ptag" id="{i}-{k}" style="left:{x}px;top:{y}px;--r:{rot}deg">{t}</div>'
    c.clip(i, a, b, tags, cls="ov", z=8)
    for k in range(len(labels)):
        t = a + 0.08 * k
        c.hide_until(f"#{i}-{k}")
        c.fromto(f"#{i}-{k}", "{opacity:1,y:-1300,rotation:-25,filter:'blur(14px)'}", "{opacity:1,y:0,rotation:0,filter:'blur(0px)'}", t, 0.32, "power3.out")
        c.fromto(f"#{i}-{k}", "{x:0,opacity:1,filter:'blur(0px)'}", f"{{x:{900 if k % 2 else -900},opacity:1,filter:'blur(14px)'}}", b - 0.35 + 0.03 * k, 0.28, "power3.in")


# ═══════════════════════════ 14 · RACK FOCUS (overlay, cut-out) ═══════════════════════════
def rack_focus(c, a, b, cut):
    """Focus pulls from the speaker to the room and back: background blurs, then the speaker softens."""
    i = c.uid("rack")
    c.plate_copy(f"{i}-bg", a, b, cls="full", z=5, style="filter:blur(0px)")
    c.video(f"{i}-cut", cut, a, b, cls="cutv", z=6)
    m = (b - a) / 2
    c.fromto(f"#{i}-bg", "{filter:'blur(0px)'}", "{filter:'blur(16px)'}", a, 0.35, "power2.inOut")
    c.fromto(f"#{i}-bg", "{filter:'blur(16px)'}", "{filter:'blur(0px)'}", a + m, 0.35, "power2.inOut")
    c.fromto(f"#{i}-cut", "{filter:'blur(0px)'}", "{filter:'blur(9px)'}", a + m, 0.35, "power2.inOut")
    c.fromto(f"#{i}-cut", "{filter:'blur(9px)'}", "{filter:'blur(0px)'}", b - 0.35, 0.3, "power2.inOut")


# ═══════════════════════════ 15 · BANKNOTE (TAKEOVER, pre-render) ═══════════════════════════
def banknote(c, a, b, src, number, caption):
    """A cream banknote: an engraved portrait (tools/stylize.py engrave) in an oval, a number typed digit by digit."""
    i = c.uid("note")
    digits = "".join(f'<span id="{i}-d{k}">{ch}</span>' for k, ch in enumerate(number))
    c.clip(i, a, b, f"""<div class="bank full"><div class="bframe"><div class="bguill"></div>
      <div class="boval"></div><div class="bnum">{digits}</div><div class="bcap">{caption}</div>
      <div class="bseal">✦</div><div class="bc bl">{number}</div><div class="bc br">{number}</div></div></div>""", z=9)
    c.video(f"{i}-v", src, a, b, cls="bportrait", z=10)
    c.fromto(f"#{i}", "{scale:1.06}", "{scale:1}", a, b - a, "power1.out")
    c.fromto(f"#{i}-v", "{scale:1.06}", "{scale:1}", a, b - a, "power1.out")
    step = min(0.12, (b - a - 0.8) / len(number))
    for k in range(len(number)):
        c.hide_until(f"#{i}-d{k}"); c.j(f"tl.set('#{i}-d{k}',{{opacity:1}},{c.q(a + 0.3 + k * step)});")


# ═══════════════════════════ 16 · VOICE NOTE (overlay) ═══════════════════════════
def voice_note(c, a, b, length="0:07", top=1270):
    """A voice-message bubble pops in under the neck and plays: the waveform fills as it goes."""
    i = c.uid("vn")
    bars = "".join(f'<i style="height:{12 + 40 * abs(math.sin(k * 1.3)) * abs(math.cos(k * 0.37))}px"></i>' for k in range(34))
    c.clip(i, a, b, f"""<div class="vnote" style="top:{top}px"><b class="play">▶</b><div class="vw"><div class="vbars">{bars}</div>
      <div class="vbars on" id="{i}-on">{bars}</div></div><em>{length}</em></div>""", cls="ov", z=8)
    c.pop(f"#{i} .vnote", a, 0.28, 0.7)
    c.fromto(f"#{i}-on", "{clipPath:'inset(0 100% 0 0)'}", "{clipPath:'inset(0 0% 0 0)'}", a + 0.3, b - a - 0.7, "none")
    c.fromto(f"#{i} .vnote", "{scale:1,opacity:1}", "{scale:.4,opacity:0}", b - 0.3, 0.3, "power3.in")


# ═══════════════════════════ 17 · IMPACT FRAME (TAKEOVER) ═══════════════════════════
def impact_frame(c, a, b, word):
    """Comic panel: the shot crushed to black-and-white ink, radiating speed lines, a heavy word, two invert flashes."""
    i = c.uid("imp")
    lines = "".join(f'<path d="M540 760 L{540 + 2000 * math.cos(math.radians(k * 4.5 + (k % 3)))} {760 + 2000 * math.sin(math.radians(k * 4.5 + (k % 3)))} L{540 + 2000 * math.cos(math.radians(k * 4.5 + 1.4))} {760 + 2000 * math.sin(math.radians(k * 4.5 + 1.4))} Z"/>' for k in range(80))
    c.plate_copy(f"{i}-v", a, b, cls="full comic", z=9)
    c.clip(i, a, b, f"""<svg class="speed full" viewBox="0 0 1080 1920"><defs><radialGradient id="{i}-g"><stop offset=".32" stop-color="#fff" stop-opacity="0"/><stop offset=".6" stop-color="#fff"/></radialGradient>
      <mask id="{i}-m"><rect width="1080" height="1920" fill="url(#{i}-g)"/></mask></defs><g fill="{INK}" mask="url(#{i}-m)">{lines}</g></svg>
      <div class="impact" id="{i}-w">{word}</div>""", cls="ov", z=10)
    c.pop(f"#{i}-w", a + 0.12, 0.2, 1.3)
    for t in (a, a + 0.5):
        c.j(f"tl.set('#{i}-v',{{filter:'grayscale(1) brightness(2.1) contrast(5) invert(1)'}},{c.q(t)});tl.set('#{i}',{{filter:'invert(1)'}},{c.q(t)});"
            f"tl.set(['#{i}-v','#{i}'],{{clearProps:'filter'}},{c.q(t + 2 / FPS)});")


# ═══════════════════════════ 18 · DOLLY ZOOM (overlay, cut-out) ═══════════════════════════
def dolly_zoom(c, a, b, cut, bg_scale=0.8, subj_scale=1.07):
    """Vertigo: the room pulls away while the speaker holds (no clean plate needed: the room shrinks under the cut-out)."""
    i = c.uid("dz")
    c.plate_copy(f"{i}-fill", a, b, cls="full", style="filter:blur(22px) brightness(.7);transform:scale(1.1)", z=5)
    c.plate_copy(f"{i}-bg", a, b, cls="full", style="transform-origin:540px 720px", z=6)
    c.video(f"{i}-cut", cut, a, b, cls="cutv", style="transform-origin:540px 720px", z=7)
    c.fromto(f"#{i}-bg", "{scale:1}", f"{{scale:{bg_scale}}}", a, b - a, "power1.inOut")
    c.fromto(f"#{i}-cut", "{scale:1}", f"{{scale:{subj_scale}}}", a, b - a, "power1.inOut")


# ═══════════════════════════ 19 · PRESS FRONT (TAKEOVER, pre-render) ═══════════════════════════
def press_front(c, a, b, src, masthead, headline, standfirst):
    """A newspaper front page: the live halftone photo (tools/stylize.py halftone) on top, masthead, headline and columns BELOW it (face rule)."""
    i = c.uid("press")
    col = "".join(f'<i style="width:{70 + (k * 37) % 30}%"></i>' for k in range(22))
    c.clip(i, a, b, f"""<div class="press full" id="{i}-p"><div class="pphoto"></div><div class="rule2"></div><div class="mast">{masthead}</div><div class="rule1"></div>
      <div class="hed">{headline}</div><div class="stand">{standfirst}</div>
      <div class="pfoot"><div class="pcol">{col}</div><div class="pcol">{col}</div><div class="pcol">{col}</div></div></div>""", z=9)
    c.video(f"{i}-v", src, a, b, cls="pvideo", z=10)
    c.fromto(f"#{i}-p", "{scale:1.04}", "{scale:1}", a, b - a, "power1.out")
    return i


# ═══════════════════════════ 20 · PAPER TEAR (transition out of a full card) ═══════════════════════════
def paper_tear(c, a, b, strips=5, color=CREAM, hold=0.0):
    """Torn paper strips fall away to reveal the shot underneath (place it over the end of a cream card)."""
    i = c.uid("tear"); html = ""
    def edge(e, j):  # x (%) of the torn edge between strip e-1 and e at row j; shared, so the strips interlock
        if e in (0, strips): return 100.0 * e / strips
        return 100.0 * e / strips + 1.6 * math.sin(j * 2.3 + e * 1.7) + 0.8 * math.sin(j * 5.1 + e)
    J = 20
    for k in range(strips):
        right = [f"{edge(k + 1, j):.2f}% {100 * j / J:.2f}%" for j in range(J + 1)]
        left = [f"{edge(k, j):.2f}% {100 * j / J:.2f}%" for j in range(J, -1, -1)]
        html += f'<div class="strip" id="{i}-{k}" style="background:{color};clip-path:polygon({",".join(right + left)})"></div>'
    c.clip(i, a, b, html, cls="full", z=11)
    for k in range(strips):
        c.fromto(f"#{i}-{k}", "{y:0,rotation:0}", f"{{y:{2100 + 200 * (k % 2)},rotation:{(-1) ** k * (8 + 3 * k)}}}", a + hold + 0.04 * k, b - a - hold - 0.04 * k, "power2.in")


# ═══════════════════════════ 21 · BLOW AWAY (TAKEOVER ending, pre-render) ═══════════════════════════
def blow_away(c, a, b, src, bg=CREAM, end_text=None):
    """The speaker breaks into particles and drifts off (tools/stylize.py blowaway) over a brand background."""
    i = c.uid("blow")
    end = f'<div class="blowend" id="{i}-e">{end_text}</div>' if end_text else ""
    c.clip(i, a, b, f'<div class="full" style="background:{bg}"></div>{end}', z=9)
    c.video(f"{i}-v", src, a, b, cls="cutv", z=10)
    if end_text: c.rise(f"#{i}-e", a + (b - a) * 0.6, 0.4, 20)


# ═══════════════════════════ chapter label (demo / list reels) ═══════════════════════════
def chapter(c, a, b, n, total, name, top=1530):
    """A small 'n / total · name' pill in the caption band, for list-style reels."""
    i = c.uid("chap")
    c.clip(i, a, b, f'<div class="chap" style="top:{top}px"><b>{n:02d}</b><span>/ {total}</span> {name}</div>', cls="ov", z=20)
    c.pop(f"#{i} .chap", a, 0.2, 0.8)
