"""
brief_to_spec.py — turn a .md content brief into a draft JSON spec.

Rule-based parser with a documented schema. Only fills fields it can
recognise unambiguously; everything else is left as `TODO` for the
author to complete.

Documented input schema (anything not in this list is ignored):

  # <Title>                              ──► spec.youtube.title (fallback)
  ## Hook                                ──► scene 1 of kind "hook"
  ## Scene <N> — <Title>                 ──► scene N
  ## YouTube Metadata
    **Title options:**
    1. <title 1>
    2. <title 2>                          ──► spec.youtube.title (first option)
    **Description:** <text>              ──► spec.youtube.description
    **Tags:** <a, b, c>                   ──► spec.youtube.tags
    **Category:** <Sports>                ──► spec.youtube.category_id
  ## Thumbnail Concept
    <ignored — thumbnail_path is set later>
  ## Audio Direction
    <ignored — voice/tone metadata only>
  ## Format & Length
    **Target length:** <text>             ──► spec.total_length_hint (informational)

Per-scene block, inside ## Scene / ## Hook:

  **Kind:** <hook|scale|portrait|record|grid|quote|list|split>
  **Duration:** <NN>s                    ──► scene.duration_s
  **Query:** <text>                      ──► scene.query
  **Top label:** <text>                  ──► scene.top_label
  **Bottom label:** <text>               ──► scene.bottom_label
  **Eyebrow:** <text>                    ──► scene.eyebrow
  **Headline:** <text>                   ──► scene.headline
  **Subhead / Sub:** <text>              ──► scene.subhead / sub
  **Pill:** <text>                       ──► scene.pill
  **Stats:**
    - <num> <label>                      ──► scene.stats[]
  **Names:**
    - <name> | <year>                    ──► scene.names[]
  **Cards:** (for kind=grid)
    - 🇺🇸 | USA | "..." | "<quote>"       ──► scene.cards[] (one per card)
  **Items:** (for kind=list)
    - <item>                             ──► scene.items[]
  **Image query:** <text>                ──► scene.image_query (for kind=split)
  **Voiceover / Script:** <text>         ──► scene.script
  (or a block quote under Voiceover:)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────
# Documented schema
# ─────────────────────────────────────────────────────────────────────
SCENE_KINDS = {"hook", "scale", "portrait", "record", "grid", "quote", "list", "split"}

# Fields that are always top-level on a scene.
# Per-kind extra fields are checked at write-time.
COMMON_SCENE_FIELDS = {
    "kind", "duration", "query", "top label", "bottom label",
    "eyebrow", "headline", "subhead", "sub", "pill",
    "voiceover", "script",
}

# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────
class BriefParseError(ValueError):
    pass


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────
def parse_brief(text: str) -> dict[str, Any]:
    """Parse a .md brief string and return a spec dict (possibly incomplete)."""
    sections = _split_sections(text)
    spec: dict[str, Any] = {"scenes": []}
    top_title = _h1_title(text)

    if "YouTube Metadata" in sections:
        _fill_youtube(spec, sections["YouTube Metadata"], top_title)

    # First scene may be under ## Hook.
    if "Hook" in sections:
        scene = _parse_scene_block("Hook", 1, sections["Hook"])
        if scene.get("kind") is None:
            scene["kind"] = "hook"
        spec["scenes"].append(scene)

    # Remaining scenes under ## Scene N — Title.
    scene_n = len(spec["scenes"]) + 1
    for name, body in sections.items():
        if not re.match(r"^Scene\b", name):
            continue
        scene = _parse_scene_block(name, scene_n, body)
        if scene.get("kind") is None:
            # Default the kind by shape, but the user should set it explicitly.
            scene["kind"] = "TODO"
        spec["scenes"].append(scene)
        scene_n += 1

    if not spec["scenes"]:
        raise BriefParseError("no scenes found in brief (no ## Hook or ## Scene section)")

    spec.setdefault("id", _slugify(spec.get("youtube", {}).get("title", "draft")))
    return spec


def parse_brief_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    return parse_brief(p.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────
# Section parser
# ─────────────────────────────────────────────────────────────────────
def _split_sections(text: str) -> dict[str, str]:
    """Split on `## ` headings. Returns {section_name: body}."""
    sections: dict[str, str] = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip()
            sections[current] = ""
        elif current is not None:
            sections[current] += line + "\n"
    return sections


def _h1_title(text: str) -> str | None:
    m = re.match(r"^#\s+(.+?)\s*$", text.splitlines()[0] if text else "")
    return m.group(1).strip() if m else None


def _fill_youtube(spec: dict, body: str, top_title: str | None) -> None:
    yt: dict[str, Any] = {}
    # First numbered title wins.
    m = re.search(r"^\s*\d+\.\s+(.+?)\s*$", body, re.MULTILINE)
    if m:
        yt["title"] = m.group(1).strip()
    elif top_title:
        yt["title"] = top_title
    else:
        yt["title"] = "TODO"

    desc_m = re.search(r"\*\*Description:\*\*\s*(.+?)(?=\n\n|\Z)", body, re.DOTALL)
    if desc_m:
        yt["description"] = desc_m.group(1).strip()
    else:
        yt["description"] = "TODO"

    tags_m = re.search(r"\*\*Tags:\*\*\s*(.+?)(?=\n\n|\Z)", body, re.DOTALL)
    if tags_m:
        raw = tags_m.group(1).strip()
        if raw.startswith("[") and raw.endswith("]"):
            yt["tags"] = [t.strip().strip("'\"") for t in raw[1:-1].split(",") if t.strip()]
        else:
            yt["tags"] = [t.strip() for t in re.split(r",\s*", raw) if t.strip()]
    else:
        yt["tags"] = []

    cat_m = re.search(r"\*\*Category:\*\*\s*(\w+)", body)
    if cat_m:
        cat = cat_m.group(1).strip()
        yt["category_id"] = "17" if cat.lower() == "sports" else "22"

    yt.setdefault("privacy", "private")
    spec["youtube"] = yt


# ─────────────────────────────────────────────────────────────────────
# Per-scene parser
# ─────────────────────────────────────────────────────────────────────
def _parse_scene_block(name: str, idx: int, body: str) -> dict[str, Any]:
    """Extract a scene dict from a ## section body."""
    scene_id = _scene_id(name, idx)
    scene: dict[str, Any] = {"id": scene_id}

    # Kind
    m = re.search(r"\*\*Kind:\*\*\s*(\w+)", body)
    if m:
        k = m.group(1).strip().lower()
        if k in SCENE_KINDS:
            scene["kind"] = k
        else:
            scene["kind"] = f"TODO_unknown({k})"

    # Duration
    m = re.search(r"\*\*Duration:\*\*\s*(\d+)\s*s", body)
    if m:
        scene["duration_s"] = int(m.group(1))

    # Top/bottom labels
    m = re.search(r"\*\*Top label:\*\*\s*(.+?)\s*$", body, re.MULTILINE)
    if m:
        scene["top_label"] = m.group(1).strip()
    m = re.search(r"\*\*Bottom label:\*\*\s*(.+?)\s*$", body, re.MULTILINE)
    if m:
        scene["bottom_label"] = m.group(1).strip()

    # Query
    m = re.search(r"\*\*Query:\*\*\s*(.+?)\s*$", body, re.MULTILINE)
    if m:
        scene["query"] = m.group(1).strip()

    # Pill
    m = re.search(r"\*\*Pill:\*\*\s*(.+?)\s*$", body, re.MULTILINE)
    if m:
        scene["pill"] = m.group(1).strip()

    # Headline / sub / subhead / eyebrow / name.
    # "Name" is the headline for kind=record (the big right-side word).
    for k in ("eyebrow", "headline", "subhead", "sub", "name"):
        m = re.search(rf"\*\*{k.capitalize()}:\*\*\s*(.+?)\s*$", body, re.MULTILINE)
        if not m:
            m = re.search(rf"\*\*{k.capitalize()}:?\*\*\s*(.+?)\s*$", body, re.MULTILINE)
        if m:
            scene[k] = m.group(1).strip()

    # Counter fields (for kind=record). The "Counter" prefix splits as
    # two words in the markdown heading, so we use a phrase match.
    for ck, target in [
        ("counter label",   "counter_label"),
        ("counter num",     "counter_num"),
        ("counter suffix",  "counter_suffix"),
    ]:
        m = re.search(rf"\*\*{ck.capitalize()}:?\*\*\s*(.+?)\s*$", body, re.MULTILINE)
        if m:
            scene[target] = m.group(1).strip()

    # Image query (for split kind)
    m = re.search(r"\*\*Image query:\*\*\s*(.+?)\s*$", body, re.MULTILINE)
    if m:
        scene["image_query"] = m.group(1).strip()

    # Stats
    stats_block = _list_block(body, "Stats")
    if stats_block:
        scene["stats"] = []
        for line in stats_block:
            parts = re.split(r"\s*\|\s*|\s{2,}", line.strip(), maxsplit=1)
            if len(parts) == 2:
                scene["stats"].append({"num": parts[0].strip(), "label": parts[1].strip()})
            else:
                m2 = re.match(r"^(\S+)\s+(.+)$", line.strip())
                if m2:
                    scene["stats"].append({"num": m2.group(1), "label": m2.group(2)})

    # Names
    names_block = _list_block(body, "Names")
    if names_block:
        scene["names"] = []
        for line in names_block:
            parts = re.split(r"\s*\|\s*", line.strip(), maxsplit=1)
            if len(parts) == 2:
                scene["names"].append({"name": parts[0].strip(), "year": parts[1].strip()})

    # Items
    items_block = _list_block(body, "Items")
    if items_block:
        scene["items"] = [line.strip() for line in items_block]

    # Cards (one bullet per card, fields separated by |)
    cards_block = _list_block(body, "Cards")
    if cards_block:
        scene["cards"] = []
        for line in cards_block:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                card = {
                    "flag": parts[0],
                    "name": parts[1],
                    "stats": [s.strip() for s in parts[2:-1] if s.strip()] if len(parts) > 3 else [],
                    "quote": parts[-1] if len(parts) >= 2 and parts[-1].startswith(("'", '"')) else "",
                }
                # Drop empty quote
                if not card["quote"] and len(parts) == 4:
                    card["quote"] = parts[3]
                scene["cards"].append(card)

    # Voiceover / script: prefer a "Voiceover:" line, fall back to a quoted block.
    m = re.search(r"\*\*(?:Voiceover|Script):\*\*\s*(.+?)(?=\n\n|\Z)", body, re.DOTALL)
    if m:
        scene["script"] = m.group(1).strip()
    else:
        # Quote-style block
        qb = re.search(r"^>\s*(.+?)(?=\n[^>]|\Z)", body, re.MULTILINE | re.DOTALL)
        if qb:
            scene["script"] = qb.group(1).strip()

    return scene


