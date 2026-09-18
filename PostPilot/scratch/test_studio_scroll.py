import sys
import os
sys.path.insert(0, os.path.abspath("."))
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
win.resize(1350, 900)
win.show()
app.processEvents()

# Scroll down to show Browser Studio
accounts_tab = win.accounts_tab
accounts_tab.studio.show()
scroll = accounts_tab.findChild(type(accounts_tab.children()[1])) # get scroll area
for child in accounts_tab.children():
    if hasattr(child, "verticalScrollBar"):
        child.verticalScrollBar().setValue(400)

app.processEvents()
pixmap = win.grab()
pixmap.save("scratch/accounts_tab_scrolled_studio.png")
print("Saved scratch/accounts_tab_scrolled_studio.png")

app.quit()
