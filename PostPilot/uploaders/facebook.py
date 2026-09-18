"""Facebook uploader for PostPilot v1.

Flow:
  1. Navigate to the reels composer (https://www.facebook.com/reels/create/).
     If that is unavailable, fall back to the Page's own composer with a
     video attachment (open Page -> "Photo/video" -> attach file).
  2. Attach the video file to the file input.
  3. Wait for processing, fill the caption (contenteditable .ql-editor).
  4. Click Post/Share (text-based; Facebook labels vary).
  5. Verify: success toast text appears ("shared"/"published").

ASSUMPTIONS (read before use):
  - The Chrome profile controlled via CDP is logged in with the account
    that administers the target Facebook Page (the tool's browser profile
    holds the login; no login is performed here).
  - PAGE_URL override: if set (e.g. "https://www.facebook.com/MyPage"),
    the uploader navigates there first and uses the Page composer.
    If empty, the uploader tries the reels composer, then looks for a
    left-nav link whose text matches account["name"] to find the Page.
    If the Page cannot be located, upload() fails with a message telling
    the user to set PAGE_URL.
  - Posting as the Page vs. the profile depends on Facebook's composer
    context; verify the identity switcher manually on first run.
"""

from __future__ import annotations

import json
import os
import time

from .base import CDPError, CDPTimeout, click_text, fail, fill_contenteditable, human_delay

PLATFORM = "facebook"

# Set this to your Page's URL to skip Page discovery, e.g.
# PAGE_URL = "https://www.facebook.com/TheWealthCode"
PAGE_URL = ""

REELS_CREATE_URL = "https://www.facebook.com/reels/create/"
HOME_URL = "https://www.facebook.com/"

# If the site changes and uploads break, fix selectors here first.
# Facebook renames classes constantly; aria-labels, roles, and visible
# button text are the most stable hooks.
SELECTORS = {
    # Reels composer drop zone / file input (appears on reels/create/).
    "file_input": 'input[type="file"]',
    # Caption editor inside the composer dialog.
    "caption_box": '.ql-editor[contenteditable="true"]',
    # The create-post composer dialog, scoped by its editable area.
    "composer_dialog": "[role='dialog']",
    # "Photo/video" button inside the Page composer (aria-label based).
    "photo_video_button": "[aria-label='Photo/video']",
    # Publish button labels tried in order (Facebook varies these).
    "post_button_tag": "div",
}


def _find_page_link(cdp, page_name: str) -> str:
    """Find the Page's URL from nav links whose text matches page_name.

    Returns the href (absolute URL) or '' if not found.
    """
    if not page_name:
        return ""
    js = (
        "(function(name){"
        "  var needle = name.toLowerCase();"
        "  var links = document.querySelectorAll('a[href]');"
        "  for (var i = 0; i < links.length; i++) {"
        "    var t = (links[i].innerText || '').trim().toLowerCase();"
        "    if (t && t.indexOf(needle) !== -1) {"
        "      var href = links[i].getAttribute('href') || '';"
        "      if (href && href.charAt(0) === '/') return 'https://www.facebook.com' + href;"
        "      if (href.indexOf('facebook.com') !== -1) return href;"
        "    }"
        "  }"
        "  return '';"
        "})(%s)" % json.dumps(page_name)
    )
    try:
        return cdp.evaluate(js) or ""
    except Exception:
        return ""


