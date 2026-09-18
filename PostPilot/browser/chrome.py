"""Chrome discovery, launch, and WinAPI embedding for PostPilot v1.

Each social-media account gets its own real Google Chrome process launched
with ``--user-data-dir`` (so logins persist per account) and
``--remote-debugging-port`` (so :class:`CDPClient` can drive it). The Chrome
window is then embedded inside the PySide6 UI with WinAPI ``SetParent``.

This module is Windows-only at *runtime*: every method that touches the OS
raises ``RuntimeError`` when ``sys.platform != "win32"``, but the module
imports cleanly on Linux (for ``py_compile`` checks) and ``ctypes`` is the
only WinAPI mechanism used — no pywin32 dependency.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request

from .cdp import CDPClient


def _require_win32() -> None:
    if sys.platform != "win32":
        raise RuntimeError("ChromeHost requires Windows (sys.platform == 'win32')")


def find_chrome_exe() -> str | None:
    """Locate chrome.exe.

    Discovery order:
      1. Registry: HKCU/HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\chrome.exe
      2. %ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe
      3. %ProgramFiles(x86)%\\Google\\Chrome\\Application\\chrome.exe
      4. %LocalAppData%\\Google\\Chrome\\Application\\chrome.exe

    Returns the path or None. Import-safe on Linux (returns None).
    """
    # Registry lookup is Windows-only.
    if sys.platform == "win32":
        try:
            import winreg

            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, key_path) as key:
                        path, _ = winreg.QueryValueEx(key, "")
                        if path and os.path.isfile(path):
                            return path
                except OSError:
                    continue
        except ImportError:
            pass

    candidates = []
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        candidates.append(os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"))
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    if program_files_x86:
        candidates.append(os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"))
    local_app_data = os.environ.get("LocalAppData")
    if local_app_data:
        candidates.append(os.path.join(local_app_data, "Google", "Chrome", "Application", "chrome.exe"))

    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


class ChromeHost:
    """Owns one Chrome process for one social-media account.

    Parameters
    ----------
    profile_dir: per-account ``--user-data-dir`` so logins persist.
    proxy: optional dict like
        ``{"type": "http"|"https"|"socks5", "host": str, "port": int,
          "username": str, "password": str}``.
    app_url: URL opened in ``--app`` mode (no browser chrome UI).
    debug_port: ``--remote-debugging-port`` value for CDP connections.
    """

    def __init__(self, profile_dir: str, proxy: dict | None, app_url: str,
                 width: int = 1100, height: int = 750, debug_port: int = 9331):
        self.profile_dir = profile_dir
        self.proxy = proxy or {}
        self.app_url = app_url
        self.width = width
        self.height = height
        self._debug_port = debug_port
        self._proc: subprocess.Popen | None = None
        self._hwnd: int | None = None

    @property
    def cdp_port(self) -> int:
        return self._debug_port

    # ------------------------------------------------------------------ #
    # Launch
    # ------------------------------------------------------------------ #
    def _proxy_server_arg(self) -> str | None:
        host = self.proxy.get("host")
        port = self.proxy.get("port")
        if not host or not port:
            return None
        ptype = (self.proxy.get("type") or "http").lower()
        scheme = "socks5" if ptype == "socks5" else "http"
        return f"{scheme}://{host}:{port}"

    def _build_args(self, chrome_exe: str) -> list[str]:
        args = [
            chrome_exe,
            f"--app={self.app_url}",
            f'--user-data-dir={self.profile_dir}',
            f"--remote-debugging-port={self._debug_port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=Translate",
            f"--window-size={self.width},{self.height}",
            # Keep local CDP traffic off the proxy so /json stays reachable.
            "--proxy-bypass-list=<-loopback>",
        ]
        proxy_server = self._proxy_server_arg()
        if proxy_server:
            args.append(f"--proxy-server={proxy_server}")
        return args

    def launch(self) -> bool:
        """Find Chrome, launch it with the account's args, and return True if
        the process is alive.

        After launch, polls ``http://127.0.0.1:<port>/json`` for up to ~15 s;
        if the proxy dict carries username/password, a :class:`CDPClient` is
        connected and ``set_proxy_auth`` is armed immediately (see
        ``cdp.py`` for how proxy credentials are injected via the CDP Fetch
        domain — Chrome has no native inline ``--proxy-server`` auth support).
        """
        _require_win32()
        chrome_exe = find_chrome_exe()
        if not chrome_exe:
            raise RuntimeError("Google Chrome was not found (registry and default install paths checked)")

        os.makedirs(self.profile_dir, exist_ok=True)
        args = self._build_args(chrome_exe)
        try:
            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            self._proc = None
            return False

        # Wait for the DevTools HTTP endpoint to come up (~15 s max).
        json_url = f"http://127.0.0.1:{self._debug_port}/json"
        deadline = time.time() + 15
        reachable = False
        while time.time() < deadline:
            if not self.is_running():
                return False
            try:
                with urllib.request.urlopen(json_url, timeout=2) as resp:
                    if resp.status == 200:
                        reachable = True
                        break
            except Exception:
                pass
            time.sleep(0.5)

        if not reachable or not self.is_running():
            return False

        # Arm proxy authentication right away so uploaders never have to.
        username = self.proxy.get("username")
        password = self.proxy.get("password") or ""
        if username:
            client = CDPClient(self._debug_port)
            try:
                client.connect()
                client.set_proxy_auth(username, password)
            finally:
                client.close()

        return True

    def is_running(self) -> bool:
        """True if the Chrome process we launched is still alive."""
        if self._proc is None:
            return False
        return self._proc.poll() is None

    def terminate(self) -> None:
        """Terminate the Chrome process (graceful first, then kill)."""
        if self._proc is None:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None
        self._hwnd = None

    @property
    def is_embedded(self) -> bool:
        return getattr(self, "_embedded", False)

    # ------------------------------------------------------------------ #
    # Window handle + WinAPI embedding
    # ------------------------------------------------------------------ #
    def wait_for_window(self, timeout: float = 20) -> int | None:
        """Find the top-level window owned by our Chrome process.

        Uses ``EnumWindows`` + ``GetWindowThreadProcessId`` and matches on
        the PID of the process launched in :meth:`launch`. Prioritizes windows
        with class containing ``Chrome_WidgetWin`` to avoid secondary utility
        overlays. Returns the hwnd (int) or None if no window appears within
        ``timeout`` seconds.
        """
        _require_win32()
        if self._proc is None:
            return None
        target_pid = self._proc.pid

        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found_primary: list[int] = []
        found_other: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_cb(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == target_pid:
                buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, buf, 256)
                cname = buf.value
                if "Chrome_WidgetWin" in cname:
                    found_primary.append(hwnd)
                else:
                    found_other.append(hwnd)
            return True

        deadline = time.time() + timeout
        while time.time() < deadline:
            found_primary.clear()
            found_other.clear()
            user32.EnumWindows(enum_cb, 0)
            if found_primary:
                self._hwnd = found_primary[0]
                return self._hwnd
            if found_other:
                # If no Chrome_WidgetWin has appeared yet, wait slightly longer
                # to avoid prematurely grabbing a utility overlay.
                time.sleep(0.4)
                continue
            time.sleep(0.3)

        if found_other:
            self._hwnd = found_other[0]
            return self._hwnd
        return None

    def embed_into(self, qt_win_id: int) -> bool:
        """Embed the Chrome window inside the Qt container widget.

        ``SetParent(hwnd, qt_win_id)`` reparents the window; the window style
        is then rewritten to ``WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS``
        with ``WS_CAPTION``, ``WS_THICKFRAME``, ``WS_POPUP``, and min/max/sysmenu bits
        stripped. Crucially, ``SetWindowPos`` with ``SWP_FRAMECHANGED`` is called
        so Windows recalculates the non-client frame and eliminates the title bar,
        and ``MoveWindow`` sizes it to fill the container 100%.
        """
        _require_win32()
        hwnd = self._hwnd or self.wait_for_window(timeout=6)
        if not hwnd:
            return False

        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        GWL_STYLE = -16
        GWL_EXSTYLE = -20
        WS_CHILD = 0x40000000
        WS_VISIBLE = 0x10000000
        WS_CLIPCHILDREN = 0x02000000
        WS_CLIPSIBLINGS = 0x04000000
        WS_CAPTION = 0x00C00000
        WS_THICKFRAME = 0x00040000
        WS_MINIMIZEBOX = 0x00020000
        WS_MAXIMIZEBOX = 0x00010000
        WS_SYSMENU = 0x00080000
        WS_POPUP = 0x80000000

        WS_EX_DLGMODALFRAME = 0x0001
        WS_EX_WINDOWEDGE = 0x0100
        WS_EX_CLIENTEDGE = 0x0200
        WS_EX_STATICEDGE = 0x20000

        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020
        SWP_SHOWWINDOW = 0x0040

        h_wnd = wintypes.HWND(hwnd)
        p_wnd = wintypes.HWND(qt_win_id)

        # Reparent into the Qt widget.
        if not user32.SetParent(h_wnd, p_wnd):
            return False

        # Rewrite styles: strip caption, frames, system menus, popup flags.
        style = user32.GetWindowLongW(h_wnd, GWL_STYLE)
        style = (style | WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS) & ~(
            WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU | WS_POPUP
        )
        user32.SetWindowLongW(h_wnd, GWL_STYLE, style)

        exstyle = user32.GetWindowLongW(h_wnd, GWL_EXSTYLE)
        exstyle = exstyle & ~(WS_EX_DLGMODALFRAME | WS_EX_WINDOWEDGE | WS_EX_CLIENTEDGE | WS_EX_STATICEDGE)
        user32.SetWindowLongW(h_wnd, GWL_EXSTYLE, exstyle)

        # Tell Windows to recalculate non-client area (removes title bar completely).
        user32.SetWindowPos(
            h_wnd, 0, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW
        )

        # Fill the container immediately.
        rect = wintypes.RECT()
        user32.GetClientRect(p_wnd, ctypes.byref(rect))
        w = max(rect.right - rect.left, 100)
        h = max(rect.bottom - rect.top, 100)
        user32.MoveWindow(h_wnd, 0, 0, w, h, True)
        user32.UpdateWindow(h_wnd)

        self._embedded = True
        self._current_parent = qt_win_id
        return True

    def detach(self) -> bool:
        """Detach Chrome from the Qt container and restore as a standalone desktop window."""
        _require_win32()
        if not self._hwnd:
            return False
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        h_wnd = wintypes.HWND(self._hwnd)

        # Reparent to desktop
        user32.SetParent(h_wnd, None)

        GWL_STYLE = -16
        WS_CHILD = 0x40000000
        WS_OVERLAPPEDWINDOW = 0x00CF0000
        WS_VISIBLE = 0x10000000

        SWP_SHOWWINDOW = 0x0040
        SWP_FRAMECHANGED = 0x0020

        style = user32.GetWindowLongW(h_wnd, GWL_STYLE)
        style = (style & ~WS_CHILD) | WS_OVERLAPPEDWINDOW | WS_VISIBLE
        user32.SetWindowLongW(h_wnd, GWL_STYLE, style)

        # Position at generous desktop dimensions (1200x800)
        user32.SetWindowPos(h_wnd, 0, 80, 80, 1200, 800, SWP_FRAMECHANGED | SWP_SHOWWINDOW)
        user32.SetForegroundWindow(h_wnd)
        self._embedded = False
        self._current_parent = None
        return True

    def resize_embedded(self, w: int, h: int) -> None:
        """Resize the embedded Chrome window (called on Qt container resize)."""
        _require_win32()
        if not self._hwnd or not getattr(self, "_embedded", False):
            return
        if w <= 0 or h <= 0:
            return
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        h_wnd = wintypes.HWND(self._hwnd)
        user32.MoveWindow(h_wnd, 0, 0, w, h, True)
        user32.UpdateWindow(h_wnd)

    def reload(self) -> bool:
        """Reload page via CDP."""
        try:
            client = CDPClient(self._debug_port)
            client.connect()
            client.call("Page.reload", {})
            client.close()
            return True
        except Exception:
            return False

    def navigate(self, url: str) -> bool:
        """Navigate page to url via CDP."""
        try:
            client = CDPClient(self._debug_port)
            client.connect()
            client.navigate(url)
            client.close()
            return True
        except Exception:
            return False
