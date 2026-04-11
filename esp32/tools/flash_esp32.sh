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

# ── Download third-party libraries ──────────────────────────────────────────
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

echo "Downloading MicroPython libraries..."

# MFRC522 driver (wendlers/micropython-mfrc522)
curl -sSL "https://raw.githubusercontent.com/wendlers/micropython-mfrc522/master/mfrc522.py" \
  -o "$TMPDIR/mfrc522.py"

# SSD1306 OLED driver (micropython/micropython-lib)
curl -sSL "https://raw.githubusercontent.com/micropython/micropython-lib/master/micropython/drivers/display/ssd1306/ssd1306.py" \
  -o "$TMPDIR/ssd1306.py"

echo "Libraries downloaded."
# Note: urequests is frozen into the ESP32-S3 firmware — no download needed.

# ── Patch mfrc522.py for ESP32/ESP32-S3 ─────────────────────────────────────
# The wendlers library only handles WiPy/LoPy/FiPy and ESP8266. It raises
# RuntimeError("Unsupported platform") on ESP32/ESP32-S3. We inject an elif
# branch before the else so it constructs SPI(1, ...) using the Pin objects
# already built in __init__.
python3 - "$TMPDIR/mfrc522.py" <<'PYEOF'
import sys
path = sys.argv[1]
with open(path) as f:
    src = f.read()
patch_old = '\telse:\n\t\traise RuntimeError("Unsupported platform")'
patch_new = (
    '\telif \'esp32\' in board.lower():\n'
    '\t\tself.spi = SPI(1, baudrate=1000000, polarity=0, phase=0,\n'
    '\t\t\tsck=self.sck, mosi=self.mosi, miso=self.miso)\n'
    '\telse:\n'
    '\t\traise RuntimeError("Unsupported platform")'
)
if patch_old in src:
    src = src.replace(patch_old, patch_new)
    with open(path, 'w') as f:
        f.write(src)
    print("  mfrc522.py patched: added ESP32/ESP32-S3 SPI support.")
else:
    print("  WARNING: mfrc522.py patch anchor not found — library may have changed upstream.")
PYEOF

# ── Build config.py for this station ────────────────────────────────────────
cp esp32/station/config.py "$TMPDIR/config.py"
# Patch STATION_ID in-place
sed -i.bak "s/^STATION_ID = .*/STATION_ID = \"$STATION\"/" "$TMPDIR/config.py"
rm -f "$TMPDIR/config.py.bak"

# ── Upload files ─────────────────────────────────────────────────────────────
upload() {
  local src=$1
  local dst=$2
  echo "  Uploading $dst..."
  mpremote connect "$PORT" cp "$src" ":$dst"
}

echo ""
echo "=== Uploading firmware for Station $STATION ==="

# Third-party libraries
upload "$TMPDIR/mfrc522.py"  "mfrc522.py"
upload "$TMPDIR/ssd1306.py"  "ssd1306.py"
# Station config (patched with correct STATION_ID)
upload "$TMPDIR/config.py"   "config.py"

# Shared station modules
upload "esp32/station/rfid.py"    "rfid.py"
upload "esp32/station/display.py" "display.py"
upload "esp32/station/leds.py"    "leds.py"
upload "esp32/station/buzzer.py"  "buzzer.py"
upload "esp32/station/api_client.py" "api_client.py"

# Main entry point — community or station
if [[ "$STATION" == "C" ]]; then
  upload "esp32/community/main.py" "main.py"
else
  upload "esp32/station/main.py"   "main.py"
fi

echo ""
echo "=== Station $STATION flashed successfully! ==="
echo "    Reset the ESP32 (press EN/RST button) to start firmware."
echo "    Monitor serial output with:"
echo "    mpremote connect $PORT"
