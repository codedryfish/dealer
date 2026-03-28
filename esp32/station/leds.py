"""
leds.py — WS2812B LED ring control for MicroPython.

Patterns:
  thinking  — pulsing blue
  acted     — solid green
  folded    — solid red (dim)
  idle      — off
  reading   — fast white blink
"""
import time
from machine import Pin
from config import PIN_LEDS, LED_COUNT

try:
    import neopixel
    _NP_AVAILABLE = True
except ImportError:
    print("WARNING: neopixel library not found. LED output will be printed to serial.")
    _NP_AVAILABLE = False


# Colour constants (R, G, B)
OFF    = (0, 0, 0)
BLUE   = (0, 0, 60)
GREEN  = (0, 60, 0)
RED    = (40, 0, 0)
WHITE  = (40, 40, 40)
GOLD   = (60, 40, 0)


class LEDRing:
    def __init__(self):
        self._np = None
        if _NP_AVAILABLE:
            try:
                self._np = neopixel.NeoPixel(Pin(PIN_LEDS), LED_COUNT)
                self.idle()
            except Exception as e:
                print(f"LED init error: {e}")

    def _fill(self, colour):
        if self._np:
            for i in range(LED_COUNT):
                self._np[i] = colour
            self._np.write()
        else:
            print(f"LED: fill {colour}")

    def idle(self):
        self._fill(OFF)

    def thinking(self, pulses=1):
        """Pulse blue for thinking. Run this in a loop while waiting."""
        for _ in range(pulses):
            self._fill(BLUE)
            time.sleep_ms(400)
            self._fill(OFF)
            time.sleep_ms(400)

    def acted(self):
        """Solid green: decision made."""
        self._fill(GREEN)

    def folded(self):
        """Dim red: folded."""
        self._fill(RED)

    def card_read(self):
        """Quick flash white: card read confirmation."""
        self._fill(WHITE)
        time.sleep_ms(150)
        self._fill(OFF)

    def winner(self):
        """Gold flash: won the hand."""
        for _ in range(3):
            self._fill(GOLD)
            time.sleep_ms(200)
            self._fill(OFF)
            time.sleep_ms(200)
        self._fill(GOLD)

    def error(self):
        """Rapid red flash: error."""
        for _ in range(4):
            self._fill(RED)
            time.sleep_ms(100)
            self._fill(OFF)
            time.sleep_ms(100)
