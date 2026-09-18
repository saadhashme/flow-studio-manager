import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from app.main_window import MainWindow
from app.accounts_tab import BrowserManager
from scheduler import Scheduler
from accounts import load_config

app = QApplication(sys.argv)
cfg = load_config()
bm = BrowserManager()
logs_dir = os.path.join(os.path.expanduser("~/PostPilot"), "logs")
os.makedirs(logs_dir, exist_ok=True)
scheduler = Scheduler(get_cdp=bm.get_cdp, get_item=lambda i: None, get_account=lambda p: None, logs_dir=logs_dir)

win = MainWindow(cfg, on_save=lambda c: None, browser_manager=bm, scheduler=scheduler)
win.resize(1350, 880)
win.show()
app.processEvents()

# Open Facebook in Studio
acc = cfg["accounts"][0] # Facebook
print("Opening Facebook in Studio...")
ok = bm.open_browser(acc, embed=True)
print("open_browser result:", ok)

win.accounts_tab.show_studio()
app.processEvents()

def capture():
    pixmap = win.grab()
    pixmap.save("scratch/accounts_tab_active_studio.png")
    print("Saved scratch/accounts_tab_active_studio.png")
    bm.close_platform("facebook")
    app.quit()

QTimer.singleShot(3000, capture)
app.exec()
