"""Account and app configuration storage for PostPilot v1.

Configuration lives in a plain JSON file (``config.json`` next to this
package). No credentials are hardcoded anywhere: proxy credentials and the
Telegram bot token are filled in by the user in the Settings/Accounts tabs
and only ever persisted to the local config file.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path

# Platforms in fixed order; each maps to a config slot and a Chrome profile.
PLATFORMS = ("facebook", "instagram", "youtube", "tiktok")

# Default display names shown in the Accounts tab.
_DEFAULT_NAMES = {
    "facebook": "The Wealth Code (Page)",
    "instagram": "Instagram",
    "youtube": "YouTube",
    "tiktok": "TikTok",
}


def _default_account(i: int, platform: str) -> dict:
    return {
        "id": f"acc{i + 1}",
        "platform": platform,
        "name": _DEFAULT_NAMES[platform],
        "proxy": {
            "type": "http",
            "host": "",
            "port": 0,
            "username": "",
            "password": "",
        },
        "profile_dir": "",
    }


DEFAULT_CONFIG: dict = {
    "accounts": [_default_account(i, p) for i, p in enumerate(PLATFORMS)],
    "telegram": {"bot_token": "", "chat_id": ""},
    "inbox_dir": "",
}

# Where user data lives on the user's Windows laptop.
APP_DIR = Path(os.path.expanduser("~/PostPilot"))
DEFAULT_INBOX_DIR = APP_DIR / "inbox"


def config_path() -> Path:
    """Path of the JSON config file (next to this package's parent dir)."""
    return Path(__file__).resolve().parent.parent / "config.json"


def _merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* over *base* (non-dict values replaced)."""
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_config() -> dict:
    """Load config.json, merging stored values over DEFAULT_CONFIG."""
    path = config_path()
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stored = {}
        cfg = _merge(DEFAULT_CONFIG, stored) if isinstance(stored, dict) else copy.deepcopy(DEFAULT_CONFIG)
    else:
        cfg = copy.deepcopy(DEFAULT_CONFIG)

    # Guarantee exactly one well-formed slot per platform.
    accounts = cfg.get("accounts")
    if not isinstance(accounts, list) or len(accounts) != len(PLATFORMS):
        accounts = []
    by_platform = {}
    for acc in accounts:
        if isinstance(acc, dict) and acc.get("platform") in PLATFORMS:
            by_platform.setdefault(acc["platform"], acc)
    cfg["accounts"] = [
        _merge(_default_account(i, p), by_platform.get(p, {}))
        for i, p in enumerate(PLATFORMS)
    ]
    return cfg


def save_config(cfg: dict) -> None:
    """Atomically write *cfg* to config.json (write temp file, then replace)."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".config", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def profile_dir_for(account_id: str) -> str:
    """Default Chrome profile directory for an account id."""
    return str(APP_DIR / "profiles" / account_id)


def inbox_dir_for(cfg: dict) -> str:
    """Resolve the inbox dir; falls back to ~/PostPilot/inbox when empty."""
    raw = (cfg.get("inbox_dir") or "").strip()
    return raw or str(DEFAULT_INBOX_DIR)
