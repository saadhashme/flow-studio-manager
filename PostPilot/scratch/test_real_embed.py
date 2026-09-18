import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
import subprocess
import ctypes
from ctypes import wintypes
from PIL import ImageGrab
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QTimer
from browser.chrome import find_chrome_exe

app = QApplication(sys.argv)
win = QMainWindow()
win.setWindowTitle("PostPilot Test")
win.resize(1000, 700)
central = QWidget()
layout = QVBoxLayout(central)
label = QLabel("Test Embedding Chrome")
layout.addWidget(label)

container = QWidget()
container.setStyleSheet("background-color: #07090E;")
layout.addWidget(container, 1)
win.setCentralWidget(central)
win.show()
app.processEvents()

chrome_exe = find_chrome_exe()
port = 9446
temp_dir = os.path.abspath("scratch/test_pyside_profile2")
os.makedirs(temp_dir, exist_ok=True)

proc = subprocess.Popen([
    chrome_exe,
    "--app=https://www.google.com",
    f"--user-data-dir={temp_dir}",
    f"--remote-debugging-port={port}",
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1000,700",
])

time.sleep(2.5)

user32 = ctypes.windll.user32
target_pid = proc.pid

def find_chrome_window():
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
            if "Chrome_WidgetWin" in buf.value:
                found.append(hwnd)
        return True
    user32.EnumWindows(enum_cb, 0)
    return found[0] if found else None

hwnd = find_chrome_window()
print("Target Chrome HWND:", hwnd)

if hwnd:
    qt_win_id = int(container.winId())
    GWL_STYLE = -16
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
    
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_FRAMECHANGED = 0x0020
    SWP_SHOWWINDOW = 0x0040

    old_style = user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_STYLE)
    
    # Reparent
    user32.SetParent(wintypes.HWND(hwnd), wintypes.HWND(qt_win_id))
    
    new_style = (old_style | WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS) & ~(
        WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU | WS_POPUP
    )
    user32.SetWindowLongW(wintypes.HWND(hwnd), GWL_STYLE, new_style)
    
    user32.SetWindowPos(
        wintypes.HWND(hwnd), 0, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW
    )

    rect = wintypes.RECT()
    user32.GetClientRect(wintypes.HWND(qt_win_id), ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    user32.MoveWindow(wintypes.HWND(hwnd), 0, 0, w, h, True)

def capture_and_quit():
    time.sleep(1)
    rect = wintypes.RECT()
    user32.GetWindowRect(wintypes.HWND(int(win.winId())), ctypes.byref(rect))
    bbox = (rect.left, rect.top, rect.right, rect.bottom)
    img = ImageGrab.grab(bbox=bbox)
    img.save("scratch/real_embed_result.png")
    print("Saved scratch/real_embed_result.png")
    proc.terminate()
    proc.wait()
    app.quit()

QTimer.singleShot(2500, capture_and_quit)
app.exec()
