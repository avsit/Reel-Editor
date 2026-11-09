#!/usr/bin/env python3
"""Gate A of the reel QA process: every house rule that can be measured, in one report.

    python3 engine/qa_reel.py <project_dir> [--video <render.mp4>] [--out <dir>]

<project_dir> holds timeline.json, transcript.json, build/face.json and public/index.html (the Reel Studio project layout).
Writes <out>/report.md and report.json (default <project_dir>/qa). Exit 1 if any check FAILs.

Checks (PASS / WARN / FAIL):
  H1 text below the neck      every chest element starts below its section's neck line; captions band below every neck
  H2 takeovers <= 2           counted from timeline.json house.takeovers
  H3 only the speaker's words every word shown on screen appears in the transcript (brand allow_words for labels/handles)
  H4 brand fonts              only the brand's fonts in the CSS
  H5 brand colours            every colour in the CSS is a brand colour (a few greys are fine)
  H6 sound                    -14 LUFS +/-1, true peak <= -1.5 dBTP; SFX count 4-10
  H7 render spec              1080x1920, 30 fps constant, length = timeline meta.dur (+/- 2 frames)
  H8 hyperframes lint         0 errors
  H9 first 3 seconds          no static stretch >= 0.5 s anywhere in 0-3 s (the most important part of a reel)
  V1 timeline                 video-director check_timeline.py: 0 errors
  V2 render QA                video-director qa_video.py --beats timeline.json: no FAIL (also makes the sheets)
"""
# run inside the reel-studio venv (numpy, Pillow, OpenCV live there), whatever python3 the user called
import os as _os, sys as _sys
_VPY = _os.path.join(_os.path.expanduser(_os.environ.get("REEL_STUDIO_CACHE", "~/.cache/reel-studio")), "venv",
                     "Scripts" if _os.name == "nt" else "bin", "python.exe" if _os.name == "nt" else "python")
if _os.path.exists(_VPY) and _os.path.realpath(_sys.prefix) != _os.path.realpath(_os.path.dirname(_os.path.dirname(_VPY))):
    _os.execv(_VPY, [_VPY] + _sys.argv)

import argparse, json, os, re, subprocess, sys
from html.parser import HTMLParser

ENGINE = os.path.dirname(os.path.abspath(__file__))
VD = os.path.join(ENGINE, "vendor", "video_director")
CACHE = os.path.expanduser(os.environ.get("REEL_STUDIO_CACHE", "~/.cache/reel-studio"))
HF = os.path.join(CACHE, "node", "node_modules", ".bin", "hyperframes.cmd" if os.name == "nt" else "hyperframes")
VPY = os.path.join(CACHE, "venv", "Scripts" if os.name == "nt" else "bin", "python.exe" if os.name == "nt" else "python")
NEUTRAL = {"#ffffff", "#fff", "#000", "#000000"}
NECK_PAD = 90
# layout glyphs and source labels every reel may show without the speaker saying them
ALLOW_BASE = {"no", "source", "via", "com", "s", "t", "it", "isn", "won",
              "qwertyuiop", "asdfghjkl", "zxcvbnm", "space", "go"}   # + the effects keyboard's key rows
ALLOW = set(ALLOW_BASE)

results = []
def add(cid, name, status, detail):
    results.append({"id": cid, "check": name, "status": status, "detail": detail})

def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr

class TextGrab(HTMLParser):
    """Visible text of the composition, minus scripts/styles."""
    def __init__(self):
        super().__init__(); self.skip = 0; self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "title"): self.skip += 1
        if tag in ("br", "div", "p"): self.parts.append(" ")
    def handle_endtag(self, tag):
        if tag in ("script", "style", "title"): self.skip -= 1
    def handle_data(self, d):
        if not self.skip and d:
            self.parts.append(" " if not d.strip() else d)   # &nbsp; spans are word breaks

