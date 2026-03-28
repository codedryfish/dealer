"""
main.py — ESP32-S3 Agent Station firmware entry point.

Boot sequence:
  1. Show startup screen
  2. Connect to Pi WiFi AP
  3. Enter main loop:
     a. Wait for new hand (poll state)
     b. On DEALING phase: read 2 hole cards, POST to API
     c. Poll for agent action, display on OLED + LEDs + buzzer
     d. On SHOWDOWN: display result
"""
import time
import gc

from config import STATION_ID, POLL_INTERVAL
from network import connect_wifi, get_action, get_state, post_cards
from rfid import RFIDReader
from display import OLEDDisplay
from leds import LEDRing
from buzzer import Buzzer


def main():
    # Init hardware
    display = OLEDDisplay()
    leds = LEDRing()
    buzzer = Buzzer()
    rfid = RFIDReader()

    display.show_startup()
    leds.idle()

    # Connect WiFi with retry
    connected = False
    while not connected:
        connected = connect_wifi()
        if not connected:
            display.show_error("WiFi failed")
            leds.error()
            time.sleep(5)

    state = get_state() or {}
    stack = _my_stack(state)
    display.show_ready(stack)

    last_action = None
    last_phase = None

    while True:
        try:
            gc.collect()
            state = get_state()
            if not state:
                time.sleep(POLL_INTERVAL)
                continue

            phase = state.get("phase", "idle")
            stack = _my_stack(state)

            # ── New hand: DEALING phase ──────────────────────────────────
            if phase == "dealing" and last_phase != "dealing":
                display.show_waiting_cards(stack)
                leds.idle()
                # Wait for hole cards to be dealt on the reader
                cards = rfid.read_n_cards(
                    n=2,
                    timeout_ms=60_000,
                    beep_fn=buzzer.card_read,
                    flash_fn=lambda c: leds.card_read(),
                )
                if len(cards) == 2:
                    display.show_cards_received(cards, stack)
                    post_cards(cards)
                else:
                    display.show_error("Card read failed")
                    buzzer.error()

            # ── Betting phase: show thinking / action ───────────────────
            elif phase in ("pre_flop", "flop_bet", "turn_bet", "river_bet"):
                action_data = get_action()
                action = action_data.get("action") if action_data else None
                amount = action_data.get("amount", 0) if action_data else 0

                if action and action != "waiting" and action != last_action:
                    last_action = action
                    display.show_action(action, amount, stack, phase)
                    if action == "fold":
                        leds.folded()
                        buzzer.fold()
                    else:
                        leds.acted()
                        buzzer.action()
                elif action == "waiting" or not action:
                    if _is_my_turn(state):
                        display.show_thinking(stack, phase)
                        leds.thinking(pulses=1)

            # ── Showdown ─────────────────────────────────────────────────
            elif phase == "showdown" and last_phase != "showdown":
                result = state.get("last_result")
                if result:
                    won = STATION_ID in result.get("winner_ids", [])
                    hand_name = result.get("hand_ranks", {}).get(STATION_ID, "")
                    display.show_result(won, result.get("pot", 0), hand_name)
                    if won:
                        leds.winner()
                        buzzer.winner()
                    else:
                        leds.folded()

            # ── IDLE ─────────────────────────────────────────────────────
            elif phase == "idle":
                display.show_ready(stack)
                leds.idle()
                last_action = None

            last_phase = phase
            time.sleep(POLL_INTERVAL)

        except Exception as e:
            print(f"Main loop error: {e}")
            display.show_error(str(e)[:16])
            time.sleep(2)


def _my_stack(state: dict) -> int:
    """Extract this station's player stack from game state."""
    for p in state.get("players", []):
        if p.get("player_id") == STATION_ID:
            return p.get("stack", 0)
    return 0


def _is_my_turn(state: dict) -> bool:
    return state.get("current_player_id") == STATION_ID


if __name__ == "__main__":
    main()
