# Plan: Generalize `gh-ffyt` into a JSON-spec-driven video factory

## Context

The current `gh-ffyt` repo at `C:\Users\PC\Desktop\gh-ffyt` is a single-video pipeline hard-coded to the 2026 World Cup explainer. The user wants it refactored into a **generalized factory**: write a JSON spec, get an MP4 + YouTube publish. The new pipeline must support any number of videos from a single codebase, each described by a spec file.

**Locked decisions** (from prior Q&A):
- **Renderer:** HyperFrames end-to-end. FFmpeg only for the final per-scene concat with baked-in voiceover.
- **Footage source per scene:** Pixabay first, fall back to Pexels.
- **Spec format:** plain JSON, ordered `scenes` array.
- **Workflow:** multi-spec, picked via `workflow_dispatch` dropdown.
- **HTML:** one file per scene, written by a Python composer. No cross-scene GSAP transitions in the simple model.
- **Scene kinds in v1:** `hook`, `scale`, `portrait` (renamed from `last_dance`), `record`, `grid`, `quote`, `list`, `split`.
- **Failure policy:** loud on unknown kinds or missing fields.
- **Repo name:** keep `gh-ffyt`. Full refactor in one pass.

## 1. Spec schema

Top-level fields:

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `id` | string | yes | — | Used for `build/<id>/` and YouTube default title slug. |
| `youtube` | object | yes | — | See YouTube block below. |
| `tts` | object | no | `{}` | ElevenLabs overrides. Inherits from env defaults. |
| `palette` | object | no | World Cup palette | Optional re-skin: `bg`, `fg`, `accent`. |
| `scenes` | array | yes | — | Ordered list of scene objects. |

**YouTube block:**
- `title` (string, required)
- `description` (string, required)
- `tags` (string[], required)
- `privacy` (`public` \| `unlisted` \| `private`, default `private`)
- `category_id` (string, default `"17"` = Sports)
- `publish_at` (ISO 8601 string, optional — schedule instead of publish-now)
- `thumbnail_path` (path string, optional)
- `captions_path` (path string, optional)

**Per-scene fields (all kinds):**
- `id` (string, required, unique within the spec)
- `kind` (string, required, one of the 8 kinds)
- `duration_s` (number, required)
- `script` (string, required — the voiceover text for this scene)
- `source` (string, default `"pixabay"` — what to try first; allowed: `pixabay`, `pexels`)
- `query` (string, optional — search query for the source; if `source` is the literal string, that string is used as the query)
- `min_width` (number, default `1280`)
- `top_label` / `bottom_label` (strings, optional — fill the top/bottom metadata bars)
- `pill` (string, optional — a small pill in the bottom-right of the bottom-bar)

**Per-scene-kind fields:**

| Kind | Required | Optional |
|---|---|---|
| `hook` | `eyebrow`, `headline` (with `accent` substring for the gold word), `subhead` | `pill` |
| `scale` | `headline`, `stats` (array of `{num, label}`) | `eyebrow`, `sub` |
| `portrait` | `eyebrow`, `headline`, `names` (array of `{name, year}`) | `sub` |
| `record` | `counter_label`, `counter_num`, `counter_suffix`, `name` | `eyebrow`, `quote` |
| `grid` | `headline`, `cards` (array of `{flag, name, stats, quote}`) | `eyebrow` |
| `quote` | `eyebrow`, `quote`, `attribution` | `sub` |
| `list` | `eyebrow`, `headline`, `items` (array of strings) | `sub` |
| `split` | `eyebrow`, `headline`, `body`, `image_query` (a separate Pixabay/Pexels query for a still) | — |

