#!/usr/bin/env python3
"""
agent_send.py -- PostPilot v1 agent-side helper (runs on the agent's Linux machine).

Sends a finished, user-approved vertical video to the PostPilot Telegram inbox
bot as a *document* (no recompression), with a JSON manifest in the caption
telling the tool which accounts to post to and what text to use.

Usage:
    python3 agent_send.py --video /path/to/video.mp4 --bot-token <TOKEN> --chat-id <CHAT_ID> \
        --targets tiktok,youtube,instagram,facebook \
        --title "My title" --caption "Post text" --hashtags "#money,#wealth"

    Manifest can also be passed directly:
    python3 agent_send.py --video v.mp4 --bot-token T --chat-id C \
        --manifest '{"targets":["tiktok"],"title":"T","caption":"Hi","hashtags":["#a"]}'

Bot API limits: files up to 50MB via sendDocument. Larger files are rejected
here with a clear error before wasting upload time.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import requests

API = "https://api.telegram.org/bot{token}/{method}"
MAX_BYTES = 50 * 1024 * 1024  # Bot API file limit
VALID_TARGETS = {"tiktok", "youtube", "instagram", "facebook"}


def build_manifest(targets: str, title: str, caption: str, hashtags: str) -> dict:
    target_list = [t.strip().lower() for t in targets.split(",") if t.strip()]
    bad = [t for t in target_list if t not in VALID_TARGETS]
    if bad:
        raise ValueError(f"Invalid targets: {bad}. Valid: {sorted(VALID_TARGETS)}")
    tags = [h.strip() for h in hashtags.split(",") if h.strip()]
    tags = [h if h.startswith("#") else f"#{h}" for h in tags]
    return {
        "targets": target_list,
        "title": title,
        "caption": caption,
        "hashtags": tags,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Send a video to the PostPilot Telegram inbox.")
    ap.add_argument("--video", required=True, help="Path to the .mp4 file")
    ap.add_argument("--bot-token", required=True, help="Telegram bot token")
    ap.add_argument("--chat-id", required=True, help="Target chat id (bot DM / group)")
    ap.add_argument("--manifest", default=None, help="Raw JSON manifest (overrides other fields)")
    ap.add_argument("--targets", default="tiktok,youtube,instagram,facebook")
    ap.add_argument("--title", default="")
    ap.add_argument("--caption", default="")
    ap.add_argument("--hashtags", default="")
    args = ap.parse_args()

    if not os.path.isfile(args.video):
        print(f"ERROR: video not found: {args.video}", file=sys.stderr)
        return 2

    size = os.path.getsize(args.video)
    if size > MAX_BYTES:
        print(
            f"ERROR: file is {size / 1024 / 1024:.1f} MB > 50 MB Bot API limit. "
            "Compress/split the video first.",
            file=sys.stderr,
        )
        return 2

    if args.manifest:
        try:
            manifest = json.loads(args.manifest)
        except json.JSONDecodeError as e:
            print(f"ERROR: invalid --manifest JSON: {e}", file=sys.stderr)
            return 2
    else:
        try:
            manifest = build_manifest(args.targets, args.title, args.caption, args.hashtags)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2

    caption = json.dumps(manifest, ensure_ascii=False)
    if len(caption.encode("utf-8")) > 1024:
        print("ERROR: manifest caption exceeds Telegram's 1024-char caption limit.", file=sys.stderr)
        return 2

    url = API.format(token=args.bot_token, method="sendDocument")
    print(f"Sending {os.path.basename(args.video)} ({size / 1024 / 1024:.1f} MB) ...")
    with open(args.video, "rb") as f:
        r = requests.post(
            url,
            data={"chat_id": args.chat_id, "caption": caption},
            files={"document": (os.path.basename(args.video), f, "video/mp4")},
            timeout=300,
        )
    try:
        data = r.json()
    except ValueError:
        print(f"ERROR: non-JSON response (HTTP {r.status_code}): {r.text[:200]}", file=sys.stderr)
        return 1
    if not data.get("ok"):
        print(f"ERROR: Telegram API: {data}", file=sys.stderr)
        return 1
    print(f"OK: message_id={data['result']['message_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
