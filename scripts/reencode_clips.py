"""
Re-encode the 8 processed HyperFrames clips with proper GOP structure.

Fixes the "sparse keyframes" warning HyperFrames emits at render time by
forcing a keyframe every 1 second (30 frames at 30fps) and adding the
`+faststart` flag so the renderer can stream the file.

This is a one-time helper, run locally before the first commit. It is
not invoked by the CI workflow; the resulting files are committed.
"""

import os
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path("hf/assets/clips")

# ffmpeg flags: H.264 yuv420p, fast preset, CRF 20 (visually lossless for stock
# footage), GOP=30 (one keyframe per second at 30fps), audio passthrough,
# faststart moves the moov atom to the front of the file.
FFMPEG_CMD = [
    "ffmpeg", "-y",
    "-i", "{input}",
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "20",
    "-g", "30",
    "-keyint_min", "30",
    "-r", "30",
    "-pix_fmt", "yuv420p",
    "-c:a", "copy",
    "-movflags", "+faststart",
    "{output}",
]


def reencode(src: Path) -> bool:
    tmp = src.with_suffix(".reencode.mp4")
    cmd = [c.format(input=str(src), output=str(tmp)) for c in FFMPEG_CMD]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(f"  FAIL ffmpeg for {src.name}:")
        print(result.stderr.decode(errors="replace")[-1000:])
        return False
    os.replace(tmp, src)
    print(f"  OK {src.name}")
    return True


def main() -> int:
    targets = sorted(SRC_DIR.glob("*_processed.mp4"))
    if not targets:
        print(f"  ! no *_processed.mp4 files in {SRC_DIR}")
        return 1

    print(f"  Re-encoding {len(targets)} clip(s) in {SRC_DIR}\n")
    failed = 0
    for src in targets:
        if not reencode(src):
            failed += 1
    if failed:
        print(f"\n  FAIL: {failed} clip(s) failed to re-encode")
        return 1
    print(f"\n  OK: all {len(targets)} clip(s) re-encoded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
