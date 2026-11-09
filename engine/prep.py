#!/usr/bin/env python3
"""Turn a rough cut into a Reel Studio project (phase 1).

    python3 engine/prep.py <rough_cut.mp4> <project_dir> --brand <brand.json> [--name NAME] [--open graphic|talking|ask]
        [--lang en] [--model base]

Does, in order:
  1. plate      1080x1920 / 30 fps, a light grade only (contrast +4%, saturation +6%, gentle sharpen), no audio -> public/input-video.mp4
  2. voice      the speech track cleaned to -14 LUFS -> build/voice.wav (the mix reads it)
  3. words      faster-whisper word timings -> transcript.json (check them against the audio before planning)
  4. face       OpenCV YuNet face samples -> build/face.json (the face guard reads it)
  5. project    reel.json, an edit.py from the template, public/ (gsap, particles.js, brand fonts), broll/
"""
import argparse, json, os, platform, shutil, subprocess, sys

ENGINE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ENGINE)
OS = {"Darwin": "mac", "Windows": "windows"}.get(platform.system(), "linux")
CACHE = os.path.expanduser(os.environ.get("REEL_STUDIO_CACHE", "~/.cache/reel-studio"))
VPY = os.path.join(CACHE, "venv", "Scripts" if OS == "windows" else "bin", "python.exe" if OS == "windows" else "python")

def sh(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd)[:160]); subprocess.run(cmd, check=True, **kw)

def duration(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout.strip())

WHISPER = r'''
import json, subprocess, sys
import numpy as np
from faster_whisper import WhisperModel
src, out, lang, size = sys.argv[1:5]
# decode with ffmpeg ourselves (16 kHz mono float): faster-whisper's own loader breaks on newer PyAV releases
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
audio = np.frombuffer(raw, np.float32)
m = WhisperModel(size, device="cpu", compute_type="int8")
segs, _ = m.transcribe(audio, language=None if lang == "auto" else lang, word_timestamps=True, vad_filter=True)
words = [{"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)} for s in segs for w in (s.words or []) if w.word.strip()]
json.dump(words, open(out, "w"), indent=0); print(f"{len(words)} words -> {out}")
'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("project"); ap.add_argument("--brand", required=True)
    ap.add_argument("--name"); ap.add_argument("--open", default="ask"); ap.add_argument("--lang", default="en"); ap.add_argument("--model", default="base")
    a = ap.parse_args()
    P = os.path.abspath(a.project); pub = f"{P}/public"
    for d in ("build", "sound", "public/broll", "public/fonts", "public/vendor", "public/pre"): os.makedirs(f"{P}/{d}", exist_ok=True)
    if not os.path.exists(VPY): sys.exit("Run setup first: python3 scripts/doctor.py, then scripts/setup.py python-deps")
    print("1. plate")
    sh(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,eq=contrast=1.04:saturation=1.06,unsharp=5:5:0.4",
        "-an", "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-g", "30", "-pix_fmt", "yuv420p", f"{pub}/input-video.mp4"])
    print("2. voice")
    sh(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-vn", "-af", "highpass=f=80,afftdn=nf=-25,loudnorm=I=-14:TP=-2:LRA=7",
        "-ar", "48000", "-ac", "2", f"{P}/build/voice.wav"])
    print("3. words (faster-whisper; first run downloads the model)")
    open(f"{P}/build/_whisper.py", "w").write(WHISPER)
    sh([VPY, f"{P}/build/_whisper.py", f"{P}/build/voice.wav", f"{P}/transcript.json", a.lang, a.model])
    print("4. face")
    sh([VPY, f"{ENGINE}/vendor/ghost_editor/face_track.py", f"{pub}/input-video.mp4", "--out", f"{P}/build/face.json"])
    print("5. project")
    vid = round(duration(f"{pub}/input-video.mp4"), 2)
    name = a.name or os.path.basename(P)
    brand_rel = os.path.relpath(os.path.abspath(a.brand), P)
    json.dump({"name": name, "brand": brand_rel, "vid": vid, "dur": round(vid + 1.2, 2), "open": a.open}, open(f"{P}/reel.json", "w"), indent=1)
    if not os.path.exists(f"{P}/edit.py"): shutil.copy(f"{REPO}/templates/edit_example.py", f"{P}/edit.py")
    shutil.copy(f"{ENGINE}/templates/particles.js", f"{pub}/particles.js")
    gsap = os.path.join(CACHE, "node", "node_modules", "gsap", "dist", "gsap.min.js")
    if os.path.exists(gsap): shutil.copy(gsap, f"{pub}/vendor/gsap.min.js")
    else: print("  ! GSAP not found in the cache: run python3 scripts/setup.py node-deps")
    fonts = os.path.join(CACHE, "fonts", os.path.basename(a.brand).split(".")[0])
    if os.path.isdir(fonts):
        for f in os.listdir(fonts): shutil.copy(os.path.join(fonts, f), f"{pub}/fonts/{f}")
    else: print(f"  ! brand fonts not fetched yet: python3 engine/brand.py fonts {a.brand} {fonts}")
    print(f"\nproject ready: {P}\n  next: plan the edit from transcript.json, write edit.py, then python3 {ENGINE}/build.py {P}")

if __name__ == "__main__":
    main()
