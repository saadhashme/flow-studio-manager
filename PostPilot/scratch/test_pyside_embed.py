import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
import subprocess
import ctypes
from ctypes import wintypes
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QTimer, Qt
from browser.chrome import find_chrome_exe

app = QApplication(sys.argv)
win = QMainWindow()
win.resize(900, 600)
central = QWidget()
layout = QVBoxLayout(central)
label = QLabel("Header bar")
layout.addWidget(label)

container = QWidget()
container.setStyleSheet("background-color: #07090E;")
layout.addWidget(container, 1)
win.setCentralWidget(central)
win.show()

chrome_exe = find_chrome_exe()
port = 9445
temp_dir = os.path.abspath("scratch/test_pyside_profile")
os.makedirs(temp_dir, exist_ok=True)

proc = subprocess.Popen([
    chrome_exe,
    "--app=https://www.google.com",
    f"--user-data-dir={temp_dir}",
    f"--remote-debugging-port={port}",
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=900,600",
])

time.sleep(2.5)

user32 = ctypes.windll.user32
target_pid = proc.pid

found_hwnd = None
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
    print("Qt container winId:", qt_win_id)
    
    # Win32 Constants
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
    
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020
    SWP_SHOWWINDOW = 0x0040

    old_style = user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_STYLE)
    print("Old style:", hex(old_style))
    
    # Reparent
    user32.SetParent(wintypes.HWND(hwnd), wintypes.HWND(qt_win_id))
    
    # Strip non-client styles and set child styles
    new_style = (old_style | WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS) & ~(
        WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU | WS_POPUP
    )
    user32.SetWindowLongW(wintypes.HWND(hwnd), GWL_STYLE, new_style)
    
    # SWP_FRAMECHANGED is crucial to force Windows to recalculate non-client area
    user32.SetWindowPos(
        wintypes.HWND(hwnd), 0, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW
    )

    rect = wintypes.RECT()
    user32.GetClientRect(wintypes.HWND(qt_win_id), ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    print(f"Container client rect: {w}x{h}")
    user32.MoveWindow(wintypes.HWND(hwnd), 0, 0, w, h, True)

def capture_and_quit():
    time.sleep(1)
    pixmap = win.grab()
    pixmap.save("scratch/embed_result.png")
    print("Saved scratch/embed_result.png")
    proc.terminate()
    proc.wait()
    app.quit()

QTimer.singleShot(2000, capture_and_quit)
app.exec()
