"""
Video 01 Production Pipeline
"The 2026 World Cup Is About to Break Everything"
------------------------------------------------------
Pexels stock footage + FFmpeg composition.

Requirements:
  pip install requests tqdm pillow
  ffmpeg must be in PATH

Configuration via environment variables:
  PEXELS_API_KEY   (required)   Pexels API key

Usage:
  1. export PEXELS_API_KEY=...
  2. python produce_video_01.py
  3. Output: video_01_assets/world_cup_video_01.mp4 (legacy concat build;
     the real final video is produced by the HyperFrames renderer, not
     this script).
"""

import os
import sys
import time
import subprocess
import requests
from pathlib import Path
from tqdm import tqdm

# ─────────────────────────────────────────────
# CONFIG — secrets read from environment
# ─────────────────────────────────────────────
try:
    PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
except KeyError:
    print("ERROR: PEXELS_API_KEY is not set.")
    print("  export PEXELS_API_KEY=your-key-from-pexels.com/api")
    sys.exit(1)

WORK_DIR = Path("video_01_assets")
CLIPS_DIR = WORK_DIR / "clips"
OUTPUT_FILE = WORK_DIR / "world_cup_video_01.mp4"

WORK_DIR.mkdir(exist_ok=True)
CLIPS_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# SCENES
# ─────────────────────────────────────────────
SCENES = [
    {
        "id": "01_hook",
        "query": "soccer stadium crowd cheering",
        "duration": 8,
        "text": "Every World Cup gets called historic.\nThis one actually is.",
        "text_size": 48,
    },
    {
        "id": "02_scale",
        "query": "soccer football world cup stadium",
        "duration": 37,
        "text": "48 TEAMS. 104 GAMES. 3 COUNTRIES.",
        "text_size": 52,
    },
    {
        "id": "03_last_dance",
        "query": "soccer football match crowd",
        "duration": 60,
        "text": "The Last Dance.",
        "text_size": 64,
    },
    {
        "id": "04_mbappe",
        "query": "football player dribbling ball",
        "duration": 45,
        "text": "4 goals from the all-time record.",
        "text_size": 44,
    },
    {
        "id": "05_hosts",
        "query": "sports stadium crowd cheering",
        "duration": 45,
        "text": "USA. CANADA. MEXICO.\nHome advantage.",
        "text_size": 48,
    },
    {
        "id": "06_new_world",
        "query": "world map globe football soccer",
        "duration": 35,
        "text": "New nations. New stories.",
        "text_size": 52,
    },
    {
        "id": "07_verdict",
        "query": "soccer trophy championship golden",
        "duration": 30,
        "text": "Football history.\nIn real time.",
        "text_size": 56,
    },
    {
        "id": "08_cta",
        "query": "soccer football team celebration",
        "duration": 15,
        "text": "SUBSCRIBE\nEvery subplot. Every upset. Every moment.",
        "text_size": 40,
    },
]

TOTAL_DURATION = sum(s["duration"] for s in SCENES)


# ─────────────────────────────────────────────
# PILLOW TEXT RENDERING
# ─────────────────────────────────────────────
def ensure_pillow():
    try:
        from PIL import Image
    except ImportError:
        print("  Installing Pillow...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pillow", "-q"])


def make_text_overlay_png(text, font_size, dest, width=1280, height=720, is_fallback=False):
    from PIL import Image, ImageDraw, ImageFont

    if is_fallback:
        img = Image.new("RGB", (width, height), color=(10, 10, 10))
    else:
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    draw = ImageDraw.Draw(img)

    font = None
    # Linux (CI) paths first, then Windows (local dev).
    for fp in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
        r"C:\Windows\Fonts\verdanab.ttf",
    ]:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue

    if font is None:
        font = ImageFont.load_default()

    lines = text.split("\n")
    line_height = font_size + 12
    total_h = line_height * len(lines)

    if is_fallback:
        y_start = (height - total_h) // 2
        color = (255, 255, 255)
    else:
        y_start = int(height * 0.78) - total_h // 2
        color = (255, 215, 0)  # gold

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) // 2
        y = y_start + i * line_height

        if not is_fallback:
            pad = 14
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            box_draw = ImageDraw.Draw(overlay)
            box_draw.rectangle(
                [x - pad, y - pad, x + text_w + pad, y + font_size + pad],
                fill=(0, 0, 0, 140)
            )
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)

        draw.text((x, y), line, font=font, fill=color)

    img.save(str(dest))
    return True


# ─────────────────────────────────────────────
# PEXELS
# ─────────────────────────────────────────────
def search_pexels_video(query, min_duration=10):
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 10, "orientation": "landscape"}
    try:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers, params=params, timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  Pexels search failed: {e}")
        return None

    for video in data.get("videos", []):
        if video.get("duration", 0) < min_duration:
            continue
        files = video.get("video_files", [])
        hd = [f for f in files if f.get("width", 0) >= 1280]
        if not hd:
            hd = files
        hd.sort(key=lambda f: f.get("width", 0), reverse=True)
        for f in hd:
            if f.get("width", 9999) <= 1920:
                return f.get("link")
    return None


def download_file(url, dest):
    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        with open(dest, "wb") as f, tqdm(
            total=total, unit="B", unit_scale=True,
            desc=f"  {dest.name}", leave=False
        ) as bar:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                bar.update(len(chunk))
        return True
    except Exception as e:
        print(f"  Download failed: {e}")
        return False


