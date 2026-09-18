"""Main window: tab widget (Accounts / Upload Queue / Settings) + console log dock.

Applies the centralized dark theme, manages top-level navigation,
and orchestrates component lifecycle and clean shutdown.
"""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .accounts_tab import AccountsTab, BrowserManager
from .components import Badge
from .log_view import LogView, setup_logging
from .queue_tab import QueueTab
from .settings_tab import SettingsTab

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level window wiring config, tabs, scheduler, poller, and theme."""

    def __init__(self, config: dict, on_save, browser_manager: BrowserManager,
                 scheduler, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PostPilot v1 – Social Video Distribution")
        self.resize(1320, 880)
        self.setMinimumSize(1100, 700)

        # Set Window Corner Icon
        assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        icon_candidates = [
            os.path.join(assets_dir, "icon.ico"),
            os.path.join(assets_dir, "icon.png"),
        ]
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
            icon_candidates.insert(0, os.path.join(meipass, "app", "assets", "icon.ico"))
            icon_candidates.insert(1, os.path.join(meipass, "app", "assets", "icon.png"))

        for ic_path in icon_candidates:
            if os.path.exists(ic_path):
                win_icon = QIcon(ic_path)
                if not win_icon.isNull():
                    self.setWindowIcon(win_icon)
                    break

        self._on_save = on_save
        self.bm = browser_manager
        self.scheduler = scheduler

        # Apply global application stylesheet
        self.setStyleSheet(theme.get_application_stylesheet())

        # Root Central Widget
        central = QWidget()
        central.setObjectName("centralWidget")
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(14, 12, 14, 8)
        central_layout.setSpacing(10)

        # --------------------------------------------- Top App Brand Bar
        top_bar = QFrame()
        top_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.BG_SURFACE};
                border: 1px solid {theme.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 6, 12, 6)
        top_layout.setSpacing(10)

        # Top Bar Brand Logo Image
        logo_png = os.path.join(assets_dir, "icon.png")
        if not os.path.exists(logo_png):
            logo_png = os.path.join(assets_dir, "icon.ico")

        logo_lbl = QLabel()
        if os.path.exists(logo_png):
            pm = QPixmap(logo_png)
            if not pm.isNull():
                scaled_pm = pm.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                logo_lbl.setPixmap(scaled_pm)
        if not logo_lbl.pixmap():
            logo_lbl.setText("PP")
            logo_lbl.setStyleSheet(f"color: {theme.ACCENT_PRIMARY}; font-size: 18px; font-weight: bold; background: transparent;")
        else:
            logo_lbl.setStyleSheet("background: transparent;")
        top_layout.addWidget(logo_lbl)

        brand_lbl = QLabel("PostPilot")
        brand_lbl.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: 15px; font-weight: 700; background: transparent;")
        top_layout.addWidget(brand_lbl)

        ver_badge = Badge("v1.0 Pro", status="info")
        top_layout.addWidget(ver_badge)

        top_layout.addStretch(1)

        info_lbl = QLabel("Multi-Platform Vertical Video Ingestion & CDP Auto-Upload")
        info_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px; background: transparent;")
        top_layout.addWidget(info_lbl)

        central_layout.addWidget(top_bar)

        # ---------------------------------------------------- Main Tabs
        self.tabs = QTabWidget()
        self.accounts_tab = AccountsTab(config, self._save_accounts, self.bm)
        self.queue_tab = QueueTab(scheduler, scheduler.queue)
        self.settings_tab = SettingsTab(config, self._save_settings)

        self.tabs.addTab(self.accounts_tab, " 🌐 Accounts & Browsers ")
        self.tabs.addTab(self.queue_tab, " 📋 Upload Queue ")
        self.tabs.addTab(self.settings_tab, " ⚙️ Settings & Ingestion ")

        central_layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        # --------------------------------------------- Console Log Dock
        self.log_view = LogView()
        self.dock = QDockWidget("Console Activity", self)
        self.dock.setWidget(self.log_view)
        self.dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock)
        self.resizeDocks([self.dock], [160], Qt.Orientation.Vertical)
        setup_logging(self.log_view)

    # ------------------------------------------------------------- wiring
    def connect_poller(self) -> None:
        """Wire each new TelegramPoller's new_item signal into the queue tab."""
        self.settings_tab.poller_started.connect(
            lambda poller: poller.new_item.connect(self.queue_tab.on_new_item))

    # -------------------------------------------------------------- saves
    def _save_accounts(self, partial: dict) -> None:
        self._on_save(partial)

    def _save_settings(self, partial: dict) -> None:
        self._on_save(partial)

    # -------------------------------------------------------------- close
    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        log.info("Shutting down...")
        try:
            self.settings_tab.stop_polling()
        except Exception:
            log.exception("Error stopping poller")
        try:
            self.scheduler.stop()
        except Exception:
            log.exception("Error stopping scheduler")
        try:
            self.bm.shutdown()
        except Exception:
            log.exception("Error shutting down browsers")
        super().closeEvent(event)
        event.accept()
