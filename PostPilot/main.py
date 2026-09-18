"""PostPilot v1 entry point.

Windows desktop app: 4 embedded Chrome browsers (one per social account),
Telegram inbox for pre-approved videos, and a scheduler that auto-uploads
them per platform.
"""

from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger(__name__)


def _make_on_save(config: dict):
    """Return a save callback that merges a partial dict into the config."""
    from accounts import save_config

    def on_save(partial: dict) -> None:
        config.update(partial)
        save_config(config)
        log.info("Configuration saved")

    return on_save


def main() -> int:
    # Make sibling packages importable (script may be run from any cwd).
    base = os.path.dirname(os.path.abspath(__file__))
    if base not in sys.path:
        sys.path.insert(0, base)

    # Ensure Windows taskbar displays the custom app icon rather than generic python.exe
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = "museai.postpilot.v1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            log.debug("Could not set AppUserModelID: %s", e)

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from accounts import inbox_dir_for, load_config
    from app import BrowserManager, MainWindow
    from scheduler import Scheduler

    config = load_config()

    app = QApplication(sys.argv)
    app.setApplicationName("PostPilot v1")

    # Locate application icon (works for dev run and PyInstaller bundle)
    icon_candidates = [
        os.path.join(base, "app", "assets", "icon.ico"),
        os.path.join(base, "app", "assets", "icon.png"),
        os.path.join(base, "icon.ico"),
    ]
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        icon_candidates.insert(0, os.path.join(meipass, "app", "assets", "icon.ico"))
        icon_candidates.insert(1, os.path.join(meipass, "app", "assets", "icon.png"))
        icon_candidates.insert(2, os.path.join(meipass, "icon.ico"))

    app_icon = None
    for cand in icon_candidates:
        if os.path.exists(cand):
            app_icon = QIcon(cand)
            if not app_icon.isNull():
                break

    if app_icon and not app_icon.isNull():
        app.setWindowIcon(app_icon)

    on_save = _make_on_save(config)
    browser_manager = BrowserManager()

    def get_cdp(platform: str):
        return browser_manager.get_cdp(platform)

    def get_item(item_id: str):
        return scheduler.queue.get(item_id)

    def get_account(platform: str):
        # Look up fresh on every call: the user may edit accounts in the
        # Accounts tab and save without restarting the app.
        return {a.get("platform"): a for a in config.get("accounts", [])}.get(platform)

    logs_dir = os.path.join(os.path.expanduser("~/PostPilot"), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    scheduler = Scheduler(get_cdp=get_cdp, get_item=get_item,
                          get_account=get_account, logs_dir=logs_dir)

    window = MainWindow(config, on_save, browser_manager, scheduler)
    if app_icon and not app_icon.isNull():
        window.setWindowIcon(app_icon)

    window.connect_poller()

    inbox_dir = inbox_dir_for(config)
    os.makedirs(inbox_dir, exist_ok=True)

    scheduler.start()
    window.show()
    log.info("PostPilot v1 started")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
