"""
models.py — Core dataclasses for D.E.A.L.E.R. poker engine.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Any


# ---------------------------------------------------------------------------
# Card representation
# ---------------------------------------------------------------------------

RANKS = "23456789TJQKA"
SUITS = "HDCS"  # Hearts, Diamonds, Clubs, Spades

RANK_NAMES = {
    "2": "Two", "3": "Three", "4": "Four", "5": "Five", "6": "Six",
    "7": "Seven", "8": "Eight", "9": "Nine", "T": "Ten",
    "J": "Jack", "Q": "Queen", "K": "King", "A": "Ace",
}
SUIT_NAMES = {"H": "Hearts", "D": "Diamonds", "C": "Clubs", "S": "Spades"}
SUIT_SYMBOLS = {"H": "♥", "D": "♦", "C": "♣", "S": "♠"}


@dataclass(frozen=True)
class Card:
    """Immutable card: rank char + suit char, e.g. 'AH', 'TC', '2S'."""

    rank: str  # one of RANKS
    suit: str  # one of SUITS

    def __post_init__(self) -> None:
        if self.rank not in RANKS:
            raise ValueError(f"Invalid rank: {self.rank!r}")
        if self.suit not in SUITS:
            raise ValueError(f"Invalid suit: {self.suit!r}")

    @classmethod
    def from_str(cls, s: str) -> "Card":
        """Parse '2-char string like 'AH' or 'TC'."""
        if len(s) != 2:
            raise ValueError(f"Card string must be 2 chars, got {s!r}")
        return cls(rank=s[0].upper(), suit=s[1].upper())

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        return f"Card({self!s})"

    @property
    def display(self) -> str:
        return f"{RANK_NAMES[self.rank]} of {SUIT_NAMES[self.suit]}"

    @property
    def symbol(self) -> str:
        return f"{self.rank}{SUIT_SYMBOLS[self.suit]}"

    def to_treys(self) -> str:
        """Convert to treys library format (e.g. 'Ah', '2s')."""
        rank = self.rank if self.rank != "T" else "T"
        return f"{rank}{self.suit.lower()}"


# ---------------------------------------------------------------------------
# Game enums
# ---------------------------------------------------------------------------

class GamePhase(str, Enum):
    IDLE = "idle"
    DEALING = "dealing"
    PRE_FLOP = "pre_flop"
    FLOP_DEAL = "flop_deal"
    FLOP_BET = "flop_bet"
    TURN_DEAL = "turn_deal"
    TURN_BET = "turn_bet"
    RIVER_DEAL = "river_deal"
    RIVER_BET = "river_bet"
    SHOWDOWN = "showdown"


class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    RAISE = "raise"
    ALL_IN = "all_in"


class PlayerType(str, Enum):
    AGENT = "agent"
    HUMAN = "human"


class GameMode(str, Enum):
    OBSERVER = "observer"    # Agent A vs Agent B
    PLAYER = "player"        # Agent A vs Agent B vs Human
    TRAINING = "training"    # Agent A vs Human (heads-up)


class AgentProfile(str, Enum):
    TAG = "TAG"        # Tight-Aggressive
    LAG = "LAG"        # Loose-Aggressive
    NIT = "Nit"        # Tight-Passive
    FISH = "Fish"      # Loose-Passive
    MANIAC = "Maniac"  # Hyper-Aggressive


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------

@dataclass
class Action:
    action_type: ActionType
    amount: int = 0           # chips (0 for fold/check/call)
    player_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action_type.value,
            "amount": self.amount,
            "player_id": self.player_id,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

@dataclass
class Player:
    player_id: str            # "A", "B", or "human"
    name: str
    player_type: PlayerType
    stack: int                # chip count
    profile: AgentProfile = AgentProfile.TAG  # only relevant for agents
    hole_cards: List[Card] = field(default_factory=list)
    bet_this_round: int = 0
    is_folded: bool = False
    is_all_in: bool = False
    station_id: str = ""      # "A", "B", "C" (community)

    def reset_for_hand(self) -> None:
        self.hole_cards = []
        self.bet_this_round = 0
        self.is_folded = False
        self.is_all_in = False

    def reset_for_betting_round(self) -> None:
        self.bet_this_round = 0

    @property
    def is_active(self) -> bool:
        """Can still act (not folded, not all-in)."""
        return not self.is_folded and not self.is_all_in

    @property
    def can_act(self) -> bool:
        """Has chips and hasn't folded."""
        return not self.is_folded and self.stack > 0

    def to_dict(self, reveal_cards: bool = False) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "name": self.name,
            "player_type": self.player_type.value,
            "stack": self.stack,
            "profile": self.profile.value,
            "hole_cards": [str(c) for c in self.hole_cards] if reveal_cards else (
                ["??", "??"] if self.hole_cards else []
            ),
            "bet_this_round": self.bet_this_round,
            "is_folded": self.is_folded,
            "is_all_in": self.is_all_in,
        }


# ---------------------------------------------------------------------------
# Hand result
# ---------------------------------------------------------------------------

@dataclass
class HandResult:
    winner_ids: List[str]
    hand_ranks: Dict[str, str]          # player_id -> hand name
    pot: int
    side_pots: List[Dict[str, Any]] = field(default_factory=list)
    folded_win: bool = False             # True if everyone else folded
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "winner_ids": self.winner_ids,
            "hand_ranks": self.hand_ranks,
            "pot": self.pot,
            "side_pots": self.side_pots,
            "folded_win": self.folded_win,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Game state (snapshot, for API responses and WebSocket broadcasts)
# ---------------------------------------------------------------------------

@dataclass
class GameState:
    phase: GamePhase
    mode: GameMode
    players: List[Player]
    dealer_index: int
    community_cards: List[Card]
    pot: int
    current_bet: int                    # highest bet this round
    current_player_id: Optional[str]    # who needs to act
    hand_history: List[Dict[str, Any]]  # list of action dicts
    hand_number: int
    small_blind: int
    big_blind: int
    last_result: Optional[HandResult]

    def to_dict(self, reveal_all: bool = False) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "mode": self.mode.value,
            "players": [p.to_dict(reveal_cards=reveal_all or p.player_type == PlayerType.HUMAN) for p in self.players],
            "dealer_index": self.dealer_index,
            "community_cards": [str(c) for c in self.community_cards],
            "pot": self.pot,
            "current_bet": self.current_bet,
            "current_player_id": self.current_player_id,
            "hand_history": self.hand_history,
            "hand_number": self.hand_number,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "last_result": self.last_result.to_dict() if self.last_result else None,
        }
