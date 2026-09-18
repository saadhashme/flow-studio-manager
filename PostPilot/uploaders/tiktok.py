"""TikTok uploader for PostPilot v1.

Flow:
  1. Navigate to the TikTok web upload page.
  2. Attach the video file to the (hidden) file input.
  3. Wait for upload + processing to finish (caption editor appears).
  4. Fill the caption editor (contenteditable) with the full caption.
  5. Leave all defaults (privacy, etc.) untouched.
  6. Click "Post" (text-based, classes are dynamic).
  7. Verify: URL contains /video/ or a success toast appears.

Assumptions:
  - The Chrome profile controlled via CDP is already logged in to the
    target TikTok account. No login is performed here.
  - The video file meets TikTok's limits (<= 4 GB, <= 60 min).
"""

from __future__ import annotations

import json
import os
import time

from .base import CDPError, CDPTimeout, click_text, fail, fill_contenteditable, human_delay, wait_gone

PLATFORM = "tiktok"
UPLOAD_URL = "https://www.tiktok.com/upload"

# If the site changes and uploads break, fix selectors here first.
# Preferred strategy: stable attributes (input[type=file], contenteditable)
# and text-based clicks instead of dynamic class names.
SELECTORS = {
    # Hidden file input on the upload page. CDP's setFileInputFiles works
    # even when the input is invisible, so no need to unhide it.
    "file_input": 'input[type="file"]',
    # "Select video" button (text-based click fallback if needed).
    "select_video_button": "button",
    # The caption editor: a DraftJS-style contenteditable div.
    "caption_editor": 'div[contenteditable="true"]',
    # Video preview element: appears once the file starts uploading.
    "video_preview": "video",
    # Upload progress indicator (varies; we mainly wait for it to vanish).
    "upload_progress": '[role="progressbar"]',
    # Error toast that appears if the file is rejected.
    "error_toast": '[role="alert"]',
}


def _has_error_toast(cdp) -> str:
    """Return toast text if an error toast is showing, else empty string."""
    try:
        text = cdp.evaluate(
            "(function(){ var el = document.querySelector(%s);"
            " return el ? (el.innerText || '') : ''; })()"
            % json.dumps(SELECTORS["error_toast"])
        )
        return (text or "").strip()
    except Exception:
        return ""


def upload(cdp, item: dict, account: dict) -> tuple[bool, str]:
    """Upload one video to TikTok. Returns (True, msg) or (False, msg).

    item keys: id, file_path, file_name, title, caption, hashtags (list),
    full_caption. account keys: platform, name.
    """
    file_path = item.get("file_path") or ""
    caption = item.get("full_caption") or item.get("caption") or ""

    try:
        # --- Step 0: sanity checks -------------------------------------
        if not file_path or not os.path.isfile(file_path):
            return fail(cdp, PLATFORM, f"video file not found: {file_path!r}")

        # --- Step 1: open the upload page -------------------------------
        try:
            cdp.navigate(UPLOAD_URL)
        except (CDPError, CDPTimeout) as exc:
            return fail(cdp, PLATFORM, f"navigate to upload page failed: {exc}")
        human_delay()

        # --- Step 2: attach the video file ------------------------------
        if not cdp.wait_selector(SELECTORS["file_input"], timeout=60):
            return fail(cdp, PLATFORM, "file input not found on upload page (login expired?)")
        try:
            if not cdp.set_file_input(SELECTORS["file_input"], file_path, timeout=60):
                return fail(cdp, PLATFORM, "set_file_input returned False for the video file")
        except (CDPError, CDPTimeout) as exc:
            return fail(cdp, PLATFORM, f"attaching video file failed: {exc}")
        human_delay(2.0, 4.0)

        toast = _has_error_toast(cdp)
        if toast:
            return fail(cdp, PLATFORM, f"TikTok rejected the file: {toast}")

        # --- Step 3: wait for upload + processing -----------------------
        # The caption editor shows up once the video is accepted.
        if not cdp.wait_selector(SELECTORS["caption_editor"], timeout=180):
            toast = _has_error_toast(cdp)
            return fail(
                cdp,
                PLATFORM,
                "caption editor never appeared after upload"
                + (f" (site says: {toast})" if toast else ""),
            )

        # --- Step 4: fill the caption -----------------------------------
        if caption and not fill_contenteditable(cdp, SELECTORS["caption_editor"], caption, timeout=30):
            return fail(cdp, PLATFORM, "could not fill the caption editor")
        human_delay()

        # Verify the caption actually landed.
        try:
            got = cdp.evaluate(
                "(function(){ var el = document.querySelector(%s);"
                " return el ? (el.innerText || '').length : 0; })()"
                % json.dumps(SELECTORS["caption_editor"])
            )
        except Exception:
            got = 0
        if caption and not got:
            return fail(cdp, PLATFORM, "caption editor is still empty after filling")

        # --- Step 5: click Post (text-based; defaults left alone) -------
        human_delay(1.5, 3.0)
        if not click_text(cdp, "button", "Post", timeout=30):
            return fail(cdp, PLATFORM, "'Post' button not found/clickable")

        # --- Step 6: verify the post went through -----------------------
        # Success usually redirects to /@user/video/<id>.
        if cdp.wait_url_contains("/video/", timeout=90):
            return (True, f"tiktok: posted '{item.get('file_name', file_path)}' (url: {cdp.current_url()})")
        if cdp.wait_text_present("uploaded", timeout=30) or cdp.wait_text_present(
            "Your video is being uploaded", timeout=10
        ):
            return (True, f"tiktok: post submitted for '{item.get('file_name', file_path)}'")
        return fail(cdp, PLATFORM, "no confirmation after clicking Post (no /video/ url, no success text)")

    except Exception as exc:  # never raise out of upload()
        return fail(cdp, PLATFORM, f"unexpected error during TikTok upload: {exc}")
