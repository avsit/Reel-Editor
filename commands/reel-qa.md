---
description: Run Gate A and an independent Gate B review on a rendered reel
argument-hint: "<project folder> [render .mp4]"
---
Run Gate A (`engine/qa_reel.py`) on $ARGUMENTS, then spawn the reel-qa agent with only the project folder and the render. Report the scores, the defects and the verdict. Don't change the build.
