"""
Voiceover Generator - Video 01
"The 2026 World Cup Is About to Break Everything"
--------------------------------------------------
ElevenLabs TTS pipeline that produces per-scene MP3s and a single
full_voiceover.mp3 that the HyperFrames composition embeds.

Requirements:
  pip install requests

Configuration via environment variables:
  ELEVENLABS_API_KEY   (required)   ElevenLabs API key
  ELEVENLABS_VOICE_ID  (required)   ElevenLabs voice ID

Usage:
  1. export ELEVENLABS_API_KEY=... ELEVENLABS_VOICE_ID=...
  2. python generate_voiceover.py
  3. Outputs: hf/assets/audio/{NN_id}.mp3 and hf/assets/audio/full_voiceover.mp3

The HyperFrames render is the final mux - this script does NOT
merge audio onto a video file.
"""

import os
import sys
import time
import requests
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIG — secrets read from environment
# ─────────────────────────────────────────────
try:
    ELEVENLABS_API_KEY = os.environ["ELEVENLABS_API_KEY"]
except KeyError:
    print("ERROR: ELEVENLABS_API_KEY is not set.")
    print("  export ELEVENLABS_API_KEY=your-key-from-elevenlabs.io")
    sys.exit(1)

try:
    VOICE_ID = os.environ["ELEVENLABS_VOICE_ID"]
except KeyError:
    print("ERROR: ELEVENLABS_VOICE_ID is not set.")
    print("  Pick a voice at elevenlabs.io -> Voices -> My Voices and copy the ID.")
    sys.exit(1)

# Voice settings — tweak to taste
VOICE_SETTINGS = {
    "stability": 0.45,          # lower = more expressive/dynamic
    "similarity_boost": 0.80,   # how closely to match the voice
    "style": 0.35,              # style exaggeration (0-1)
    "use_speaker_boost": True
}

MODEL_ID = "eleven_multilingual_v2"  # best quality model on free tier