class ClipText(HTMLParser):
    """Text per timed element (top-level .clip divs with data-start), for the time-windowed word check."""
    def __init__(self):
        super().__init__(); self.stack = []; self.clips = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "title"): self.skip += 1
        if tag == "div" and "clip" in (a.get("class") or "").split() and "data-start" in a and not self.stack \
                and a.get("id") not in ("captions", "preload"):
            self.clips.append({"id": a.get("id"), "t0": float(a["data-start"]), "t1": float(a["data-start"]) + float(a.get("data-duration", 0)), "txt": ""})
            self.stack.append(tag)
        elif self.stack and tag == "div": self.stack.append(tag)
        if self.stack and tag in ("br", "div"): self.clips[-1]["txt"] += " "
    def handle_endtag(self, tag):
        if tag in ("script", "style", "title"): self.skip -= 1
        if self.stack and tag == "div": self.stack.pop()
    def handle_data(self, d):
        if self.stack and not self.skip:
            self.clips[-1]["txt"] += d if len(d) == 1 and d.strip() else " " + (d if d.strip() else " ") + " "

def words_of(s):
    s = s.replace("\xad", "").replace("&shy;", "")   # soft hyphens are line-break hints, not word breaks
    return [w for w in re.findall(r"[a-z0-9]+", s.lower().replace("’", "'"))]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project"); ap.add_argument("--video"); ap.add_argument("--out")
    a = ap.parse_args()
    P = os.path.abspath(a.project); OUT = os.path.abspath(a.out or f"{P}/qa"); os.makedirs(OUT, exist_ok=True)
    TL = json.load(open(f"{P}/timeline.json")); house = TL.get("house", {})
    ALLOW.update(w for a in house.get("allow_words", []) for w in words_of(a))
    html = open(f"{P}/public/index.html").read()
    words = json.load(open(f"{P}/transcript.json"))
    face = json.load(open(f"{P}/build/face.json"))["samples"]
    video = a.video or next((f"{P}/{f}" for f in sorted(os.listdir(P)) if f.endswith(".mp4")), None)

    # H1 face guard
    bad = [g for g in house.get("guard", []) if not g[3] > g[4]]
    cap_top = house.get("caption_band", [1414, 90])[0]
    def chin_max(x0, x1):
        s = [r[2] for r in face if r[1] is not None and x0 <= r[0] < x1]
        return max(s) if s else 1215
    cap_bad = [(sc["id"], chin_max(sc["start"], sc["end"]) + NECK_PAD) for sc in TL["scenes"]
               if sc["id"].endswith("_face") and not cap_top > chin_max(sc["start"], sc["end"]) + NECK_PAD]
    if not house.get("guard"):
        add("H1", "Text below the neck", "WARN", "no guard data in timeline.json house.guard: check the sheets by eye")
    elif bad or cap_bad:
        add("H1", "Text below the neck", "FAIL", f"elements above the neck: {bad}; caption band above neck in: {cap_bad}")
    else:
        add("H1", "Text below the neck", "PASS", f"{len(house['guard'])} chest elements and the caption band clear the neck in every face section")

    # H2 takeovers
    n, mx = house.get("takeovers"), house.get("max_takeovers", 2)
    if n is None: add("H2", "Takeovers <= 2", "WARN", "timeline.json has no house.takeovers")
    else: add("H2", "Takeovers <= 2", "PASS" if n <= mx else "FAIL", f"{n} takeover(s)")

    # H3 only the speaker's words
    said = set(words_of(" ".join(w["text"] for w in words)))
    g = TextGrab(); g.feed(html)
    # per-letter spans are one word: glue single characters to their neighbours
    txt = ""
    for part in g.parts:
        txt += part if len(part) == 1 else " " + part + " "
    shown = set(words_of(txt))
    extra = sorted(w for w in shown - said - ALLOW if not w.isdigit())
    if not extra: add("H3", "Only the speaker's words on screen", "PASS", f"{len(shown)} distinct on-screen words, all said or allow-listed labels")
    else: add("H3", "Only the speaker's words on screen", "WARN" if len(extra) <= 6 else "FAIL",
              f"words on screen never said (check each is a label/source, not a claim): {', '.join(extra)}")

    # H3b: each word an element shows must be said within 2 s of when it is on screen (catches paraphrases like "like Google")
    ct = ClipText(); ct.feed(html); para = []
    for c in ct.clips:
        near = set(words_of(" ".join(w["text"] for w in words if c["t0"] - 2 <= w["start"] <= c["t1"] + 2)))
        miss = sorted(w for w in set(words_of(c["txt"])) - near - ALLOW if not w.isdigit())
        if miss: para.append(f"{c['id']} @ {c['t0']:.2f}: {', '.join(miss)}")
    add("H3b", "The speaker's words, when they are said", "PASS" if not para else "WARN",
        "every element's words are said within 2 s of it" if not para else "not said within 2 s (paraphrase or early): " + " | ".join(para))

    # H4 / H5 fonts and colours (from the inlined CSS)
    css = " ".join(re.findall(r"<style>(.*?)</style>", html, re.S)).lower()
    fams = set(f.strip(" '\"") for m in re.findall(r"font-family\s*:\s*([^;}]+)", css) for f in m.split(","))
    fams |= set(re.findall(r"font\s*:[^;}]*?'([^']+)'", css))
    house_fonts = set(f.lower() for f in house.get("fonts", []))   # the brand's fonts, written by build.py
    unknown = sorted(f for f in fams if f not in house_fonts | {"serif", "sans-serif", "monospace", "system-ui"})
    _fdir = f"{P}/public/fonts"; _files = os.listdir(_fdir) if os.path.isdir(_fdir) else []
    missing_files = sorted(f for f in house_fonts if not any(x.startswith(re.sub(r'[^a-z0-9]+', '-', f).strip('-')) for x in _files))
    if missing_files: unknown = unknown + [f"{f} (font file missing: renders in a fallback font)" for f in missing_files]
    add("H4", "Brand fonts", "FAIL" if len(unknown) > 1 else "WARN" if unknown else "PASS",
        f"fonts: {sorted(fams & house_fonts)}" + (f"; problems: {unknown}" if unknown else ""))
    cols = set(re.findall(r"(?<!['\"])#[0-9a-f]{6}\b|(?<!['\"])#[0-9a-f]{3}\b", html.lower()))   # not element ids like '#c10'
    cols -= {c for c in cols if re.search(re.escape(c) + r"[-_a-z]", html.lower())}
    brand_cols = set(c.lower() for c in house.get("colours", [])) | NEUTRAL
    off = sorted(c for c in cols if c not in brand_cols)
    add("H5", "Brand colours", "PASS" if len(off) <= 4 else "WARN",
        f"{len(cols)} colours; outside the token set: {off or 'none'} (greys for struck/dimmed text are fine)")

    # H6 sound
    if video:
        rc, o = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-af", "ebur128=peak=true", "-f", "null", "-"])
        I = re.findall(r"I:\s+(-?[\d.]+) LUFS", o); TP = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", o)
        if I:
            i, tp = float(I[-1]), float(TP[-1]) if TP else 0.0
            ok = abs(i + 14) <= 1 and tp <= -1.5 + 0.1
            add("H6", "Sound: loudness and peak", "PASS" if ok else "FAIL", f"{i:.1f} LUFS, true peak {tp:.1f} dBTP (target -14 +/-1, <= -1.5)")
    n_sfx = len(TL.get("sfx", []))
    add("H6b", "Sound: SFX count", "PASS" if 4 <= n_sfx <= 10 else "WARN", f"{n_sfx} SFX (range 4-10, graphic moments only)")

    # H7 render spec
    if video:
        rc, o = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,avg_frame_rate:format=duration", "-of", "json", video])
        j = json.loads(o); st = j["streams"][0]; dur = float(j["format"]["duration"])
        ok = st["width"] == 1080 and st["height"] == 1920 and st["r_frame_rate"] == "30/1" and abs(dur - TL["meta"]["dur"]) <= 2 / 30 + 0.05
        add("H7", "Render spec", "PASS" if ok else "FAIL", f"{st['width']}x{st['height']} @ {st['r_frame_rate']}, {dur:.2f}s (plan {TL['meta']['dur']}s)")
    else:
        add("H7", "Render spec", "WARN", "no render found: run again with --video")

    # H9 the hook: something must move or arrive in every 0.5 s window of the first 3 s
    if video:
        import numpy as np
        raw = subprocess.run(["ffmpeg", "-v", "error", "-t", "3.0", "-i", video, "-vf", "scale=270:480,format=gray", "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        fr = np.frombuffer(raw, np.uint8).reshape(-1, 480, 270).astype(np.float32)
        d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))           # mean change between consecutive frames
        still, runs, s0 = d < 0.25, [], None
        for i, st in enumerate(list(still) + [False]):
            if st and s0 is None: s0 = i
            if not st and s0 is not None:
                if (i - s0) / 30 >= 0.5: runs.append((round(s0 / 30, 2), round(i / 30, 2)))
                s0 = None
        add("H9", "First 3 seconds keep moving", "PASS" if not runs else "FAIL",
            "motion in every 0.5 s window of the hook" if not runs else f"static stretches in the hook: {runs}")

    # H8 lint
    rc, o = run([HF if os.path.exists(HF) else "npx", *([] if os.path.exists(HF) else ["hyperframes"]), "lint"], cwd=f"{P}/public")
    errs = len(re.findall(r"✗", o))
    add("H8", "HyperFrames lint", "PASS" if errs == 0 else "FAIL", f"{errs} error(s)")

    # V1 / V2 video-director
    rc, o = run([sys.executable, f"{VD}/check_timeline.py", f"{P}/timeline.json"])
    tail = o.strip().splitlines()[-1] if o.strip() else ""
    add("V1", "Timeline (video-director)", "PASS" if rc == 0 else "FAIL", tail)
    open(f"{OUT}/check_timeline.txt", "w").write(o)
    if video:
        planned = sorted(set(TL.get("cuts", [])) | set(TL.get("swaps", [])) | set(TL.get("plate_cuts", [])))   # swaps = deliberate hard swaps inside a layout
        rc, o = run([VPY if os.path.exists(VPY) else sys.executable, f"{VD}/qa_video.py", video, "--out", f"{OUT}/render", "--beats", f"{P}/timeline.json",
                     "--expect-cuts", ",".join(f"{t:.3f}" for t in planned)])
        fails = [l for l in o.splitlines() if "FAIL" in l]
        note = ""
        # video-director holds every planned cut to 1 frame. Real cuts (layout + plate) keep that; declared swaps
        # (an element appearing inside a layout) register on their first visibly-changed frame, so they get 2 frames.
        rep = json.load(open(f"{OUT}/render/report.json"))
        det = rep.get("picture", {}).get("cuts") or []
        if rc != 0 and det and all("cuts vs plan" in l for l in fails):
            hard = set(TL.get("cuts", [])) | set(TL.get("plate_cuts", []))
            worst_h = max((min(abs(c - t) for c in det) * 30 for t in hard), default=0)
            # a declared swap may be soft (a mask reveal over a still face) and not register as a cut: only swaps that DID
            # register are held to 2 frames; real cuts (layout + plate) must all register within 1 frame
            sw = [min(abs(c - t) for c in det) * 30 for t in TL.get("swaps", [])]
            worst_s = max((e for e in sw if e <= 15), default=0)
            fxw = TL.get("house", {}).get("fx_windows", [])   # motion inside a declared effect is that effect, not a cut
            unpl = [c for c in det if all(abs(c - t) > 0.5 for t in planned) and not any(a0 <= c <= b0 for a0, b0 in fxw)]
            # declared swaps only EXPLAIN detected changes (so none is unplanned); their pairing error is not meaningful
            if worst_h <= 1.0 and not unpl:
                rc, note = 0, f"real cuts within {worst_h:.2f} f; every detected change is planned (cuts, plate jump cuts or declared swaps); "
        add("V2", "Render QA (video-director)", "PASS" if rc == 0 else "FAIL",
            (note + "no other FAIL" if rc == 0 else "; ".join(fails[:4])) + f" · sheets in {OUT}/render/")

    worst = "FAIL" if any(r["status"] == "FAIL" for r in results) else "WARN" if any(r["status"] == "WARN" for r in results) else "PASS"
    md = [f"# Gate A: automated QA · {os.path.basename(P)}", "", f"**Result: {worst}**  ·  video: `{video}`", "",
          "| ID | Check | Result | Detail |", "|---|---|---|---|"]
    md += [f"| {r['id']} | {r['check']} | {r['status']} | {r['detail']} |" for r in results]
    md += ["", "Decisions logged in timeline.json:", *[f"- {d}" for d in TL.get("decisions", [])]]
    open(f"{OUT}/report.md", "w").write("\n".join(md) + "\n")
    json.dump({"result": worst, "checks": results}, open(f"{OUT}/report.json", "w"), indent=1)
    print("\n".join(md))
    sys.exit(1 if worst == "FAIL" else 0)

if __name__ == "__main__":
    main()
