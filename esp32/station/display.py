"""
display.py — SSD1306 OLED display driver + UI layout for MicroPython.

Layout:
  Line 1: Agent name + stack
  Line 2: Game phase
  Line 3: Last action (e.g. "RAISE 400")
  Line 4: Status / waiting message
"""
from machine import I2C, Pin
from config import PIN_I2C_SDA, PIN_I2C_SCL, OLED_WIDTH, OLED_HEIGHT, OLED_ADDR, AGENT_NAME

try:
    import ssd1306
    _SSD1306_AVAILABLE = True
except ImportError:
    print("WARNING: ssd1306 library not found. Display output will be printed to serial.")
    _SSD1306_AVAILABLE = False


class OLEDDisplay:
    def __init__(self):
        self._oled = None
        if _SSD1306_AVAILABLE:
            try:
                i2c = I2C(0, scl=Pin(PIN_I2C_SCL), sda=Pin(PIN_I2C_SDA), freq=400000)
                self._oled = ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, addr=OLED_ADDR)
                self.clear()
            except Exception as e:
                print(f"OLED init error: {e}")

    def clear(self):
        if self._oled:
            self._oled.fill(0)
            self._oled.show()

    def _line(self, row, text, invert=False):
        """Write text to a line (0–7 for 128x64 with 8px font)."""
        if self._oled:
            y = row * 8
            if invert:
                self._oled.fill_rect(0, y, OLED_WIDTH, 8, 1)
                self._oled.text(text[:16], 0, y, 0)
            else:
                self._oled.fill_rect(0, y, OLED_WIDTH, 8, 0)
                self._oled.text(text[:16], 0, y, 1)
        else:
            print(f"OLED[{row}]: {text}")

    def show_startup(self):
        """Boot screen."""
        if self._oled:
            self._oled.fill(0)
        self._line(0, "D.E.A.L.E.R.", invert=True)
        self._line(2, AGENT_NAME[:16])
        self._line(4, "Connecting...")
        if self._oled:
            self._oled.show()

    def show_ready(self, stack: int):
        if self._oled:
            self._oled.fill(0)
        self._line(0, AGENT_NAME[:16], invert=True)
        self._line(2, f"Stack: {stack}")
        self._line(4, "Ready")
        if self._oled:
            self._oled.show()

    def show_waiting_cards(self, stack: int):
        if self._oled:
            self._oled.fill(0)
        self._line(0, AGENT_NAME[:16], invert=True)
        self._line(2, f"Stack: {stack}")
        self._line(4, "Place cards...")
        if self._oled:
            self._oled.show()

    def show_cards_received(self, cards, stack: int):
        if self._oled:
            self._oled.fill(0)
        self._line(0, AGENT_NAME[:16], invert=True)
        self._line(2, f"Stack: {stack}")
        card_str = " ".join(cards) if cards else "??"
        self._line(4, f"Cards: {card_str}")
        self._line(6, "Received OK")
        if self._oled:
            self._oled.show()

    def show_thinking(self, stack: int, phase: str):
        if self._oled:
            self._oled.fill(0)
        self._line(0, AGENT_NAME[:16], invert=True)
        self._line(2, f"Stack: {stack}")
        self._line(4, phase.upper()[:16])
        self._line(6, "Thinking...")
        if self._oled:
            self._oled.show()

    def show_action(self, action: str, amount: int, stack: int, phase: str):
        if self._oled:
            self._oled.fill(0)
        self._line(0, AGENT_NAME[:16], invert=True)
        self._line(2, f"Stack: {stack}")
        self._line(4, phase.upper()[:16])
        action_str = action.upper()
        if amount > 0:
            action_str += f" {amount}"
        self._line(6, action_str[:16], invert=True)
        if self._oled:
            self._oled.show()

    def show_result(self, won: bool, pot: int, hand_name: str = ""):
        if self._oled:
            self._oled.fill(0)
        self._line(0, "SHOWDOWN", invert=True)
        self._line(2, "YOU WIN!" if won else "You lose")
        self._line(4, f"Pot: {pot}")
        if hand_name:
            self._line(6, hand_name[:16])
        if self._oled:
            self._oled.show()

    def show_error(self, msg: str):
        if self._oled:
            self._oled.fill(0)
        self._line(0, "ERROR", invert=True)
        self._line(2, msg[:16])
        self._line(4, msg[16:32])
        if self._oled:
            self._oled.show()

    def show(self):
        if self._oled:
            self._oled.show()
