"""Account storage package: config load/save and path helpers."""

from .store import (
    DEFAULT_CONFIG,
    PLATFORMS,
    config_path,
    inbox_dir_for,
    load_config,
    profile_dir_for,
    save_config,
)

__all__ = [
    "DEFAULT_CONFIG",
    "PLATFORMS",
    "config_path",
    "inbox_dir_for",
    "load_config",
    "profile_dir_for",
    "save_config",
]
