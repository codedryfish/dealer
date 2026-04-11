"""
boot.py — Runs before main.py on every boot.

Provides a 3-second window where the board is idle so mpremote (or any serial
tool) can send Ctrl+C and enter the REPL. Without this, a crash-looping
main.py makes it impossible to re-flash without erasing the firmware.
"""
import time
time.sleep(3)
