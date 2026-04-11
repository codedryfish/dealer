"""
write_nfc_tags.py — Utility to program all 52 playing cards with NFC tag IDs.

Run on an ESP32 station with MFRC522 connected.
Prompts Arvind to place each card on the reader; writes the 2-byte card ID.

Usage (from Mac, via mpremote):
  mpremote connect /dev/tty.usbmodemXXXX run esp32/tools/write_nfc_tags.py
"""
import time
from machine import SPI, Pin

try:
    from mfrc522 import MFRC522
    MFRC522_AVAILABLE = True
except ImportError:
    print("mfrc522 library not available. Running in simulation mode.")
    MFRC522_AVAILABLE = False

# Pin config (same as station)
PIN_SS   = 5
PIN_SCK  = 18
PIN_MOSI = 23
PIN_MISO = 19
PIN_RST  = 4

# Full 52-card deck in programming order
DECK = [
    # Aces
    "AS", "AC", "AD", "AH",
    # Kings
    "KS", "KC", "KD", "KH",
    # Queens
    "QS", "QC", "QD", "QH",
    # Jacks
    "JS", "JC", "JD", "JH",
    # Tens
    "TS", "TC", "TD", "TH",
    # Nines
    "9S", "9C", "9D", "9H",
    # Eights
    "8S", "8C", "8D", "8H",
    # Sevens
    "7S", "7C", "7D", "7H",
    # Sixes
    "6S", "6C", "6D", "6H",
    # Fives
    "5S", "5C", "5D", "5H",
    # Fours
    "4S", "4C", "4D", "4H",
    # Threes
    "3S", "3C", "3D", "3H",
    # Twos
    "2S", "2C", "2D", "2H",
]

RANK_NAMES = {
    "A": "Ace", "K": "King", "Q": "Queen", "J": "Jack", "T": "Ten",
    "9": "Nine", "8": "Eight", "7": "Seven", "6": "Six", "5": "Five",
    "4": "Four", "3": "Three", "2": "Two",
}
SUIT_NAMES = {"S": "Spades", "C": "Clubs", "D": "Diamonds", "H": "Hearts"}


def card_display(code):
    return f"{RANK_NAMES[code[0]]} of {SUIT_NAMES[code[1]]}"


def write_tag(reader, data: str):
    """Write 2-byte ASCII string to NTAG page 4 (first user-data page).
    Pages 0-3 on NTAG213/215 are UID/lock/CC — do not write there.
    No Mifare auth needed for NTAG tags.
    """
    payload = list(data.encode("ascii")) + [0] * 14  # Pad to 16 bytes
    (stat, tag_type) = reader.request(reader.REQIDL)
    if stat != reader.OK:
        return False
    (stat, uid) = reader.SelectTagSN()
    if stat != reader.OK:
        return False
    stat = reader.write(4, payload)
    reader.stop_crypto1()
    return stat == reader.OK


def run():
    if MFRC522_AVAILABLE:
        spi = SPI(1, baudrate=2500000, polarity=0, phase=0,
                  sck=Pin(PIN_SCK), mosi=Pin(PIN_MOSI), miso=Pin(PIN_MISO))
        reader = MFRC522(spi=spi, gpioCs=Pin(PIN_SS, Pin.OUT), gpioRst=Pin(PIN_RST, Pin.OUT))
    else:
        reader = None

    total = len(DECK)
    print(f"\n=== NFC Tag Writer — {total} cards ===")
    print("Place each card (sticker-side down) on the reader when prompted.\n")

    for i, code in enumerate(DECK):
        name = card_display(code)
        print(f"[{i+1}/{total}] Place the {name} on the reader...")

        if not MFRC522_AVAILABLE:
            print(f"  [SIM] Would write '{code}' → OK")
            time.sleep_ms(500)
            continue

        success = False
        attempts = 0
        while not success and attempts < 10:
            attempts += 1
            (stat, _) = reader.request(reader.REQIDL)
            if stat != reader.OK:
                time.sleep_ms(200)
                continue
            success = write_tag(reader, code)

        if success:
            print(f"  ✓ Written '{code}'")
        else:
            print(f"  ✗ FAILED after {attempts} attempts. Re-run this card later.")

        # Wait for card to be removed
        time.sleep_ms(800)

    print(f"\n=== Done! {total} cards programmed. ===")
    print("Run test_rfid.py to verify any card.")


run()
