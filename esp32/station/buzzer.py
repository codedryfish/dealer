"""
buzzer.py — Passive buzzer patterns for MicroPython.
"""
import time
from machine import Pin, PWM
from config import PIN_BUZZER


class Buzzer:
    def __init__(self):
        self._pin = Pin(PIN_BUZZER, Pin.OUT)
        self._pwm = None

    def _beep(self, freq_hz: int, duration_ms: int):
        try:
            pwm = PWM(self._pin, freq=freq_hz, duty=512)
            time.sleep_ms(duration_ms)
            pwm.deinit()
            self._pin.value(0)
        except Exception as e:
            print(f"Buzzer error: {e}")

    def card_read(self):
        """Short high beep: card confirmed."""
        self._beep(1800, 80)

    def action(self):
        """Two quick beeps: agent has decided."""
        self._beep(1200, 80)
        time.sleep_ms(60)
        self._beep(1200, 80)

    def winner(self):
        """Ascending melody: won the hand."""
        for freq in [800, 1000, 1200, 1600]:
            self._beep(freq, 100)
            time.sleep_ms(30)

    def error(self):
        """Low descending: error."""
        for freq in [600, 400]:
            self._beep(freq, 150)
            time.sleep_ms(40)

    def fold(self):
        """Single low beep: fold."""
        self._beep(600, 120)