**Example spec (the World Cup video as JSON):**
```json
{
  "id": "world_cup_2026",
  "youtube": {
    "title": "Why the 2026 World Cup Is Different From Every Other One",
    "description": "...",
    "tags": ["2026 World Cup", "FIFA", "Mbappe", "Messi"],
    "privacy": "unlisted",
    "category_id": "17"
  },
  "scenes": [
    {"id":"hook","kind":"hook","duration_s":8,"source":"pixabay","query":"soccer stadium crowd","script":"Every World Cup gets called historic. This one actually is.","eyebrow":"// THE RECKONING","headline":"EVERY WORLD CUP GETS CALLED <accent>HISTORIC.</accent>","subhead":"// 4 MINUTES // 8 REASONS // 1 VERDICT","pill":"PROOF","top_label":"LIVE — FIFA WORLD CUP 2026","bottom_label":"JUNE 11, 2026 — JULY 19, 2026"},
    {"id":"scale","kind":"scale","duration_s":22,"source":"pixabay","query":"world map football","script":"48 teams. 104 games. 16 cities. Three countries. A completely different animal.","eyebrow":"// THE ANIMAL IS DIFFERENT","headline":"BIGGER THAN EVERY CUP <accent>BEFORE.</accent>","sub":"A completely different tournament. The largest single sporting event on Earth.","stats":[{"num":"48","label":"NATIONS"},{"num":"104","label":"MATCHES"},{"num":"16","label":"HOST CITIES"},{"num":"3","label":"COUNTRIES"}],"top_label":"01 — THE SCALE","bottom_label":"USA · CAN · MEX"},
    "..."
  ]
}
```

## 2. Repo layout (refactored)

```
gh-ffyt/
├── .github/workflows/render-and-upload.yml
├── scripts/
│   ├── compose.py                  NEW — single entry point, replaces the 3 old scripts
│   ├── upload_to_youtube.py        refactored — reads spec instead of env
│   ├── reencode_clips.py           KEPT (used internally by compose.py)
│   └── spec_schema.py              NEW — JSON schema validation
├── templates/
│   ├── base.html                   NEW — the shared <head>, palette, vignette, top/bottom bars
│   ├── hook.html.j2                NEW — one template per scene kind
│   ├── scale.html.j2
│   ├── portrait.html.j2
│   ├── record.html.j2
│   ├── grid.html.j2
│   ├── quote.html.j2
│   ├── list.html.j2
│   └── split.html.j2
├── specs/
│   ├── world_cup_2026.json         NEW — the migrated WC spec
│   └── _example.json               NEW — minimal reference spec
├── build/                          gitignored — all render output
├── .gitignore                      updated
├── README.md                       updated
├── PLAN.md                         NEW — this document
├── requirements.txt                updated
├── LICENSE                         KEPT
└── video_01_content_brief.md       KEPT for reference
```

**Deleted from the current repo:**
- `hf/index.html` (replaced by the per-scene templates)
- `hf/assets/clips/*` and `hf/assets/audio/*` (regenerated by the composer on every run; the gitignore pattern `build/` covers them)
- `scripts/produce_video_01.py` (replaced by compose.py)
- `scripts/generate_voiceover.py` (replaced by compose.py)

**Kept:**
- `scripts/upload_to_youtube.py` (with one change: read metadata from spec)
- `scripts/reencode_clips.py` (called by compose.py)
- The license, the .gitignore patterns (lightly updated)

**Why templates use `str.format` not Jinja2:**
The current spec is small and structured. Adding Jinja2 is one more dependency with no benefit. `str.format` with carefully-named `{slots}` keeps the templates readable and the dependency surface small.

## 3. `scripts/compose.py` — the main new file

```
def main():
    args = parse_args()       # --spec, --output-dir, --hyperframes-version, --no-upload
    spec = load_spec(args.spec)               # + validate against spec_schema.py
    out  = Path(args.output_dir)              # build/<spec.id>
    (out / "clips").mkdir(parents=True)
    (out / "audio").mkdir(parents=True)
    (out / "html").mkdir(parents=True)
    (out / "render").mkdir(parents=True)

    # 1. Per-scene: fetch footage (Pixabay first, fall back to Pexels).
    for scene in spec.scenes:
        clip_path = out / "clips" / f"{scene.id}.mp4"
        if not clip_path.exists():
            url = fetch_pixabay_clip(scene) or fetch_pexels_clip(scene)
            download_and_trim(url, clip_path, scene.duration_s)
            reencode(clip_path)              # -g 30 -keyint_min 30 +faststart

    # 2. Per-scene: generate voiceover.
    for scene in spec.scenes:
        audio_path = out / "audio" / f"{scene.id}.mp3"
        if not audio_path.exists():
            elevenlabs_tts(scene.script, audio_path, voice_id=spec.tts.voice_id or os.environ["ELEVENLABS_VOICE_ID"])

    # 3. Per-scene: render HTML from template.
    for i, scene in enumerate(spec.scenes, 1):
        html_path = out / "html" / f"scene_{i:02d}_{scene.kind}.html"
        html_path.write_text(render_scene_html(scene, spec, out))

    # 4. Per-scene: HyperFrames render.
    for html_path in sorted((out / "html").glob("scene_*.html")):
        mp4_path = out / "render" / (html_path.stem + ".mp4")
        run_hyperframes(html_path, mp4_path, args.hyperframes_version)

    # 5. Final concat with crossfade.
    final = out / f"{spec.id}.mp4"
    ffmpeg_concat_with_xfade(sorted((out / "render").glob("scene_*.mp4")), final, xfade_s=0.3)
    return final
```

