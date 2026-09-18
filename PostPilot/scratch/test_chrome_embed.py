import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
import subprocess
import ctypes
from ctypes import wintypes
from browser.chrome import find_chrome_exe

chrome_exe = find_chrome_exe()
print("Using Chrome:", chrome_exe)

# Launch a test instance
port = 9444
temp_dir = os.path.abspath("scratch/test_profile")
os.makedirs(temp_dir, exist_ok=True)

proc = subprocess.Popen([
    chrome_exe,
    "--app=https://www.google.com",
    f"--user-data-dir={temp_dir}",
    f"--remote-debugging-port={port}",
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=800,600",
])

time.sleep(3)
target_pid = proc.pid
user32 = ctypes.windll.user32

found = []
@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def enum_cb(hwnd, _lparam):
    if not user32.IsWindowVisible(hwnd):
        return True
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == target_pid:
        buf = ctypes.create_unicode_buffer(512)
        user32.GetClassNameW(hwnd, buf, 512)
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title, 512)
        found.append((hwnd, buf.value, title.value))
    return True

user32.EnumWindows(enum_cb, 0)
print("Found windows:", found)

proc.terminate()
proc.wait()
print("Terminated successfully")
