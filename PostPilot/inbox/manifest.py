"""Manifest parsing for inbox items.

The agent can send a video with a caption that is either:
  1. JSON with optional keys ``targets`` / ``title`` / ``caption`` /
     ``hashtags`` — the structured manifest.
  2. Plain text — used as the caption for all four platforms.
"""

from __future__ import annotations

import json

VALID_TARGETS = {"tiktok", "youtube", "instagram", "facebook"}
ALL_TARGETS = ["tiktok", "youtube", "instagram", "facebook"]


def _coerce_hashtags(raw) -> list[str]:
    """Coerce the hashtags field to a list of non-empty strings."""
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return []
    tags: list[str] = []
    for tag in raw:
        if isinstance(tag, str):
            tag = tag.strip()
            if tag:
                tags.append(tag)
        elif tag is not None:
            text = str(tag).strip()
            if text:
                tags.append(text)
    return tags


def _json_manifest(text: str, data: dict) -> dict:
    targets_raw = data.get("targets")
    targets: list[str] = []
    if isinstance(targets_raw, (list, tuple)):
        for t in targets_raw:
            if isinstance(t, str) and t.strip().lower() in VALID_TARGETS:
                key = t.strip().lower()
                if key not in targets:
                    targets.append(key)
    if not targets:
        targets = list(ALL_TARGETS)

    title = data.get("title")
    caption = data.get("caption")
    hashtags = _coerce_hashtags(data.get("hashtags"))

    title = str(title).strip() if title is not None else ""
    if caption is None:
        caption = text
    caption = str(caption)

    full_caption = (caption + "\n" + " ".join(hashtags)).strip() if hashtags else caption.strip()

    return {
        "targets": targets,
        "title": title,
        "caption": caption.strip(),
        "hashtags": hashtags,
        "full_caption": full_caption,
        "raw_text": text,
        "is_json": True,
    }


def parse_manifest(caption_text: str) -> dict:
    """Parse a Telegram caption into a normalized manifest dict.

    Always returns keys: targets, title, caption, hashtags, full_caption,
    raw_text, is_json.
    """
    text = (caption_text or "").strip()
    if text:
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            data = None
        if isinstance(data, dict):
            return _json_manifest(text, data)

    full_caption = text
    return {
        "targets": list(ALL_TARGETS),
        "title": text[:90],
        "caption": text,
        "hashtags": [],
        "full_caption": full_caption,
        "raw_text": text,
        "is_json": False,
    }
