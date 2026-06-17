"""
JSON schema validation for video specs.

A spec is a single JSON file under specs/ that describes one video end-to-end:
YouTube metadata + ordered list of scenes, each tied to one of 8 "kinds".

Validation is intentionally strict: unknown kinds and missing required
fields fail loudly with a line-precise error message. The composer
relies on this so downstream code can assume shape, not possibility.

Top-level shape:

  {
    "id": "world_cup_2026",
    "youtube": { ... },
    "tts": { ... },            // optional
    "palette": { ... },        // optional
    "scenes": [ ... ]
  }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable


# ─────────────────────────────────────────────────────────────────────
# 8 supported scene kinds in v1.
# Add a new kind by:
#   1. Add it to SCENE_KINDS.
#   2. Add a REQUIRED/OPTIONAL entry in KIND_SCHEMAS.
#   3. Create templates/<kind>.html matching the slot names.
# ─────────────────────────────────────────────────────────────────────
SCENE_KINDS = {
    "hook",
    "scale",
    "portrait",  # was "last_dance" in the legacy build
    "record",
    "grid",
    "quote",
    "list",
    "split",
}

# All common fields every scene needs, regardless of kind.
COMMON_SCENE_FIELDS = {
    "id":           (str, True),
    "kind":         (str, True),
    "duration_s":   (int, True),  # whole seconds; float also accepted
    "script":       (str, True),  # voiceover text
    "source":       (str, False),  # "pixabay" | "pexels"
    "query":        (str, False),
    "min_width":    (int, False),
    "top_label":    (str, False),
    "bottom_label": (str, False),
    "pill":         (str, False),
}

# Per-kind required + optional fields. Optional fields are still validated
# for type when present.
KIND_SCHEMAS: dict[str, dict[str, tuple[type, bool]]] = {
    "hook": {
        "required": {"eyebrow", "headline", "subhead"},
        "optional": {"pill"},
        "types": {
            "eyebrow": str,
            "headline": str,   # may contain <accent>...</accent> for gold word
            "subhead": str,
            "pill": str,
        },
    },
    "scale": {
        "required": {"headline", "stats"},
        "optional": {"eyebrow", "sub"},
        "types": {
            "eyebrow": str,
            "headline": str,
            "sub": str,
            "stats": list,   # list of {num, label}
        },
    },
    "portrait": {
        "required": {"eyebrow", "headline", "names"},
        "optional": {"sub"},
        "types": {
            "eyebrow": str,
            "headline": str,
            "sub": str,
            "names": list,   # list of {name, year}
        },
    },
    "record": {
        "required": {"counter_label", "counter_num", "counter_suffix", "name"},
        "optional": {"eyebrow", "quote"},
        "types": {
            "eyebrow": str,
            "counter_label": str,
            "counter_num": (str, int),
            "counter_suffix": str,
            "name": str,
            "quote": str,
        },
    },
    "grid": {
        "required": {"headline", "cards"},
        "optional": {"eyebrow"},
        "types": {
            "eyebrow": str,
            "headline": str,
            "cards": list,   # list of {flag, name, stats, quote}
        },
    },
    "quote": {
        "required": {"eyebrow", "quote", "attribution"},
        "optional": {"sub"},
        "types": {
            "eyebrow": str,
            "quote": str,
            "attribution": str,
            "sub": str,
        },
    },
    "list": {
        "required": {"eyebrow", "headline", "items"},
        "optional": {"sub"},
        "types": {
            "eyebrow": str,
            "headline": str,
            "sub": str,
            "items": list,   # list of strings
        },
    },
    "split": {
        "required": {"eyebrow", "headline", "body", "image_query"},
        "optional": set(),
        "types": {
            "eyebrow": str,
            "headline": str,
            "body": str,
            "image_query": str,
        },
    },
}


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────
class SpecError(ValueError):
    """Raised on any spec validation failure."""


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────
def load_and_validate(path: str | Path) -> dict[str, Any]:
    """Read a JSON spec file, validate it, return the parsed dict.

    Raises:
        FileNotFoundError: if the path does not exist.
        SpecError: on any structural or type problem.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Spec file not found: {p}")
    try:
        spec = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SpecError(f"{p}: invalid JSON: {e}") from e
    validate(spec)
    return spec


