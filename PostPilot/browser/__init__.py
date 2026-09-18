"""PostPilot browser package: real-Chrome hosting + CDP control.

Exports:
    CDPClient  - synchronous Chrome DevTools Protocol client (cdp.py)
    CDPError   - base CDP exception
    CDPTimeout - raised when a CDP call exceeds its timeout
    ChromeHost - Chrome discovery, per-account launch, WinAPI embedding (chrome.py)
"""

from .cdp import CDPClient, CDPError, CDPTimeout
from .chrome import ChromeHost, find_chrome_exe

__all__ = ["CDPClient", "CDPError", "CDPTimeout", "ChromeHost", "find_chrome_exe"]
