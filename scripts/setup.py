#!/usr/bin/env python3
"""Reel Studio setup: install ONE named step. The setup skill runs doctor, then asks the user before each step.

    python3 scripts/setup.py <step>
    steps: node-deps · browser · python-deps · matte · ocr · earshot · models · xcode-clt

System tools (FFmpeg, Node, Python) are installed with the OS package manager command doctor prints; the skill shows it
and asks first, because those can need an administrator password.
"""
import os, platform, subprocess, sys, urllib.request

OS = {"Darwin": "mac", "Windows": "windows", "Linux": "linux"}.get(platform.system(), "linux")
CACHE = os.path.expanduser(os.environ.get("REEL_STUDIO_CACHE", "~/.cache/reel-studio"))
VENV = os.path.join(CACHE, "venv")
VPY = os.path.join(VENV, "Scripts" if OS == "windows" else "bin", "python.exe" if OS == "windows" else "python")
NODE_DIR = os.path.join(CACHE, "node")
EARSHOT = "git+https://github.com/Leonxlnx/earshot@4ac3d2a"   # pinned to the reviewed commit
YUNET = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

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

def sh(cmd, **kw):
    print("$", " ".join(cmd) if isinstance(cmd, list) else cmd); sys.stdout.flush()
    subprocess.run(cmd, check=True, **kw)

def venv():
    if not os.path.exists(VPY):
        py = best_python() or sys.exit("No Python 3.10+ found: install it first (doctor shows the command).")
        sh([py, "-m", "venv", VENV])
        sh([VPY, "-m", "pip", "install", "--upgrade", "pip"])

def step(name):
    os.makedirs(CACHE, exist_ok=True)
    if name == "node-deps":
        os.makedirs(NODE_DIR, exist_ok=True)
        if not os.path.exists(os.path.join(NODE_DIR, "package.json")):
            open(os.path.join(NODE_DIR, "package.json"), "w").write('{"name":"reel-studio-cache","private":true}\n')
        sh(["npm", "install", "--no-fund", "--no-audit", "hyperframes@latest", "gsap@3"], cwd=NODE_DIR, shell=(OS == "windows"))
    elif name == "browser":
        hf = os.path.join(NODE_DIR, "node_modules", ".bin", "hyperframes.cmd" if OS == "windows" else "hyperframes")
        sh([hf, "browser", "ensure"])
    elif name == "python-deps":
        venv(); sh([VPY, "-m", "pip", "install", "numpy", "pillow", "opencv-python-headless", "faster-whisper"])
    elif name == "matte":
        if OS == "mac": print("On a Mac the cut-out uses Apple Vision (needs Xcode Command Line Tools: step xcode-clt)."); return
        venv(); sh([VPY, "-m", "pip", "install", "mediapipe"])
    elif name == "ocr":
        if OS == "mac": print("On a Mac the word finder uses Apple Vision (needs Xcode Command Line Tools: step xcode-clt)."); return
        venv(); sh([VPY, "-m", "pip", "install", "rapidocr-onnxruntime"])
    elif name == "earshot":
        venv(); sh([VPY, "-m", "pip", "install", EARSHOT])
    elif name == "models":
        d = os.path.join(CACHE, "models"); os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, "face_detection_yunet_2023mar.onnx")
        if not os.path.exists(dst):
            print(f"downloading {YUNET}"); urllib.request.urlretrieve(YUNET, dst)
        print("faster-whisper downloads its speech model (~150 MB) on first use.")
    elif name == "xcode-clt":
        sh(["xcode-select", "--install"])
    else:
        raise SystemExit(f"unknown step '{name}'")
    print(f"step {name}: done")

if __name__ == "__main__":
    if len(sys.argv) < 2: raise SystemExit(__doc__)
    step(sys.argv[1])
