"""YouTube uploader for PostPilot v1.

Flow:
  1. Navigate to https://www.youtube.com/upload (redirects into Studio).
  2. Attach the video file. Studio's file input lives inside Polymer
     shadow DOM, so we first move it to document.body via JS
     (_expose_file_input), then use the plain CSS selector.
  3. Wait for the Details step (title/description boxes appear).
  4. Fill the title (item title, else the file stem, max 100 chars) and
     the description (full caption).
  5. Select "No, it's not made for kids".
  6. Click Next until the Visibility step is reached (tolerates 2-4).
  7. Select Public, then Publish (2026 Studio labels it "Publish"/"Save").
  8. Verify: the publish dialog shows a youtu.be link or "published" text.

Assumptions:
  - The Chrome profile controlled via CDP is already logged in to the
    Google account that owns the target YouTube channel.
  - Studio is a single-page app: the URL does not change between steps,
    so step changes are detected via DOM text, not the URL.
  - English UI labels ("Next", "Public", "Publish"/"Save"). If the
    account runs in another locale, extend NEXT_LABELS etc. below.
"""

from __future__ import annotations

import json
import os
import time

from .base import CDPError, CDPTimeout, fail, human_delay

PLATFORM = "youtube"
UPLOAD_URL = "https://www.youtube.com/upload"

# If the site changes and uploads break, fix selectors here first.
# Studio 2026 dropped most data-testid attributes; the stable hooks are
# aria-label substrings, ids (#next-button, #textbox), the dialog host
# tag "ytcp-uploads-dialog", and the Polymer radio tag
# "tp-yt-paper-radio-button". Shadow-DOM piercing is done via JS.
SELECTORS = {
    # After _expose_file_input() moves it out of shadow DOM, this plain
    # selector finds the video file input.
    "file_input": 'input[type="file"]',
    # Host of the whole upload dialog (shadow DOM root).
    "upload_dialog": "ytcp-uploads-dialog",
    # Title and description boxes (contenteditable, id="textbox"); found
    # by piercing shadow DOM, first = title, second = description.
    "textbox": "#textbox",
    # Kids-audience radios (Polymer elements, matched by name attr via JS).
    "kids_radio": "tp-yt-paper-radio-button",
    # Next button on Details/Video elements/Checks steps.
    "next_button": "#next-button",
    # Visibility radios on the final step.
    "visibility_radio": "tp-yt-paper-radio-button",
    # Video URL shown on the publish confirmation dialog.
    "video_url": ".video-url-fadeable",
    # Upload progress element inside the dialog.
    "upload_progress": "ytcp-video-upload-progress",
}

# Button labels tried at each step (English first; extend for other locales).
NEXT_LABELS = ["Next"]
PUBLISH_LABELS = ["Publish", "Save", "Done"]


def _deep(query_fn: str) -> str:
    """Wrap a per-root query function so it pierces all shadow roots.

    `query_fn` is JS taking `root` and returning a value; the first
    truthy value found across document + every shadow root is returned.
    """
    return (
        "(function(){"
        "  var fn = " + query_fn + ";"
        "  var roots = [document];"
        "  var seen = [];"
        "  var queue = [document];"
        "  while (queue.length) {"
        "    var r = queue.pop();"
        "    var els = r.querySelectorAll('*');"
        "    for (var i = 0; i < els.length; i++) {"
        "      var sr = els[i].shadowRoot;"
        "      if (sr && seen.indexOf(sr) === -1) {"
        "        seen.push(sr); roots.push(sr); queue.push(sr);"
        "      }"
        "    }"
        "  }"
        "  for (var k = 0; k < roots.length; k++) {"
        "    var v;"
        "    try { v = fn(roots[k]); } catch (e) { v = null; }"
        "    if (v) return v;"
        "  }"
        "  return null;"
        "})()"
    )


def _expose_file_input(cdp) -> bool:
    """Move Studio's hidden file input out of shadow DOM into document.body.

    This makes the plain 'input[type="file"]' CSS selector work with the
    CDP client's set_file_input(). The input keeps its event listeners,
    so the upload still triggers. Returns True on success.
    """
    js = _deep(
        "(function(root){"
        "  var inp = root.querySelector('input[type=\"file\"]');"
        "  if (inp && inp !== document.body) {"
        "    try { document.body.appendChild(inp); return true; }"
        "    catch (e) { return false; }"
        "  }"
        "  return inp ? true : null;"
        "})"
    )
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            if cdp.evaluate(js):
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def _textboxes(cdp):
    """Return list of title/description textbox texts (piercing shadow DOM)."""
    js = _deep(
        "(function(root){"
        "  var boxes = root.querySelectorAll('#textbox');"
        "  if (boxes && boxes.length) return boxes.length;"
        "  return null;"
        "})"
    )
    try:
        return int(cdp.evaluate(js) or 0)
    except Exception:
        return 0


