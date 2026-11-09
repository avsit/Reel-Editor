"""Pre-render tools for the effects library (looks a browser can't draw per frame).

    python stylize.py [--brand brand.json] cutout   SRC A B OUT.webm            person cut-out with alpha (Apple Vision, local)
    python stylize.py code     SRC A B OUT.mp4             'Code body': the person redrawn in code characters
    python stylize.py engrave  SRC A B OUT.mp4             'Banknote': engraved-line portrait (crop around the face)
    python stylize.py halftone SRC A B OUT.mp4             'Press front': newspaper halftone portrait (crop around the face)
    python stylize.py blowaway SRC A B OUT.webm            'Blow away': the person disintegrates to the right (alpha)

SRC is any 1080x1920 plate; A..B are source seconds. All output is 30 fps. Colours come from --brand (ground, paper, text, accent).
Person mattes: Apple Vision on a Mac (compiled once into the reel-studio cache), MediaPipe selfie segmentation elsewhere
(python3 scripts/setup.py matte). Everything runs locally; no frame leaves the machine.
"""
import json, os, platform, subprocess, sys, shutil, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.expanduser(os.environ.get("REEL_STUDIO_CACHE", "~/.cache/reel-studio"))
MATTE = os.path.join(CACHE, "bin", "matte_frames")
FPS, W, H = 30, 1080, 1920
INK, CREAM, LIME, GREEN = (14, 17, 16), (236, 231, 220), (229, 255, 31), (14, 17, 16)   # ground, paper, accent, engraving ink
BONE = (239, 234, 223)                                                                     # text

def set_brand(path):
    global INK, CREAM, LIME, GREEN, BONE
    c = json.load(open(path))["colors"]; rgb = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
    INK, CREAM, LIME, GREEN, BONE = rgb(c["ground"]), rgb(c["paper"]), rgb(c["accent"]), rgb(c["ground"]), rgb(c["text"])

def mono_font(size):
    """A bold monospace font on any OS (Menlo, Consolas, DejaVu Sans Mono), else Pillow's default."""
    for path, idx in (("/System/Library/Fonts/Menlo.ttc", 1), ("C:/Windows/Fonts/consolab.ttf", 0),
                      ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 0), ("DejaVuSansMono-Bold.ttf", 0)):
        try: return ImageFont.truetype(path, size, index=idx)
        except OSError: continue
    return ImageFont.load_default()
FACE = (540, 720)  # face centre on the plate (tracked in build/face.json for real builds)

def frames(src, a, b, d):
    os.makedirs(d, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src,
                    "-vf", f"fps={FPS}", f"{d}/%05d.png"], check=True)
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".png"))

def mattes(fdir, mdir):
    os.makedirs(mdir, exist_ok=True)
    if platform.system() == "Darwin":
        if not os.path.exists(MATTE):
            os.makedirs(os.path.dirname(MATTE), exist_ok=True)
            subprocess.run(["swiftc", "-O", os.path.join(HERE, "matte_frames.swift"), "-o", MATTE], check=True)
        subprocess.run([MATTE, fdir, mdir, "accurate"], check=True, capture_output=True)
    else:
        import mediapipe as mp   # python3 scripts/setup.py matte
        with mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=0) as seg:
            for f in sorted(os.listdir(fdir)):
                if not f.endswith(".png"): continue
                rgb = np.asarray(Image.open(os.path.join(fdir, f)).convert("RGB"))
                m = seg.process(rgb).segmentation_mask
                Image.fromarray((np.clip((m - 0.35) / 0.3, 0, 1) * 255).astype(np.uint8)).save(os.path.join(mdir, f))
    return sorted(os.path.join(mdir, f) for f in os.listdir(mdir) if f.endswith(".png"))

