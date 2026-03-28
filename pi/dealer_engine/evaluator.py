"""
evaluator.py — 7-card hand evaluator wrapper using the treys library.

treys uses its own card representation. This module bridges between
our Card dataclass and treys, and provides convenience functions for
the poker engine.
"""
from __future__ import annotations

from typing import List, Optional

from treys import Card as TreysCard, Evaluator as TreysEvaluator

from .models import Card


_evaluator = TreysEvaluator()

# Treys hand rank classes (lower = better)
# Treys get_rank_class() returns 0-indexed values (0=Straight Flush/Royal, 8=High Card)
HAND_RANK_NAMES = {
    0: "Royal Flush",    # highest straight flush
    1: "Straight Flush",
    2: "Four of a Kind",
    3: "Full House",
    4: "Flush",
    5: "Straight",
    6: "Three of a Kind",
    7: "Two Pair",
    8: "Pair",
    9: "High Card",
}

# Maps treys class (1-10) to human name
def _treys_card(card: Card) -> int:
    """Convert our Card to a treys card integer."""
    return TreysCard.new(card.to_treys())


def evaluate(hole_cards: List[Card], community_cards: List[Card]) -> int:
    """
    Return a treys hand rank score (lower = better).
    Requires exactly 2 hole cards and 3–5 community cards.
    """
    if len(hole_cards) != 2:
        raise ValueError("evaluate() requires exactly 2 hole cards")
    if not (3 <= len(community_cards) <= 5):
        raise ValueError("evaluate() requires 3–5 community cards")

    hand = [_treys_card(c) for c in hole_cards]
    board = [_treys_card(c) for c in community_cards]
    return _evaluator.evaluate(board, hand)


def hand_rank_class(score: int) -> int:
    """Return 1–10 hand class from a treys score (1=Royal Flush, 10=High Card)."""
    return _evaluator.get_rank_class(score)


def hand_rank_name(score: int) -> str:
    """Return human-readable hand name from a treys score."""
    cls = hand_rank_class(score)
    return HAND_RANK_NAMES.get(cls, "Unknown")


def compare_hands(
    hole_cards_a: List[Card],
    hole_cards_b: List[Card],
    community_cards: List[Card],
) -> int:
    """
    Compare two hands.
    Returns:
      -1 if A wins, 1 if B wins, 0 if tie.
    """
    score_a = evaluate(hole_cards_a, community_cards)
    score_b = evaluate(hole_cards_b, community_cards)
    if score_a < score_b:
        return -1
    elif score_a > score_b:
        return 1
    return 0


def evaluate_partial(hole_cards: List[Card], community_cards: List[Card]) -> float:
    """
    Estimate hand strength as a 0–1 float using Monte Carlo simulation.
    Used by agents before full community cards are revealed.

    Returns fraction of 500 random runouts where our hand wins or ties.
    """
    import random
    from itertools import combinations

    if len(hole_cards) != 2:
        return 0.5

    # Build the remaining deck
    all_cards = [Card(r, s) for r in "23456789TJQKA" for s in "HDCS"]
    used = set(str(c) for c in hole_cards + community_cards)
    remaining = [c for c in all_cards if str(c) not in used]

    needed = 5 - len(community_cards)  # cards still to come
    if needed == 0:
        # Full board: just evaluate one hand against random opponent
        needed_opp = 2
        wins = 0
        trials = min(500, len(list(combinations(remaining, 2))))
        sample = random.sample(list(combinations(remaining, 2)), trials)
        for opp_cards in sample:
            result = compare_hands(hole_cards, list(opp_cards), community_cards)
            if result <= 0:  # win or tie
                wins += 1
        return wins / trials if trials > 0 else 0.5

    wins = 0
    trials = 300
    for _ in range(trials):
        if len(remaining) < needed + 2:
            break
        runout = random.sample(remaining, needed + 2)
        board = community_cards + runout[:needed]
        opp_cards = runout[needed:]
        result = compare_hands(hole_cards, opp_cards, board)
        if result <= 0:
            wins += 1

    return wins / trials if trials > 0 else 0.5
