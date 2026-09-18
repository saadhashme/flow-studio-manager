"""Telegram Bot API long-poller.

Runs in a QThread. Polls ``getUpdates`` with a 30s long-poll timeout and
downloads accepted videos/documents (Bot API 50MB limit enforced) into the
inbox directory, emitting one ``new_item`` dict per accepted file.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone

import requests
from PySide6.QtCore import QThread, Signal

from .manifest import ALL_TARGETS, parse_manifest

log = logging.getLogger(__name__)

MAX_FILE_SIZE = 50 * 1024 * 1024  # Telegram Bot API limit: 50 MB


class TelegramPoller(QThread):
    """Long-poll a Telegram bot for incoming videos, running in its own thread."""

    new_item = Signal(dict)
    status = Signal(str)
    error = Signal(str)

    def __init__(self, bot_token: str, chat_id: str, inbox_dir: str) -> None:
        super().__init__()
        self.bot_token = bot_token or ""
        self.chat_id = (chat_id or "").strip()
        self.inbox_dir = inbox_dir
        self._stop = False
        self._offset = 0

    def stop(self) -> None:
        """Ask the thread to finish (interrupts the long poll on next tick)."""
        self._stop = True

    # ------------------------------------------------------------------ API
    def _api(self, method: str, **params):
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        resp = requests.post(url, data=params, timeout=45)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error: {payload}")
        return payload.get("result")

    def _download_file(self, file_path: str, dest_path: str) -> None:
        url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
        with requests.get(url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if self._stop:
                        raise InterruptedError("stopping")
                    if chunk:
                        f.write(chunk)

    # ------------------------------------------------------------- handling
    def _unique_name(self, file_name: str) -> str:
        safe = "".join(c if (c.isalnum() or c in "._- ") else "_" for c in file_name).strip() or "file"
        base, dot, ext = safe.rpartition(".")
        if not dot or not base:
            base, ext = safe, ""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{base}_{stamp}{('.' + ext) if ext else ''}"

    def _build_item(self, file_id: str, file_size: int, file_name: str, caption: str) -> dict | None:
        if file_size and file_size > MAX_FILE_SIZE:
            mb = file_size / (1024 * 1024)
            self.error.emit(f"oversize: {file_name} is {mb:.1f} MB, limit 50MB")
            return None
        info = self._api("getFile", file_id=file_id)
        tg_path = (info or {}).get("file_path")
        if not tg_path:
            self.error.emit(f"no file path returned for {file_name}")
            return None
        os.makedirs(self.inbox_dir, exist_ok=True)
        dest_name = self._unique_name(file_name)
        dest_path = os.path.join(self.inbox_dir, dest_name)
        try:
            self._download_file(tg_path, dest_path)
        except InterruptedError:
            try:
                os.unlink(dest_path)
            except OSError:
                pass
            return None

        manifest = parse_manifest(caption or "")
        item = {
            "id": uuid.uuid4().hex,
            "file_path": dest_path,
            "file_name": dest_name,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "manifest": manifest,
            "targets": {
                p: {
                    "enabled": p in manifest["targets"],
                    "status": "pending",
                    "error": "",
                    "scheduled_at": None,
                }
                for p in ALL_TARGETS
            },
        }
        return item

    def _handle_message(self, message: dict) -> None:
        if not message:
            return
        if self.chat_id:
            chat = message.get("chat") or {}
            if str(chat.get("id")) != str(self.chat_id):
                return
        elif not self._offset_warned:
            self.status.emit("Telegram poller: no chat id set, accepting messages from any chat")
            self._offset_warned = True

        file_id = file_size = file_name = None
        if "video" in message:
            v = message["video"]
            file_id, file_size = v.get("file_id"), v.get("file_size", 0)
            file_name = v.get("file_name") or "video.mp4"
        elif "document" in message:
            d = message["document"]
            file_id, file_size = d.get("file_id"), d.get("file_size", 0)
            file_name = d.get("file_name") or "file"
        else:
            return

        caption = message.get("caption") or ""
        try:
            item = self._build_item(file_id, file_size or 0, file_name, caption)
        except Exception as exc:  # keep the poller alive; report and continue
            log.exception("Failed to process Telegram file %s", file_name)
            self.error.emit(f"failed to save {file_name}: {exc}")
            return
        if item:
            self.new_item.emit(item)
            self.status.emit(f"inbox: received {item['file_name']}")

    # ----------------------------------------------------------------- loop
    def run(self) -> None:
        self._offset_warned = False
        if not self.bot_token:
            self.error.emit("Telegram bot token is empty; polling not started")
            return
        backoff = 1.0
        self.status.emit("Telegram poller started")
        while not self._stop:
            try:
                updates = self._api("getUpdates", offset=self._offset, timeout=30, allowed_updates='["message"]')
                backoff = 1.0
            except Exception as exc:
                log.warning("Telegram poll error: %s (retry in %.0fs)", exc, backoff)
                self.status.emit(f"Telegram poll error: {exc}; retrying in {backoff:.0f}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                continue
            for upd in updates or []:
                self._offset = max(self._offset, (upd.get("update_id") or 0) + 1)
                self._handle_message(upd.get("message"))
        self.status.emit("Telegram poller stopped")
