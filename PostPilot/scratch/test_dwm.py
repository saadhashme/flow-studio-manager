import sys
import os
sys.path.insert(0, os.path.abspath("."))
import ctypes
from ctypes import wintypes
from browser.chrome import ChromeHost
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout

app = QApplication(sys.argv)
win = QMainWindow()
win.resize(1000, 700)
central = QWidget()
layout = QVBoxLayout(central)

container = QWidget()
container.setStyleSheet("background-color: #07090E;")
layout.addWidget(container, 1)
win.setCentralWidget(central)
win.show()
app.processEvents()

temp_dir = os.path.abspath("scratch/test_dwm_profile")
os.makedirs(temp_dir, exist_ok=True)

host = ChromeHost(
    profile_dir=temp_dir,
    proxy=None,
    app_url="https://www.google.com",
    debug_port=9460,
)

host.launch()
import time
time.sleep(2)
host.embed_into(int(container.winId()))

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
h_wnd = wintypes.HWND(host._hwnd)

# Try disabling non-client rendering
val = wintypes.DWORD(1) # DWMNCRP_DISABLED
dwmapi.DwmSetWindowAttribute(h_wnd, 2, ctypes.byref(val), ctypes.sizeof(val))

w_rect = wintypes.RECT()
c_rect = wintypes.RECT()
user32.GetWindowRect(h_wnd, ctypes.byref(w_rect))
user32.GetClientRect(h_wnd, ctypes.byref(c_rect))

ww = w_rect.right - w_rect.left
wh = w_rect.bottom - w_rect.top
cw = c_rect.right - c_rect.left
ch = c_rect.bottom - c_rect.top

print(f"Window: {ww}x{wh}, Client: {cw}x{ch}")
host.terminate()
app.quit()