def _composer_open(cdp, timeout: float = 60) -> bool:
    """True when a composer with a file input or caption box is on screen."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if cdp.query_exists(SELECTORS["file_input"]) or cdp.query_exists(SELECTORS["caption_box"]):
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def _click_photo_video(cdp) -> bool:
    """Click the 'Photo/video' button inside the composer via aria-label."""
    js = (
        "(function(){"
        "  var els = document.querySelectorAll(\"[aria-label='Photo/video']\");"
        "  for (var i = 0; i < els.length; i++) {"
        "    var r = els[i].getBoundingClientRect();"
        "    if (r.width > 0 && r.height > 0) { els[i].click(); return true; }"
        "  }"
        "  return false;"
        "})()"
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            if cdp.evaluate(js):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def upload(cdp, item: dict, account: dict) -> tuple[bool, str]:
    """Upload one video to Facebook (Page). Returns (True, msg)/(False, msg).

    item keys: id, file_path, file_name, title, caption, hashtags (list),
    full_caption. account keys: platform, name.
    """
    file_path = item.get("file_path") or ""
    caption = item.get("full_caption") or item.get("caption") or ""
    page_name = (account.get("name") or "").strip()

    try:
        # --- Step 0: sanity checks -------------------------------------
        if not file_path or not os.path.isfile(file_path):
            return fail(cdp, PLATFORM, f"video file not found: {file_path!r}")

        composer_ready = False

        # --- Step 1a: try the reels composer ----------------------------
        try:
            cdp.navigate(REELS_CREATE_URL)
        except (CDPError, CDPTimeout) as exc:
            return fail(cdp, PLATFORM, f"navigate to reels composer failed: {exc}")
        human_delay(2.0, 4.0)
        if _composer_open(cdp, timeout=20):
            composer_ready = True

        # --- Step 1b: fall back to the Page composer --------------------
        if not composer_ready:
            page_url = PAGE_URL
            if not page_url:
                # Try to discover the Page from the left nav.
                try:
                    cdp.navigate(HOME_URL)
                except (CDPError, CDPTimeout) as exc:
                    return fail(cdp, PLATFORM, f"navigate to facebook home failed: {exc}")
                human_delay(2.0, 4.0)
                page_url = _find_page_link(cdp, page_name)
            if not page_url:
                return fail(
                    cdp,
                    PLATFORM,
                    "could not reach the reels composer and could not find the Page. "
                    "Set the PAGE_URL constant at the top of uploaders/facebook.py to the "
                    "Page's URL (e.g. https://www.facebook.com/YourPage) and retry.",
                )
            try:
                cdp.navigate(page_url)
            except (CDPError, CDPTimeout) as exc:
                return fail(cdp, PLATFORM, f"navigate to Page failed: {exc}")
            human_delay(2.0, 4.0)
            # Open the create-post composer (text varies by locale).
            if not (
                click_text(cdp, "*", "What's on your mind", timeout=15)
                or click_text(cdp, "*", "Create post", timeout=10)
            ):
                return fail(cdp, PLATFORM, "Page composer ('What's on your mind') not found")
            human_delay()
            if not _click_photo_video(cdp):
                return fail(cdp, PLATFORM, "'Photo/video' button not found in the composer")
            human_delay()
            if not _composer_open(cdp, timeout=20):
                return fail(cdp, PLATFORM, "file input never appeared in the Page composer")
            composer_ready = True

        # --- Step 2: attach the video file ------------------------------
        if not cdp.wait_selector(SELECTORS["file_input"], timeout=30):
            return fail(cdp, PLATFORM, "file input not found in the composer")
        try:
            if not cdp.set_file_input(SELECTORS["file_input"], file_path, timeout=120):
                return fail(cdp, PLATFORM, "set_file_input returned False for the video file")
        except (CDPError, CDPTimeout) as exc:
            return fail(cdp, PLATFORM, f"attaching video file failed: {exc}")
        human_delay(3.0, 5.0)

        # --- Step 3: fill the caption -----------------------------------
        if caption:
            if not cdp.wait_selector(SELECTORS["caption_box"], timeout=120):
                return fail(cdp, PLATFORM, "caption editor never appeared after attaching the video")
            if not fill_contenteditable(cdp, SELECTORS["caption_box"], caption, timeout=30):
                return fail(cdp, PLATFORM, "could not fill the caption editor")
            human_delay()

        # --- Step 4: Post / Share ---------------------------------------
        posted = (
            click_text(cdp, SELECTORS["post_button_tag"], "Post", timeout=20)
            or click_text(cdp, SELECTORS["post_button_tag"], "Share", timeout=15)
            or click_text(cdp, SELECTORS["post_button_tag"], "Publish", timeout=15)
        )
        if not posted:
            return fail(cdp, PLATFORM, "Post/Share/Publish button not found/clickable")

        # --- Step 5: verify ----------------------------------------------
        for phrase in ("shared", "Shared", "published", "Published", "Your reel", "Your post"):
            if cdp.wait_text_present(phrase, timeout=30):
                return (True, f"facebook: posted '{item.get('file_name', file_path)}' ({phrase})")
        # Last resort: the composer closing is a weak success signal.
        if not cdp.query_exists(SELECTORS["caption_box"]):
            return (True, f"facebook: post submitted for '{item.get('file_name', file_path)}' (composer closed)")
        return fail(cdp, PLATFORM, "no success confirmation after clicking Post/Share")

    except Exception as exc:  # never raise out of upload()
        return fail(cdp, PLATFORM, f"unexpected error during Facebook upload: {exc}")
