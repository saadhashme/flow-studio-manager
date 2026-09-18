"""Upload scheduler for PostPilot v1.

``QueueStore`` holds the queue items (owned by the UI thread). ``Scheduler``
runs in a QThread and every 5 seconds picks up due targets (``pending`` or
``scheduled`` with reached time), uploads via the platform uploader module,
and updates target status. Control methods (``post_now``, ``schedule``,
``skip``) are called from the UI thread and take effect on the worker's
next 5s tick.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from PySide6.QtCore import QObject, QThread, Signal

log = logging.getLogger(__name__)

PENDING = "pending"
SCHEDULED = "scheduled"
UPLOADING = "uploading"
DONE = "done"
FAILED = "failed"
SKIPPED = "skipped"


def _lazy_get_uploader(platform: str):
    """Import the uploaders package lazily (it lives outside our tree)."""
    try:
        from uploaders import get_uploader  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"uploaders package unavailable: {exc}") from exc
    return get_uploader(platform)


class QueueStore:
    """Thread-safe in-memory store for inbox/upload queue items."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}
        self._lock = threading.Lock()

    def add_item(self, item: dict) -> None:
        with self._lock:
            self.items[item["id"]] = item

    def get(self, item_id: str) -> dict | None:
        with self._lock:
            return self.items.get(item_id)

    def all(self) -> list[dict]:
        with self._lock:
            return list(self.items.values())

    def remove(self, item_id: str) -> dict | None:
        with self._lock:
            return self.items.pop(item_id, None)


class _SchedulerThread(QThread):
    """Worker thread: runs the 5s polling loop directly in run().

    Using run() instead of a started->slot hop avoids relying on the
    worker thread's event loop.
    """

    def __init__(self, scheduler: "Scheduler") -> None:
        super().__init__()
        self._scheduler = scheduler
        self._stop = False

    def run(self) -> None:
        log.info("Scheduler loop started")
        while not self._stop:
            try:
                self._scheduler._process_due()
            except Exception:
                log.exception("Scheduler tick failed")
            time.sleep(5)
        log.info("Scheduler loop stopped")

    def request_stop(self) -> None:
        self._stop = True


class Scheduler(QObject):
    """Owns the scheduler QThread and exposes thread-safe control methods."""

    item_updated = Signal()

    def __init__(self, get_cdp, get_item, get_account, logs_dir: str) -> None:
        super().__init__()
        self.get_cdp = get_cdp          # platform -> CDPClient | None
        self.get_item = get_item        # item_id -> dict | None
        self.get_account = get_account  # platform -> account dict | None
        self.logs_dir = logs_dir
        self.queue = QueueStore()

        self._thread = _SchedulerThread(self)

    # ---------------------------------------------------------- lifecycle
    def start(self) -> None:
        if not self._thread.isRunning():
            self._thread.start()

    def stop(self) -> None:
        if self._thread.isRunning():
            self._thread.request_stop()
            self._thread.quit()
            self._thread.wait(8000)

    # ------------------------------------------------- thread-safe control
    def post_now(self, item_id: str, target: str) -> None:
        """Mark target pending immediately (worker uploads it on next tick)."""
        self._set_target(item_id, target, {"status": PENDING, "error": "", "scheduled_at": None})

    def schedule(self, item_id: str, target: str, qdatetime) -> None:
        """Schedule target for a QDateTime (stored as UTC ISO string)."""
        try:
            iso = qdatetime.toUTC().toString("yyyy-MM-ddTHH:mm:ss") + "Z"
        except Exception:
            iso = ""
        self._set_target(item_id, target, {"status": SCHEDULED, "error": "", "scheduled_at": iso})

    def skip(self, item_id: str, target: str) -> None:
        self._set_target(item_id, target, {"status": SKIPPED})

    def _set_target(self, item_id: str, target: str, patch: dict) -> None:
        item = self.queue.get(item_id)
        if not item:
            return
        tgt = (item.get("targets") or {}).get(target)
        if not tgt:
            return
        tgt.update(patch)
        self.item_updated.emit()

    # ------------------------------------------------------------ worker
    def _due(self, tgt: dict) -> bool:
        status = tgt.get("status")
        if status == PENDING:
            return True
        if status == SCHEDULED:
            at = tgt.get("scheduled_at")
            if not at:
                return False
            try:
                when = datetime.fromisoformat(at.replace("Z", "+00:00"))
            except ValueError:
                return False
            return when <= datetime.now(timezone.utc)
        return False

    def _process_due(self) -> None:
        for item in self.queue.all():
            for platform, tgt in (item.get("targets") or {}).items():
                if not tgt.get("enabled"):
                    continue
                if tgt.get("status") == UPLOADING:
                    continue
                if not self._due(tgt):
                    continue

                cdp = self.get_cdp(platform)
                if cdp is None:
                    tgt["status"] = tgt.get("status") or PENDING
                    tgt["error"] = f"browser not open for {platform}"
                    self.item_updated.emit()
                    continue

                account = self.get_account(platform)
                tgt["status"] = UPLOADING
                tgt["error"] = ""
                self.item_updated.emit()
                # Uploaders expect a FLAT item dict (title/caption/hashtags/full_caption
                # at top level); the queue item nests these under item["manifest"].
                # Merge them here so every platform module gets what it needs.
                manifest = item.get("manifest") or {}
                upload_item = dict(item)
                upload_item.update(
                    {
                        "title": manifest.get("title", ""),
                        "caption": manifest.get("caption", ""),
                        "hashtags": manifest.get("hashtags", []),
                        "full_caption": manifest.get(
                            "full_caption", manifest.get("caption", "")
                        ),
                    }
                )
                try:
                    ok, message = _lazy_get_uploader(platform).upload(cdp, upload_item, account)
                except Exception as exc:
                    log.exception("Upload raised for %s", platform)
                    ok, message = False, str(exc)
                tgt["status"] = DONE if ok else FAILED
                tgt["error"] = "" if ok else (message or "upload failed")
                self.item_updated.emit()
