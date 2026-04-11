"""
main.py — ESP32-S3 Community Station firmware.

Handles:
  - Community card RFID reads (flop=3, turn=1, river=1)
  - 3 physical buttons: FOLD / CALL / RAISE (for human player)

Polls game state, detects when community cards are expected,
reads RFID tags, and POSTs them to the Pi API.

Button presses POST /api/human-action directly.
"""
import time
import gc
import network as net_module
import urequests
import ujson
from machine import Pin

from rfid import RFIDReader
from buzzer import Buzzer

# ── Config ──────────────────────────────────────────────────────────────────
WIFI_SSID = "DEALER"
WIFI_PASSWORD = "dealermeplease"
API_BASE = "http://192.168.4.1:8000/api"
STATION_ID = "C"
POLL_INTERVAL = 0.5

# Community station pin assignments
# NOTE: GPIO 19/20 = USB D-/D+. GPIO 22-25 don't exist on ESP32-S3.
#       GPIO 26-32 = internal flash on WROOM-1 module — do not use.
PIN_RFID_SS   = 5
PIN_RFID_SCK  = 18
PIN_RFID_MOSI = 11  # Was 23 — does not exist on ESP32-S3
PIN_RFID_MISO = 13  # Was 19 — USB D-
PIN_RFID_RST  = 4
PIN_BUZZER    = 17

# Human action buttons (active LOW with internal pull-up)
PIN_BTN_FOLD  = 6   # Was 25 — does not exist on ESP32-S3
PIN_BTN_CALL  = 7   # Was 26 — internal flash pin
PIN_BTN_RAISE = 8   # Was 27 — internal flash pin

# Expected card counts per phase
COMMUNITY_COUNTS = {
    "flop_deal": 3,
    "turn_deal": 1,
    "river_deal": 1,
}


# ── WiFi ────────────────────────────────────────────────────────────────────
def connect_wifi():
    wlan = net_module.WLAN(net_module.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return True
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    for _ in range(30):
        if wlan.isconnected():
            print(f"Connected: {wlan.ifconfig()}")
            return True
        time.sleep(0.5)
    return False


# ── API helpers ──────────────────────────────────────────────────────────────
def get_state():
    try:
        resp = urequests.get(f"{API_BASE}/state")
        d = resp.json(); resp.close()
        return d
    except Exception as e:
        print(f"get_state err: {e}")
        return None


def post_community(cards):
    try:
        payload = ujson.dumps({"cards": cards})
        resp = urequests.post(f"{API_BASE}/community", data=payload,
                              headers={"Content-Type": "application/json"})
        d = resp.json(); resp.close()
        return d
    except Exception as e:
        print(f"post_community err: {e}")
        return None


def post_human_action(action, amount=0):
    try:
        payload = ujson.dumps({"action": action, "amount": amount})
        resp = urequests.post(f"{API_BASE}/human-action", data=payload,
                              headers={"Content-Type": "application/json"})
        d = resp.json(); resp.close()
        return d
    except Exception as e:
        print(f"post_human_action err: {e}")
        return None


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    rfid = RFIDReader()
    buzzer = Buzzer()

    # Button setup
    btn_fold  = Pin(PIN_BTN_FOLD,  Pin.IN, Pin.PULL_UP)
    btn_call  = Pin(PIN_BTN_CALL,  Pin.IN, Pin.PULL_UP)
    btn_raise = Pin(PIN_BTN_RAISE, Pin.IN, Pin.PULL_UP)

    print("Community station booting...")
    connected = False
    while not connected:
        connected = connect_wifi()
        if not connected:
            print("WiFi failed, retrying...")
            time.sleep(3)

    print("Community station ready")

    last_phase = None
    last_btn_state = {"fold": 1, "call": 1, "raise": 1}

    while True:
        try:
            gc.collect()
            state = get_state()
            if not state:
                time.sleep(POLL_INTERVAL)
                continue

            phase = state.get("phase", "idle")

            # ── Community card reading ──────────────────────────────────
            if phase in COMMUNITY_COUNTS and last_phase != phase:
                n = COMMUNITY_COUNTS[phase]
                print(f"Waiting for {n} community card(s) ({phase})")
                cards = rfid.read_n_cards(
                    n=n,
                    timeout_ms=120_000,
                    beep_fn=buzzer.card_read,
                    flash_fn=None,
                )
                if len(cards) == n:
                    print(f"Community cards: {cards}")
                    post_community(cards)
                else:
                    print(f"Expected {n} cards, got {len(cards)}")
                    buzzer.error()

            last_phase = phase

            # ── Human button polling (debounce) ─────────────────────────
            fold_now  = btn_fold.value()
            call_now  = btn_call.value()
            raise_now = btn_raise.value()

            if fold_now == 0 and last_btn_state["fold"] == 1:
                print("Button: FOLD")
                post_human_action("fold")
                buzzer.fold()
                time.sleep_ms(300)

            if call_now == 0 and last_btn_state["call"] == 1:
                print("Button: CALL")
                # Determine call amount from state
                human = _human_player(state)
                to_call = 0
                if human:
                    to_call = max(0, state.get("current_bet", 0) - human.get("bet_this_round", 0))
                post_human_action("call", to_call)
                buzzer.action()
                time.sleep_ms(300)

            if raise_now == 0 and last_btn_state["raise"] == 1:
                print("Button: RAISE (min raise)")
                big_blind = state.get("big_blind", 100)
                current_bet = state.get("current_bet", 0)
                min_raise = max(current_bet * 2, big_blind)
                post_human_action("raise", min_raise)
                buzzer.action()
                time.sleep_ms(300)

            last_btn_state = {"fold": fold_now, "call": call_now, "raise": raise_now}
            time.sleep(POLL_INTERVAL)

        except Exception as e:
            print(f"Community loop error: {e}")
            time.sleep(2)


def _human_player(state):
    for p in state.get("players", []):
        if p.get("player_type") == "human":
            return p
    return None


if __name__ == "__main__":
    main()