## 4. Per-scene HTML template

A single Python function `render_scene_html(scene, spec, build_dir) -> str` picks the right template file from `templates/`, fills in slots, and writes the output.

**Base template (`templates/base.html`):** the body of the current `hf/index.html` (lines 1-580-ish) — fonts, color palette, .scene, .scene-video, .scene-vignette, .scene-glow, .top-bar, .bottom-bar. No `__timelines` script block.

**Per-scene HTML structure (per kind):**
```html
<!doctype html>
<html><head>
  <meta charset="UTF-8">
  <title>{scene.id}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Manrope:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500;700&display=swap">
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <style>/* base CSS + per-kind CSS */</style>
</head>
<body>
  <div id="root"
       data-composition-id="{spec.id}-{scene.id}"
       data-width="1920" data-height="1080"
       data-start="0"
       data-duration="{scene.duration_s}">

    <div id="scene1" class="scene">
      <video class="scene-video" src="../clips/{scene.id}.mp4" muted playsinline
             data-start="0" data-duration="{scene.duration_s}"></video>
      <div class="scene-vignette"></div>
      <div class="top-bar"><span><span class="mark">●</span>&nbsp;{scene.top_label}</span></div>
      <div class="scene-content">
        <!-- per-kind DOM, slot-filled from scene fields -->
      </div>
      <div class="bottom-bar">
        <span>{scene.bottom_label}</span>
        {f'<span class="pill">{scene.pill}</span>' if scene.pill else ''}
      </div>
    </div>

    <audio id="vo-track" src="../audio/{scene.id}.mp3"
           data-start="0" data-duration="{scene.duration_s}"></audio>
  </div>

  <script>
    var tl = gsap.timeline({{paused: true}});
    // per-kind entrance animations only — no cross-scene logic
    window.__timelines["{spec.id}-{scene.id}"] = tl;
  </script>
</body></html>
```

Each per-kind template overrides the `.scene-content` block and the per-kind CSS. The rest is identical.

**Why no cross-scene transitions in the simple model:** HyperFrames' lint warning flags the 60+ GSAP-targeted elements. Per-scene HTMLs are ~150-300 lines each, GSAP targets 5-15 elements per scene, no `__timelines` collision, no master timeline. The cost is loss of the cross-scene transitions (zoom-fade, chromatic-split, shutter, focus-pull, etc.). Trade-off accepted for v1; can be added in v2 by mounting the per-scene HTMLs via `data-composition-src` in a master `index.html`.

**Loss-of-transitions mitigation:** FFmpeg xfade between scene MP4s at concat time (0.3s). Costs 0.3s per scene transition; for an 8-scene video that's 2.4s total. Visually a small loss; structurally much simpler.

## 5. Pixabay + Pexels fetchers

**Pixabay:**
```python
def fetch_pixabay_clip(scene) -> Optional[str]:
    params = {
        "key": os.environ["PIXABAY_API_KEY"],
        "q": scene.query,
        "per_page": "10",
        "min_width": str(scene.min_width),
    }
    r = requests.get("https://pixabay.com/api/videos/", params=params, timeout=15)
    r.raise_for_status()
    hits = r.json().get("hits", [])
    for hit in hits:
        for v in hit.get("videos", []):
            if v["width"] <= 1920 and v["width"] >= scene.min_width:
                return v["url"]
    return None
```

