"""PostPilot v1 uploader registry.

Each platform module exposes ``upload(cdp, item, account)``. Use
``get_uploader("tiktok")`` (etc.) to fetch the right module.
"""

from . import facebook, instagram, tiktok, youtube

PLATFORMS = {
    "tiktok": tiktok,
    "youtube": youtube,
    "instagram": instagram,
    "facebook": facebook,
}


def get_uploader(platform: str):
    """Return the uploader module for a platform name.

    Accepts "tiktok", "youtube", "instagram", "facebook" (case-insensitive).
    Raises KeyError for unknown platforms.
    """
    return PLATFORMS[platform.strip().lower()]
