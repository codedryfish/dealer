"""
agents.py — Programmatic agent decision engine with 5 personality profiles.

Each agent profile encodes:
  - VPIP range (% of hands played)
  - Aggression factor
  - Bluff frequency
  - Bet sizing tendencies

The agent uses hand strength (from evaluator.py monte-carlo) + pot odds
to choose between FOLD / CHECK / CALL / RAISE / ALL_IN.
"""
from __future__ import annotations

import random
import time
from typing import List, Optional, Dict, Any

from .models import Action, ActionType, AgentProfile, Card
from .evaluator import evaluate_partial


# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

PROFILE_CONFIG: Dict[AgentProfile, Dict[str, Any]] = {
    AgentProfile.TAG: {
        "vpip": 0.22,          # plays ~22% of hands preflop
        "pfr": 0.18,           # pre-flop raise frequency when playing
        "bluff": 0.10,         # bluff frequency post-flop
        "aggression": 0.65,    # raise vs call when ahead (0=always call, 1=always raise)
        "bet_size_min": 0.5,   # min bet as fraction of pot
        "bet_size_max": 1.0,   # max bet as fraction of pot
        "thinking_min": 1.5,
        "thinking_max": 3.5,
        "name": "Solid TAG",
    },
    AgentProfile.LAG: {
        "vpip": 0.40,
        "pfr": 0.32,
        "bluff": 0.22,
        "aggression": 0.75,
        "bet_size_min": 0.6,
        "bet_size_max": 1.5,
        "thinking_min": 1.0,
        "thinking_max": 2.5,
        "name": "Loose-Aggressive",
    },
    AgentProfile.NIT: {
        "vpip": 0.12,
        "pfr": 0.08,
        "bluff": 0.03,
        "aggression": 0.30,
        "bet_size_min": 0.4,
        "bet_size_max": 0.75,
        "thinking_min": 2.0,
        "thinking_max": 4.0,
        "name": "Nit",
    },
    AgentProfile.FISH: {
        "vpip": 0.55,
        "pfr": 0.10,
        "bluff": 0.07,
        "aggression": 0.20,
        "bet_size_min": 0.3,
        "bet_size_max": 0.6,
        "thinking_min": 0.5,
        "thinking_max": 1.5,
        "name": "Fish",
    },
    AgentProfile.MANIAC: {
        "vpip": 0.70,
        "pfr": 0.55,
        "bluff": 0.35,
        "aggression": 0.90,
        "bet_size_min": 0.75,
        "bet_size_max": 2.5,
        "thinking_min": 0.5,
        "thinking_max": 1.5,
        "name": "Maniac",
    },
}


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

