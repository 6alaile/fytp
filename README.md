# gh-ffyt — JSON-spec-driven faceless video factory

A general-purpose pipeline that turns a JSON spec into a 1920×1080 30 fps
MP4 and optionally publishes it to YouTube. The first spec is the 2026
FIFA World Cup explainer; new specs need zero code changes.

```
specs/<name>.json  ──►  python scripts/compose.py
                              │
                              ├─ fetch stock footage (Pixabay → Pexels)
                              ├─ ElevenLabs voiceover per scene
                              ├─ render per-scene HTML (templates/)
                              ├─ npx hyperframes render (per scene)
                              └─ ffmpeg xfade concat
                                          │
                                          ▼
                          build/<id>/<id>.mp4   ──►  scripts/upload_to_youtube.py
                                                       │
                                                       ▼
                                                 YouTube Data API v3
```

API keys and OAuth tokens live in **Settings → Secrets**; never in code.

---

## What is in this repo

| Path | Purpose |
|---|---|
| `specs/*.json` | One spec per video. JSON, validated, fully describes the video. |
| `templates/base.html` | Shared HTML shell: palette, fonts, top/bottom bars, vignette. |
| `scripts/spec_schema.py` | JSON schema validator for specs. Loud on errors. |
| `scripts/kind_renderers.py` | Per-kind (8 kinds) CSS + content + GSAP animations. |
| `scripts/fetchers.py` | Pixabay + Pexels video search. |
| `scripts/compose.py` | The single entry point. Orchestrates everything. |
| `scripts/upload_to_youtube.py` | Spec-driven YouTube uploader. |
| `scripts/brief_to_spec.py` | Optional: parse a .md content brief into a draft spec. |
| `.github/workflows/render-and-upload.yml` | CI: per-spec render + optional upload. |

---

## Write a spec

A spec has three top-level sections: `id`, `youtube`, `scenes`.
Optional: `tts` (ElevenLabs overrides), `palette` (re-skin).

```json
{
  "id": "my_video",
  "youtube": {
    "title": "...",
    "description": "...",
    "tags": ["..."],
    "privacy": "private",
    "category_id": "17"
  },
  "scenes": [
    { "id": "01_hook", "kind": "hook",   "duration_s": 6, "script": "...",
      "eyebrow": "...", "headline": "...", "subhead": "..." },
    { "id": "02_scale", "kind": "scale", "duration_s": 12, "script": "...",
      "headline": "...", "stats": [{"num":"48","label":"NATIONS"}, ...] }
    // ... one entry per scene
  ]
}
```

### The 8 scene kinds

| Kind | Required fields | Vibe |
|---|---|---|
| `hook` | `eyebrow`, `headline` (use `<accent>…</accent>` for the gold word), `subhead` | Big opening slam |
| `scale` | `headline`, `stats` (list of `{num,label}`) | Numbers wall |
| `portrait` | `eyebrow`, `headline`, `names` (list of `{name,year}`) | Two (or more) faces |
| `record` | `counter_label`, `counter_num`, `counter_suffix`, `name` | One big counter |
| `grid` | `headline`, `cards` (list of `{flag,name,stats,quote}`) | 3-4 host cards |
| `quote` | `eyebrow`, `quote` (use `<accent>…</accent>` for the gold word), `attribution` | One big quote |
| `list` | `eyebrow`, `headline`, `items` (list of strings) | Numbered list |
| `split` | `eyebrow`, `headline`, `body`, `image_query` | Two-column text + image |

See `specs/_example.json` for a minimal reference spec that uses every
kind, and `specs/world_cup_2026.json` for the full reference implementation.

Common per-scene fields (all kinds): `source` (`pixabay` | `pexels`),
`query` (search string), `min_width`, `top_label`, `bottom_label`, `pill`.

### Multi-line voiceover

Embed `\n` for newlines in the `script` field. JSON strings handle this
naturally:

```json
"script": "Line one.\nLine two.\nLine three."
```

---

## Run locally

