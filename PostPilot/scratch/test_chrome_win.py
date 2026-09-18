import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
import subprocess
import ctypes
from ctypes import wintypes
from browser.chrome import find_chrome_exe

chrome = find_chrome_exe()
print("Chrome path:", chrome)
