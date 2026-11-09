#!/usr/bin/env python3
"""Find a phrase in a (tall) screenshot and print its box per text line, for one-phrase underlines in shot().

    python3 engine/tools/find_text.py <image> <y0> <y1> "<phrase>"
    -> [[x, y, w, h], ...] in the image's pixels (a phrase that wraps gets one box per line)

Mac: Apple Vision OCR (compiled once into the reel-studio cache). Windows/Linux: RapidOCR (python3 scripts/setup.py ocr).
Runs locally.
"""
import json, os, platform, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.expanduser(os.environ.get("REEL_STUDIO_CACHE", "~/.cache/reel-studio"))

def vision(img, y0, y1, phrase):
    exe = os.path.join(CACHE, "bin", "find_text")
    if not os.path.exists(exe):
        os.makedirs(os.path.dirname(exe), exist_ok=True)
        subprocess.run(["swiftc", "-O", os.path.join(HERE, "find_text.swift"), "-o", exe], check=True)
    return json.loads(subprocess.run([exe, img, str(y0), str(y1), phrase], capture_output=True, text=True, check=True).stdout)

def rapid(img, y0, y1, phrase):
    from rapidocr_onnxruntime import RapidOCR
    from PIL import Image
    import numpy as np
    crop = np.asarray(Image.open(img).convert("RGB"))[int(y0):int(y1)]
    res, _ = RapidOCR()(crop)
    words, out = phrase.lower().split(), []
    for box, text, _score in res or []:
        s = text.lower()
        for n in range(len(words), 0, -1):   # the whole phrase, or the part of it on this line (>= 6 chars)
            hit = next((" ".join(words[i:i + n]) for i in range(len(words) - n + 1)
                        if " ".join(words[i:i + n]) in s and (n == len(words) or len(" ".join(words[i:i + n])) >= 6)), None)
            if hit: break
        if not hit: continue
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        x0, x1 = min(xs), max(xs); k = s.index(hit)
        cw = (x1 - x0) / max(1, len(s))           # proportional estimate of the sub-string inside the line box
        out.append([int(x0 + k * cw), int(y0 + min(ys)), int(len(hit) * cw), int(max(ys) - min(ys))])
    return out

if __name__ == "__main__":
    img, y0, y1, phrase = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    print(json.dumps((vision if platform.system() == "Darwin" else rapid)(img, y0, y1, phrase)))
