"""
rfid.py — MFRC522 RFID driver wrapper for MicroPython.

Reads NTAG213 NFC stickers programmed with 2-byte card IDs (e.g. "AH", "KD").
Uses the mfrc522 MicroPython library (must be uploaded to the ESP32).

Card IDs stored on tags: Rank (2-9,T,J,Q,K,A) + Suit (H,D,C,S)
"""
import time
from config import PIN_RFID_SS, PIN_RFID_SCK, PIN_RFID_MOSI, PIN_RFID_MISO, PIN_RFID_RST

try:
    from mfrc522 import MFRC522
    _MFRC522_AVAILABLE = True
except ImportError:
    print("WARNING: mfrc522 library not found. RFID reads will be simulated.")
    _MFRC522_AVAILABLE = False


VALID_RANKS = set("23456789TJQKA")
VALID_SUITS = set("HDCS")


class RFIDReader:
    def __init__(self):
        if _MFRC522_AVAILABLE:
            # wendlers/micropython-mfrc522 takes raw pin numbers and builds SPI internally
            self._reader = MFRC522(
                sck=PIN_RFID_SCK,
                mosi=PIN_RFID_MOSI,
                miso=PIN_RFID_MISO,
                rst=PIN_RFID_RST,
                cs=PIN_RFID_SS,
            )
        else:
            self._reader = None

    def read_card(self, timeout_ms=5000):
        """
        Block until a card is detected or timeout expires.
        Returns 2-char card string (e.g. "AH") or None on timeout/error.
        """
        if not _MFRC522_AVAILABLE:
            return None

        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            (stat, tag_type) = self._reader.request(self._reader.REQIDL)
            if stat != self._reader.OK:
                time.sleep_ms(50)
                continue

            (stat, raw_uid) = self._reader.SelectTagSN()
            if stat != self._reader.OK:
                time.sleep_ms(50)
                continue

            # Read page 4 — first user-data page on NTAG213/215.
            # Pages 0-3 are UID / lock bytes / CC (read-only or reserved).
            # No auth needed for NTAG; stop_crypto1 is a safe no-op.
            (stat, data) = self._reader.read(4)
            self._reader.stop_crypto1()

            if stat == self._reader.OK and data:
                card_str = _decode_tag(bytes(data))
                if card_str:
                    return card_str

            time.sleep_ms(100)

        return None

    def read_n_cards(self, n, timeout_ms=30000, beep_fn=None, flash_fn=None):
        """
        Read exactly n distinct cards sequentially.
        Returns list of card strings, or partial list on timeout.
        """
        cards = []
        seen = set()
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)

        while len(cards) < n and time.ticks_diff(deadline, time.ticks_ms()) > 0:
            remaining_ms = time.ticks_diff(deadline, time.ticks_ms())
            card = self.read_card(timeout_ms=min(remaining_ms, 3000))
            if card and card not in seen:
                seen.add(card)
                cards.append(card)
                print(f"Card read: {card}")
                if beep_fn:
                    beep_fn()
                if flash_fn:
                    flash_fn("green")
                # Brief pause to avoid double-reads
                time.sleep_ms(500)

        return cards


def _decode_tag(data: bytes):
    """
    Decode raw RFID tag data to a card string.
    Expects first 2 bytes to be ASCII rank + suit.
    """
    try:
        raw = data[:2].decode("ascii").upper().strip()
        if len(raw) >= 2 and raw[0] in VALID_RANKS and raw[1] in VALID_SUITS:
            return raw[:2]
    except Exception:
        pass
    return None
