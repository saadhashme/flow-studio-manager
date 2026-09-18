"""Instagram uploader for PostPilot v1.

Flow:
  1. Navigate to instagram.com (feed home).
  2. Click the Create icon (aria-label "New post"), which opens a submenu.
  3. Click "Post" in the submenu (falls back to "Reel" for video-only flows).
  4. Attach the video file to the dialog's file input.
  5. Click through Crop -> Edit using text-based "Next" buttons.
  6. Fill the caption box (contenteditable) with the full caption.
  7. Click "Share".
  8. Verify: success toast text appears ("shared"/"posted").

Assumptions:
  - The Chrome profile controlled via CDP is already logged in to the
    target Instagram account. No login is performed here.
  - Instagram web may relabel buttons in other locales; English labels
    are tried first, with the text-matching logic tolerating partial text.
"""

from __future__ import annotations

import os
import time

from .base import CDPError, CDPTimeout, click_text, fail, fill_contenteditable, human_delay

PLATFORM = "instagram"
UPLOAD_URL = "https://www.instagram.com/"

# If the site changes and uploads break, fix selectors here first.
# Instagram renames classes constantly; aria-labels and visible button text
# are the most stable hooks.
SELECTORS = {
    # The Create icon in the left nav: svg[aria-label="New post"].
    # We click its closest <a> via JS (see _click_create()).
    "create_icon": 'svg[aria-label="New post"]',
    # Menu items after clicking Create ("Post" / "Reel"), clicked by text.
    "menu_item_tag": "a",
    # The file input inside the create-post dialog.
    "file_input": "[role='dialog'] input[type='file']",
    # "Next" buttons on the Crop/Edit steps (div[role=button] with text).
    "next_tag": "div",
    # Caption box on the final step.
    "caption_box": '[role="dialog"] [contenteditable="true"]',
    # "Share" button on the final step.
    "share_tag": "div",
}


def _click_create(cdp) -> bool:
    """Click the Create nav item via its aria-labelled SVG icon."""
    js = (
        "(function(){"
        "  var svg = document.querySelector('svg[aria-label=\"New post\"]');"
        "  if (!svg) return false;"
        "  var a = svg.closest('a') || svg.closest('[role=\"link\"]') || svg.parentElement;"
        "  if (!a) return false;"
        "  a.click();"
        "  return true;"
        "})()"
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if cdp.evaluate(js):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _click_next(cdp, timeout: float = 30) -> bool:
    """Click the dialog's Next button (div[role=button] with text 'Next')."""
    js = (
        "(function(){"
        "  var els = document.querySelectorAll('[role=\"dialog\"] [role=\"button\"]');"
        "  for (var i = 0; i < els.length; i++){"
        "    var t = (els[i].innerText || '').trim();"
        "    if (t === 'Next' || t === 'Continue'){"
        "      var r = els[i].getBoundingClientRect();"
        "      if (r.width > 0 && r.height > 0) { els[i].click(); return true; }"
        "    }"
        "  }"
        "  return false;"
        "})()"
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


def upload(cdp, item: dict, account: dict) -> tuple[bool, str]:
    """Upload one video to Instagram. Returns (True, msg) or (False, msg).

    item keys: id, file_path, file_name, title, caption, hashtags (list),
    full_caption. account keys: platform, name.
    """
    file_path = item.get("file_path") or ""
    caption = item.get("full_caption") or item.get("caption") or ""

    try:
        # --- Step 0: sanity checks -------------------------------------
        if not file_path or not os.path.isfile(file_path):
            return fail(cdp, PLATFORM, f"video file not found: {file_path!r}")

        # --- Step 1: open Instagram home --------------------------------
        try:
            cdp.navigate(UPLOAD_URL)
        except (CDPError, CDPTimeout) as exc:
            return fail(cdp, PLATFORM, f"navigate to instagram.com failed: {exc}")
        human_delay(2.0, 4.0)

        # --- Step 2: open the Create menu -------------------------------
        if not _click_create(cdp):
            return fail(cdp, PLATFORM, "Create ('New post') button not found (login expired?)")
        human_delay()

        # --- Step 3: choose Post (fallback: Reel) -----------------------
        if not click_text(cdp, SELECTORS["menu_item_tag"], "Post", timeout=15):
            if not click_text(cdp, SELECTORS["menu_item_tag"], "Reel", timeout=15):
                return fail(cdp, PLATFORM, "neither 'Post' nor 'Reel' menu item appeared")
        human_delay()

        # --- Step 4: attach the video file ------------------------------
        if not cdp.wait_selector(SELECTORS["file_input"], timeout=60):
            return fail(cdp, PLATFORM, "file input did not appear in the create dialog")
        try:
            if not cdp.set_file_input(SELECTORS["file_input"], file_path, timeout=60):
                return fail(cdp, PLATFORM, "set_file_input returned False for the video file")
        except (CDPError, CDPTimeout) as exc:
            return fail(cdp, PLATFORM, f"attaching video file failed: {exc}")
        human_delay(2.0, 4.0)

        # --- Step 5: click through Crop -> Edit --------------------------
        # Tolerate 1-3 Next clicks; stop early once the caption box shows.
        for _ in range(3):
            if cdp.query_exists(SELECTORS["caption_box"]):
                break
            if not _click_next(cdp, timeout=30):
                # Maybe we are already on the caption step.
                if cdp.query_exists(SELECTORS["caption_box"]):
                    break
                return fail(cdp, PLATFORM, "'Next' button not found on crop/edit step")
            human_delay(1.5, 3.0)
        if not cdp.wait_selector(SELECTORS["caption_box"], timeout=30):
            return fail(cdp, PLATFORM, "caption step never appeared")

        # --- Step 6: fill the caption -----------------------------------
        if caption and not fill_contenteditable(cdp, SELECTORS["caption_box"], caption, timeout=30):
            return fail(cdp, PLATFORM, "could not fill the caption box")
        human_delay()

        # --- Step 7: Share ----------------------------------------------
        if not click_text(cdp, SELECTORS["share_tag"], "Share", timeout=30):
            return fail(cdp, PLATFORM, "'Share' button not found/clickable")

        # --- Step 8: verify ----------------------------------------------
        # Instagram shows a toast like "Your reel was shared" / "Your photo was posted".
        for phrase in ("shared", "posted", "Your reel", "Your photo"):
            if cdp.wait_text_present(phrase, timeout=30):
                return (True, f"instagram: shared '{item.get('file_name', file_path)}' ({phrase})")
        # Last resort: the dialog closing and returning to feed is a good sign.
        if not cdp.query_exists(SELECTORS["file_input"]):
            return (True, f"instagram: share submitted for '{item.get('file_name', file_path)}' (dialog closed)")
        return fail(cdp, PLATFORM, "no success confirmation after clicking Share")

    except Exception as exc:  # never raise out of upload()
        return fail(cdp, PLATFORM, f"unexpected error during Instagram upload: {exc}")
