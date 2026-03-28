# Wiring Guide: Agent Station (A or B)

Each agent station connects an **ESP32-S3-WROOM-1 DevKit** to:
- MFRC522 RFID reader (SPI)
- SSD1306 OLED 128×64 (I2C)
- WS2812B LED ring (12-LED)
- Passive buzzer

## Power Rails

Set up your breadboard with a **3.3V rail** and a **5V rail** (GND shared).

| Source | Voltage | Used by |
|--------|---------|---------|
| ESP32 3V3 pin | 3.3V | MFRC522, OLED |
| ESP32 5V (VBUS) | 5V | WS2812B LED ring |
| ESP32 GND | 0V | All components |

⚠️ **The MFRC522 must NOT be powered from 5V — it has no onboard regulator and will be damaged.**

---

## Pin Map

### MFRC522 RFID Reader (SPI)

| MFRC522 Pin | ESP32-S3 Pin | Wire Colour | Notes |
|-------------|-------------|-------------|-------|
| SDA (SS/CS) | GPIO 5 | Yellow | Chip select |
| SCK | GPIO 18 | Orange | SPI clock |
| MOSI | GPIO 23 | Green | SPI data out |
| MISO | GPIO 19 | Blue | SPI data in |
| RST | GPIO 4 | White | Reset |
| 3.3V | 3.3V rail | Red | Power — NOT 5V |
| GND | GND rail | Black | Ground |

### SSD1306 OLED Display (I2C, address 0x3C)

| OLED Pin | ESP32-S3 Pin | Wire Colour | Notes |
|----------|-------------|-------------|-------|
| SDA | GPIO 21 | Purple | I2C data |
| SCL | GPIO 22 | Grey | I2C clock |
| VCC | 3.3V rail | Red | Shared with MFRC522 |
| GND | GND rail | Black | Ground |

### WS2812B LED Ring (12-LED)

| LED Pin | ESP32-S3 Pin | Wire Colour | Notes |
|---------|-------------|-------------|-------|
| DIN (Data In) | GPIO 16 | Brown | 3.3V signal tolerated |
| 5V | 5V (VBUS) | Red | From USB power rail |
| GND | GND rail | Black | Ground |

> If the LEDs flicker or glitch, add a **300–500Ω resistor** on the DIN line.

### Passive Buzzer

| Buzzer Pin | ESP32-S3 Pin | Wire Colour | Notes |
|------------|-------------|-------------|-------|
| + (positive) | GPIO 17 | Orange | Via 100Ω series resistor |
| – (negative) | GND rail | Black | Ground |

---

## Breadboard Layout Tips

1. Place the ESP32-S3 spanning the centre of the breadboard.
2. Run the 3.3V and GND power rails along the top (positive) and bottom (negative) strips.
3. Wire MFRC522 first — it's the most critical component.
4. Wire OLED next to the I2C pins.
5. Place the LED ring off the breadboard; run 3 wires (5V, GND, DIN) to it.
6. Add the buzzer last.

---

## Verification Checklist

Before powering on:
- [ ] MFRC522 connected to 3.3V (not 5V)
- [ ] All GND connections share a common rail
- [ ] OLED I2C address confirmed as 0x3C (4-pin display)
- [ ] LED ring 5V connected to VBUS (not 3.3V)
- [ ] Buzzer has series resistor on positive leg

After flashing firmware:
- [ ] OLED shows "D.E.A.L.E.R." startup screen
- [ ] LED ring lights up briefly (idle = off)
- [ ] Serial output shows "Connecting to DEALER..."
- [ ] Place a tagged card → buzzer beeps + LED flashes white

---

## MicroPython Libraries Needed

Upload these to the ESP32 before running station firmware:

| Library | Source |
|---------|--------|
| `mfrc522.py` | https://github.com/wendlers/micropython-mfrc522 |
| `ssd1306.py` | Built into MicroPython firmware (or from micropython/drivers) |
| `neopixel` | Built into MicroPython firmware |