**Pexels (refactor of the existing `search_pexels_video` in `produce_video_01.py`):**
```python
def fetch_pexels_clip(scene) -> Optional[str]:
    headers = {"Authorization": os.environ["PEXELS_API_KEY"]}
    r = requests.get("https://api.pexels.com/videos/search",
                     headers=headers,
                     params={"query": scene.query, "per_page": 10, "orientation": "landscape"},
                     timeout=15)
    r.raise_for_status()
    for video in r.json().get("videos", []):
        if video.get("duration", 0) < scene.duration_s: continue
        files = sorted([f for f in video.get("video_files", []) if f.get("width", 0) <= 1920],
                       key=lambda f: f.get("width", 0), reverse=True)
        if files: return files[0]["link"]
    return None
```

**Trim + re-encode:** `ffmpeg -y -i input.mp4 -ss 0 -t <duration_s> -vf scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720 -c:v libx264 -preset fast -crf 20 -g 30 -keyint_min 30 -r 30 -pix_fmt yuv420p -c:a aac -ar 44100 -movflags +faststart output.mp4`. (Reuses the ffmpeg command from the current `produce_video_01.py` and `reencode_clips.py`.)

## 6. `scripts/upload_to_youtube.py` — read spec instead of env

The only change from the current implementation: instead of `os.environ.get("YT_TITLE")` etc., read the spec at `os.environ.get("YT_SPEC_PATH", "specs/world_cup_2026.json")` and pull from `spec["youtube"]`. Env vars become a one-shot override (the `workflow_dispatch` "Skip YouTube upload" + "Use default metadata" inputs pass `YT_SPEC_PATH`).

`get_authenticated_service()` is unchanged from the current implementation. The `OAuth-from-base64-env` flow stays as-is.

## 7. GitHub Actions workflow (`.github/workflows/render-and-upload.yml`)

**Triggers:**
- `push` to `main` → render + upload the spec named in `current_spec.json` (a tiny file at the repo root: `{"spec": "specs/world_cup_2026.json"}`).
- `push` of `v*` tag → render + upload, 365-day artifact retention.
- `pull_request` to `main` → render the spec named in the PR's `current_spec.json` (allow PRs to swap specs), no upload.
- `workflow_dispatch` → manual, with two inputs:
  - `spec` (choice, populated by reading the contents of `specs/*.json` at workflow dispatch time — using `actions/github-script` to populate the dropdown)
  - `skip_upload` (boolean, default `false`)

**Runner:** `ubuntu-latest` (same justification as the current repo).

**Steps:**
1. `actions/checkout@v4`
2. `actions/setup-python@v5` (3.11, pip cache)
3. `actions/setup-node@v4` (20, npm cache)
4. `apt-get install -y ffmpeg fonts-dejavu fonts-liberation`
5. `pip install -r requirements.txt`
6. `actions/cache@v4` for `~/.cache/hyperframes` (key on `templates/*.html` hash + hyperframes version)
7. `python scripts/compose.py --spec specs/<chosen>.json --output-dir build/<spec_id> --hyperframes-version 0.6.103` (timeout 60 min)
8. `ffprobe` verify
9. `actions/upload-artifact@v4` (90 days for push, 365 days for tag, 14 days for PR)
10. `python scripts/upload_to_youtube.py` (skipped on PR; skipped on manual when `skip_upload=true`; timeout 30 min)

**Required secrets:**
- `PIXABAY_API_KEY` (NEW)
- `PEXELS_API_KEY`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `YT_CLIENT_SECRETS_BASE64`
- `YT_TOKEN_PICKLE_BASE64`
- `YT_PRIVACY_STATUS` (optional, default `private`)

## 8. `.gitignore` updates

- Add `build/` (everything under build is per-run output)
- Keep credential patterns, Python/Node patterns
- Drop the per-pattern `*_raw.mp4`, `*_scaled.mp4`, `*_overlay.png`, `*_card.png` — they no longer exist
- Drop `world_cup_video_01*.mp4` — replaced by `build/`

## 9. `README.md` rewrite

Sections:
- **What is this** — one paragraph.
- **Write a spec** — link to `specs/_example.json`, walk through the 8 scene kinds with screenshots/ASCII.
- **Run locally** — `pip install -r requirements.txt`, set env vars, `python scripts/compose.py --spec specs/world_cup_2026.json --output-dir build/world_cup_2026`.
- **Add to GitHub** — list the 7 secrets, link to OAuth setup.
- **Trigger the workflow** — manual dispatch with the spec dropdown.
- **Spec reference** — link to the schema in `scripts/spec_schema.py`.
- **Troubleshooting** — common failures (Pixabay rate limit, Pexels fallback, voiceover not generating, etc.).

