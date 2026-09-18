import sys
import os
sys.path.insert(0, os.path.abspath("."))
from PySide6.QtWidgets import QApplication
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
win.resize(1300, 850)
win.show()
app.processEvents()

pixmap = win.grab()
pixmap.save("scratch/accounts_tab_new_idle.png")
print("Saved scratch/accounts_tab_new_idle.png")

app.quit()
