"""Shared helpers for the PostPilot v1 platform uploaders.

Every uploader module imports from here for the defensive bits:
failure handling (screenshot + message), human-like delays, and the
JS-driven interactions that keep working when CSS classes go dynamic.
"""

from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime

try:
    from browser.cdp import CDPError, CDPTimeout
except ImportError:  # duck-typed fallback so modules import standalone
    class CDPError(Exception):
        pass

    class CDPTimeout(CDPError):
        pass


def fail(cdp, platform: str, message: str, logs_dir: str = "logs") -> tuple[bool, str]:
    """Record a failure: save a screenshot, then return (False, message).

    The screenshot goes to ``logs/<platform>_<timestamp>.png`` so a broken
    upload can be diagnosed later. Never raises.
    """
    try:
        os.makedirs(logs_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(logs_dir, f"{platform}_{stamp}.png")
        cdp.screenshot(path)
    except Exception:
        pass
    return (False, message)


def human_delay(a: float = 1.0, b: float = 2.5) -> None:
    """Sleep a random amount of time between a and b seconds."""
    time.sleep(random.uniform(a, b))


def _js_str(value: str) -> str:
    """Safely embed a Python string as a JS string literal."""
    return json.dumps(value)


def fill_contenteditable(cdp, css: str, text: str, timeout: float = 30) -> bool:
    """Fill a contenteditable element (caption editors, etc.).

    Uses execCommand('insertText') after selecting all existing text, then
    dispatches input/change events so React-style UIs pick up the change.
    Falls back to the CDP client's type_text() if JS injection fails.
    Returns True on success.
    """
    deadline = time.time() + timeout
    js = (
        "(function(css, text){"
        "  var el = document.querySelector(css);"
        "  if (!el) return false;"
        "  el.focus();"
        "  try {"
        "    var sel = window.getSelection();"
        "    sel.removeAllRanges();"
        "    var range = document.createRange();"
        "    range.selectNodeContents(el);"
        "    sel.addRange(range);"
        "  } catch (e) {}"
        "  var ok = false;"
        "  try { ok = document.execCommand('insertText', false, text); } catch (e) {}"
        "  if (!ok) {"
        "    try { el.textContent = text; ok = true; } catch (e) {}"
        "  }"
        "  try { el.dispatchEvent(new InputEvent('input', {bubbles: true})); } catch (e) {}"
        "  try { el.dispatchEvent(new Event('change', {bubbles: true})); } catch (e) {}"
        "  return ok;"
        "})(%s, %s)" % (_js_str(css), _js_str(text))
    )
    while time.time() < deadline:
        try:
            if cdp.evaluate(js):
                return True
        except Exception:
            pass
        time.sleep(0.5)

    # Fallback: click + type through the CDP client.
    try:
        return bool(cdp.type_text(css, text, clear_first=True, timeout=timeout))
    except Exception:
        return False


def click_text(cdp, tag: str, text: str, timeout: float = 30) -> bool:
    """Click a visible <tag> element whose visible text matches `text`.

    Prefers an exact trimmed match, then falls back to a contains-match.
    Useful for buttons ("Post", "Next", "Share") whose classes change often.
    `tag` may be '*' to search all elements (slower).
    Returns True if something was clicked.
    """
    js = (
        "(function(tag, text){"
        "  var needle = text.toLowerCase();"
        "  var els = (tag === '*') ? document.querySelectorAll('*')"
        "                          : document.getElementsByTagName(tag);"
        "  function visible(el){"
        "    if (!el || !el.getBoundingClientRect) return false;"
        "    var r = el.getBoundingClientRect();"
        "    return r.width > 0 && r.height > 0;"
        "  }"
        "  var fallback = null;"
        "  for (var i = 0; i < els.length; i++){"
        "    var el = els[i];"
        "    if (!visible(el)) continue;"
        "    var t = (el.innerText || '').trim();"
        "    if (!t) continue;"
        "    var low = t.toLowerCase();"
        "    if (low === needle) { el.click(); return true; }"
        "    if (!fallback && low.indexOf(needle) !== -1) fallback = el;"
        "  }"
        "  if (fallback) { fallback.click(); return true; }"
        "  return false;"
        "})(%s, %s)" % (_js_str(tag), _js_str(text))
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if cdp.evaluate(js):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def wait_gone(cdp, css: str, timeout: float = 30) -> bool:
    """Wait until `css` no longer matches anything on the page.

    Used for upload progress spinners / loading overlays. Returns True when
    the element is gone (or was never there), False on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if not cdp.query_exists(css):
                return True
        except Exception:
            return True  # if we can't even query, treat it as gone
        time.sleep(0.5)
    return False
