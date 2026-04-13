"""
mfrc522.py — MFRC522 RFID reader driver for MicroPython on ESP32-S3.

Drop-in replacement for wendlers/micropython-mfrc522 with the same public API.
Uses SPI(1, baudrate=100kHz) with integer pin numbers — the only combination
confirmed working on breadboard jumper wires with MicroPython v1.27.0.

Optimised for NTAG213/215 NFC stickers (NTAG WRITE 0xA2, not Mifare 0xA0).
"""
from machine import SPI, Pin
import time


class MFRC522:
    OK       = 0
    NOTAGERR = 1
    ERR      = 2

    REQIDL    = 0x26
    REQALL    = 0x52
    AUTHENT1A = 0x60
    AUTHENT1B = 0x61

    # Registers
    _COMIEN  = 0x02
    _COMIRQ  = 0x04
    _DIVIRQ  = 0x05
    _ERR_REG = 0x06
    _STATUS2 = 0x08
    _FIFO    = 0x09
    _FLEVEL  = 0x0A
    _CTRL    = 0x0C
    _BFRAME  = 0x0D
    _MODE    = 0x11
    _TXCTRL  = 0x14
    _TXASK   = 0x15
    _CRCL    = 0x22   # LSB first for ISO 14443
    _CRCH    = 0x21
    _TMODE   = 0x2A
    _TPRE    = 0x2B
    _TRELH   = 0x2C
    _TRELL   = 0x2D

    def __init__(self, sck, mosi, miso, rst, cs):
        self.rst = Pin(rst, Pin.OUT)
        self.cs  = Pin(cs,  Pin.OUT)

        # Hardware reset
        self.rst.value(0)
        self.cs.value(1)
        time.sleep_ms(50)
        self.rst.value(1)
        time.sleep_ms(50)

        # 100 kHz works reliably on breadboard jumper wires.
        # Pass raw integer pin numbers — Pin objects cause 0xff reads.
        self.spi = SPI(1, baudrate=100000, polarity=0, phase=0,
                       sck=Pin(sck), mosi=Pin(mosi), miso=Pin(miso))
        self._init()

    # ── Register I/O ───────────────────────────────────────────────────────────

    def _wr(self, addr, val):
        self.cs.value(0)
        self.spi.write(bytes([(addr << 1) & 0x7E, val]))
        self.cs.value(1)

    def _rd(self, addr):
        self.cs.value(0)
        self.spi.write(bytes([0x80 | ((addr << 1) & 0x7E)]))
        val = self.spi.read(1)
        self.cs.value(1)
        return val[0]

    def _sf(self, addr, mask):
        self._wr(addr, self._rd(addr) | mask)

    def _cf(self, addr, mask):
        self._wr(addr, self._rd(addr) & ~mask)

    # Backwards-compat aliases used by rfid.py diagnostic code
    def _rreg(self, addr): return self._rd(addr)
    def _wreg(self, addr, val): self._wr(addr, val)

    # ── Chip initialisation ────────────────────────────────────────────────────

    def _init(self):
        self._wr(0x01, 0x0F)           # SoftReset
        time.sleep_ms(50)
        self._wr(self._TMODE,  0x8D)   # timer auto, 6.78MHz / prescaler
        self._wr(self._TPRE,   0x3E)
        self._wr(self._TRELH,  0x00)
        self._wr(self._TRELL,  0x1E)   # ~5 ms timeout
        self._wr(self._TXASK,  0x40)   # 100% ASK modulation
        self._wr(self._MODE,   0x3D)   # CRC preset 0x6363
        self._sf(self._TXCTRL, 0x03)   # antenna on

    # ── CRC ────────────────────────────────────────────────────────────────────

    def _crc(self, data):
        self._cf(self._DIVIRQ, 0x04)   # clear CRCIrq
        self._sf(self._FLEVEL, 0x80)   # flush FIFO
        for b in data:
            self._wr(self._FIFO, b)
        self._wr(0x01, 0x03)           # CalcCRC command
        i = 255
        while i:
            if self._rd(self._DIVIRQ) & 0x04:
                break
            i -= 1
        return [self._rd(self._CRCL), self._rd(self._CRCH)]

    # ── Core transceive ────────────────────────────────────────────────────────

    def _transceive(self, send):
        self._wr(self._COMIEN, 0x77 | 0x80)  # enable irqs
        self._cf(self._COMIRQ, 0x80)          # clear irq flags
        self._sf(self._FLEVEL, 0x80)          # flush FIFO
        self._wr(0x01, 0x00)                  # Idle
        for b in send:
            self._wr(self._FIFO, b)
        self._wr(0x01, 0x0C)                  # Transceive
        self._sf(self._BFRAME, 0x80)          # StartSend

        i = 2000
        while True:
            n = self._rd(self._COMIRQ)
            i -= 1
            if not (i and not (n & 0x01) and not (n & 0x30)):
                break

        self._cf(self._BFRAME, 0x80)

        stat, recv, bits = self.ERR, [], 0
        if i:
            if not (self._rd(self._ERR_REG) & 0x1B):
                stat = self.OK
                if n & 0x01:
                    stat = self.NOTAGERR
                n = self._rd(self._FLEVEL)
                lbits = self._rd(self._CTRL) & 0x07
                bits = (n - 1) * 8 + lbits if lbits else n * 8
                n = min(max(n, 1), 16)
                recv = [self._rd(self._FIFO) for _ in range(n)]
        return stat, recv, bits

    # ── Public API ─────────────────────────────────────────────────────────────

    def request(self, req_mode):
        """Probe for a card. Returns (OK/ERR, bits)."""
        self._wr(self._BFRAME, 0x07)   # 7-bit frame for REQA
        stat, recv, bits = self._transceive([req_mode])
        if stat != self.OK or bits != 0x10:
            return self.ERR, 0
        return self.OK, bits

    def anticoll(self):
        """Anti-collision loop. Returns (status, uid_bytes)."""
        self._wr(self._BFRAME, 0x00)  # full bytes, clear 7-bit flag left by request()
        stat, recv, bits = self._transceive([0x93, 0x20])
        if stat == self.OK and len(recv) == 5:
            if recv[0] ^ recv[1] ^ recv[2] ^ recv[3] == recv[4]:
                return self.OK, recv
        return self.ERR, []

    def SelectTagSN(self):
        """Anti-collision + SELECT. Returns (status, 4-byte uid)."""
        stat, uid = self.anticoll()
        if stat != self.OK:
            return self.ERR, []
        buf = [0x93, 0x70] + uid
        buf += self._crc(buf)
        self._wr(self._BFRAME, 0x00)  # full bytes
        stat, recv, bits = self._transceive(buf)
        if stat == self.OK and bits == 0x18:
            return self.OK, uid[:4]
        return self.ERR, []

    def read(self, addr):
        """Read 16 bytes from NTAG page addr. Returns (status, data)."""
        buf = [0x30, addr]
        buf += self._crc(buf)
        self._wr(self._BFRAME, 0x00)  # full bytes
        stat, recv, bits = self._transceive(buf)
        if stat == self.OK and len(recv) >= 4:
            return self.OK, recv
        return self.ERR, []

    def write(self, addr, data):
        """Write 4 bytes to NTAG page addr using NTAG WRITE (0xA2).
        Note: Mifare WRITE (0xA0) is different — don't use for NTAG stickers."""
        buf = [0xA2, addr] + list(data[:4])
        buf += self._crc(buf)
        self._wr(self._BFRAME, 0x00)  # full bytes — must clear 7-bit flag from request()
        stat, recv, bits = self._transceive(buf)
        if stat == self.OK and bits == 4 and recv and (recv[0] & 0x0F) == 0x0A:
            return self.OK
        return self.ERR

    def stop_crypto1(self):
        """No-op for NTAG; clears Mifare crypto flag for compatibility."""
        self._cf(self._STATUS2, 0x08)

    def auth(self, auth_mode, addr, key, uid):
        """Mifare auth — not needed for NTAG but kept for API compatibility."""
        buf = [auth_mode, addr] + list(key) + list(uid[:4])
        stat, recv, bits = self._transceive(buf)
        return stat

    def antenna_on(self):
        self._sf(self._TXCTRL, 0x03)
