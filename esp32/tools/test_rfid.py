"""
test_rfid.py — Continuous RFID read loop for verifying NFC card tags.

Run on an ESP32 station, place any tagged card on the reader.
Prints the decoded card ID. Press Ctrl-C to stop.

Usage:
  mpremote connect /dev/tty.usbmodemXXXX run esp32/tools/test_rfid.py
"""
import time
from machine import SPI, Pin

try:
    from mfrc522 import MFRC522
    MFRC522_AVAILABLE = True
except ImportError:
    print("mfrc522 not available. Simulation mode.")
    MFRC522_AVAILABLE = False

PIN_SS   = 5
PIN_SCK  = 18
PIN_MOSI = 23
PIN_MISO = 19
PIN_RST  = 4

VALID_RANKS = set("23456789TJQKA")
VALID_SUITS = set("HDCS")


def decode(data):
    try:
        raw = bytes(data[:2]).decode("ascii").upper().strip()
        if len(raw) >= 2 and raw[0] in VALID_RANKS and raw[1] in VALID_SUITS:
            return raw[:2]
    except Exception:
        pass
    return None


def run():
    if MFRC522_AVAILABLE:
        spi = SPI(1, baudrate=2500000, polarity=0, phase=0,
                  sck=Pin(PIN_SCK), mosi=Pin(PIN_MOSI), miso=Pin(PIN_MISO))
        reader = MFRC522(spi=spi, gpioCs=Pin(PIN_SS, Pin.OUT), gpioRst=Pin(PIN_RST, Pin.OUT))
    else:
        reader = None

    print("=== RFID Test — place cards on reader (Ctrl-C to stop) ===\n")
    last_uid = None

    while True:
        if not MFRC522_AVAILABLE:
            print("[SIM] No reader. Place simulated card: 'AH'")
            time.sleep(2)
            continue

        (stat, tag_type) = reader.request(reader.REQIDL)
        if stat != reader.OK:
            time.sleep_ms(100)
            continue

        (stat, uid) = reader.SelectTagSN()
        if stat != reader.OK:
            continue

        uid_str = ":".join(f"{b:02X}" for b in uid)
        if uid_str == last_uid:
            time.sleep_ms(500)
            continue
        last_uid = uid_str

        reader.auth(reader.AUTHENT1A, 1, b'\xff\xff\xff\xff\xff\xff', uid)
        (stat, data) = reader.read(1)
        reader.stop_crypto1()

        if stat == reader.OK:
            card = decode(data)
            if card:
                print(f"  UID: {uid_str}  →  Card: {card}  ✓")
            else:
                raw = bytes(data[:4]).hex()
                print(f"  UID: {uid_str}  →  Raw: {raw} (not a card tag)")
        else:
            print(f"  UID: {uid_str}  →  Read error")

        time.sleep_ms(300)


run()