def validate(spec: dict[str, Any]) -> None:
    """Validate a parsed spec in-place. Raises SpecError on the first problem."""
    _check_type(spec, "spec", dict)
    _check_required(spec, "spec", {"id", "youtube", "scenes"})

    _check_type(spec["id"], "spec.id", str)
    _check_type(spec["youtube"], "spec.youtube", dict)
    _check_type(spec["scenes"], "spec.scenes", list)

    _validate_youtube(spec["youtube"])
    _validate_tts(spec.get("tts"))
    _validate_palette(spec.get("palette"))
    _validate_scenes(spec["scenes"])


# ─────────────────────────────────────────────────────────────────────
# Top-level sub-validators
# ─────────────────────────────────────────────────────────────────────
def _validate_youtube(yt: dict[str, Any]) -> None:
    _check_required(yt, "spec.youtube", {"title", "description", "tags"})
    _check_type(yt["title"], "spec.youtube.title", str)
    _check_type(yt["description"], "spec.youtube.description", str)
    _check_type(yt["tags"], "spec.youtube.tags", list)
    if not all(isinstance(t, str) for t in yt["tags"]):
        raise SpecError("spec.youtube.tags: every element must be a string")
    if "privacy" in yt and yt["privacy"] not in {"public", "unlisted", "private"}:
        raise SpecError(
            f"spec.youtube.privacy: must be public/unlisted/private, got {yt['privacy']!r}"
        )
    if "category_id" in yt and not isinstance(yt["category_id"], str):
        raise SpecError("spec.youtube.category_id: must be a string (e.g. '17')")
    if "publish_at" in yt and not isinstance(yt["publish_at"], str):
        raise SpecError("spec.youtube.publish_at: must be ISO 8601 string")
    if "thumbnail_path" in yt and not isinstance(yt["thumbnail_path"], str):
        raise SpecError("spec.youtube.thumbnail_path: must be a string path")
    if "captions_path" in yt and not isinstance(yt["captions_path"], str):
        raise SpecError("spec.youtube.captions_path: must be a string path")


def _validate_tts(tts: Any) -> None:
    if tts is None:
        return
    _check_type(tts, "spec.tts", dict)
    if "voice_id" in tts and not isinstance(tts["voice_id"], str):
        raise SpecError("spec.tts.voice_id: must be a string")
    if "stability" in tts and not isinstance(tts["stability"], (int, float)):
        raise SpecError("spec.tts.stability: must be a number 0..1")
    if "model_id" in tts and not isinstance(tts["model_id"], str):
        raise SpecError("spec.tts.model_id: must be a string")


def _validate_palette(p: Any) -> None:
    if p is None:
        return
    _check_type(p, "spec.palette", dict)
    for k in ("bg", "fg", "accent"):
        if k in p and not isinstance(p[k], str):
            raise SpecError(f"spec.palette.{k}: must be a CSS colour string")


