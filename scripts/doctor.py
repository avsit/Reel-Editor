#!/usr/bin/env python3
"""Reel Studio doctor: check every dependency on macOS, Windows or Linux and say exactly what's missing.

    python3 scripts/doctor.py            # human report
    python3 scripts/doctor.py --json     # for the setup skill

Nothing is installed here. scripts/setup.py installs one step at a time, and the setup skill asks the user before each.
"""
import json, os, platform, re, shutil, subprocess, sys

OS = {"Darwin": "mac", "Windows": "windows", "Linux": "linux"}.get(platform.system(), "linux")
CACHE = os.path.expanduser(os.environ.get("REEL_STUDIO_CACHE", "~/.cache/reel-studio"))
VENV_PY = os.path.join(CACHE, "venv", "Scripts" if OS == "windows" else "bin", "python.exe" if OS == "windows" else "python")

def best_python():
    """The newest Python 3.10+ on PATH (python3.13 … python3.10, python3, py -3 on Windows)."""
    import shutil, subprocess
    for name in ["python3.13", "python3.12", "python3.11", "python3.10", "python3", "python"]:
        exe = shutil.which(name)
        if not exe: continue
        try:
            out = subprocess.run([exe, "-c", "import sys;print(sys.version_info[:2] >= (3, 10))"], capture_output=True, text=True, timeout=20).stdout
            if "True" in out: return exe
        except Exception: pass
    return None

def run(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)

def ver(s, pat=r"(\d+)\.(\d+)"):
    m = re.search(pat, s); return tuple(int(x) for x in m.groups()) if m else (0, 0)

HOW = {  # install hints per OS (setup.py runs these when the user says yes)
    "ffmpeg":  {"mac": "brew install ffmpeg", "windows": "winget install --id Gyan.FFmpeg -e", "linux": "sudo apt-get install -y ffmpeg"},
    "node":    {"mac": "brew install node", "windows": "winget install --id OpenJS.NodeJS.LTS -e", "linux": "sudo apt-get install -y nodejs npm"},
    "python":  {"mac": "brew install python@3.12", "windows": "winget install --id Python.Python.3.12 -e", "linux": "sudo apt-get install -y python3 python3-venv"},
}

def checks():
    out = []
    def add(key, ok, detail, required=True, step=None):
        out.append({"key": key, "ok": ok, "detail": detail, "required": required, "step": step,
                    "how": HOW.get(key, {}).get(OS) if not ok else None})
    # Python
    bp = best_python()
    add("python", bool(bp), f"Python 3.10+ at {bp}" if bp else "no Python 3.10+ on PATH")
    # FFmpeg with the codecs/filters the engine uses
    ff = shutil.which("ffmpeg")
    if ff:
        _, enc = run([ff, "-hide_banner", "-encoders"]); _, flt = run([ff, "-hide_banner", "-filters"])
        need = [n for n, s in (("libvpx-vp9", enc), ("libx264", enc), ("scdet", flt), ("ebur128", flt), ("loudnorm", flt)) if n not in s]
        add("ffmpeg", not need, "FFmpeg found" + (f", missing: {', '.join(need)}" if need else " (vp9, x264, scdet, loudnorm ok)"))
    else:
        add("ffmpeg", False, "FFmpeg not found")
    # Node + npm
    node = shutil.which("node")
    nv = ver(run([node, "--version"])[1]) if node else (0, 0)
    add("node", nv >= (18, 0), f"Node {nv[0]}.{nv[1]}" if node else "Node not found (need 18+)")
    # Engine node deps (HyperFrames renderer + GSAP), installed into the cache
    nm = os.path.join(CACHE, "node", "node_modules")
    add("node-deps", os.path.isdir(os.path.join(nm, "hyperframes")) and os.path.isfile(os.path.join(nm, "gsap", "dist", "gsap.min.js")),
        "HyperFrames + GSAP in the reel-studio cache", step="node-deps")
    # Chrome for rendering (HyperFrames manages its own)
    hf = os.path.join(nm, ".bin", "hyperframes.cmd" if OS == "windows" else "hyperframes")
    if os.path.exists(hf):
        rc, o = run([hf, "browser", "path"], timeout=60)   # only Chrome matters; hyperframes doctor also fails on optional extras (TTS, Docker)
        path = o.strip().splitlines()[-1] if o.strip() else ""
        ok = rc == 0 and os.path.exists(path)
        add("browser", ok, f"render Chrome at {path}" if ok else "render Chrome not downloaded yet", step="browser")
    else:
        add("browser", False, "HyperFrames not installed yet (comes with node-deps)", step="browser")
    # Python environment with the engine's packages
    if os.path.exists(VENV_PY):
        rc, o = run([VENV_PY, "-c", "import numpy, PIL, cv2, faster_whisper; print('ok')"], timeout=120)
        add("python-deps", rc == 0, "numpy, Pillow, OpenCV, faster-whisper" + ("" if rc == 0 else f": {o.strip().splitlines()[-1][:80]}"), step="python-deps")
        if OS != "mac":
            rc, _ = run([VENV_PY, "-c", "import mediapipe"]); add("matte", rc == 0, "person cut-out (MediaPipe)", required=False, step="matte")
            rc, _ = run([VENV_PY, "-c", "import rapidocr_onnxruntime"]); add("ocr", rc == 0, "word finder for underlines (RapidOCR)", required=False, step="ocr")
        rc, _ = run([VENV_PY, "-c", "import earshot"]); add("earshot", rc == 0, "earshot (listen to and pick sound effects)", required=False, step="earshot")
    else:
        add("python-deps", False, "reel-studio Python environment not created yet", step="python-deps")
    if OS == "mac":
        sw = shutil.which("swiftc") or run(["xcrun", "--find", "swiftc"])[0] == 0
        add("matte", bool(sw), "Apple Vision cut-out + word finder (needs Xcode Command Line Tools)", required=False,
            step=None if sw else "xcode-clt")
    # Models
    add("models", os.path.exists(os.path.join(CACHE, "models", "face_detection_yunet_2023mar.onnx")),
        "face detector model (OpenCV YuNet, 0.2 MB)", step="models")
    return out

if __name__ == "__main__":
    res = checks()
    if "--json" in sys.argv:
        print(json.dumps({"os": OS, "cache": CACHE, "checks": res}, indent=1)); sys.exit(0)
    print(f"Reel Studio doctor · {OS} · cache {CACHE}\n")
    for c in res:
        mark = "✓" if c["ok"] else ("✗" if c["required"] else "·")
        print(f"  {mark} {c['key']:12s} {c['detail']}")
        if not c["ok"]:
            if c["how"]: print(f"      install: {c['how']}")
            if c["step"]: print(f"      or: python3 scripts/setup.py {c['step']}")
    req = [c for c in res if c["required"] and not c["ok"]]
    print("\nReady." if not req else f"\nNot ready: {len(req)} required item(s) missing.")
    sys.exit(0 if not req else 1)
