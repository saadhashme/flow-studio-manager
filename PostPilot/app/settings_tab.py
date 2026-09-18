"""Settings tab: Telegram inbox configuration + poller lifecycle.

Modern card-based layout with show/hide password toggle, asynchronous
"Test connection" Telegram API check, live status badge, directory browser,
and a security alert banner.
"""

from __future__ import annotations

import logging
import threading

import requests
from PySide6.QtCore import QMetaObject, Q_ARG, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from inbox import TelegramPoller
from . import theme
from .components import (
    Badge,
    Card,
    CardAlt,
    DangerButton,
    GhostButton,
    PrimaryButton,
    SecondaryButton,
    SectionHeader,
)

log = logging.getLogger(__name__)


class SettingsTab(QWidget):
    """Bot token / chat id / inbox dir + Start/Stop polling + Test Connection."""

    poller_started = Signal(object)

    def __init__(self, config: dict, on_save, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.on_save = on_save
        self._poller: TelegramPoller | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 16, 24, 16)
        root_layout.setSpacing(14)

        # Header
        header = SectionHeader(
            title="Application Settings",
            subtitle="Configure Telegram bot video ingestion and local storage directories",
        )
        root_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        # Centered container for balanced layout on all screen sizes
        scroll_content = QWidget()
        center_box = QHBoxLayout(scroll_content)
        center_box.setContentsMargins(0, 0, 0, 0)

        inner = QWidget()
        inner.setMaximumWidth(880)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 4, 0, 16)
        inner_layout.setSpacing(16)

        tg = config.get("telegram", {}) or {}

        # ---------------------------------- Card 1: Telegram Bot Config
        bot_card = Card()
        bot_layout = QVBoxLayout(bot_card)
        bot_layout.setContentsMargins(20, 18, 20, 18)
        bot_layout.setSpacing(14)

        card1_title = QLabel("Telegram Bot Ingestion")
        card1_title.setObjectName("cardHeader")
        bot_layout.addWidget(card1_title)

        form1 = QFormLayout()
        form1.setSpacing(12)
        form1.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Token row
        token_row = QHBoxLayout()
        token_row.setSpacing(6)
        self.token_edit = QLineEdit(tg.get("bot_token", ""))
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")

        self.show_token_btn = GhostButton("👁")
        self.show_token_btn.setFixedSize(32, 32)
        self.show_token_btn.setToolTip("Show / Hide Bot Token")
        self.show_token_btn.clicked.connect(self._toggle_token_visibility)

        self.test_btn = SecondaryButton("Test Connection")
        self.test_btn.clicked.connect(self._test_connection)

        token_row.addWidget(self.token_edit, 1)
        token_row.addWidget(self.show_token_btn)
        token_row.addWidget(self.test_btn)
        form1.addRow("Bot Token:", token_row)

        # Test result badge
        self.test_badge = Badge("Ready to test", status="neutral")
        self.test_badge.setVisible(False)
        form1.addRow("", self.test_badge)

        # Chat ID row
        self.chat_edit = QLineEdit(str(tg.get("chat_id", "")))
        self.chat_edit.setPlaceholderText("Numeric chat ID (e.g. 123456789) — leave blank to accept any chat")
        form1.addRow("Chat ID:", self.chat_edit)

        bot_layout.addLayout(form1)

        # Security warning callout
        security_callout = CardAlt()
        sec_layout = QHBoxLayout(security_callout)
        sec_layout.setContentsMargins(12, 10, 12, 10)
        sec_layout.setSpacing(10)
        sec_icon = QLabel("🔒")
        sec_icon.setStyleSheet("font-size: 16px; background: transparent;")
        sec_layout.addWidget(sec_icon)
        sec_text = QLabel("Security Notice: Never share screenshots or recordings of this tab — it contains your Bot Token.")
        sec_text.setStyleSheet(f"color: {theme.STATUS_WARNING}; font-size: 12px; font-weight: 500; background: transparent;")
        sec_text.setWordWrap(True)
        sec_layout.addWidget(sec_text, 1)
        bot_layout.addWidget(security_callout)

        inner_layout.addWidget(bot_card)

        # ---------------------------------- Card 2: Inbox & Poller Status
        inbox_card = Card()
        inbox_layout = QVBoxLayout(inbox_card)
        inbox_layout.setContentsMargins(20, 18, 20, 18)
        inbox_layout.setSpacing(14)

        card2_title = QLabel("Local Storage & Poller Automation")
        card2_title.setObjectName("cardHeader")
        inbox_layout.addWidget(card2_title)

        form2 = QFormLayout()
        form2.setSpacing(12)
        form2.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Directory row
        inbox_row = QHBoxLayout()
        inbox_row.setSpacing(8)
        self.inbox_edit = QLineEdit(config.get("inbox_dir", ""))
        self.inbox_edit.setPlaceholderText("~/PostPilot/inbox (defaults to user home directory)")
        browse_btn = SecondaryButton("📁 Browse...")
        browse_btn.clicked.connect(self._browse)
        inbox_row.addWidget(self.inbox_edit, 1)
        inbox_row.addWidget(browse_btn)
        form2.addRow("Inbox Directory:", inbox_row)

        # Poller live status
        poller_status_row = QHBoxLayout()
        poller_status_row.setSpacing(12)
        self.poll_badge = Badge("Poller: Stopped", status="stopped")
        poller_status_row.addWidget(self.poll_badge)
        poller_status_row.addStretch(1)

        self.poll_btn = PrimaryButton("Start Inbox Polling")
        self.poll_btn.clicked.connect(self._toggle_polling)
        poller_status_row.addWidget(self.poll_btn)
        form2.addRow("Inbox Listener:", poller_status_row)

        inbox_layout.addLayout(form2)
        inner_layout.addWidget(inbox_card)

        # ---------------------------------- Save Settings Action Bar
        action_bar = QHBoxLayout()
        self.save_btn = PrimaryButton("Save Settings")
        self.save_btn.clicked.connect(self._save)
        action_bar.addWidget(self.save_btn)
        action_bar.addStretch(1)
        inner_layout.addLayout(action_bar)

        center_box.addWidget(inner)
        scroll.setWidget(scroll_content)
        root_layout.addWidget(scroll, 1)

    # ------------------------------------------------------------- UI Helpers
    def _toggle_token_visibility(self) -> None:
        if self.token_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.token_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_token_btn.setText("🔒")
        else:
            self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_token_btn.setText("👁")

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Choose inbox directory",
                                             self.inbox_edit.text() or "")
        if d:
            self.inbox_edit.setText(d)

    def _test_connection(self) -> None:
        token = self.token_edit.text().strip()
        if not token:
            self.test_badge.setVisible(True)
            self.test_badge.set_status("danger", "Bot token is empty")
            return

        self.test_badge.setVisible(True)
        self.test_badge.set_status("warning", "Testing Telegram API...")
        self.test_btn.setEnabled(False)

        def worker():
            try:
                url = f"https://api.telegram.org/bot{token}/getMe"
                resp = requests.get(url, timeout=6)
                data = resp.json()
                if resp.status_code == 200 and data.get("ok"):
                    bot_user = data.get("result", {}).get("username", "bot")
                    msg = f"Connected: @{bot_user}"
                    status = "success"
                else:
                    err = data.get("description", f"HTTP {resp.status_code}")
                    msg = f"Failed: {err}"
                    status = "danger"
            except Exception as e:
                msg = f"Network Error: {type(e).__name__}"
                status = "danger"

            QMetaObject.invokeMethod(
                self, "_on_test_finished", Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, status), Q_ARG(str, msg),
            )

        threading.Thread(target=worker, daemon=True).start()

    @Slot(str, str)
    def _on_test_finished(self, status: str, msg: str) -> None:
        self.test_btn.setEnabled(True)
        self.test_badge.set_status(status, msg)

    def _save(self) -> None:
        cfg = {
            "telegram": {
                "bot_token": self.token_edit.text().strip(),
                "chat_id": self.chat_edit.text().strip(),
            },
            "inbox_dir": self.inbox_edit.text().strip(),
        }
        try:
            self.on_save(cfg)
            log.info("Settings saved successfully")
            self.save_btn.setText("Settings Saved ✓")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1800, lambda: self.save_btn.setText("Save Settings"))
        except Exception:
            log.exception("Failed to save settings")
            self.save_btn.setText("Save Failed ✗")

    def current_settings(self) -> dict:
        return {
            "bot_token": self.token_edit.text().strip(),
            "chat_id": self.chat_edit.text().strip(),
            "inbox_dir": self.inbox_edit.text().strip(),
        }

    # -------------------------------------------------------------- Poller
    @property
    def poller(self) -> TelegramPoller | None:
        return self._poller

    def _toggle_polling(self) -> None:
        if self._poller is not None and self._poller.isRunning():
            self.stop_polling()
        else:
            self.start_polling()

    def start_polling(self) -> None:
        from accounts import inbox_dir_for

        s = self.current_settings()
        inbox_dir = s["inbox_dir"] or inbox_dir_for({"inbox_dir": ""})
        if not s["bot_token"]:
            log.warning("Cannot start polling: bot token is empty")
            self.poll_badge.set_status("danger", "Bot token is empty")
            return

        poller = TelegramPoller(s["bot_token"], s["chat_id"], inbox_dir)
        poller.status.connect(self._on_poller_status)
        poller.error.connect(self._on_poller_error)
        self._poller = poller
        poller.start()

        self.poll_btn.setText("Stop Inbox Polling")
        self.poll_btn.setObjectName("dangerBtn")
        self.poll_btn.setStyle(self.poll_btn.style())
        self.poll_badge.set_status("running", "Listening for videos...")
        log.info("Inbox polling started")
        self.poller_started.emit(poller)

    @Slot(str)
    def _on_poller_status(self, msg: str) -> None:
        self.poll_badge.set_status("running", f"Poller: {msg}")
        log.info("poller: %s", msg)

    @Slot(str)
    def _on_poller_error(self, msg: str) -> None:
        self.poll_badge.set_status("danger", f"Error: {msg}")
        log.error("poller: %s", msg)

    def stop_polling(self) -> None:
        poller = self._poller
        self._poller = None
        if poller is not None:
            try:
                poller.status.disconnect()
                poller.error.disconnect()
            except Exception:
                pass
            poller.stop()
            poller.wait(5000)

        self.poll_btn.setText("Start Inbox Polling")
        self.poll_btn.setObjectName("primaryBtn")
        self.poll_btn.setStyle(self.poll_btn.style())
        self.poll_badge.set_status("stopped", "Poller: Stopped")
        log.info("Inbox polling stopped")
