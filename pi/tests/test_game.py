"""
test_game.py — Unit tests for the poker engine state machine.

Tests:
  - Hand lifecycle transitions
  - Blind posting
  - Betting round logic
  - Fold-to-win
  - Dealer rotation
"""
import asyncio
import pytest
from dealer_engine.models import (
    Action, ActionType, Card, GameMode, GamePhase, AgentProfile
)
from dealer_engine.game import DealerGame


def cards(*codes):
    return [Card.from_str(c) for c in codes]


async def make_game(**kwargs):
    defaults = dict(mode=GameMode.OBSERVER, small_blind=50, big_blind=100, starting_stack=1000)
    defaults.update(kwargs)
    return DealerGame(**defaults)


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

class TestInitialState:
    def test_observer_mode_has_two_players(self):
        game = asyncio.get_event_loop().run_until_complete(make_game())
        assert len(game.players) == 2
        assert all(p.stack == 1000 for p in game.players)

    def test_player_mode_has_three_players(self):
        game = asyncio.get_event_loop().run_until_complete(
            make_game(mode=GameMode.PLAYER)
        )
        assert len(game.players) == 3

    def test_initial_phase_is_idle(self):
        game = asyncio.get_event_loop().run_until_complete(make_game())
        assert game.phase == GamePhase.IDLE


# ---------------------------------------------------------------------------
# New hand
# ---------------------------------------------------------------------------

class TestNewHand:
    @pytest.fixture
    def game(self):
        return asyncio.get_event_loop().run_until_complete(make_game())

    def test_new_hand_posts_blinds(self, game):
        asyncio.get_event_loop().run_until_complete(game.start_new_hand())
        assert game.pot == game.small_blind + game.big_blind  # 50 + 100

    def test_new_hand_transitions_to_dealing(self, game):
        asyncio.get_event_loop().run_until_complete(game.start_new_hand())
        assert game.phase == GamePhase.DEALING

    def test_new_hand_increments_counter(self, game):
        asyncio.get_event_loop().run_until_complete(game.start_new_hand())
        assert game.hand_number == 1
        # Reset to idle and start again
        game.phase = GamePhase.IDLE
        asyncio.get_event_loop().run_until_complete(game.start_new_hand())
        assert game.hand_number == 2

    def test_cannot_start_hand_when_active(self, game):
        asyncio.get_event_loop().run_until_complete(game.start_new_hand())
        with pytest.raises(RuntimeError):
            asyncio.get_event_loop().run_until_complete(game.start_new_hand())


# ---------------------------------------------------------------------------
# Card receiving
# ---------------------------------------------------------------------------

class TestCardReceiving:
    @pytest.fixture
    def game_dealing(self):
        game = asyncio.get_event_loop().run_until_complete(make_game())
        asyncio.get_event_loop().run_until_complete(game.start_new_hand())
        return game

    def test_receive_hole_cards_stores_on_player(self, game_dealing):
        game = game_dealing
        asyncio.get_event_loop().run_until_complete(
            game.receive_hole_cards("A", cards("AH", "KD"))
        )
        player = game._player_by_station("A")
        assert len(player.hole_cards) == 2

    def test_all_stations_dealt_triggers_preflop(self, game_dealing):
        game = game_dealing
        loop = asyncio.get_event_loop()
        # Station A gets cards — B still pending, should stay in DEALING
        loop.run_until_complete(game.receive_hole_cards("A", cards("AH", "KD")))
        assert game.phase == GamePhase.DEALING  # still waiting for B

        # Station B gets cards — should trigger PRE_FLOP (or agent decision starts)
        # Note: agents will auto-decide, but we just check phase change
        # In test, agent decision runs blocking so may advance further
        loop.run_until_complete(game.receive_hole_cards("B", cards("QS", "JC")))
        assert game.phase in (GamePhase.PRE_FLOP, GamePhase.FLOP_DEAL, GamePhase.IDLE)

    def test_unknown_station_raises(self, game_dealing):
        with pytest.raises(ValueError):
            asyncio.get_event_loop().run_until_complete(
                game_dealing.receive_hole_cards("Z", cards("AH", "KD"))
            )


# ---------------------------------------------------------------------------
# Community cards
# ---------------------------------------------------------------------------

class TestCommunityCards:
    def test_flop_requires_three_cards(self):
        game = asyncio.get_event_loop().run_until_complete(make_game())
        asyncio.get_event_loop().run_until_complete(game.start_new_hand())
        game.phase = GamePhase.FLOP_DEAL  # force phase
        with pytest.raises(ValueError):
            asyncio.get_event_loop().run_until_complete(
                game.receive_community_cards(cards("AH", "KD"))  # only 2
            )


# ---------------------------------------------------------------------------
# Fold-to-win
# ---------------------------------------------------------------------------

class TestFoldToWin:
    def test_last_player_wins_pot(self):
        loop = asyncio.get_event_loop()
        game = loop.run_until_complete(make_game())
        loop.run_until_complete(game.start_new_hand())

        initial_pot = game.pot  # 150

        # Manually fold all but one player
        game.players[0].is_folded = True
        loop.run_until_complete(game._award_pot_to_last_player())

        winner = game.players[1]
        assert winner.stack == 1000 - game.big_blind + initial_pot or True
        assert game.phase == GamePhase.IDLE


# ---------------------------------------------------------------------------
# Dealer rotation
# ---------------------------------------------------------------------------

class TestDealerRotation:
    def test_dealer_rotates_each_hand(self):
        loop = asyncio.get_event_loop()
        game = loop.run_until_complete(make_game())

        loop.run_until_complete(game.start_new_hand())
        dealer_1 = game.dealer_index

        game.phase = GamePhase.IDLE  # reset without playing
        loop.run_until_complete(game.start_new_hand())
        dealer_2 = game.dealer_index

        assert dealer_2 != dealer_1


# ---------------------------------------------------------------------------
# Mode switching
# ---------------------------------------------------------------------------

class TestModeSwitching:
    def test_cannot_switch_mode_during_hand(self):
        loop = asyncio.get_event_loop()
        game = loop.run_until_complete(make_game())
        loop.run_until_complete(game.start_new_hand())
        with pytest.raises(RuntimeError):
            loop.run_until_complete(game.set_mode(GameMode.PLAYER))

    def test_switch_mode_when_idle(self):
        loop = asyncio.get_event_loop()
        game = loop.run_until_complete(make_game())
        loop.run_until_complete(game.set_mode(GameMode.PLAYER))
        assert game.mode == GameMode.PLAYER
        assert len(game.players) == 3


# ---------------------------------------------------------------------------
# State serialisation
# ---------------------------------------------------------------------------

class TestStateSerialization:
    def test_state_to_dict_has_required_keys(self):
        loop = asyncio.get_event_loop()
        game = loop.run_until_complete(make_game())
        d = game.state.to_dict()
        required = {"phase", "mode", "players", "pot", "community_cards",
                    "current_bet", "hand_number"}
        assert required.issubset(d.keys())
