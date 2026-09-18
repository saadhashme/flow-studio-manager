"""Bottom log dock: terminal-style read-only text view with color-coded levels.

Features monospace font, live color coding (INFO/WARN/ERROR), auto-scroll toggle,
level filtering, and copy/clear actions.
"""

from __future__ import annotations

import html
import logging
import re

from PySide6.QtCore import QMetaObject, Q_ARG, Qt, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .components import GhostButton


class LogView(QWidget):
    """Modern dark-themed terminal log viewer with color highlighting and controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._auto_scroll = True
        self._filter_level = "ALL"
        self._records: list[tuple[str, str]] = []  # (level, raw_msg)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 6, 10, 8)
        root_layout.setSpacing(6)

        # --------------------------------------------- Control Bar
        bar = QHBoxLayout()
        bar.setSpacing(10)

        # Title & Indicator
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {theme.STATUS_SUCCESS}; font-size: 9px;")
        bar.addWidget(dot)

        title = QLabel("Console Output")
        title.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-weight: 600; font-size: 12px;")
        bar.addWidget(title)

        bar.addSpacing(12)

        # Level filter
        filter_lbl = QLabel("Filter:")
        filter_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        bar.addWidget(filter_lbl)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["ALL", "INFO", "WARNING", "ERROR"])
        self.filter_combo.setStyleSheet("padding: 2px 6px; font-size: 11px;")
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        bar.addWidget(self.filter_combo)

        # Auto-scroll checkbox
        self.scroll_cb = QCheckBox("Auto-scroll")
        self.scroll_cb.setChecked(True)
        self.scroll_cb.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 11px;")
        self.scroll_cb.toggled.connect(self._on_scroll_toggled)
        bar.addWidget(self.scroll_cb)

        bar.addStretch(1)

        # Copy & Clear buttons
        copy_btn = GhostButton("📋 Copy")
        copy_btn.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        copy_btn.clicked.connect(self._copy_all)
        bar.addWidget(copy_btn)

        clear_btn = GhostButton("🗑 Clear")
        clear_btn.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        clear_btn.clicked.connect(self.clear)
        bar.addWidget(clear_btn)

        root_layout.addLayout(bar)

        # --------------------------------------------- Terminal View
        self.text = QTextEdit(self)
        self.text.setObjectName("terminalView")
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.text.document().setMaximumBlockCount(2500)
        root_layout.addWidget(self.text, 1)

    def _on_scroll_toggled(self, checked: bool) -> None:
        self._auto_scroll = checked

    def _on_filter_changed(self, level: str) -> None:
        self._filter_level = level
        self._rebuild_view()

    def _format_html(self, raw_msg: str) -> str:
        """Color-code a log line based on timestamp, level, and message."""
        escaped = html.escape(raw_msg)

        # Match pattern: "12:34:56 [LEVEL] logger: message"
        m = re.match(r"^(\d{2}:\d{2}:\d{2})\s+\[([A-Z]+)\]\s+([^:]+):\s+(.*)$", escaped)
        if m:
            time_str, level_str, logger_str, body = m.groups()
            if level_str in ("ERROR", "CRITICAL"):
                color = theme.STATUS_DANGER
                badge_bg = theme.STATUS_DANGER_BG
            elif level_str in ("WARNING", "WARN"):
                color = theme.STATUS_WARNING
                badge_bg = theme.STATUS_WARNING_BG
            elif level_str == "INFO":
                color = theme.STATUS_INFO
                badge_bg = theme.STATUS_INFO_BG
            else:
                color = theme.TEXT_MUTED
                badge_bg = theme.BG_INPUT

            return (
                f"<span style='color: {theme.TEXT_MUTED}; font-family: monospace;'>{time_str}</span> "
                f"<span style='color: {color}; background-color: {badge_bg}; padding: 1px 4px; border-radius: 3px; font-weight: 600; font-size: 11px;'>[{level_str}]</span> "
                f"<span style='color: {theme.TEXT_MUTED}; font-size: 11px;'>{logger_str}:</span> "
                f"<span style='color: {theme.TEXT_PRIMARY};'>{body}</span>"
            )

        # Fallback formatting
        return f"<span style='color: {theme.TEXT_PRIMARY};'>{escaped}</span>"

    def _extract_level(self, raw_msg: str) -> str:
        m = re.search(r"\[([A-Z]+)\]", raw_msg)
        return m.group(1) if m else "INFO"

    @Slot(str)
    def append(self, msg: str) -> None:
        level = self._extract_level(msg)
        self._records.append((level, msg))
        if len(self._records) > 2500:
            self._records.pop(0)

        # Check if visible under current filter
        if self._matches_filter(level):
            formatted = self._format_html(msg)
            self.text.append(formatted)
            if self._auto_scroll:
                cursor = self.text.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.text.setTextCursor(cursor)

    def _matches_filter(self, level: str) -> bool:
        if self._filter_level == "ALL":
            return True
        if self._filter_level == "INFO":
            return level in ("INFO", "WARNING", "ERROR", "CRITICAL")
        if self._filter_level == "WARNING":
            return level in ("WARNING", "WARN", "ERROR", "CRITICAL")
        if self._filter_level == "ERROR":
            return level in ("ERROR", "CRITICAL")
        return True

    def _rebuild_view(self) -> None:
        self.text.clear()
        lines = []
        for lvl, raw in self._records:
            if self._matches_filter(lvl):
                lines.append(self._format_html(raw))
        if lines:
            self.text.setHtml("<br>".join(lines))
        if self._auto_scroll:
            cursor = self.text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.text.setTextCursor(cursor)

    def clear(self) -> None:
        self._records.clear()
        self.text.clear()

    def _copy_all(self) -> None:
        plain_text = "\n".join([r[1] for r in self._records])
        QApplication.clipboard().setText(plain_text)


def setup_logging(widget: LogView) -> logging.Handler:
    """Wire the root logger to *widget*; returns the installed handler."""
    handler = logging.Handler()

    def _emit(record: logging.LogRecord) -> None:
        try:
            text = handler.format(record)
        except Exception:
            text = record.getMessage()
        try:
            # Queued so calls from worker threads are safe.
            QMetaObject.invokeMethod(
                widget, "append", Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, text),
            )
        except RuntimeError:
            pass  # widget already destroyed during shutdown

    handler.emit = _emit  # type: ignore[method-assign]
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
    root = logging.getLogger()
    root.addHandler(handler)
    if root.level > logging.INFO:
        root.setLevel(logging.INFO)
    return handler
