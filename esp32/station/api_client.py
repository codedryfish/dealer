"""
network.py — WiFi connection and HTTP API client for MicroPython.
"""
import network
import time
import urequests
import ujson
from config import WIFI_SSID, WIFI_PASSWORD, API_BASE, STATION_ID


def connect_wifi(max_retries=20):
    """Connect to the Pi's WiFi AP. Returns True on success."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        return True

    print(f"Connecting to {WIFI_SSID}...")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    for i in range(max_retries):
        if wlan.isconnected():
            print(f"Connected: {wlan.ifconfig()}")
            return True
        time.sleep(0.5)

    print("WiFi connection failed")
    return False


def post_cards(cards):
    """
    POST hole cards to the Pi API.
    cards: list of 2-char strings e.g. ["AH", "KD"]
    Returns API response dict or None.
    """
    url = f"{API_BASE}/cards"
    payload = ujson.dumps({"station_id": STATION_ID, "cards": cards})
    try:
        resp = urequests.post(url, data=payload, headers={"Content-Type": "application/json"})
        data = resp.json()
        resp.close()
        return data
    except Exception as e:
        print(f"post_cards error: {e}")
        return None


def get_action():
    """
    GET the latest action for this station.
    Returns dict with "action" and "amount" keys, or None.
    """
    url = f"{API_BASE}/action/{STATION_ID}"
    try:
        resp = urequests.get(url)
        data = resp.json()
        resp.close()
        return data
    except Exception as e:
        print(f"get_action error: {e}")
        return None


def get_state():
    """GET full game state. Returns dict or None."""
    url = f"{API_BASE}/state"
    try:
        resp = urequests.get(url)
        data = resp.json()
        resp.close()
        return data
    except Exception as e:
        print(f"get_state error: {e}")
        return None
