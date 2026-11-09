# Credits

Reel Studio stands on open-source work. Thank you to the authors below.

## Vendored (copied into this repo, licence kept alongside)
| Path | From | Licence |
|---|---|---|
| `engine/vendor/video_director/check_timeline.py`, `qa_video.py` | [win4r/video-director](https://github.com/win4r/video-director) | MIT, © 2026 win4r (`engine/vendor/video_director/LICENSE`) |
| `engine/vendor/ghost_editor/face_track.py` (model path changed to the reel-studio cache) | [kurbaitaev/ghost-editor](https://github.com/kurbaitaev/ghost-editor) | MIT, © 2026 kurbaitaev (`engine/vendor/ghost_editor/LICENSE`) |

## Installed at setup (not bundled)
| Package | Source | Licence |
|---|---|---|
| HyperFrames (renderer) | npm `hyperframes` | Apache-2.0 |
| GSAP 3 (animation) | npm `gsap` | GreenSock "Standard No-Charge" licence |
| faster-whisper (word timings) | PyPI | MIT |
| OpenCV + YuNet face detector | PyPI `opencv-python-headless`, opencv_zoo | Apache-2.0 / MIT |
| numpy, Pillow | PyPI | BSD / HPND |
| earshot (optional, SFX by listening) | [Leonxlnx/earshot](https://github.com/Leonxlnx/earshot), pinned commit | MIT |
| MediaPipe (optional, cut-outs off Mac) | PyPI | Apache-2.0 |
| RapidOCR (optional, word finder off Mac) | PyPI `rapidocr-onnxruntime` | Apache-2.0 |
| Brand fonts | Google Fonts (fetched per brand, with the user's OK) | mostly OFL; check each family |

## Method and inspiration
- Planning with a single `timeline.json`, the critic rubric and the "user is never the first viewer" rule follow video-director.
- Motion principles (never teleport, moves ≥ 100 ms, calm idle loops) follow rossark-motion-skill (MIT).
- Measuring a reference's motion frame by frame follows reanimate (MIT).
- The effects library was studied from a public "20 video effects" reel and rebuilt from scratch; no frames or assets from it are included.

## Not included on purpose
- No music or sound-effect files: libraries without clear licences aren't redistributed. Use earshot's synthesised bank or files you're licensed to use.
- No footage, transcripts or brand of any real creator. `brand/example.*` describes a fictional creator.