```bash
pip install -r requirements.txt

# Required for stock footage
export PIXABAY_API_KEY=...     # primary source
export PEXELS_API_KEY=...      # fallback

# Required for voiceover
export ELEVENLABS_API_KEY=...
export ELEVENLABS_VOICE_ID=...

# Render
python scripts/compose.py --spec specs/world_cup_2026.json --output-dir build
# Final MP4: build/world_cup_2026/world_cup_2026.mp4
```

You can validate a spec without running anything:

```bash
python scripts/spec_schema.py specs/world_cup_2026.json
# OK: specs/world_cup_2026.json validates
```

---

## Write a spec from a markdown content brief

If you start from prose, the converter turns a structured .md brief into
a draft spec you can edit. See `scripts/brief_to_spec.py` for the
documented schema. Quick example:

```bash
python scripts/brief_to_spec.py content_brief.md --out specs/_draft.json
# Reads brief, writes draft spec, prints which fields it filled.
```

The converter is rule-based: it only fills fields it can recognise
unambiguously. Everything else is left as `TODO` for you to fill in.

---

## GitHub Actions

| Event | What happens |
|---|---|
| Push to `main` | Render + upload (with `YT_PRIVACY_STATUS`) |
| Push tag `v*` | Render + upload, 365-day artifact retention |
| Pull request to `main` | Render only, no upload; PR preview artifact for 14 days |
| `workflow_dispatch` | Manual, with `spec` dropdown + `skip_upload` + `privacy_status` |

The `meta` job discovers every `specs/*.json` (except `_example.json`)
and exposes them as the dispatch dropdown options. So adding a new
spec to the repo automatically adds it to the manual UI.

Render step: ~16 min for an 8-scene video. Upload: a few more. Total
job time: 18–25 min for upload-included runs.

### Required secrets

| Secret | Why |
|---|---|
| `PIXABAY_API_KEY` | Primary footage source |
| `PEXELS_API_KEY` | Fallback footage source |
| `ELEVENLABS_API_KEY` | Voiceover |
| `ELEVENLABS_VOICE_ID` | Voiceover |
| `YT_CLIENT_SECRETS_BASE64` | YouTube publish |
| `YT_TOKEN_PICKLE_BASE64` | YouTube publish |
| `YT_PRIVACY_STATUS` | Optional default privacy |
| `YT_THUMBNAIL_PATH` | Optional thumbnail |
| `YT_CAPTIONS_PATH` | Optional captions.srt |

For YouTube OAuth you need a **"Desktop app"** client, not a Web
application client. Run `python scripts/upload_to_youtube.py` once
locally to complete the consent flow and generate
`youtube_token.pickle`. Base64-encode both files (`base64 -w0 … > .b64`)
and paste the contents as the matching secret.

---

## Adding a new scene kind

1. Add it to `SCENE_KINDS` and `KIND_SCHEMAS` in `scripts/spec_schema.py`.
2. Add a renderer in `scripts/kind_renderers.py` (CSS + HTML + GSAP).
3. Add a kind-specific section in `templates/base.html` (if needed).
4. Add a `##` section to the README describing it.

---

## Architecture

```
specs/<id>.json
   ├─ spec_schema.py validates
   ├─ fetchers.py: pixabay → pexels (fallback) → download → reencode
   ├─ generate_voiceover (per scene)
   ├─ kind_renderers.py + base.html → per-scene HTML
   ├─ npx hyperframes render (per scene)
   └─ ffmpeg xfade concat
                                          │
                                          ▼
              build/<id>/<id>.mp4
                                          │
                                          ▼
              upload_to_youtube.py → YouTube Data API v3
```

Per-scene renders replace the original master composition. The trade-off:
no cross-scene GSAP transitions (zoom-fade, chromatic split, shutter,
focus pull, etc.). Mitigated by a 0.3 s xfade between every scene pair.
If a v2 brings back the master composition, set `--xfade 0` in the
composer.

---

## License

UNLICENSED — see `LICENSE`. Private repo.
