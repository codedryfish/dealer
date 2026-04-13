"""debug_rfid.py — Hold a sticker on the reader before running."""
from mfrc522 import MFRC522
import time

r = MFRC522(sck=18, mosi=11, miso=13, rst=4, cs=5)
print("version:", hex(r._rreg(0x37)))

# Wait for card
for _ in range(50):
    stat, bits = r.request(r.REQIDL)
    if stat == r.OK:
        break
    time.sleep_ms(100)
else:
    print("NO CARD DETECTED")
    raise SystemExit

print("request OK bits:", bits)

stat, uid = r.SelectTagSN()
print("select stat:", stat, "uid:", uid)
if stat != r.OK:
    raise SystemExit

buf = [0xA2, 4, 65, 72, 0, 0]
buf += r._crc(buf)
r._wr(r._BFRAME, 0x00)
stat, recv, bits = r._transceive(buf)
print("write stat:", stat, "recv:", recv, "bits:", bits)