def _validate_scenes(scenes: list[Any]) -> None:
    if not scenes:
        raise SpecError("spec.scenes: must contain at least one scene")
    seen_ids: set[str] = set()
    for i, scene in enumerate(scenes):
        idx = f"scenes[{i}]"
        _check_type(scene, idx, dict)

        # Common fields
        for field, (typ, required) in COMMON_SCENE_FIELDS.items():
            if required and field not in scene:
                raise SpecError(f"{idx}: missing required common field {field!r}")
            if field in scene and field not in ("kind",):
                # kind is checked below; check type for the rest
                if field == "duration_s":
                    if not isinstance(scene[field], (int, float)):
                        raise SpecError(
                            f"{idx}.{field}: must be a number (got {type(scene[field]).__name__})"
                        )
                else:
                    if not isinstance(scene[field], typ):
                        raise SpecError(
                            f"{idx}.{field}: expected {typ.__name__}, "
                            f"got {type(scene[field]).__name__}"
                        )

        # Per-scene id uniqueness
        sid = scene.get("id")
        if sid in seen_ids:
            raise SpecError(f"{idx}: duplicate scene id {sid!r}")
        seen_ids.add(sid)

        # Kind dispatch
        kind = scene.get("kind")
        if kind not in SCENE_KINDS:
            raise SpecError(
                f"{idx}.kind: unknown kind {kind!r}. "
                f"Allowed: {', '.join(sorted(SCENE_KINDS))}"
            )
        _validate_kind_fields(idx, kind, scene)


def _validate_kind_fields(idx: str, kind: str, scene: dict[str, Any]) -> None:
    schema = KIND_SCHEMAS[kind]

    # Required fields present?
    for f in schema["required"]:
        if f not in scene:
            raise SpecError(f"{idx} (kind={kind}): missing required field {f!r}")

    # Type-check present fields
    for f, t in schema["types"].items():
        if f in scene:
            if isinstance(t, tuple):
                ok = isinstance(scene[f], t)
            else:
                ok = isinstance(scene[f], t)
            if not ok:
                raise SpecError(
                    f"{idx}.{f} (kind={kind}): "
                    f"expected {t.__name__ if not isinstance(t, tuple) else '/'.join(x.__name__ for x in t)}, "
                    f"got {type(scene[f]).__name__}"
                )

    # Reject unknown fields (catches typos)
    allowed = set(schema["required"]) | set(schema["optional"]) | set(COMMON_SCENE_FIELDS)
    unknown = set(scene.keys()) - allowed
    if unknown:
        raise SpecError(
            f"{idx} (kind={kind}): unknown field(s) {sorted(unknown)}. "
            f"Allowed: {sorted(allowed)}"
        )

    # Per-kind structural checks
    if kind == "scale":
        for j, s in enumerate(scene["stats"]):
            _check_type(s, f"{idx}.stats[{j}]", dict)
            for k in ("num", "label"):
                if k not in s:
                    raise SpecError(f"{idx}.stats[{j}]: missing {k!r}")

    elif kind == "portrait":
        for j, n in enumerate(scene["names"]):
            _check_type(n, f"{idx}.names[{j}]", dict)
            for k in ("name", "year"):
                if k not in n:
                    raise SpecError(f"{idx}.names[{j}]: missing {k!r}")

    elif kind == "grid":
        for j, c in enumerate(scene["cards"]):
            _check_type(c, f"{idx}.cards[{j}]", dict)
            for k in ("flag", "name", "stats", "quote"):
                if k not in c:
                    raise SpecError(f"{idx}.cards[{j}]: missing {k!r}")

    elif kind == "list":
        for j, item in enumerate(scene["items"]):
            if not isinstance(item, str):
                raise SpecError(
                    f"{idx}.items[{j}]: must be a string, got {type(item).__name__}"
                )


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _check_type(value: Any, path: str, expected: type | tuple[type, ...]) -> None:
    if not isinstance(value, expected):
        raise SpecError(
            f"{path}: expected {expected.__name__}, got {type(value).__name__}"
        )


def _check_required(obj: dict[str, Any], path: str, required: Iterable[str]) -> None:
    missing = set(required) - set(obj.keys())
    if missing:
        raise SpecError(f"{path}: missing required field(s) {sorted(missing)}")


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────
def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python spec_schema.py <spec.json>", file=sys.stderr)
        return 2
    try:
        load_and_validate(argv[1])
    except SpecError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print(f"OK: {argv[1]} validates")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
