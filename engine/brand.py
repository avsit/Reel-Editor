#!/usr/bin/env python3
"""Brand files: validate, turn into CSS, fetch fonts.

    python3 engine/brand.py validate <brand.json>
    python3 engine/brand.py fonts <brand.json> <dest_fonts_dir>      # downloads the brand's Google Fonts (asks first in the skill)

A brand.json is written by Claude from the user's brand.md (skills/reel-brand). Schema: brand/schema.json.
"""
import json, os, re, sys, urllib.request

REQUIRED_COLORS = ["ground", "text", "muted", "paper", "accent"]
ROLES = ["display", "body", "label"]

def slug(family): return re.sub(r"[^a-z0-9]+", "-", family.lower()).strip("-")

def validate(b):
    errs = []
    for k in ("name", "colors", "fonts"):
        if k not in b: errs.append(f"missing '{k}'")
    for c in REQUIRED_COLORS:
        v = b.get("colors", {}).get(c)
        if not (isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v)): errs.append(f"colors.{c} must be #RRGGBB")
    for r in ROLES:
        f = b.get("fonts", {}).get(r)
        if not f or "family" not in f: errs.append(f"fonts.{r}.family missing")
    def lum(h):
        r, g, bb = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        f = lambda c: c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
        return .2126 * f(r) + .7152 * f(g) + .0722 * f(bb)
    def contrast(a, c):
        l1, l2 = sorted([lum(a), lum(c)], reverse=True); return (l1 + .05) / (l2 + .05)
    if not errs:
        cl = b["colors"]
        if contrast(cl["text"], cl["ground"]) < 7: errs.append(f"text on ground is {contrast(cl['text'], cl['ground']):.1f}:1 (needs >= 7:1 for phone legibility)")
        if contrast(cl["accent"], cl["ground"]) < 4.5: errs.append(f"accent on ground is {contrast(cl['accent'], cl['ground']):.1f}:1 (needs >= 4.5:1)")
        if contrast(cl.get("accent_ink", cl["accent"]), cl["paper"]) < 1.1: errs.append("accent_ink on paper is invisible: set a deeper accent_ink for underlines on light grounds")
    return errs

def weights(b, fam):
    """The weights a family is used at in this brand (plus 400 for running text)."""
    return sorted({int(b["fonts"][r].get("weight", {"display": 600, "body": 500, "label": 500}[r])) for r in ROLES
                   if b["fonts"][r]["family"] == fam} | {400})

def font_faces(b):
    """@font-face rules: one per fetched weight (fonts/<slug>-<w>.woff2), plus a catch-all for a user-supplied
    fonts/<slug>.woff2|ttf (a variable or single file covering every weight)."""
    out, seen = [], set()
    for role in ROLES:
        fam = b["fonts"][role]["family"]
        if fam in seen: continue
        seen.add(fam); sl = slug(fam)
        out.append(f"@font-face {{ font-family:'{fam}'; src:url('fonts/{sl}.woff2') format('woff2'), url('fonts/{sl}.ttf') format('truetype'); font-weight:100 900; font-display:block; }}")
        for w in weights(b, fam):
            out.append(f"@font-face {{ font-family:'{fam}'; src:url('fonts/{sl}-{w}.woff2') format('woff2'); font-weight:{w}; font-display:block; }}")
        if b["fonts"][role].get("italic"):
            out.append(f"@font-face {{ font-family:'{fam}'; font-style:italic; src:url('fonts/{sl}-italic.woff2') format('woff2'), url('fonts/{sl}-italic.ttf') format('truetype'); font-weight:100 900; font-display:block; }}")
    return "\n".join(out)

def css_for(b, template):
    """Fill templates/reel.css: {{colors.x}}, {{fonts.role.family|weight|tracking}}, {{font_faces}}, {{captions.size}}."""
    cl, f, cap = b["colors"], b["fonts"], b.get("captions", {})
    vals = {f"colors.{k}": v for k, v in cl.items()}
    vals.setdefault("colors.accent_ink", cl["accent"])
    for r in ROLES:
        vals[f"fonts.{r}.family"] = f[r]["family"]
        vals[f"fonts.{r}.weight"] = str(f[r].get("weight", {"display": 600, "body": 500, "label": 500}[r]))
        vals[f"fonts.{r}.tracking"] = f"{f[r].get('tracking', {'display': -0.045, 'body': -0.01, 'label': 0.08}[r])}em"
    vals["captions.size"] = f"{cap.get('size', 54)}px"
    vals["font_faces"] = font_faces(b)
    return re.sub(r"\{\{([a-z_.]+)\}\}", lambda m: vals.get(m.group(1), m.group(0)), template)

def fetch_fonts(b, dest):
    """Download the brand's fonts from Google Fonts: one latin woff2 per weight the brand uses (fonts/<slug>-<w>.woff2).
    Families not on Google Fonts must be supplied by the user as fonts/<slug>.woff2 or .ttf."""
    os.makedirs(dest, exist_ok=True)
    ua = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
    done = []
    for fam in sorted({b["fonts"][r]["family"] for r in ROLES}):
        ws = weights(b, fam)
        url = f"https://fonts.googleapis.com/css2?family={fam.replace(' ', '+')}:wght@{';'.join(map(str, ws))}&display=block"
        try:
            css = urllib.request.urlopen(urllib.request.Request(url, headers=ua), timeout=20).read().decode()
        except Exception as e:
            print(f"  {fam}: not on Google Fonts at weights {ws} ({e}). Put the font file at {dest}/{slug(fam)}.woff2 (or .ttf) yourself."); continue
        for block in re.findall(r"/\* latin \*/\s*@font-face\s*\{(.*?)\}", css, re.S):
            w = re.search(r"font-weight:\s*(\d+)", block); m = re.search(r"url\((https://[^)]+\.woff2)\)", block)
            if not (w and m): continue
            name = f"{slug(fam)}-{w.group(1)}.woff2"
            if not os.path.exists(f"{dest}/{name}"):
                open(f"{dest}/{name}", "wb").write(urllib.request.urlopen(urllib.request.Request(m.group(1), headers=ua), timeout=30).read())
            done.append(name); print(f"  {fam} {w.group(1)} -> {dest}/{name}")
        italic = any(b["fonts"][r].get("italic") and b["fonts"][r]["family"] == fam for r in ROLES)
        if italic: print(f"  {fam} italic: supply {dest}/{slug(fam)}-italic.woff2 yourself if you want true italics")
    return done

if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    b = json.load(open(path))
    if cmd == "validate":
        e = validate(b)
        print("OK: brand file is valid" if not e else "Brand file problems:\n  - " + "\n  - ".join(e)); sys.exit(1 if e else 0)
    if cmd == "fonts":
        fetch_fonts(b, sys.argv[3])
