"""
test_evaluator.py — Unit tests for the hand evaluator.

Tests:
  - Hand ranking for all standard hands (Royal Flush → High Card)
  - Kicker comparison
  - Split pot detection
  - compare_hands winner detection
"""
import pytest
from dealer_engine.models import Card
from dealer_engine.evaluator import (
    evaluate, hand_rank_class, hand_rank_name, compare_hands
)


def cards(*codes):
    return [Card.from_str(c) for c in codes]


# ---------------------------------------------------------------------------
# Hand rank detection
# ---------------------------------------------------------------------------

class TestHandRanking:
    # Treys get_rank_class() is 0-indexed:
    # 0=Royal Flush, 1=Straight Flush, 2=Quads, 3=Full House,
    # 4=Flush, 5=Straight, 6=Trips, 7=Two Pair, 8=Pair, 9=High Card

    def test_royal_flush(self):
        hole = cards("AH", "KH")
        board = cards("QH", "JH", "TH")
        assert hand_rank_class(evaluate(hole, board)) == 0

    def test_straight_flush(self):
        hole = cards("9H", "8H")
        board = cards("7H", "6H", "5H")
        assert hand_rank_class(evaluate(hole, board)) == 1

    def test_four_of_a_kind(self):
        hole = cards("AH", "AD")
        board = cards("AC", "AS", "2H")
        assert hand_rank_class(evaluate(hole, board)) == 2

    def test_full_house(self):
        hole = cards("AH", "AD")
        board = cards("AC", "KH", "KD")
        assert hand_rank_class(evaluate(hole, board)) == 3

    def test_flush(self):
        hole = cards("AH", "KH")
        board = cards("9H", "7H", "2H")
        assert hand_rank_class(evaluate(hole, board)) == 4

    def test_straight(self):
        hole = cards("AH", "KD")
        board = cards("QC", "JS", "TH")
        assert hand_rank_class(evaluate(hole, board)) == 5

    def test_three_of_a_kind(self):
        hole = cards("AH", "AD")
        board = cards("AC", "KH", "2D")
        assert hand_rank_class(evaluate(hole, board)) == 6

    def test_two_pair(self):
        hole = cards("AH", "KH")
        board = cards("AD", "KC", "2H")
        assert hand_rank_class(evaluate(hole, board)) == 7

    def test_one_pair(self):
        hole = cards("AH", "KH")
        board = cards("AD", "7C", "2H")
        assert hand_rank_class(evaluate(hole, board)) == 8

    def test_high_card(self):
        hole = cards("AH", "KD")
        board = cards("9C", "7S", "2H")
        assert hand_rank_class(evaluate(hole, board)) == 9

    def test_hand_rank_name_royal_flush(self):
        hole = cards("AH", "KH")
        board = cards("QH", "JH", "TH")
        assert hand_rank_name(evaluate(hole, board)) == "Royal Flush"

    def test_hand_rank_name_pair(self):
        hole = cards("AH", "KD")
        board = cards("AC", "7S", "2H")
        assert hand_rank_name(evaluate(hole, board)) == "Pair"


# ---------------------------------------------------------------------------
# Winner detection
# ---------------------------------------------------------------------------

class TestCompareHands:
    def test_flush_beats_straight(self):
        # A wins: flush vs straight
        hole_a = cards("AH", "KH")  # flush
        hole_b = cards("AS", "KD")  # straight with board
        board = cards("QH", "9H", "8H")  # A gets flush; B gets Q-high straight (no)
        # Actually let's use a cleaner example
        hole_a = cards("AH", "2H")
        hole_b = cards("AS", "KD")
        board = cards("9H", "7H", "5H")
        result = compare_hands(hole_a, hole_b, board)
        assert result == -1  # A wins (flush)

    def test_higher_pair_wins(self):
        hole_a = cards("AH", "AD")
        hole_b = cards("KH", "KD")
        board = cards("2C", "5S", "9H")
        assert compare_hands(hole_a, hole_b, board) == -1

    def test_equal_hands_is_tie(self):
        # Both use the board for a straight
        hole_a = cards("AH", "2D")
        hole_b = cards("AS", "2C")
        board = cards("KH", "KD", "KC")
        # Both have A-K-K-K-2, tied on kicker A
        result = compare_hands(hole_a, hole_b, board)
        assert result == 0

    def test_full_hand_five_cards(self):
        # A: AH, AD + 2C, 2H, 2S → three aces + pair twos = Aces full of Twos
        # B: KH, KD + 2C, 2H, 2S → three twos + pair kings = Twos full of Kings
        # A wins (higher full house)
        hole_a = cards("AH", "AD")
        hole_b = cards("KH", "KD")
        board = cards("2C", "2H", "2S")
        result = compare_hands(hole_a, hole_b, board)
        assert result == -1


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_invalid_rank_raises(self):
        with pytest.raises(ValueError):
            Card.from_str("XH")

    def test_invalid_suit_raises(self):
        with pytest.raises(ValueError):
            Card.from_str("AX")

    def test_too_few_community_cards(self):
        hole = cards("AH", "KH")
        board = cards("QH", "JH")  # only 2 cards
        with pytest.raises(ValueError):
            evaluate(hole, board)

    def test_too_many_hole_cards(self):
        hole = cards("AH", "KH", "QH")
        board = cards("JH", "TH", "2C")
        with pytest.raises(ValueError):
            evaluate(hole, board)