AUDIO_DIR = Path("hf/assets/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# VOICEOVER SCRIPT — scene by scene
# ─────────────────────────────────────────────
SCENES = [
    {
        "id": "01_hook",
        "duration_hint": 8,
        "text": (
            "Every World Cup gets called historic. "
            "This one actually is. "
            "And I can prove it in four minutes."
        ),
    },
    {
        "id": "02_scale",
        "duration_hint": 37,
        "text": (
            "48 teams. 104 games. 16 cities spread across three countries. "
            "The 2026 World Cup isn't just bigger than every tournament before it - "
            "it's a completely different animal. "
            "More nations, more drama, more paths to the final. "
            "The old rules about who can win this thing? "
            "They don't apply anymore."
        ),
    },
    {
        "id": "03_last_dance",
        "duration_hint": 60,
        "text": (
            "Let's talk about Messi and Ronaldo. "
            "Two men who defined an entire era of football - "
            "arguably the two greatest players the sport has ever seen - "
            "sharing a World Cup stage for almost certainly the very last time. "
            "Messi is coming in carrying a hamstring issue. "
            "Ronaldo at 41. "
            "Neither of them cares. "
            "They have spent their entire careers chasing this tournament. "
            "One has it. The other doesn't. "
            "And this is the last chapter."
        ),
    },
    {
        "id": "04_mbappe",
        "duration_hint": 45,
        "text": (
            "While the legends prepare for their final act, "
            "Kylian Mbappe is four goals away from the all-time World Cup scoring record. "
            "He is 27 years old. "
            "If he stays fit and France go deep - which they're fully capable of - "
            "we could watch that record fall in real time. "
            "That's the torch being passed, live, in front of a billion people."
        ),
    },
    {
        "id": "05_hosts",
        "duration_hint": 45,
        "text": (
            "USA. Canada. Mexico. "
            "Three host nations, three very different expectations. "
            "Mexico are experienced - this is nothing new for them. "
            "Canada are energised - their first World Cup since 1986. "
            "And the United States? "
            "Mauricio Pochettino has publicly said his team can win the whole thing. "
            "On home soil, in front of a country that is only just starting to take football seriously - "
            "that is either the boldest call in USMNT history, or the most delusional."
        ),
    },
    {
        "id": "06_new_world",
        "duration_hint": 35,
        "text": (
            "And then there are the debutants. "
            "Cape Verde. Curacao. Jordan. Uzbekistan. "
            "Nations stepping onto the world's biggest stage for the first time ever. "
            "The 48-team format created those spots - "
            "and someone is going to use one of them to cause the upset of the tournament."
        ),
    },
    {
        "id": "07_verdict",
        "duration_hint": 30,
        "text": (
            "Whatever happens between June 11th and July 19th - "
            "whoever lifts that trophy - "
            "we are watching football history unfold in real time. "
            "This is not a normal World Cup. "
            "Don't treat it like one."
        ),
    },
    {
        "id": "08_cta",
        "duration_hint": 15,
        "text": (
            "Subscribe. "
            "We are covering every subplot, every upset, and every controversy "
            "until the final whistle. "
            "You don't want to miss what's coming."
        ),
    },
]


# ─────────────────────────────────────────────
# ELEVENLABS API CALL
# ─────────────────────────────────────────────
def generate_audio(text: str, output_path: Path) -> bool:
    """Send text to ElevenLabs TTS API and save the mp3."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    payload = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": VOICE_SETTINGS,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)

        if resp.status_code == 401:
            print("  Invalid API key - check ELEVENLABS_API_KEY")
            return False
        if resp.status_code == 422:
            print("  Invalid voice ID - check ELEVENLABS_VOICE_ID")
            return False
        if resp.status_code != 200:
            print(f"  API error {resp.status_code}: {resp.text[:300]}")
            return False

        with open(output_path, "wb") as f:
            f.write(resp.content)
        return True

    except requests.exceptions.Timeout:
        print("  Request timed out - ElevenLabs may be slow, try again")
        return False
    except Exception as e:
        print(f"  Unexpected error: {e}")
        return False


# ─────────────────────────────────────────────
# COMBINE ALL SCENES INTO ONE FILE (via concat)
# ─────────────────────────────────────────────
def combine_audio_files(scene_files: list[Path]) -> Path | None:
    """Concatenate all scene mp3s into one full voiceover file using ffmpeg."""
    import subprocess

    concat_list = AUDIO_DIR / "audio_concat.txt"
    output = AUDIO_DIR / "full_voiceover.mp3"

    with open(concat_list, "w") as f:
        for p in scene_files:
            f.write(f"file '{p.resolve()}'\n")

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c:a", "libmp3lame",
            "-q:a", "2",
            str(output)
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if result.returncode != 0:
        print("  FFmpeg concat failed:")
        print(result.stderr.decode(errors="replace")[-1000:])
        return None

    return output


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  VOICEOVER GENERATOR - VIDEO 01")
    print("  Powered by ElevenLabs")
    print("=" * 60)

    total_chars = sum(len(s["text"]) for s in SCENES)
    print(f"\n  Scenes: {len(SCENES)}")
    print(f"  Total characters: {total_chars} (free tier limit: 10,000/month)")
    print(f"  Audio output: {AUDIO_DIR}\n")

    # Generate each scene
    scene_files = []
    for i, scene in enumerate(SCENES, 1):
        sid = scene["id"]
        dest = AUDIO_DIR / f"{sid}.mp3"

        if dest.exists():
            print(f"  [skip] [{i}/{len(SCENES)}] {sid} already exists")
            scene_files.append(dest)
            continue

        print(f"  [{i}/{len(SCENES)}] Generating {sid}...")
        ok = generate_audio(scene["text"], dest)

        if ok:
            size_kb = dest.stat().st_size // 1024
            print(f"  OK {sid} -> {size_kb}KB")
            scene_files.append(dest)
        else:
            print(f"  ! Skipping {sid} due to error")

        time.sleep(0.5)  # avoid rate limiting

    if not scene_files:
        print("\nNo audio generated. Check your API key and voice ID.")
        sys.exit(1)

    # Combine into one file
    print(f"\nCombining {len(scene_files)} audio scenes...")
    full_audio = combine_audio_files(scene_files)

    if not full_audio:
        print("Could not combine audio files.")
        sys.exit(1)

    size_mb = full_audio.stat().st_size / 1_000_000
    print(f"  Full voiceover: {full_audio} ({size_mb:.1f} MB)")
    print()


if __name__ == "__main__":
    main()
