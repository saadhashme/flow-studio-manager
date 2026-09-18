import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from browser.chrome import ChromeHost, find_chrome_exe
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import QTimer

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

temp_dir = os.path.abspath("scratch/test_dock_profile")
os.makedirs(temp_dir, exist_ok=True)

host = ChromeHost(
    profile_dir=temp_dir,
    proxy=None,
    app_url="https://www.google.com",
    debug_port=9450,
)

print("Launching host...")
if not host.launch():
    print("Launch failed!")
    sys.exit(1)

print("Embedding into Qt...")
time.sleep(2)
ok = host.embed_into(int(container.winId()))
print("Embed result:", ok)
host.resize_embedded(container.width(), container.height())

def step1_detach():
    print("Testing detach (pop-out)...")
    host.detach()
    print("Detached! is_embedded:", host.is_embedded)

def step2_reembed():
    print("Testing re-embed (dock)...")
    host.embed_into(int(container.winId()))
    host.resize_embedded(container.width(), container.height())
    print("Re-embedded! is_embedded:", host.is_embedded)

def step3_quit():
    print("Terminating...")
    host.terminate()
    print("Done!")
    app.quit()

QTimer.singleShot(1500, step1_detach)
QTimer.singleShot(3000, step2_reembed)
QTimer.singleShot(4500, step3_quit)

app.exec()