def _list_block(body: str, name: str) -> list[str]:
    """Return the bullet list under '**Name:**' as a list of strings."""
    m = re.search(rf"\*\*{name}:\*\*\s*\n((?:\s*[-*]\s+.+?\n)+)", body)
    if not m:
        return []
    raw = m.group(1)
    return [re.sub(r"^\s*[-*]\s+", "", l).rstrip() for l in raw.splitlines() if l.strip()]


def _scene_id(name: str, idx: int) -> str:
    """Build a scene id from a heading name like 'Scene 4 — The Hosts'."""
    m = re.match(r"Scene\s+(\d+)\s*[—-]\s*(.+)", name)
    if m:
        n, title = m.group(1), m.group(2)
    else:
        n, title = str(idx), name
    slug = _slugify(title)
    return f"{int(n):02d}_{slug}"


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return s or "scene"


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────
def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Convert a .md content brief into a draft spec")
    p.add_argument("brief", help="path to the .md brief")
    p.add_argument("--out", default="specs/_draft.json", help="output spec path (default: specs/_draft.json)")
    args = p.parse_args(argv[1:])

    try:
        spec = parse_brief_file(args.brief)
    except (BriefParseError, FileNotFoundError) as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: wrote {out}")
    print(f"  scenes: {len(spec['scenes'])}")
    print(f"  id:     {spec['id']}")
    todo = _count_todos(spec)
    if todo:
        print(f"  TODO fields: {todo} (open {out} and fill them in)")
    return 0


def _count_todos(spec: dict) -> int:
    n = 0
    s = json.dumps(spec)
    n += s.count('"TODO')
    return n


if __name__ == "__main__":
    sys.exit(main(sys.argv))