def download_clips():
    print("\nSTEP 1: Downloading clips from Pexels\n")
    paths = {}
    for scene in SCENES:
        sid = scene["id"]
        dest = CLIPS_DIR / f"{sid}_raw.mp4"
        if dest.exists():
            print(f"  [skip] {sid} already downloaded")
            paths[sid] = dest
            continue
        print(f"  Searching: {scene['query']}")
        url = search_pexels_video(scene["query"], min_duration=scene["duration"])
        if not url:
            print(f"  ! No clip found for {sid} - will use colour card")
            paths[sid] = None
            continue
        ok = download_file(url, dest)
        paths[sid] = dest if ok else None
        time.sleep(0.5)
    return paths


# ─────────────────────────────────────────────
# FFMPEG
# ─────────────────────────────────────────────
def run_ffmpeg(args, desc=""):
    cmd = ["ffmpeg", "-y"] + args
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(f"\n  FFmpeg error ({desc}):")
        print(result.stderr.decode(errors="replace")[-1500:])
        return False
    return True


def make_fallback_clip(scene, dest):
    png = CLIPS_DIR / f"{scene['id']}_card.png"
    make_text_overlay_png(scene["text"], scene["text_size"], png, is_fallback=True)
    return run_ffmpeg([
        "-loop", "1",
        "-i", str(png),
        "-c:v", "libx264",
        "-t", str(scene["duration"]),
        "-pix_fmt", "yuv420p",
        "-r", "30",
        str(dest)
    ], desc=f"fallback {scene['id']}")


def process_clip(scene, raw_path, dest):
    if raw_path is None or not raw_path.exists():
        return make_fallback_clip(scene, dest)

    duration = scene["duration"]

    # Step 1: trim + scale
    scaled = CLIPS_DIR / f"{scene['id']}_scaled.mp4"
    ok = run_ffmpeg([
        "-i", str(raw_path),
        "-ss", "0", "-t", str(duration),
        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
        "-af", "volume=0.0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-r", "30", "-c:a", "aac", "-ar", "44100",
        str(scaled)
    ], desc=f"scale {scene['id']}")
    if not ok:
        return False

    # Step 2: render text as PNG
    png = CLIPS_DIR / f"{scene['id']}_overlay.png"
    make_text_overlay_png(scene["text"], scene["text_size"], png, is_fallback=False)

    # Step 3: overlay PNG onto video
    return run_ffmpeg([
        "-i", str(scaled),
        "-i", str(png),
        "-filter_complex", "[0:v][1:v]overlay=0:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy",
        str(dest)
    ], desc=f"text overlay {scene['id']}")


def process_all_clips(raw_paths):
    print("\nSTEP 2: Processing clips\n")
    processed = []
    for scene in SCENES:
        sid = scene["id"]
        dest = CLIPS_DIR / f"{sid}_processed.mp4"
        if dest.exists():
            print(f"  [skip] {sid} already processed")
            processed.append(dest)
            continue
        print(f"  Processing {sid}...")
        ok = process_clip(scene, raw_paths.get(sid), dest)
        if ok:
            print(f"  OK {sid}")
            processed.append(dest)
        else:
            print(f"  FAIL {sid} - skipping")
    return processed


# ─────────────────────────────────────────────
# STITCH
# ─────────────────────────────────────────────
def stitch_clips(clip_paths):
    print("\nSTEP 3: Stitching final video\n")
    concat_list = WORK_DIR / "concat_list.txt"
    with open(concat_list, "w") as f:
        for p in clip_paths:
            f.write(f"file '{str(p.resolve()).replace(chr(92), '/')}'\n")

    print(f"  Joining {len(clip_paths)} clips -> {OUTPUT_FILE}")
    ok = run_ffmpeg([
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-movflags", "+faststart",
        str(OUTPUT_FILE)
    ], desc="final stitch")

    if ok:
        size_mb = OUTPUT_FILE.stat().st_size / 1_000_000
        print(f"\n  Final video: {OUTPUT_FILE} ({size_mb:.1f} MB)")
    return ok


# ─────────────────────────────────────────────
# METADATA
# ─────────────────────────────────────────────
def print_metadata():
    if not sys.stdout.isatty():
        return
    print("\nSTEP 4: YouTube Metadata\n" + "-" * 60)
    print("TITLE: Why the 2026 World Cup Is Different From Every Other One\n")
    print("DESCRIPTION:")
    print("""The 2026 FIFA World Cup kicks off June 11 - the biggest, most consequential tournament ever staged. 48 teams, 104 games, three host nations.

Messi and Ronaldo's last dance. Mbappe four goals from the all-time record. The USA hosting on home soil for the first time. First-time nations stepping onto the world stage.

Subscribe - we're covering every subplot, every upset, every controversy through the final on July 19th.

0:00 Intro
0:08 The Scale of 2026
0:45 Messi & Ronaldo's Last Dance
1:45 The Mbappe Record
2:30 USA, Canada & Mexico as Hosts
3:15 First-Time Nations
3:50 The Verdict
4:20 Subscribe""")
    print("\nTAGS: 2026 World Cup, FIFA World Cup 2026, World Cup preview, Messi last World Cup, Ronaldo 2026, Mbappe record, USMNT World Cup, football 2026, soccer analysis, World Cup history")
    print("\nCATEGORY: Sports | LANGUAGE: English | MADE FOR KIDS: No")
    print("-" * 60)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    ensure_pillow()

    print("=" * 60)
    print("  VIDEO 01 PRODUCTION PIPELINE")
    print(f"  Total runtime: ~{TOTAL_DURATION // 60}m {TOTAL_DURATION % 60}s")
    print("=" * 60)

    raw_paths = download_clips()
    processed = process_all_clips(raw_paths)

    if not processed:
        print("\nNo clips processed.")
        sys.exit(1)

    ok = stitch_clips(processed)
    if not ok:
        sys.exit(1)

    print_metadata()
    print("\nDONE. world_cup_video_01.mp4 is ready to upload.\n")


if __name__ == "__main__":
    main()
