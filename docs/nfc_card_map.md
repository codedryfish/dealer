# NFC Card Map — Full 52-Card Deck

Each playing card gets an NTAG213 sticker on its back, programmed with a 2-byte ASCII card ID.

## ID Format

`<Rank><Suit>` where:
- **Rank:** `2 3 4 5 6 7 8 9 T J Q K A`
- **Suit:** `H` (Hearts) `D` (Diamonds) `C` (Clubs) `S` (Spades)

**Examples:** `AH` = Ace of Hearts, `TC` = Ten of Clubs, `2S` = Two of Spades

---

## Full Mapping

| Card | ID | Card | ID | Card | ID | Card | ID |
|------|----|------|----|------|----|------|----|
| Ace ♠ | `AS` | Ace ♣ | `AC` | Ace ♦ | `AD` | Ace ♥ | `AH` |
| King ♠ | `KS` | King ♣ | `KC` | King ♦ | `KD` | King ♥ | `KH` |
| Queen ♠ | `QS` | Queen ♣ | `QC` | Queen ♦ | `QD` | Queen ♥ | `QH` |
| Jack ♠ | `JS` | Jack ♣ | `JC` | Jack ♦ | `JD` | Jack ♥ | `JH` |
| Ten ♠ | `TS` | Ten ♣ | `TC` | Ten ♦ | `TD` | Ten ♥ | `TH` |
| Nine ♠ | `9S` | Nine ♣ | `9C` | Nine ♦ | `9D` | Nine ♥ | `9H` |
| Eight ♠ | `8S` | Eight ♣ | `8C` | Eight ♦ | `8D` | Eight ♥ | `8H` |
| Seven ♠ | `7S` | Seven ♣ | `7C` | Seven ♦ | `7D` | Seven ♥ | `7H` |
| Six ♠ | `6S` | Six ♣ | `6C` | Six ♦ | `6D` | Six ♥ | `6H` |
| Five ♠ | `5S` | Five ♣ | `5C` | Five ♦ | `5D` | Five ♥ | `5H` |
| Four ♠ | `4S` | Four ♣ | `4C` | Four ♦ | `4D` | Four ♥ | `4H` |
| Three ♠ | `3S` | Three ♣ | `3C` | Three ♦ | `3D` | Three ♥ | `3H` |
| Two ♠ | `2S` | Two ♣ | `2C` | Two ♦ | `2D` | Two ♥ | `2H` |

---

## Programming Procedure

Run `esp32/tools/write_nfc_tags.py` on any station with RFID connected.

The script walks through all 52 cards in the order above, prompting:
```
[1/52] Place the Ace of Spades on the reader...
  ✓ Written 'AS'
[2/52] Place the Ace of Clubs on the reader...
```

**Tips:**
- Sort your physical deck to match the script order before starting
- Keep each card on the reader until you hear the beep, then remove it
- The full session takes ~10 minutes
- Extra NTAG213 stickers are recommended for re-tagging worn cards

## Sticker Placement

- Place the NFC sticker **centred on the card back**
- Smooth side of the sticker down onto the card
- Avoid air bubbles — press firmly from the centre outward
- The MFRC522 reads best at **0–20mm distance** through the card

## Re-programming a Card

If a sticker is damaged or needs re-encoding:
1. Peel off old sticker (or place new one on top — NTAG213 can be re-written)
2. Run `write_nfc_tags.py` and skip to the specific card using keyboard interrupt and restart
3. Or run `test_rfid.py` to verify the existing data before re-programming
