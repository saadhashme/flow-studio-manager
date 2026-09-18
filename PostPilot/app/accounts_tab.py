"""Accounts tab: Account profile cards with proxy settings and dedicated Browser Studio.

Features:
  * 4 per-platform account cards (TikTok, YouTube, Instagram, Facebook) with
    collapsible proxy configuration, status badges, and dual launch modes.
  * Dedicated full-width Browser Studio with auto-resizing, multi-session tabs,
    zero WinAPI title-bar artifacts, and 100% edge-to-edge embedding.
  * Instant Pop-out / Dock capability: switch between docked Studio mode and
    native desktop window mode with one click.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from accounts import PLATFORMS, profile_dir_for
from . import theme
from .components import (
    Badge,
    Card,
    CardAlt,
    CollapsibleBox,
    DangerButton,
    GhostButton,
    PlatformChip,
    PrimaryButton,
    SecondaryButton,
    SectionHeader,
)

log = logging.getLogger(__name__)

PLATFORM_URLS = {
    "tiktok": "https://www.tiktok.com/",
    "youtube": "https://www.youtube.com/",
    "instagram": "https://www.instagram.com/",
    "facebook": "https://www.facebook.com/",
}

DEBUG_PORTS = {"facebook": 9331, "instagram": 9332, "youtube": 9333, "tiktok": 9334}

PROXY_TYPES = ("http", "https", "socks5")


# ===================================================================== #
# Browser Manager
# ===================================================================== #
class BrowserManager(QObject):
    """Owns ChromeHost instances per platform slot; manages CDP and embedding."""

    # Emits (platform, is_running, is_embedded)
    browser_state_changed = Signal(str, bool, bool)
    active_session_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hosts: dict[str, object] = {}
        self._containers: dict[str, QWidget] = {}
        self._cdp: dict[str, object] = {}
        self._acc_platform: dict[str, str] = {}
        self._active_platform: str = ""

    # --------------------------------------------------- Container registry
    def register_container(self, platform: str, container: QWidget) -> None:
        self._containers[platform] = container

    def get_container(self, platform: str) -> QWidget | None:
        return self._containers.get(platform)

    # --------------------------------------------------------------- State
    def is_running(self, platform: str) -> bool:
        host = self._hosts.get(platform)
        if host is None:
            return False
        try:
            return bool(host.is_running())
        except Exception:
            return False

    def is_embedded(self, platform: str) -> bool:
        host = self._hosts.get(platform)
        if host is None:
            return False
        return bool(getattr(host, "is_embedded", False))

    def active_platform(self) -> str:
        return self._active_platform

    def set_active_platform(self, platform: str) -> None:
        self._active_platform = platform
        self.active_session_changed.emit(platform)

    def running_platforms(self) -> list[str]:
        return [p for p in self._hosts if self.is_running(p)]

    # -------------------------------------------------------------- Launch
    def open_browser(self, account: dict, embed: bool = True) -> bool:
        """Launch Chrome for account. If embed=True, docks into registered container."""
        platform = account.get("platform", "")
        acc_id = account.get("id", "")
        if acc_id:
            self._acc_platform[acc_id] = platform

        self.close_platform(platform)

        try:
            from browser.chrome import ChromeHost
        except Exception as exc:
            log.error("browser package unavailable: %s", exc)
            return False

        proxy_cfg = account.get("proxy") or {}
        proxy = None
        if proxy_cfg.get("host"):
            proxy = {
                "type": proxy_cfg.get("type") or "http",
                "host": proxy_cfg.get("host"),
                "port": int(proxy_cfg.get("port") or 0),
                "username": proxy_cfg.get("username") or "",
                "password": proxy_cfg.get("password") or "",
            }

        profile_dir = account.get("profile_dir") or profile_dir_for(account.get("id", ""))
        app_url = PLATFORM_URLS.get(platform, "https://www.google.com/")
        debug_port = DEBUG_PORTS.get(platform, 9331)

        try:
            host = ChromeHost(
                profile_dir=profile_dir,
                proxy=proxy,
                app_url=app_url,
                debug_port=debug_port,
                width=1200,
                height=800,
            )
            ok = host.launch()
            if not ok:
                log.error("ChromeHost.launch() failed for %s", platform)
                self.browser_state_changed.emit(platform, False, False)
                return False

            self._hosts[platform] = host
            self._active_platform = platform

            if embed:
                container = self._containers.get(platform)
                if container is not None:
                    container.show()
                    # Let Qt process any pending layout events before embedding
                    host.embed_into(int(container.winId()))
                    self.resize(platform, container.width(), container.height())

            log.info("Browser opened for %s (embedded=%s)", platform, embed)
            self.browser_state_changed.emit(platform, True, embed)
            self.active_session_changed.emit(platform)
            return True

        except Exception:
            log.exception("Failed to open browser for %s", platform)
            self.browser_state_changed.emit(platform, False, False)
            return False

    # ------------------------------------------------------------- Pop / Dock
    def pop_out(self, platform: str) -> bool:
        """Detach Chrome from container into a standalone desktop window."""
        host = self._hosts.get(platform)
        if host is None:
            return False
        try:
            ok = host.detach()
            if ok:
                self.browser_state_changed.emit(platform, True, False)
            return ok
        except Exception:
            log.exception("Failed to pop out browser for %s", platform)
            return False

    def dock_into(self, platform: str) -> bool:
        """Dock Chrome back into the registered Qt container."""
        host = self._hosts.get(platform)
        container = self._containers.get(platform)
        if host is None or container is None:
            return False
        try:
            container.show()
            ok = host.embed_into(int(container.winId()))
            if ok:
                self.resize(platform, container.width(), container.height())
                self.browser_state_changed.emit(platform, True, True)
                self.active_session_changed.emit(platform)
            return ok
        except Exception:
            log.exception("Failed to dock browser for %s", platform)
            return False

    # ------------------------------------------------------ Navigation helpers
    def reload_page(self, platform: str) -> bool:
        host = self._hosts.get(platform)
        if host is None:
            return False
        try:
            return bool(host.reload())
        except Exception:
            return False

    def navigate_home(self, platform: str) -> bool:
        host = self._hosts.get(platform)
        if host is None:
            return False
        url = PLATFORM_URLS.get(platform, "https://www.google.com/")
        try:
            return bool(host.navigate(url))
        except Exception:
            return False

    # ------------------------------------------------------------- Teardown
    def close_browser(self, acc_id: str) -> None:
        platform = self._acc_platform.get(acc_id)
        if platform:
            self.close_platform(platform)

    def close_platform(self, platform: str) -> None:
        host = self._hosts.pop(platform, None)
        self._cdp.pop(platform, None)
        if host is not None:
            try:
                host.terminate()
            except Exception:
                log.exception("Error terminating browser for %s", platform)
            log.info("Browser closed for %s", platform)

        self.browser_state_changed.emit(platform, False, False)
        if self._active_platform == platform:
            running = self.running_platforms()
            self._active_platform = running[0] if running else ""
            self.active_session_changed.emit(self._active_platform)

    def shutdown(self) -> None:
        for platform in list(self._hosts):
            self.close_platform(platform)

    # ----------------------------------------------------------------- CDP
    def get_cdp(self, platform: str):
        """Return a connected CDPClient for *platform*, or None."""
        host = self._hosts.get(platform)
        if host is None:
            return None
        try:
            if not host.is_running():
                self._hosts.pop(platform, None)
                self.browser_state_changed.emit(platform, False, False)
                return None
        except Exception:
            return None

        client = self._cdp.get(platform)
        if client is not None:
            return client

        try:
            from browser.cdp import CDPClient
        except Exception as exc:
            log.error("browser.cdp unavailable: %s", exc)
            return None

        try:
            client = CDPClient(host.cdp_port)
            client.connect()
        except Exception as exc:
            log.warning("CDP connect failed for %s: %s", platform, exc)
            return None

        self._cdp[platform] = client
        return client

    # -------------------------------------------------------------- Resize
    def resize(self, platform: str, w: int | None = None, h: int | None = None) -> None:
        host = self._hosts.get(platform)
        container = self._containers.get(platform)
        if host is None or container is None:
            return
        width = w if w is not None else container.width()
        height = h if h is not None else container.height()
        if width <= 0 or height <= 0:
            return
        try:
            host.resize_embedded(width, height)
        except Exception:
            log.exception("Resize failed for %s", platform)


# ===================================================================== #
# Embedded Browser Viewport Container
# ===================================================================== #
class EmbeddedBrowserContainer(QWidget):
    """Dedicated widget hosting the embedded Chrome HWND with live auto-resizing."""

    def __init__(self, platform: str, browser_manager: BrowserManager,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.platform = platform
        self.bm = browser_manager
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(480)
        self.setStyleSheet("""
            QWidget {
                background-color: #05070B;
                border: 1px solid #1E2430;
                border-radius: 8px;
            }
        """)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self.bm.resize(self.platform, self.width(), self.height())

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Deferred resize ensures Qt's layout engine has finalized geometry
        QTimer.singleShot(60, lambda: self.bm.resize(self.platform, self.width(), self.height()))


# ===================================================================== #
# Account Card
# ===================================================================== #
class _AccountCard(Card):
    """Clean, balanced account card with proxy settings and dual launch actions."""

    def __init__(self, account: dict, browser_manager: BrowserManager,
                 on_open_studio=None, on_launch_window=None, on_save_single=None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.account = account
        self.bm = browser_manager
        self.on_open_studio = on_open_studio
        self.on_launch_window = on_launch_window
        self.on_save_single = on_save_single

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet(f"""
            _AccountCard {{
                background-color: {theme.BG_SURFACE};
                border: 1px solid {theme.BORDER_SUBTLE};
                border-radius: 10px;
            }}
        """)

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        # ------------------------------------------------ Header Row
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        platform = account.get("platform", "")
        self.chip = PlatformChip(platform)
        header_row.addWidget(self.chip)

        self.slot_label = QLabel(f"Slot {account.get('id', '')}")
        self.slot_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px; font-weight: 600;")
        header_row.addWidget(self.slot_label)

        header_row.addStretch(1)

        self.status_badge = Badge("Closed", status="closed")
        header_row.addWidget(self.status_badge)
        card_layout.addLayout(header_row)

        # ------------------------------------------ Platform & Name Form
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.platform_combo = QComboBox()
        self.platform_combo.addItems(list(PLATFORMS))
        self.platform_combo.setCurrentText(platform)
        self.platform_combo.currentTextChanged.connect(self._on_platform_changed)
        form.addRow("Platform:", self.platform_combo)

        self.name_edit = QLineEdit(account.get("name", ""))
        self.name_edit.setPlaceholderText("Account display name (e.g. Channel / Page)")
        form.addRow("Display Name:", self.name_edit)
        card_layout.addLayout(form)

        # --------------------------------------------- Proxy Summary Pill
        proxy = account.get("proxy") or {}
        proxy_row = QHBoxLayout()
        proxy_row.setSpacing(8)

        proxy_title = QLabel("Proxy:")
        proxy_title.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px; font-weight: 500;")
        proxy_row.addWidget(proxy_title)

        self.proxy_summary = QLabel(self._format_proxy_summary(proxy))
        self.proxy_summary.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT_SECONDARY};
                background-color: {theme.BG_INPUT};
                border: 1px solid {theme.BORDER_SUBTLE};
                border-radius: 5px;
                padding: 3px 8px;
                font-family: monospace;
                font-size: 11px;
            }}
        """)
        proxy_row.addWidget(self.proxy_summary)
        proxy_row.addStretch(1)
        card_layout.addLayout(proxy_row)

        # ------------------------------------- Collapsible Proxy Settings
        self.proxy_collapsible = CollapsibleBox(title="Proxy Configuration")
        proxy_form = QGridLayout()
        proxy_form.setContentsMargins(8, 8, 8, 8)
        proxy_form.setSpacing(8)

        proxy_form.addWidget(QLabel("Type:"), 0, 0)
        self.proxy_type = QComboBox()
        self.proxy_type.addItems(list(PROXY_TYPES))
        self.proxy_type.setCurrentText(proxy.get("type") or "http")
        self.proxy_type.currentTextChanged.connect(self._update_proxy_summary)
        proxy_form.addWidget(self.proxy_type, 0, 1)

        proxy_form.addWidget(QLabel("Host:"), 0, 2)
        self.proxy_host = QLineEdit(proxy.get("host") or "")
        self.proxy_host.setPlaceholderText("IP or hostname")
        self.proxy_host.textChanged.connect(self._update_proxy_summary)
        proxy_form.addWidget(self.proxy_host, 0, 3)

        proxy_form.addWidget(QLabel("Port:"), 0, 4)
        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(0, 65535)
        self.proxy_port.setValue(int(proxy.get("port") or 0))
        self.proxy_port.valueChanged.connect(self._update_proxy_summary)
        proxy_form.addWidget(self.proxy_port, 0, 5)

        proxy_form.addWidget(QLabel("User:"), 1, 0)
        self.proxy_user = QLineEdit(proxy.get("username") or "")
        self.proxy_user.setPlaceholderText("Optional user")
        proxy_form.addWidget(self.proxy_user, 1, 1, 1, 2)

        proxy_form.addWidget(QLabel("Pass:"), 1, 3)
        pass_box = QHBoxLayout()
        pass_box.setSpacing(4)
        self.proxy_pass = QLineEdit(proxy.get("password") or "")
        self.proxy_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.proxy_pass.setPlaceholderText("Optional pass")

        self.show_pass_btn = GhostButton("👁")
        self.show_pass_btn.setFixedSize(28, 28)
        self.show_pass_btn.setToolTip("Show / hide password")
        self.show_pass_btn.clicked.connect(self._toggle_pass_visibility)
        pass_box.addWidget(self.proxy_pass, 1)
        pass_box.addWidget(self.show_pass_btn)
        proxy_form.addLayout(pass_box, 1, 4, 1, 2)

        self.proxy_collapsible.set_content_layout(proxy_form)
        card_layout.addWidget(self.proxy_collapsible)

        # ---------------------------------------------------- Action Row
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.open_studio_btn = PrimaryButton("⛶ Open Studio")
        self.open_studio_btn.setToolTip("Open browser embedded in the spacious Studio below")
        self.open_studio_btn.clicked.connect(self._on_open_studio_clicked)

        self.launch_win_btn = SecondaryButton("🗗 Launch Window")
        self.launch_win_btn.setToolTip("Launch as a separate standalone desktop window")
        self.launch_win_btn.clicked.connect(self._on_launch_win_clicked)

        self.close_btn = DangerButton("✕ Close")
        self.close_btn.setVisible(False)
        self.close_btn.clicked.connect(self._close)

        self.save_btn = GhostButton("Save")
        self.save_btn.clicked.connect(self._on_save_clicked)

        action_row.addWidget(self.open_studio_btn)
        action_row.addWidget(self.launch_win_btn)
        action_row.addWidget(self.close_btn)
        action_row.addStretch(1)
        action_row.addWidget(self.save_btn)
        card_layout.addLayout(action_row)

        # Wire up browser state listener
        self.bm.browser_state_changed.connect(self._on_browser_state_changed)

    # ------------------------------------------------------------- Helpers
    def _platform(self) -> str:
        return self.platform_combo.currentText()

    def _on_platform_changed(self, platform: str) -> None:
        parent_layout = self.chip.parentWidget().layout() if self.chip.parentWidget() else None
        new_chip = PlatformChip(platform)
        if parent_layout:
            parent_layout.replaceWidget(self.chip, new_chip)
            self.chip.deleteLater()
            self.chip = new_chip

    def _format_proxy_summary(self, proxy: dict) -> str:
        host = proxy.get("host") or ""
        port = proxy.get("port") or 0
        ptype = proxy.get("type") or "http"
        if host and port:
            return f"{ptype}://{host}:{port}"
        return "Direct (No Proxy)"

    def _update_proxy_summary(self) -> None:
        p = {
            "type": self.proxy_type.currentText(),
            "host": self.proxy_host.text().strip(),
            "port": self.proxy_port.value(),
        }
        self.proxy_summary.setText(self._format_proxy_summary(p))

    def _toggle_pass_visibility(self) -> None:
        if self.proxy_pass.echoMode() == QLineEdit.EchoMode.Password:
            self.proxy_pass.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_pass_btn.setText("🔒")
        else:
            self.proxy_pass.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_pass_btn.setText("👁")

    def _on_browser_state_changed(self, platform: str, is_running: bool, is_embedded: bool) -> None:
        if platform != self._platform():
            return
        if is_running:
            self.open_studio_btn.setVisible(False)
            self.launch_win_btn.setVisible(False)
            self.close_btn.setVisible(True)
            if is_embedded:
                self.status_badge.set_status("ready", "Studio Active")
            else:
                self.status_badge.set_status("info", "Window Active")
        else:
            self.open_studio_btn.setVisible(True)
            self.launch_win_btn.setVisible(True)
            self.close_btn.setVisible(False)
            self.status_badge.set_status("closed", "Closed")

    def _on_open_studio_clicked(self) -> None:
        account = self.collect()
        self.status_badge.set_status("warning", "Opening...")
        if self.on_open_studio:
            self.on_open_studio(account)
        else:
            self.bm.open_browser(account, embed=True)

    def _on_launch_win_clicked(self) -> None:
        account = self.collect()
        self.status_badge.set_status("warning", "Launching...")
        if self.on_launch_window:
            self.on_launch_window(account)
        else:
            self.bm.open_browser(account, embed=False)

    def _close(self) -> None:
        self.bm.close_platform(self._platform())

    def _on_save_clicked(self) -> None:
        if self.on_save_single:
            self.on_save_single()
        else:
            self.save_btn.setText("Saved ✓")
            QTimer.singleShot(1500, lambda: self.save_btn.setText("Save"))

    def collect(self) -> dict:
        """Read the card widgets back into an account dict."""
        self.account["platform"] = self._platform()
        self.account["name"] = self.name_edit.text().strip()
        self.account["proxy"] = {
            "type": self.proxy_type.currentText(),
            "host": self.proxy_host.text().strip(),
            "port": int(self.proxy_port.value()),
            "username": self.proxy_user.text().strip(),
            "password": self.proxy_pass.text(),
        }
        return self.account