def encode(fdir, out, alpha=False):
    if alpha:
        cmd = ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "28", "-auto-alt-ref", "0", "-row-mt", "1"]
    else:
        cmd = ["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-g", "30", "-pix_fmt", "yuv420p"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{fdir}/%05d.png", *cmd, out], check=True)

def cutout(src, a, b, out):
    t = tempfile.mkdtemp()
    fs = frames(src, a, b, f"{t}/f"); ms = mattes(f"{t}/f", f"{t}/m")
    os.makedirs(f"{t}/o")
    for i, (f, m) in enumerate(zip(fs, ms)):
        im = Image.open(f).convert("RGB"); im.putalpha(Image.open(m).convert("L"))
        im.save(f"{t}/o/{i + 1:05d}.png")
    encode(f"{t}/o", out, alpha=True); shutil.rmtree(t)

def code(src, a, b, out, cell=17):
    """Characters sized by brightness; the person in cream/lime code on ink, the room in faint ink-green code."""
    t = tempfile.mkdtemp(); fs = frames(src, a, b, f"{t}/f"); ms = mattes(f"{t}/f", f"{t}/m")
    font = mono_font(cell)
    ramp = " .:-=+*#%@"
    words = "const rate=await fetch(ad).then(r=>r.json());intent.match(query)?bid:skip;render(frame)//"
    cols, rows = W // cell, H // (cell + 2)
    os.makedirs(f"{t}/o")
    for i, (f, m) in enumerate(zip(fs, ms)):
        g = np.asarray(Image.open(f).convert("L").resize((cols, rows), Image.BILINEAR), dtype=np.float32) / 255
        mk = np.asarray(Image.open(m).convert("L").resize((cols, rows), Image.BILINEAR), dtype=np.float32) / 255
        lo, hi = np.percentile(g[mk > 0.5], [3, 97]) if (mk > 0.5).any() else (0, 1)
        g = np.clip((g - lo) / max(0.05, hi - lo), 0, 1) ** 0.8          # moody plates: stretch to full range
        im = Image.new("RGB", (W, H), INK); d = ImageDraw.Draw(im)
        for y in range(rows):
            for x in range(cols):
                lum, inside = g[y, x], mk[y, x] > 0.5
                if inside:
                    ch = words[(x + y * 7 + i) % len(words)] if lum > 0.35 else ramp[int(lum * 9)]
                    col = LIME if lum > 0.82 else tuple(int(c * (0.55 + 0.45 * lum)) for c in BONE)   # style A: Bone code, lime only on the brightest
                else:
                    if lum < 0.12: continue
                    ch = ramp[min(9, int(lum * 6))]; col = (52, 78, 60)
                d.text((x * cell, y * (cell + 2)), ch, font=font, fill=col)
        im.save(f"{t}/o/{i + 1:05d}.png")
    encode(f"{t}/o", out); shutil.rmtree(t)

def _crop(img, size=(860, 960)):
    cx, cy = FACE; w, h = size
    return img.crop((cx - w // 2, cy - h // 2 + 60, cx + w // 2, cy + h // 2 + 60))

def engrave(src, a, b, out, pitch=7.0):
    """Banknote-style line engraving: wavy horizontal lines whose thickness follows darkness, in a vignette."""
    t = tempfile.mkdtemp(); fs = frames(src, a, b, f"{t}/f")
    os.makedirs(f"{t}/o")
    for i, f in enumerate(fs):
        g = np.asarray(_crop(Image.open(f).convert("L")), dtype=np.float32) / 255
        g = np.clip((g - 0.08) / 0.75, 0, 1)
        h, w = g.shape; yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        wave = yy + 6 * np.sin(xx / 47 + i * 0.05) + 4 * np.sin((xx + yy) / 91)
        phase = (wave % pitch) / pitch                       # 0..1 across each line
        ink = np.abs(phase - 0.5) < (1 - g) * 0.48            # darker -> thicker line
        r = np.hypot((xx - w / 2) / (w * 0.47), (yy - h / 2) / (h * 0.5))
        ink &= r < 1.0
        rgb = np.where(ink[..., None], np.array(GREEN, np.uint8), np.array(CREAM, np.uint8)).astype(np.uint8)
        Image.fromarray(rgb).save(f"{t}/o/{i + 1:05d}.png")
    encode(f"{t}/o", out); shutil.rmtree(t)

def halftone(src, a, b, out, cell=12):
    """Newspaper halftone: 45-degree dot screen, dot size from darkness, ink on cream."""
    t = tempfile.mkdtemp(); fs = frames(src, a, b, f"{t}/f")
    os.makedirs(f"{t}/o")
    for i, f in enumerate(fs):
        g = np.asarray(_crop(Image.open(f).convert("L")), dtype=np.float32) / 255
        g = np.clip((g - 0.05) / 0.8, 0, 1)
        h, w = g.shape; yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        u, v = (xx + yy) / np.sqrt(2), (xx - yy) / np.sqrt(2)  # rotate the screen 45 degrees
        du, dv = (u % cell) - cell / 2, (v % cell) - cell / 2
        radius = np.sqrt(1 - g) * cell * 0.62
        ink = np.hypot(du, dv) < radius
        rgb = np.where(ink[..., None], np.array(INK, np.uint8), np.array(CREAM, np.uint8)).astype(np.uint8)
        Image.fromarray(rgb).save(f"{t}/o/{i + 1:05d}.png")
    encode(f"{t}/o", out); shutil.rmtree(t)

def blowaway(src, a, b, out, step=3):
    """The person breaks into particles from left to right and drifts off up-right (alpha video)."""
    t = tempfile.mkdtemp(); fs = frames(src, a, b, f"{t}/f"); ms = mattes(f"{t}/f", f"{t}/m")
    n = len(fs); rng = np.random.default_rng(7)
    first = np.asarray(Image.open(ms[0]).convert("L"))
    ys, xs = np.nonzero(first[::step, ::step] > 128); ys, xs = ys * step, xs * step
    noise = rng.random(len(xs))
    xmin, xmax = xs.min(), xs.max()
    thresh = 0.15 + 0.6 * (xs - xmin) / max(1, xmax - xmin) + 0.25 * noise   # left goes first
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    grain = np.asarray(Image.fromarray((rng.random((H // step, W // step)) * 255).astype(np.uint8)).resize((W, H), Image.NEAREST), np.float32) / 255
    tfield = 0.15 + 0.6 * np.clip((gx - xmin) / max(1, xmax - xmin), 0, 1) + 0.25 * grain
    vx, vy = 900 + 700 * rng.random(len(xs)), -250 - 500 * rng.random(len(xs))
    os.makedirs(f"{t}/o")
    for i, (f, m) in enumerate(zip(fs, ms)):
        p = i / max(1, n - 1)
        img = np.asarray(Image.open(f).convert("RGB"))
        mk = np.asarray(Image.open(m).convert("L")).astype(np.float32) / 255
        canvas = np.zeros((H, W, 4), np.uint8)
        # still-solid body: the LIVE matte, eaten away by a fixed threshold field (follows him as he moves)
        keep = p < thresh
        alpha = (mk * (p < tfield) * 255).astype(np.uint8)
        canvas[..., :3] = img; canvas[..., 3] = alpha
        # flying particles
        go = ~keep; dt = np.clip(p - thresh[go], 0, 1)
        px = (xs[go] + vx[go] * dt ** 1.4).astype(int); py = (ys[go] + vy[go] * dt ** 1.2 + 60 * np.sin(dt * 9)).astype(int)
        fade = np.clip(1 - dt * 2.2, 0, 1)
        ok = (px >= 0) & (px < W - 2) & (py >= 0) & (py < H - 2) & (fade > 0)
        cols = img[ys[go][ok], xs[go][ok]]
        for dx in (0, 1):
            for dy in (0, 1):
                canvas[py[ok] + dy, px[ok] + dx, :3] = cols
                canvas[py[ok] + dy, px[ok] + dx, 3] = (fade[ok] * 255).astype(np.uint8)
        Image.fromarray(canvas, "RGBA").save(f"{t}/o/{i + 1:05d}.png")
    encode(f"{t}/o", out, alpha=True); shutil.rmtree(t)

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv[:1] == ["--brand"]: set_brand(argv[1]); argv = argv[2:]
    kind, src, a, b, out = argv[0], argv[1], float(argv[2]), float(argv[3]), argv[4]
    {"cutout": cutout, "code": code, "engrave": engrave, "halftone": halftone, "blowaway": blowaway}[kind](src, a, b, out)
    print("wrote", out)