def _wait_textboxes(cdp, timeout: float = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _textboxes(cdp) >= 2:
            return True
        time.sleep(1.0)
    return False


def _fill_textbox(cdp, index: int, text: str) -> bool:
    """Fill the index-th #textbox (0=title, 1=description) via JS."""
    js = (
        "(function(idx, text){"
        "  var found = [];"
        "  var roots = [document];"
        "  var queue = [document];"
        "  var seen = [];"
        "  while (queue.length) {"
        "    var r = queue.pop();"
        "    var els = r.querySelectorAll('*');"
        "    for (var i = 0; i < els.length; i++) {"
        "      var sr = els[i].shadowRoot;"
        "      if (sr && seen.indexOf(sr) === -1) {"
        "        seen.push(sr); roots.push(sr); queue.push(sr);"
        "      }"
        "    }"
        "  }"
        "  for (var k = 0; k < roots.length; k++) {"
        "    var boxes = roots[k].querySelectorAll('#textbox');"
        "    for (var j = 0; j < boxes.length; j++) found.push(boxes[j]);"
        "  }"
        "  if (idx >= found.length) return 'missing';"
        "  var el = found[idx];"
        "  el.focus();"
        "  try { document.execCommand('selectAll', false, null); } catch (e) {}"
        "  var ok = false;"
        "  try { ok = document.execCommand('insertText', false, text); } catch (e) {}"
        "  if (!ok) { try { el.textContent = text; ok = true; } catch (e) {} }"
        "  try { el.dispatchEvent(new InputEvent('input', {bubbles: true})); } catch (e) {}"
        "  try { el.dispatchEvent(new Event('change', {bubbles: true})); } catch (e) {}"
        "  el.blur();"
        "  return 'ok';"
        "})(%d, %s)" % (index, json.dumps(text))
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if cdp.evaluate(js) == "ok":
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _click_radio_by_name(cdp, names) -> bool:
    """Click a tp-yt-paper-radio-button whose name attr is in `names`."""
    js = _deep(
        "(function(root){"
        "  var radios = root.querySelectorAll('tp-yt-paper-radio-button');"
        "  for (var i = 0; i < radios.length; i++) {"
        "    var n = radios[i].getAttribute('name') || '';"
        "    if (%s.indexOf(n) !== -1) { radios[i].click(); return true; }"
        "  }"
        "  return null;"
        "})" % json.dumps(list(names))
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if cdp.evaluate(js):
                human_delay(0.5, 1.0)
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _click_text_deep(cdp, labels, timeout: float = 30) -> str:
    """Click first visible element whose trimmed text equals one of labels.

    Pierces shadow DOM. Returns the matched label, or '' if none found.
    """
    js = _deep(
        "(function(root){"
        "  var labels = %s;"
        "  var els = root.querySelectorAll('button, [role=\"button\"], ytcp-button, tp-yt-paper-button');"
        "  for (var i = 0; i < els.length; i++) {"
        "    var el = els[i];"
        "    var t = (el.innerText || el.textContent || '').trim();"
        "    if (!t) continue;"
        "    for (var l = 0; l < labels.length; l++) {"
        "      if (t === labels[l] || t.toLowerCase() === labels[l].toLowerCase()) {"
        "        var host = el;"
        "        while (host && host.getBoundingClientRect && host.getBoundingClientRect().width === 0) {"
        "          host = host.parentElement;"
        "        }"
        "        el.click();"
        "        return labels[l];"
        "      }"
        "    }"
        "  }"
        "  return null;"
        "})" % json.dumps(list(labels))
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            hit = cdp.evaluate(js)
            if hit:
                return hit
        except Exception:
            pass
        time.sleep(0.5)
    return ""


def _dialog_text(cdp) -> str:
    """Return all visible text inside the uploads dialog (piercing shadow DOM)."""
    js = _deep(
        "(function(root){"
        "  var dlg = root.querySelector('ytcp-uploads-dialog');"
        "  if (dlg) return (dlg.innerText || '').slice(0, 4000);"
        "  return null;"
        "})"
    )
    try:
        return cdp.evaluate(js) or ""
    except Exception:
        return ""


def _published_url(cdp) -> str:
    """Return the youtu.be/watch URL from the publish dialog, or ''."""
    js = _deep(
        "(function(root){"
        "  var el = root.querySelector('.video-url-fadeable');"
        "  if (el) {"
        "    var a = el.querySelector('a');"
        "    if (a && a.href) return a.href;"
        "    var t = (el.innerText || '').trim();"
        "    if (t) return t;"
        "  }"
        "  return null;"
        "})"
    )
    try:
        return cdp.evaluate(js) or ""
    except Exception:
        return ""


def upload(cdp, item: dict, account: dict) -> tuple[bool, str]:
    """Upload one video to YouTube. Returns (True, msg) or (False, msg).

    item keys: id, file_path, file_name, title, caption, hashtags (list),
    full_caption. account keys: platform, name.
    """
    file_path = item.get("file_path") or ""
    title = (item.get("title") or "").strip()
    if not title:
        stem = os.path.splitext(item.get("file_name") or os.path.basename(file_path))[0]
        title = stem or "Untitled"
    title = title[:100]  # YouTube title limit
    description = item.get("full_caption") or item.get("caption") or ""

    try:
        # --- Step 0: sanity checks -------------------------------------
        if not file_path or not os.path.isfile(file_path):
            return fail(cdp, PLATFORM, f"video file not found: {file_path!r}")

        # --- Step 1: open the upload page -------------------------------
        try:
            cdp.navigate(UPLOAD_URL)
        except (CDPError, CDPTimeout) as exc:
            return fail(cdp, PLATFORM, f"navigate to upload page failed: {exc}")
        human_delay(2.0, 4.0)

        # --- Step 2: attach the video file ------------------------------
        if not _expose_file_input(cdp):
            # Fallback: maybe the input is already at document level.
            if not cdp.wait_selector(SELECTORS["file_input"], timeout=10):
                return fail(cdp, PLATFORM, "file input not found in Studio (login expired?)")
        try:
            if not cdp.set_file_input(SELECTORS["file_input"], file_path, timeout=120):
                return fail(cdp, PLATFORM, "set_file_input returned False for the video file")
        except (CDPError, CDPTimeout) as exc:
            return fail(cdp, PLATFORM, f"attaching video file failed: {exc}")
        human_delay(2.0, 4.0)

        # --- Step 3: wait for the Details step ---------------------------
        if not _wait_textboxes(cdp, timeout=180):
            return fail(cdp, PLATFORM, "Details form (title/description) never appeared after upload")

        # --- Step 4: fill title + description ----------------------------
        if not _fill_textbox(cdp, 0, title):
            return fail(cdp, PLATFORM, "could not fill the video title")
        human_delay()
        if description and not _fill_textbox(cdp, 1, description):
            return fail(cdp, PLATFORM, "could not fill the video description")
        human_delay()

        # --- Step 5: "No, it's not made for kids" -----------------------
        if not _click_radio_by_name(cdp, ["NOT_MADE_FOR_KIDS", "VIDEO_MADE_FOR_KIDS_NOT_MFK"]):
            return fail(cdp, PLATFORM, "'Not made for kids' radio not found/clickable")
        human_delay()

        # --- Step 6: click Next until the Visibility step ----------------
        reached_visibility = False
        for _ in range(4):
            text = _dialog_text(cdp).lower()
            if "visibility" in text or "publish" in text or "save" in text:
                reached_visibility = True
                break
            if not _click_text_deep(cdp, NEXT_LABELS, timeout=20):
                # Maybe we already advanced; re-check once more.
                text = _dialog_text(cdp).lower()
                if "visibility" in text or "publish" in text:
                    reached_visibility = True
                break
            human_delay(2.0, 3.5)
        if not reached_visibility:
            # One more check before giving up.
            text = _dialog_text(cdp).lower()
            if not ("visibility" in text or "publish" in text):
                return fail(cdp, PLATFORM, "never reached the Visibility step (Next clicks exhausted)")

        # --- Step 7: select Public ---------------------------------------
        if not _click_radio_by_name(cdp, ["PUBLIC"]):
            # Fallback: click by visible text.
            if not _click_text_deep(cdp, ["Public"], timeout=20):
                return fail(cdp, PLATFORM, "'Public' visibility option not found/clickable")
        human_delay()

        # --- Step 8: Publish ----------------------------------------------
        if not _click_text_deep(cdp, PUBLISH_LABELS, timeout=30):
            return fail(cdp, PLATFORM, "Publish/Save button not found/clickable")
        human_delay(3.0, 5.0)

        # --- Step 9: verify -----------------------------------------------
        deadline = time.time() + 120
        while time.time() < deadline:
            url = _published_url(cdp)
            if url:
                return (True, f"youtube: published '{title}' -> {url}")
            text = _dialog_text(cdp).lower()
            if "published" in text or "video published" in text:
                return (True, f"youtube: published '{title}' (confirmed by dialog text)")
            time.sleep(2.0)
        return fail(cdp, PLATFORM, "no publish confirmation (no video URL, no 'published' text)")

    except Exception as exc:  # never raise out of upload()
        return fail(cdp, PLATFORM, f"unexpected error during YouTube upload: {exc}")
