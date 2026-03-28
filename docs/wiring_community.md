# Wiring Guide: Community Station

The community station uses an **ESP32-S3-WROOM-1 DevKit** with:
- MFRC522 RFID reader (same wiring as agent stations)
- Passive buzzer (card read confirmation)
- 3 tactile push buttons: FOLD / CALL / RAISE

No OLED or LED ring required (can be added later for pot display).

---

## Pin Map

### MFRC522 RFID Reader

Identical to agent stations — see [wiring_station.md](wiring_station.md) for full details.

| MFRC522 | GPIO | Notes |
|---------|------|-------|
| SDA/CS | 5 | |
| SCK | 18 | |
| MOSI | 23 | |
| MISO | 19 | |
| RST | 4 | |
| 3.3V | 3.3V | NOT 5V |
| GND | GND | |

### Passive Buzzer

| Pin | GPIO | Notes |
|-----|------|-------|
| + | GPIO 17 | 100Ω series resistor |
| – | GND | |

### Human Input Buttons (active LOW, pull-up enabled in firmware)

| Button | GPIO | Wiring |
|--------|------|--------|
| FOLD | GPIO 25 | One leg to GPIO 25, other leg to GND |
| CALL | GPIO 26 | One leg to GPIO 26, other leg to GND |
| RAISE | GPIO 27 | One leg to GPIO 27, other leg to GND |

> The firmware enables `Pin.PULL_UP` internally — no external resistor needed on the buttons.

---

## Button Layout (suggested physical arrangement)

```
┌─────────────────────────────────┐
│   [  FOLD  ]  [  CALL  ]  [RAISE]│
│    red          green       gold  │
└─────────────────────────────────┘
```

Use 12mm momentary tactile buttons. Colour-code them for quick recognition during play.

---

## Community Station Role

The community station sits at the **centre of the table** with:
- The RFID read zone directly below the community card area
- The 3 buttons facing the human player

Cards are placed **face-down** one at a time on the read zone:
- Flop: 3 cards (placed one by one; each triggers a beep)
- Turn: 1 card
- River: 1 card

The firmware POSTs each batch to `/api/community` once all cards in the batch are read.

---

## Verification Checklist

- [ ] MFRC522 on 3.3V rail (not 5V)
- [ ] All three buttons wired to GND on one leg
- [ ] Buzzer has series resistor
- [ ] Serial output: "Community station ready"
- [ ] Place a tagged card → buzzer beeps, serial shows card code
- [ ] Press FOLD button → serial shows "Button: FOLD"
