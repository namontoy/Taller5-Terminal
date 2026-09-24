# Lets test modules import their shared helpers (qt_helpers) both when run by
# discovery (python -m unittest discover tests) and one at a time
# (python -m unittest tests.test_serial_worker).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