## 10. World Cup migration

- `specs/world_cup_2026.json` — every value transcribed from the current `hf/index.html` (headlines, subheads, stats, names, host cards, nation list, dates, voiceover script, YouTube metadata, tags).
- The 8 `duration_s` values come from the current `data-duration` attributes on the `<video>` elements (7, 22, 32, 24, 35, 20, 15, 13 — total 168s).
- The output will **not** be byte-identical: Pixabay returns different clips than the Pexels-sourced originals; the per-scene HTML is structurally similar but the GSAP timeline is per-scene (no cross-scene transitions). Crossfade concat replaces the in-renderer transitions. Acceptable for the refactor.

## 11. Verification

1. **Local:** `python scripts/compose.py --spec specs/world_cup_2026.json --output-dir build/world_cup_2026` produces a 1920x1080 30fps ~168s MP4. Open in VLC. Compare to the current `world_cup_video_01_FINAL_v2.mp4` for visual structure.
2. **`ffprobe` verify:** `h264 yuv420p 1920x1080 30/1 ~168s`.
3. **Per-scene MP4 inspection:** `build/world_cup_2026/render/scene_*.mp4` — each is a self-contained 1920x1080 clip with the per-scene voiceover baked in.
4. **Spec validation:** write a deliberately broken spec (missing `kind`, unknown `kind`, missing `script`) and confirm `spec_schema.py` rejects it with a line-precise error.
5. **Different spec:** `python scripts/compose.py --spec specs/_example.json --output-dir build/example` — confirm a different video comes out from the same code.
6. **GitHub Actions:** `workflow_dispatch` with `spec=specs/world_cup_2026.json`, `skip_upload=true`. Confirm artifact is downloadable. Then with `skip_upload=false` and YT secrets in place, confirm the upload.
7. **Refresh-token expiry:** documented in `upload_to_youtube.py` — re-run local one-time auth, base64 the new pickle, update the secret.

## 12. Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Pixabay key not yet wired. New account needed. | README has the signup link. Without it, every scene falls back to Pexels — graceful degradation. |
| 2 | Per-scene render means N hyperframes invocations instead of 1. CI time multiplies. | For an 8-scene video, ~8x ~2 min each = 16 min render step. Cache step preserves Chrome between runs. Document the time expectation. |
| 3 | Cross-scene GSAP transitions are gone. Visual quality drops. | FFmpeg xfade 0.3s per transition softens this. Document that v2 can re-add a master composition with `data-composition-src` if needed. |
| 4 | Spec-driven HTML is more error-prone than the hand-written one. | `spec_schema.py` validates the spec before any render starts. Per-kind template + base template means consistent layout. |
| 5 | 7GB RAM per render is the same as before, but N renders means N Chrome startups. | Cache step. `--quality medium` if OOMs. |
| 6 | Two new HTML files (templates + composer) to maintain. | Templates are tiny (~50 lines each); composer is the only nontrivial Python. |
| 7 | Spec is plain JSON, so JSON escape issues (newlines, quotes) are a footgun for long voiceover scripts. | Validator accepts `\n` in strings. README shows the right way to embed a multi-line voiceover. |

## 13. Open questions

- **Add a per-scene xfade between HyperFrames outputs?** Recommended yes, 0.3s. Cost: 0.3s × (N-1) extra seconds in the final video. Benefit: visually softens the loss of cross-scene GSAP transitions. The ffmpeg `xfade` filter handles this with one filter_complex per transition.

## Critical files

- `C:\Users\PC\Desktop\gh-ffyt\scripts\compose.py` — the main new file. Orchestrates the whole pipeline.
- `C:\Users\PC\Desktop\gh-ffyt\scripts\spec_schema.py` — validates the JSON spec before any rendering.
- `C:\Users\PC\Desktop\gh-ffyt\templates\base.html` + the 8 per-kind templates — the per-scene HTML generators.
- `C:\Users\PC\Desktop\gh-ffyt\specs\world_cup_2026.json` — the migrated spec, the reference implementation.
- `C:\Users\PC\Desktop\gh-ffyt\.github\workflows\render-and-upload.yml` — the multi-spec dispatcher.
- `C:\Users\PC\Desktop\gh-ffyt\scripts\upload_to_youtube.py` — the only existing file that gets a meaningful refactor (env → spec).
