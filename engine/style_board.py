#!/usr/bin/env python3
"""A one-page style board of stills in the user's brand, for approval before the first edit.

    python3 engine/style_board.py <brand.json> <out.html> [--fonts <dir with the brand's woff2/ttf>]

Six 9:16 frames: typed hook (cover open), statement below the neck, 50/50 source split, takeover with particles,
captions, end card. A grey silhouette stands in for the speaker. Open it in a browser or snapshot it.
"""
import argparse, html, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brand import validate, font_faces

def board(b, fonts_dir):
    c, f = b["colors"], b["fonts"]
    ink = c.get("accent_ink", c["accent"])
    faces = font_faces(b).replace("url('fonts/", f"url('{fonts_dir}/")
    D, L = f["display"], f["label"]
    dfont = f"font-family:'{D['family']}',sans-serif;font-weight:{D.get('weight', 600)};letter-spacing:{D.get('tracking', -0.045)}em"
    lfont = f"font-family:'{L['family']}',monospace;font-weight:{L.get('weight', 500)};letter-spacing:{L.get('tracking', 0.08)}em;text-transform:uppercase"
    name = html.escape(b["name"]); handle = html.escape(b.get("handle", ""))
    head = (f"<div class='head'><i style='background:{c['muted']}'></i><b style='background:{c['muted']}'></b></div>")
    dots = "".join(f"<s style='left:{(i * 137) % 1000 + 40}px;top:{(i * 271) % 900 + 520}px;background:{c['accent'] if i % 11 == 0 else c['text']};"
                   f"opacity:{0.25 + (i % 5) * 0.12}'></s>" for i in range(90))
    frames = [
        ("Cover open · typed hook", f"""<div class='lab' style='top:300px'>{handle or name}</div>
          <div class='disp' style='top:380px;font-size:140px'>The hook types<br>as it's <span class='acc'>said</span><u></u></div>{dots}"""),
        ("Statement below the neck", f"""{head}<div class='disp' style='top:1300px;font-size:96px'>One idea,<br>one <span class='acc'>word.</span></div>"""),
        ("50/50 source split", f"""<div class='src'><div class='strip'><span class='lab2'>Source · example.com</span></div>
          <div class='article'><p></p><p></p><p class='hl'>the phrase they say <em></em></p><p></p><p></p></div></div>
          <div class='half'>{head.replace("class='head'", "class='head low'")}</div><div class='cap seam'>captions at the seam</div>"""),
        ("Takeover · particles", f"""<div class='disp' style='top:220px;font-size:96px;color:{c['muted']}'>Not this,</div>{dots}
          <div class='disp' style='top:1250px;font-size:168px'>but <span class='acc'>this.</span></div>"""),
        ("Captions", f"""{head}<div class='cap'>words light up <span style='opacity:.45'>as they're said</span></div>"""),
        ("End card", f"""<div class='disp' style='top:860px;font-size:96px'>{name}</div><div class='lab' style='top:1000px'>{handle}</div>"""),
    ]
    cells = "".join(f"<figure><div class='fr'>{inner}</div><figcaption>{t}</figcaption></figure>" for t, inner in frames)
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>{name} · style board</title><style>{faces}
body{{margin:0;background:#1b1b1b;color:#ddd;font:14px system-ui;padding:24px}}
h1{{font-weight:500;font-size:18px;margin:0 0 16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,324px);gap:24px}}
figure{{margin:0}} figcaption{{margin-top:8px;color:#aaa}}
.fr{{width:1080px;height:1920px;transform:scale(.3);transform-origin:0 0;margin-bottom:-1344px;margin-right:-756px;position:relative;overflow:hidden;background:{c['ground']};color:{c['text']}}}
.disp{{position:absolute;left:80px;right:80px;line-height:1.02;{dfont}}}
.lab{{position:absolute;left:80px;font-size:30px;color:{c['muted']};{lfont}}}
.acc{{color:{c['accent']}}}
u{{display:inline-block;width:10px;height:120px;background:{c['accent']};margin-left:8px;vertical-align:-10px}}
s{{position:absolute;width:10px;height:10px;border-radius:50%}}
.head{{position:absolute;left:0;right:0;top:330px;height:900px}} .head.low{{top:-250px}}
.head i{{position:absolute;left:390px;top:0;width:300px;height:380px;border-radius:50%;opacity:.5}}
.head b{{position:absolute;left:190px;top:420px;width:700px;height:600px;border-radius:300px 300px 0 0;opacity:.35}}
.src{{position:absolute;left:0;top:0;width:1080px;height:960px;background:{c['paper']};overflow:hidden}}
.strip{{height:222px;display:flex;align-items:flex-end;padding:0 60px 28px}} .lab2{{font-size:28px;color:{c['ground']};{lfont}}}
.article{{padding:20px 60px}} .article p{{height:34px;margin:0 0 30px;background:{c['ground']};opacity:.12;border-radius:4px}}
.article .hl{{opacity:1;background:none;font:600 52px '{f['body']['family']}',sans-serif;color:{c['ground']};height:auto;position:relative}}
.article .hl em{{position:absolute;left:0;bottom:-6px;width:480px;height:10px;background:{ink}}}
.half{{position:absolute;left:0;top:960px;width:1080px;height:960px;overflow:hidden;background:{c['ground']}}}
.cap{{position:absolute;left:0;right:0;top:1414px;text-align:center;font-size:{b.get('captions', {}).get('size', 54)}px;{dfont}}}
.cap.seam{{top:846px}} .cap.seam{{background:none}}
</style></head><body><h1>{name} · style board (stills, scaled to 30%)</h1><div class='grid'>{cells}</div></body></html>"""

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("brand"); ap.add_argument("out")
    ap.add_argument("--fonts", default=os.path.expanduser(os.path.join(os.environ.get("REEL_STUDIO_CACHE", "~/.cache/reel-studio"), "fonts", "brand")))
    a = ap.parse_args()
    b = json.load(open(a.brand))
    errs = validate(b)
    if errs: sys.exit("Fix the brand first:\n  - " + "\n  - ".join(errs))
    fonts = os.path.relpath(a.fonts, os.path.dirname(os.path.abspath(a.out)))
    open(a.out, "w").write(board(b, fonts.replace(os.sep, "/")))
    print("wrote", a.out)
