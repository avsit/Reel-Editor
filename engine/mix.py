"""Reel Studio mix: cleaned voice + ducked music bed (optional) + SFX read from timeline.json, with stems for QA.

    python3 engine/mix.py <project_dir>

Music: reel.json "music" or brand.sound.music (a file path); none means voice + SFX only.
SFX "src" in timeline.json: an absolute path, a path relative to the project, or a file in ~/.cache/reel-studio/sfx
(render earshot's sound bank there: earshot sfx render ...). Levels are relative to the voice's p95 peak.
Accents ON a spoken word must cut through by frequency (bright, 5-9 kHz), never by level: SFX are never louder than the voice.
"""
# run inside the reel-studio venv (numpy, Pillow, OpenCV live there), whatever python3 the user called
import os as _os, sys as _sys
_VPY = _os.path.join(_os.path.expanduser(_os.environ.get("REEL_STUDIO_CACHE", "~/.cache/reel-studio")), "venv",
                     "Scripts" if _os.name == "nt" else "bin", "python.exe" if _os.name == "nt" else "python")
if _os.path.exists(_VPY) and _os.path.realpath(_sys.prefix) != _os.path.realpath(_os.path.dirname(_os.path.dirname(_VPY))):
    _os.execv(_VPY, [_VPY] + _sys.argv)

import json, os, subprocess, sys
import numpy as np
D = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
CACHE = os.path.expanduser(os.environ.get("REEL_STUDIO_CACHE", "~/.cache/reel-studio"))
SR = 48000
TL = json.load(open(f"{D}/timeline.json"))
DUR = TL["meta"]["dur"]
REEL = json.load(open(f"{D}/reel.json"))
_bp = REEL["brand"] if os.path.isabs(REEL["brand"]) else os.path.join(D, REEL["brand"])
BRAND = json.load(open(_bp))
VOICE = f"{D}/build/voice.wav"
MUSIC = REEL.get("music") or (BRAND.get("sound") or {}).get("music")
if MUSIC and not os.path.isabs(MUSIC): MUSIC = os.path.join(D, MUSIC)
BED_DB = float((BRAND.get("sound") or {}).get("bed_db_under_voice", 18))
TARGET = {"ui": -14.0, "whoosh": -8.0, "hit": -6.0}   # QA: hero hits and whooshes must read over the bed
BOOST = {}   # QA: soft textures sat 20-25 dB under the mix at peak-matched gain
beats = {f"{sc['id']}.{k}": v for sc in TL["scenes"] for k, v in sc["beats"].items()}

def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)

N = int(DUR * SR)
voice = np.zeros((N, 2), np.float32); v = load(VOICE); voice[:min(N, len(v))] = v[:N]
# QA 2026-11-09: after the voice ends the sidechain saw pure digital zero and the compressor muted the bed
# (silent end card since v5). A -120 dB floor keeps the detector finite; it is inaudible.
voice += (np.random.default_rng(1).standard_normal(voice.shape) * 1e-6).astype(np.float32)
w = int(0.05 * SR); vm = np.abs(voice).max(1)
peaks = vm[: len(vm) // w * w].reshape(-1, w).max(1)
vp95 = 20 * np.log10(np.percentile(peaks[peaks > 10 ** (-40 / 20)], 95))
print(f"voice p95 peak {vp95:.1f} dBFS")

sfx = np.zeros((N, 2), np.float32)
print("SFX (time, file, role, target peak dBFS, why):")
for e in TL["sfx"]:
    t = beats[e["at"]] + e.get("offset", 0.0)
    src = e["src"] if os.path.isabs(e["src"]) else next((p for p in (os.path.join(D, e["src"]), os.path.join(CACHE, "sfx", e["src"])) if os.path.exists(p)), None)
    if not src: print(f"  ! SFX not found: {e['src']} (skipped)"); continue
    s = load(src)
    a, b = e.get("trim", [0, None]); s = s[int(a * SR): int(b * SR) if b else None].copy()
    f = min(len(s), int(0.012 * SR)); s[-f:] *= np.linspace(1, 0, f)[:, None]          # declick the trim tail
    pk = 20 * np.log10(np.abs(s).max() + 1e-9)
    g = 10 ** ((vp95 + TARGET[e["role"]] + BOOST.get(e["src"], 0.0) - pk) / 20)
    i = int(t * SR); seg = s[: max(0, min(len(s), N - i))] * g
    sfx[i:i + len(seg)] += seg
    print(f"  {t:6.2f}  {e['src']:26s} {e['role']:7s} {vp95 + TARGET[e['role']]:6.1f}  {e['why']}")

os.makedirs(f"{D}/sound", exist_ok=True)
voice.tofile(f"{D}/sound/voice.f32"); sfx.tofile(f"{D}/sound/sfx.f32")
raw = ["-f", "f32le", "-ar", str(SR), "-ac", "2"]
enc = ["-t", str(DUR), "-c:a", "aac", "-b:a", "256k", "-ar", str(SR), f"{D}/public/mix.m4a"]
if MUSIC:
    # The bed sits about BED_DB under the voice (house default 18 dB): voice is -14 LUFS, so the bed targets -14 - BED_DB + 7.2
    # (sidechain ducking takes ~7 dB off while he talks). Measure it from sound/bed_stem.wav, never from the full mix.
    bed_i = -14.0 - BED_DB + 7.2
    fc = (f"[1]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{DUR},asetpts=PTS-STARTPTS,highpass=f=90,"
          f"loudnorm=I={bed_i:.1f}:TP=-6:LRA=6,aresample=48000,afade=t=in:d=0.4,afade=t=out:st={DUR - 0.9}:d=0.9:curve=qsin[m];"
          "[0]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.05:ratio=2.5:attack=50:release=450:makeup=1[md];"
          "[v][md][2]amix=inputs=3:normalize=0:duration=longest,alimiter=limit=0.84:level=false[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *raw, "-i", f"{D}/sound/voice.f32", "-stream_loop", "-1", "-i", MUSIC, *raw,
                    "-i", f"{D}/sound/sfx.f32", "-filter_complex", fc, "-map", "[a]", *enc], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", *raw, "-i", f"{D}/sound/voice.f32", "-stream_loop", "-1", "-i", MUSIC, "-filter_complex",
                    fc.split("[v][md][2]")[0].rstrip(";").replace("[0]asplit=2[v][sc]", "[0]asplit=2[vx][sc]") + ";[vx]anullsink",
                    "-map", "[md]", "-t", str(DUR), f"{D}/sound/bed_stem.wav"], check=True)
else:
    fc = "[0][1]amix=inputs=2:normalize=0:duration=longest,alimiter=limit=0.84:level=false[a]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *raw, "-i", f"{D}/sound/voice.f32", *raw, "-i", f"{D}/sound/sfx.f32",
                    "-filter_complex", fc, "-map", "[a]", *enc], check=True)
    print("no music bed (set reel.json 'music' or brand sound.music to add one)")
subprocess.run(["ffmpeg", "-v", "error", "-y", *raw, "-i", f"{D}/sound/sfx.f32", f"{D}/sound/sfx_stem.wav"], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", *raw, "-i", f"{D}/sound/voice.f32", f"{D}/sound/voice_stem.wav"], check=True)
for f in ("voice.f32", "sfx.f32"): os.remove(f"{D}/sound/{f}")
print("wrote public/mix.m4a + sound/*_stem.wav")
