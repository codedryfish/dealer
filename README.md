# D.E.A.L.E.R.
**Digitally Enhanced Agent-Led Entertainment Rig**

A physical AI poker station where two AI agents play Texas Hold'em using real cards and chips. The human operator deals, moves chips, and optionally plays as a third participant. Agents perceive their hole cards via RFID readers and communicate decisions through OLED displays and LED rings.

## Architecture

```
Raspberry Pi Zero 2 W (Central Brain)
├── Poker engine (Python / FastAPI)
├── WiFi Access Point (SSID: DEALER)
└── Web companion app (mobile-first)

ESP32-S3 Station A  ─── WiFi ───┐
ESP32-S3 Station B  ─── WiFi ───┤── Pi AP (192.168.4.1)
ESP32-S3 Community  ─── WiFi ───┘
```

## Play Modes

| Mode | Players | Human Role |
|------|---------|------------|
| Observer | Agent A vs Agent B | Dealer only |
| Player | Agent A vs Agent B vs Human | Dealer + player |
| Training | Agent A vs Human | Dealer + player (1v1) |

## Repository Structure

```
dealer/
├── pi/                     # Raspberry Pi Zero software
│   ├── dealer_engine/      # Poker engine Python package
│   ├── api/                # FastAPI server
│   ├── web/                # Companion web app (static)
│   ├── config/             # Pi system config files
│   └── tests/              # Unit tests
├── esp32/                  # ESP32 MicroPython firmware
│   ├── station/            # Agent station firmware
│   ├── community/          # Community reader firmware
│   └── tools/              # NFC programming utilities
└── docs/                   # Wiring guides and card maps
```

## Quick Start

### Pi Setup
1. Flash Raspberry Pi OS Lite (64-bit) to microSD
2. Connect Pi to Mac via micro-USB data port
3. SSH in: `ssh pi@dealer.local`
4. Run: `sudo bash /opt/dealer/config/setup_pi.sh`

### ESP32 Flashing
```bash
# Identify port
ls /dev/tty.usbmodem*

# Flash MicroPython + firmware (Claude handles this)
esptool.py --chip esp32s3 erase_flash
esptool.py --chip esp32s3 write_flash -z 0x0 ESP32_GENERIC_S3-*.bin
mpremote connect /dev/tty.usbmodemXXXX cp esp32/station/*.py :
```

## Development

```bash
# Run unit tests
cd pi && python -m pytest tests/ -v

# Run API locally
cd pi && uvicorn api.main:app --reload --port 8000

# Simulate a hand via API
curl -X POST http://localhost:8000/api/new-hand
```

## Hardware

See [docs/wiring_station.md](docs/wiring_station.md) for full wiring instructions.
See [docs/nfc_card_map.md](docs/nfc_card_map.md) for the 52-card NFC ID mapping.

Estimated BOM cost: £120–£171 (see spec for full list).

---

*Built by Arvind + Claude (Sonnet) — March 2026*
