#!/bin/bash
# flash_esp32.sh — Upload D.E.A.L.E.R. MicroPython firmware to an ESP32-S3
#
# Usage:
#   bash esp32/tools/flash_esp32.sh A                          # auto-detect port
#   bash esp32/tools/flash_esp32.sh A /dev/cu.usbmodem101     # specify port
#   bash esp32/tools/flash_esp32.sh B /dev/cu.usbmodem101
#   bash esp32/tools/flash_esp32.sh C /dev/cu.usbmodem101
#
# Prerequisites (run once):
#   pip3 install mpremote
#
# Run from the repo root directory.

set -e

STATION=${1:-}
PORT=${2:-}

if [[ "$STATION" != "A" && "$STATION" != "B" && "$STATION" != "C" ]]; then
  echo "Usage: bash esp32/tools/flash_esp32.sh [A|B|C] [/dev/cu.usbmodemXXXX]"
  echo "  A = Agent Alpha station"
  echo "  B = Agent Beta station"
  echo "  C = Community reader"
  echo ""
  echo "Available ports:"
  mpremote connect list 2>/dev/null || true
  exit 1
fi

# ── Check mpremote ───────────────────────────────────────────────────────────
if ! command -v mpremote &>/dev/null; then
  echo "Error: mpremote not found. Install it with:"
  echo "  pip3 install mpremote"
  exit 1
fi

# ── Resolve port ─────────────────────────────────────────────────────────────
if [[ -n "$PORT" ]]; then
  echo "Using port: $PORT"
else
  echo "Detecting connected ESP32..."
  PORT=$(mpremote connect list 2>/dev/null \
    | grep -i "usbmodem\|SLAB\|usbserial\|wchusbserial" \
    | head -1 | awk '{print $1}')
  if [[ -z "$PORT" ]]; then
    echo "Error: No ESP32 found. Specify the port manually:"
    echo "  bash esp32/tools/flash_esp32.sh $STATION /dev/cu.usbmodemXXXX"
    echo ""
    echo "Available ports:"
    mpremote connect list
    exit 1
  fi
  echo "Found: $PORT"
fi

# ── Prepare libraries ────────────────────────────────────────────────────────
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

echo "Preparing libraries..."

# MFRC522: use our own driver (esp32/lib/mfrc522.py) — tested at 100kHz with
# integer pin numbers. The wendlers library fails on ESP32-S3 because it passes
# Pin objects to SPI() which causes 0xff reads on MicroPython v1.27.0.
cp esp32/lib/mfrc522.py "$TMPDIR/mfrc522.py"
echo "  mfrc522.py: using local driver (100kHz, NTAG-compatible)"

# SSD1306 OLED driver (micropython/micropython-lib)
curl -sSL "https://raw.githubusercontent.com/micropython/micropython-lib/master/micropython/drivers/display/ssd1306/ssd1306.py" \
  -o "$TMPDIR/ssd1306.py"
echo "  ssd1306.py: downloaded"
# Note: urequests is frozen into the ESP32-S3 firmware — no download needed.

# ── Build config.py for this station ────────────────────────────────────────
cp esp32/station/config.py "$TMPDIR/config.py"
# Patch STATION_ID in-place
sed -i.bak "s/^STATION_ID = .*/STATION_ID = \"$STATION\"/" "$TMPDIR/config.py"
rm -f "$TMPDIR/config.py.bak"

# ── Select main.py source ────────────────────────────────────────────────────
if [[ "$STATION" == "C" ]]; then
  MAIN_SRC="esp32/community/main.py"
else
  MAIN_SRC="esp32/station/main.py"
fi

echo ""
echo "=== Uploading firmware for Station $STATION ==="

# ── Step 1: Upload boot.py alone, with retries ───────────────────────────────
# If main.py is crash-looping from a bad previous flash, mpremote can't enter
# raw REPL. We retry until we catch the ~3s boot window. Once boot.py lands,
# it inserts a 3-second idle delay on every boot — making future flashes safe.
echo "  Phase 1: uploading boot.py (retry loop — press RST on the board now)..."
MAX_ATTEMPTS=15
for i in $(seq 1 $MAX_ATTEMPTS); do
  printf "    attempt %d/%d... " "$i" "$MAX_ATTEMPTS"
  if mpremote connect "$PORT" cp esp32/station/boot.py :boot.py 2>/dev/null; then
    echo "OK"
    break
  fi
  echo "no repl yet"
  if [[ "$i" == "$MAX_ATTEMPTS" ]]; then
    echo ""
    echo "ERROR: Could not reach REPL after $MAX_ATTEMPTS attempts."
    echo "       Try holding RST on the board and re-running this script."
    exit 1
  fi
  sleep 1
done

# boot.py is now on the board — next reset gives a clean 3-second window.
echo "  boot.py uploaded. Waiting for board to reboot with delay..."
sleep 4

# ── Step 2: Upload remaining files in one session ───────────────────────────
echo "  Phase 2: uploading all firmware files..."
mpremote connect "$PORT" \
  cp "$TMPDIR/mfrc522.py"          :mfrc522.py    + \
  cp "$TMPDIR/ssd1306.py"          :ssd1306.py    + \
  cp "$TMPDIR/config.py"           :config.py     + \
  cp esp32/station/rfid.py         :rfid.py       + \
  cp esp32/station/display.py      :display.py    + \
  cp esp32/station/leds.py         :leds.py       + \
  cp esp32/station/buzzer.py       :buzzer.py     + \
  cp esp32/station/api_client.py   :api_client.py + \
  cp "$MAIN_SRC"                   :main.py

echo ""
echo "=== Station $STATION flashed successfully! ==="
echo "    Reset the ESP32 (press EN/RST button) to start firmware."
echo "    Monitor serial output with:"
echo "    mpremote connect $PORT"