# ===================================================================== #
# Dedicated Browser Studio
# ===================================================================== #
class BrowserStudio(CardAlt):
    """Full-width Browser Studio with multi-session tabs and edge-to-edge Chrome embedding."""

    def __init__(self, browser_manager: BrowserManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bm = browser_manager
        self._containers: dict[str, EmbeddedBrowserContainer] = {}
        self._tab_buttons: dict[str, QPushButton] = {}

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(540)
        self.setStyleSheet(f"""
            BrowserStudio {{
                background-color: {theme.BG_SURFACE_ALT};
                border: 1px solid {theme.BORDER_SUBTLE};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)

        # ------------------------------------------------ Toolbar Header
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        studio_title = QLabel("🌐 Social Browser Studio")
        studio_title.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 700;")
        self.studio_subtitle = QLabel("Dedicated workspace with isolated Chrome profiles & proxies")
        self.studio_subtitle.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        title_box.addWidget(studio_title)
        title_box.addWidget(self.studio_subtitle)
        toolbar.addLayout(title_box)

        toolbar.addSpacing(14)

        # Session tabs row
        self.tabs_layout = QHBoxLayout()
        self.tabs_layout.setSpacing(6)
        toolbar.addLayout(self.tabs_layout)

        toolbar.addStretch(1)

        # Live Proxy / Status Pill
        self.conn_pill = QLabel("Standby")
        self.conn_pill.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT_MUTED};
                background-color: {theme.BG_INPUT};
                border: 1px solid {theme.BORDER_SUBTLE};
                border-radius: 5px;
                padding: 4px 10px;
                font-family: monospace;
                font-size: 11px;
            }}
        """)
        toolbar.addWidget(self.conn_pill)

        # Control Buttons
        self.dock_toggle_btn = GhostButton("🗗 Pop-out to Window")
        self.dock_toggle_btn.setToolTip("Detach Chrome into a separate desktop window")
        self.dock_toggle_btn.clicked.connect(self._toggle_dock)
        toolbar.addWidget(self.dock_toggle_btn)

        self.reload_btn = GhostButton("🔄 Reload")
        self.reload_btn.setToolTip("Refresh active browser page")
        self.reload_btn.clicked.connect(self._reload_page)
        toolbar.addWidget(self.reload_btn)

        self.home_btn = GhostButton("🏠 Home")
        self.home_btn.setToolTip("Navigate to platform login/home URL")
        self.home_btn.clicked.connect(self._navigate_home)
        toolbar.addWidget(self.home_btn)

        self.close_btn = DangerButton("✕ Close Session")
        self.close_btn.clicked.connect(self._close_active)
        toolbar.addWidget(self.close_btn)

        layout.addLayout(toolbar)

        # ------------------------------------------------ Viewport Stack
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Page 0: Empty state placeholder
        self.empty_page = self._build_empty_state()
        self.stack.addWidget(self.empty_page)

        # Register platform containers
        for platform in PLATFORMS:
            container = EmbeddedBrowserContainer(platform, self.bm, parent=self.stack)
            self._containers[platform] = container
            self.bm.register_container(platform, container)
            self.stack.addWidget(container)

        layout.addWidget(self.stack, 1)

        # Wire up signals
        self.bm.browser_state_changed.connect(self._on_browser_state_changed)
        self.bm.active_session_changed.connect(self._on_active_session_changed)

        self._refresh_ui()

    def _build_empty_state(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #05070B; border: 1px dashed #1E2430; border-radius: 8px;")
        box = QVBoxLayout(w)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.setSpacing(10)

        icon = QLabel("💻")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 38px;")
        box.addWidget(icon)

        title = QLabel("Browser Studio Standby")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: 15px; font-weight: 600;")
        box.addWidget(title)

        desc = QLabel(
            "Click 'Open Studio' on any account card above to open its isolated Chrome session here with 100% full width,\n"
            "or click 'Launch Window' to open in an independent desktop window for manual logins & 2FA."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px; line-height: 1.4;")
        box.addWidget(desc)

        return w

    def _refresh_ui(self) -> None:
        active = self.bm.active_platform()
        running = self.bm.running_platforms()

        # Update session tab chips
        # Clear existing tabs
        while self.tabs_layout.count():
            item = self.tabs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._tab_buttons.clear()

        for platform in running:
            is_active = (platform == active)
            btn = QPushButton(f"{platform.capitalize()}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if is_active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {theme.ACCENT_PRIMARY};
                        color: #FFFFFF;
                        border: none;
                        border-radius: 5px;
                        padding: 4px 10px;
                        font-size: 11px;
                        font-weight: 700;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {theme.BG_INPUT};
                        color: {theme.TEXT_SECONDARY};
                        border: 1px solid {theme.BORDER_SUBTLE};
                        border-radius: 5px;
                        padding: 4px 10px;
                        font-size: 11px;
                        font-weight: 500;
                    }}
                    QPushButton:hover {{
                        background-color: {theme.BG_HOVER};
                        color: {theme.TEXT_PRIMARY};
                    }}
                """)
            btn.clicked.connect(lambda _, p=platform: self.bm.set_active_platform(p))
            self.tabs_layout.addWidget(btn)
            self._tab_buttons[platform] = btn

        if not active or not self.bm.is_running(active):
            self.stack.setCurrentWidget(self.empty_page)
            self.conn_pill.setText("Standby")
            self.conn_pill.setStyleSheet(f"color: {theme.TEXT_MUTED}; background-color: {theme.BG_INPUT}; border: 1px solid {theme.BORDER_SUBTLE}; border-radius: 5px; padding: 4px 10px; font-family: monospace; font-size: 11px;")
            self.dock_toggle_btn.setVisible(False)
            self.reload_btn.setVisible(False)
            self.home_btn.setVisible(False)
            self.close_btn.setVisible(False)
            return

        # An active platform exists
        self.dock_toggle_btn.setVisible(True)
        self.reload_btn.setVisible(True)
        self.home_btn.setVisible(True)
        self.close_btn.setVisible(True)

        is_emb = self.bm.is_embedded(active)
        if is_emb:
            self.dock_toggle_btn.setText("🗗 Pop-out to Window")
            self.dock_toggle_btn.setToolTip("Detach Chrome into a separate desktop window")
            container = self._containers.get(active)
            if container:
                self.stack.setCurrentWidget(container)
                QTimer.singleShot(50, lambda: self.bm.resize(active, container.width(), container.height()))
        else:
            self.dock_toggle_btn.setText("⛶ Dock into Studio")
            self.dock_toggle_btn.setToolTip("Dock standalone Chrome window into this studio")
            self.stack.setCurrentWidget(self.empty_page)

        self.conn_pill.setText(f"● {active.capitalize()} (Active)")
        self.conn_pill.setStyleSheet(f"color: {theme.STATUS_SUCCESS}; background-color: {theme.STATUS_SUCCESS_BG}; border: 1px solid {theme.STATUS_SUCCESS_BORDER}; border-radius: 5px; padding: 4px 10px; font-family: monospace; font-size: 11px; font-weight: 600;")

    def _on_browser_state_changed(self, platform: str, is_running: bool, is_embedded: bool) -> None:
        self._refresh_ui()

    def _on_active_session_changed(self, platform: str) -> None:
        self._refresh_ui()

    def _toggle_dock(self) -> None:
        active = self.bm.active_platform()
        if not active:
            return
        if self.bm.is_embedded(active):
            self.bm.pop_out(active)
        else:
            self.bm.dock_into(active)

    def _reload_page(self) -> None:
        active = self.bm.active_platform()
        if active:
            self.bm.reload_page(active)

    def _navigate_home(self) -> None:
        active = self.bm.active_platform()
        if active:
            self.bm.navigate_home(active)

    def _close_active(self) -> None:
        active = self.bm.active_platform()
        if active:
            self.bm.close_platform(active)


# ===================================================================== #
# Main AccountsTab
# ===================================================================== #
class AccountsTab(QWidget):
    """Dual-view manager: Account Profiles grid & full-height dedicated Browser Studio."""

    def __init__(self, config: dict, on_save, browser_manager: BrowserManager,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.on_save = on_save
        self.bm = browser_manager
        self.cards: list[_AccountCard] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 14, 18, 14)
        root_layout.setSpacing(12)

        # ------------------------------------------------ Header Toolbar
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        main_title = QLabel("Social Account Profiles")
        main_title.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 700;")
        main_sub = QLabel("Isolated Chrome browser sessions with per-account proxies & persistent logins")
        main_sub.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        title_layout.addWidget(main_title)
        title_layout.addWidget(main_sub)
        header_row.addLayout(title_layout)

        header_row.addStretch(1)

        # View Mode Toggle Pill Bar
        self.view_toggle_frame = QFrame()
        self.view_toggle_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.BG_INPUT};
                border: 1px solid {theme.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 2px;
            }}
        """)
        toggle_layout = QHBoxLayout(self.view_toggle_frame)
        toggle_layout.setContentsMargins(3, 3, 3, 3)
        toggle_layout.setSpacing(4)

        self.btn_view_profiles = QPushButton("📁 Account Profiles")
        self.btn_view_profiles.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view_profiles.clicked.connect(self.show_profiles)

        self.btn_view_studio = QPushButton("🌐 Browser Studio")
        self.btn_view_studio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view_studio.clicked.connect(self.show_studio)

        toggle_layout.addWidget(self.btn_view_profiles)
        toggle_layout.addWidget(self.btn_view_studio)
        header_row.addWidget(self.view_toggle_frame)

        self.save_btn = PrimaryButton("Save All Accounts")
        self.save_btn.clicked.connect(self._save)
        header_row.addWidget(self.save_btn)

        root_layout.addLayout(header_row)

        # ------------------------------------------------ View Stack
        self.view_stack = QStackedWidget()
        self.view_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # PAGE 0: Profiles View
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        profiles_inner = QWidget()
        inner_layout = QVBoxLayout(profiles_inner)
        inner_layout.setContentsMargins(2, 6, 2, 14)
        inner_layout.setSpacing(16)

        self.grid = QGridLayout()
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(14)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)

        accounts = config.get("accounts", [])
        for idx, account in enumerate(accounts):
            card = _AccountCard(
                account,
                self.bm,
                on_open_studio=self._open_in_studio,
                on_launch_window=self._open_in_window,
                on_save_single=self._save,
                parent=profiles_inner,
            )
            self.cards.append(card)
            row = idx // 2
            col = idx % 2
            self.grid.addWidget(card, row, col)

        inner_layout.addLayout(self.grid)

        # Quick Jump Banner to Studio
        self.jump_banner = CardAlt()
        jb_layout = QHBoxLayout(self.jump_banner)
        jb_layout.setContentsMargins(14, 10, 14, 10)
        jb_icon = QLabel("💻")
        jb_layout.addWidget(jb_icon)
        self.jb_text = QLabel("Browser Studio Standby — Open any account above to enter the full-screen Studio.")
        self.jb_text.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
        jb_layout.addWidget(self.jb_text)
        jb_layout.addStretch(1)
        self.jb_btn = SecondaryButton("Switch to Studio →")
        self.jb_btn.clicked.connect(self.show_studio)
        jb_layout.addWidget(self.jb_btn)
        inner_layout.addWidget(self.jump_banner)

        scroll.setWidget(profiles_inner)
        self.view_stack.addWidget(scroll)

        # PAGE 1: Dedicated Browser Studio
        self.studio = BrowserStudio(self.bm, parent=self)
        self.view_stack.addWidget(self.studio)

        root_layout.addWidget(self.view_stack, 1)

        # Wire up browser state to update toggle pill badge
        self.bm.browser_state_changed.connect(self._on_browser_state_changed)
        self._update_toggle_styles()

    def show_profiles(self) -> None:
        self.view_stack.setCurrentIndex(0)
        self._update_toggle_styles()

    def show_studio(self) -> None:
        self.view_stack.setCurrentIndex(1)
        self._update_toggle_styles()
        active = self.bm.active_platform()
        if active:
            container = self.bm.get_container(active)
            if container:
                QTimer.singleShot(60, lambda: self.bm.resize(active, container.width(), container.height()))

    def _update_toggle_styles(self) -> None:
        is_studio = (self.view_stack.currentIndex() == 1)
        running = self.bm.running_platforms()
        studio_label = f"🌐 Browser Studio ({len(running)})" if running else "🌐 Browser Studio"
        self.btn_view_studio.setText(studio_label)

        active_style = f"""
            QPushButton {{
                background-color: {theme.ACCENT_PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 700;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background-color: transparent;
                color: {theme.TEXT_SECONDARY};
                border: none;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                color: {theme.TEXT_PRIMARY};
                background-color: {theme.BG_HOVER};
            }}
        """
        if is_studio:
            self.btn_view_studio.setStyleSheet(active_style)
            self.btn_view_profiles.setStyleSheet(inactive_style)
        else:
            self.btn_view_profiles.setStyleSheet(active_style)
            self.btn_view_studio.setStyleSheet(inactive_style)

    def _on_browser_state_changed(self, platform: str, is_running: bool, is_embedded: bool) -> None:
        running = self.bm.running_platforms()
        if running:
            self.jb_text.setText(f"Active sessions: {', '.join(p.capitalize() for p in running)}. Full-screen Studio ready.")
            self.jb_btn.setText(f"Switch to Studio ({len(running)}) →")
        else:
            self.jb_text.setText("Browser Studio Standby — Open any account above to enter the full-screen Studio.")
            self.jb_btn.setText("Switch to Studio →")
        self._update_toggle_styles()

    def _open_in_studio(self, account: dict) -> None:
        ok = self.bm.open_browser(account, embed=True)
        if ok:
            self.show_studio()

    def _open_in_window(self, account: dict) -> None:
        self.bm.open_browser(account, embed=False)

    def _save(self) -> None:
        cfg = {"accounts": [card.collect() for card in self.cards]}
        try:
            self.on_save(cfg)
            log.info("Accounts saved successfully")
            self.save_btn.setText("Saved ✓")
            QTimer.singleShot(1800, lambda: self.save_btn.setText("Save All Accounts"))
        except Exception:
            log.exception("Failed to save accounts")
            self.save_btn.setText("Save Failed ✗")
            QTimer.singleShot(2500, lambda: self.save_btn.setText("Save All Accounts"))