class Agent:
    """
    A stateless agent that decides actions based on hand strength and profile.

    The decide() method is called by the poker engine when it's this agent's turn.
    It returns an Action after an artificial thinking delay.
    """

    def __init__(self, station_id: str, profile: AgentProfile = AgentProfile.TAG) -> None:
        self.station_id = station_id
        self.profile = profile
        self._cfg = PROFILE_CONFIG[profile]

    def change_profile(self, profile: AgentProfile) -> None:
        self.profile = profile
        self._cfg = PROFILE_CONFIG[profile]

    def decide(
        self,
        hole_cards: List[Card],
        community_cards: List[Card],
        pot: int,
        current_bet: int,       # what's currently owed to call (0 = check option)
        my_stack: int,
        my_bet_this_round: int, # already invested this street
        position: str,          # "early", "middle", "late", "blind"
        history: List[Dict],    # recent action history
        phase: str,
    ) -> Action:
        """
        Main decision method. Returns an Action with artificial delay already applied.
        """
        # --- Thinking delay (async sleep would be better on Pi, but sync here) ---
        thinking = random.uniform(self._cfg["thinking_min"], self._cfg["thinking_max"])
        time.sleep(thinking)

        cfg = self._cfg
        to_call = current_bet - my_bet_this_round  # chips needed to call
        to_call = max(0, to_call)

        # --- Pre-flop special logic ---
        if phase == "pre_flop" and not community_cards:
            return self._preflop_decision(hole_cards, pot, to_call, my_stack, cfg)

        # --- Post-flop: evaluate hand strength ---
        if len(community_cards) >= 3:
            strength = evaluate_partial(hole_cards, community_cards)
        else:
            # Shouldn't happen, but be safe
            strength = 0.5

        # --- Pot odds ---
        pot_odds = to_call / (pot + to_call) if (pot + to_call) > 0 else 0.0

        return self._postflop_decision(strength, pot_odds, to_call, pot, my_stack, cfg, phase)

    # -----------------------------------------------------------------------
    # Pre-flop decision
    # -----------------------------------------------------------------------

    def _preflop_decision(
        self,
        hole_cards: List[Card],
        pot: int,
        to_call: int,
        my_stack: int,
        cfg: Dict,
    ) -> Action:
        """Simple pre-flop heuristic: play top N% of hands."""
        # Score hole cards 0–1
        preflop_strength = _preflop_strength(hole_cards)

        # Decide whether to enter the pot at all
        vpip_threshold = 1.0 - cfg["vpip"]
        if preflop_strength < vpip_threshold and to_call > 0:
            return Action(ActionType.FOLD)

        # Raise with strong hands
        if preflop_strength > 0.80 and random.random() < cfg["pfr"]:
            bet = max(to_call * 3, pot // 2) if to_call > 0 else pot // 2
            bet = min(bet, my_stack)
            return Action(ActionType.RAISE, amount=bet)

        # Bluff raise occasionally
        if random.random() < cfg["bluff"] * 0.5:
            bet = max(to_call * 2, pot // 3)
            bet = min(bet, my_stack)
            return Action(ActionType.RAISE, amount=bet)

        # Call or check
        if to_call == 0:
            return Action(ActionType.CHECK)
        if to_call >= my_stack:
            return Action(ActionType.ALL_IN, amount=my_stack)
        return Action(ActionType.CALL, amount=to_call)

    # -----------------------------------------------------------------------
    # Post-flop decision
    # -----------------------------------------------------------------------

    def _postflop_decision(
        self,
        strength: float,
        pot_odds: float,
        to_call: int,
        pot: int,
        my_stack: int,
        cfg: Dict,
        phase: str,
    ) -> Action:

        # Bluff occasionally regardless of strength
        bluffing = random.random() < cfg["bluff"]

        if bluffing and to_call == 0:
            # Bluff bet
            bet_frac = random.uniform(cfg["bet_size_min"], cfg["bet_size_max"])
            bet = int(pot * bet_frac)
            bet = max(1, min(bet, my_stack))
            return Action(ActionType.RAISE, amount=bet)

        if bluffing and to_call > 0 and random.random() < 0.4:
            # Bluff-raise
            bet = int(to_call * random.uniform(2.0, 3.0))
            bet = min(bet, my_stack)
            return Action(ActionType.RAISE, amount=bet)

        # Value decisions based on strength vs pot odds
        if strength > 0.75:
            # Strong hand: bet/raise for value
            if to_call == 0:
                bet_frac = random.uniform(cfg["bet_size_min"], cfg["bet_size_max"])
                bet = int(pot * bet_frac)
                bet = max(1, min(bet, my_stack))
                if bet >= my_stack:
                    return Action(ActionType.ALL_IN, amount=my_stack)
                return Action(ActionType.RAISE, amount=bet)
            else:
                # Raise or call depending on aggression
                if random.random() < cfg["aggression"]:
                    bet = int(to_call * random.uniform(2.5, 3.5))
                    bet = min(bet, my_stack)
                    if bet >= my_stack:
                        return Action(ActionType.ALL_IN, amount=my_stack)
                    return Action(ActionType.RAISE, amount=bet)
                else:
                    if to_call >= my_stack:
                        return Action(ActionType.ALL_IN, amount=my_stack)
                    return Action(ActionType.CALL, amount=to_call)

        elif strength > 0.45:
            # Medium hand: call if odds are good, check otherwise
            if to_call == 0:
                return Action(ActionType.CHECK)
            if strength > pot_odds + 0.05:
                if to_call >= my_stack:
                    return Action(ActionType.ALL_IN, amount=my_stack)
                return Action(ActionType.CALL, amount=to_call)
            else:
                return Action(ActionType.FOLD)

        else:
            # Weak hand: fold to any bet, check if free
            if to_call == 0:
                return Action(ActionType.CHECK)
            return Action(ActionType.FOLD)


# ---------------------------------------------------------------------------
# Pre-flop hand strength heuristic (0–1)
# ---------------------------------------------------------------------------

# Pre-computed strength scores for hole card combinations.
# Pairs > suited connectors > offsuit connectors, roughly.
# AA=1.0, 72o≈0.0

def _preflop_strength(hole_cards: List[Card]) -> float:
    """
    Return a 0–1 score for a 2-card pre-flop hand.
    Uses a simplified Chen formula approximation.
    """
    if len(hole_cards) != 2:
        return 0.5

    c1, c2 = hole_cards
    # High card score (A=12=max in 0-indexed)
    rank_order = "23456789TJQKA"
    r1_val = rank_order.index(c1.rank)
    r2_val = rank_order.index(c2.rank)
    high = max(r1_val, r2_val)
    low = min(r1_val, r2_val)

    score = high / 12.0  # base on highest card

    # Pair bonus
    if r1_val == r2_val:
        score += 0.25 + (high / 12.0) * 0.15

    # Suited bonus
    if c1.suit == c2.suit:
        score += 0.05

    # Connector bonus (close ranks)
    gap = high - low
    if gap == 1:
        score += 0.04
    elif gap == 2:
        score += 0.02

    return min(1.0, score)


RANKS = "23456789TJQKA"
