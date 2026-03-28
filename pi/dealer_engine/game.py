"""
game.py — Texas Hold'em hand lifecycle state machine.

State transitions:
  IDLE → DEALING → PRE_FLOP → FLOP_DEAL → FLOP_BET → TURN_DEAL
       → TURN_BET → RIVER_DEAL → RIVER_BET → SHOWDOWN → IDLE
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Optional, Dict, Any, Callable, Awaitable

from .models import (
    Action, ActionType, Card, GameMode, GamePhase, GameState,
    HandResult, Player, PlayerType, AgentProfile,
)
from .agents import Agent
from .evaluator import evaluate, hand_rank_name, compare_hands

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Game engine
# ---------------------------------------------------------------------------

class DealerGame:
    """
    Central poker engine. Manages state and orchestrates hand lifecycle.

    broadcast_fn: async callback called with (event_type: str, payload: dict)
                  whenever state changes. Used by WebSocket manager.
    """

    def __init__(
        self,
        mode: GameMode = GameMode.OBSERVER,
        small_blind: int = 50,
        big_blind: int = 100,
        starting_stack: int = 1000,
        broadcast_fn: Optional[Callable[[str, Dict], Awaitable[None]]] = None,
    ) -> None:
        self.mode = mode
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.starting_stack = starting_stack
        self._broadcast = broadcast_fn or _noop_broadcast

        # Build players based on mode
        self.players: List[Player] = self._build_players()

        # Agents (only for AGENT-type players)
        self._agents: Dict[str, Agent] = {
            p.player_id: Agent(p.player_id, p.profile)
            for p in self.players
            if p.player_type == PlayerType.AGENT
        }

        self.phase = GamePhase.IDLE
        self.community_cards: List[Card] = []
        self.pot = 0
        self.current_bet = 0
        self.dealer_index = 0
        self.current_player_index = 0
        self.hand_number = 0
        self.hand_history: List[Dict] = []
        self.last_result: Optional[HandResult] = None

        # Cards received from RFID (set by API layer)
        self._pending_hole_cards: Dict[str, List[Card]] = {}
        self._pending_community_cards: List[Card] = []

        # Lock for state mutation
        self._lock = asyncio.Lock()

    # -----------------------------------------------------------------------
    # Public API (called by routes.py)
    # -----------------------------------------------------------------------

    async def start_new_hand(self) -> GameState:
        async with self._lock:
            if self.phase not in (GamePhase.IDLE, GamePhase.SHOWDOWN):
                raise RuntimeError(f"Cannot start new hand in phase {self.phase}")

            self.hand_number += 1
            self.hand_history = []
            self._pending_hole_cards = {}
            self._pending_community_cards = []

            for p in self.players:
                p.reset_for_hand()

            # Rotate dealer
            self.dealer_index = (self.dealer_index + 1) % len(self.players)

            # Post blinds
            self.pot = 0
            self.current_bet = self.big_blind
            sb_player = self._player_at_offset(1)
            bb_player = self._player_at_offset(2)

            self._post_blind(sb_player, self.small_blind)
            self._post_blind(bb_player, self.big_blind)

            self.phase = GamePhase.DEALING
            logger.info(f"Hand #{self.hand_number} started. Dealer: {self._dealer_player.player_id}")
            await self._broadcast("state_update", self.state.to_dict())
            return self.state

    async def receive_hole_cards(self, station_id: str, cards: List[Card]) -> GameState:
        """Called when an ESP32 station reports RFID card reads for hole cards."""
        async with self._lock:
            if self.phase != GamePhase.DEALING:
                raise RuntimeError(f"Cannot receive hole cards in phase {self.phase}")

            player = self._player_by_station(station_id)
            if player is None:
                raise ValueError(f"Unknown station: {station_id}")

            player.hole_cards = cards
            self._pending_hole_cards[station_id] = cards
            logger.info(f"Station {station_id} received cards: {cards}")
            await self._broadcast("card_read", {"station_id": station_id, "cards": [str(c) for c in cards]})

            # Check if all active players have cards
            active_stations = [
                p.station_id for p in self.players
                if p.player_type == PlayerType.AGENT and p.station_id
            ]
            if all(s in self._pending_hole_cards for s in active_stations):
                await self._enter_pre_flop()

            return self.state

    async def receive_community_cards(self, cards: List[Card]) -> GameState:
        """Called when the community reader reports RFID reads."""
        async with self._lock:
            phase = self.phase
            if phase == GamePhase.FLOP_DEAL:
                if len(cards) != 3:
                    raise ValueError("Flop requires exactly 3 cards")
                self.community_cards.extend(cards)
                self.phase = GamePhase.FLOP_BET
                await self._start_betting_round()
            elif phase == GamePhase.TURN_DEAL:
                if len(cards) != 1:
                    raise ValueError("Turn requires exactly 1 card")
                self.community_cards.extend(cards)
                self.phase = GamePhase.TURN_BET
                await self._start_betting_round()
            elif phase == GamePhase.RIVER_DEAL:
                if len(cards) != 1:
                    raise ValueError("River requires exactly 1 card")
                self.community_cards.extend(cards)
                self.phase = GamePhase.RIVER_BET
                await self._start_betting_round()
            else:
                raise RuntimeError(f"Cannot receive community cards in phase {phase}")

            await self._broadcast("state_update", self.state.to_dict())
            return self.state

    async def apply_human_action(self, action: Action) -> GameState:
        """Called when the human player acts via the web app or physical buttons."""
        async with self._lock:
            human = self._human_player
            if human is None:
                raise RuntimeError("No human player in current mode")
            if self.current_player_id != human.player_id:
                raise RuntimeError("It's not the human's turn")
            action.player_id = human.player_id
            await self._apply_action(human, action)
            return self.state

    async def set_mode(self, mode: GameMode) -> None:
        async with self._lock:
            if self.phase != GamePhase.IDLE:
                raise RuntimeError("Can only change mode when IDLE")
            self.mode = mode
            self.players = self._build_players()
            self._agents = {
                p.player_id: Agent(p.player_id, p.profile)
                for p in self.players
                if p.player_type == PlayerType.AGENT
            }
            await self._broadcast("state_update", self.state.to_dict())

    async def set_agent_profile(self, station_id: str, profile: AgentProfile) -> None:
        async with self._lock:
            player = self._player_by_station(station_id)
            if player is None or player.player_type != PlayerType.AGENT:
                raise ValueError(f"No agent at station {station_id}")
            player.profile = profile
            if player.player_id in self._agents:
                self._agents[player.player_id].change_profile(profile)

    # -----------------------------------------------------------------------
    # Internal state machine
    # -----------------------------------------------------------------------

    async def _enter_pre_flop(self) -> None:
        self.phase = GamePhase.PRE_FLOP
        await self._start_betting_round()

    async def _start_betting_round(self) -> None:
        """Reset per-round bets and set first-to-act player."""
        for p in self.players:
            p.reset_for_betting_round()

        # In pre-flop, action starts left of BB (UTG)
        # In post-flop, action starts left of dealer (SB)
        if self.phase == GamePhase.PRE_FLOP:
            start_offset = 3  # UTG: after dealer, SB, BB
        else:
            self.current_bet = 0
            start_offset = 1  # Left of dealer

        active = self._active_players()
        if len(active) <= 1:
            await self._award_pot_to_last_player()
            return

        # Find first active player
        n = len(self.players)
        for offset in range(start_offset, start_offset + n):
            idx = (self.dealer_index + offset) % n
            if not self.players[idx].is_folded and not self.players[idx].is_all_in:
                self.current_player_index = idx
                break

        await self._broadcast("state_update", self.state.to_dict())
        await self._run_betting_round()

    async def _run_betting_round(self) -> None:
        """Run a full betting round. Handles agent auto-decisions."""
        n = len(self.players)
        last_raiser_idx = -1
        acted_count = 0
        active = self._active_players()
        max_actions = len(active) * len(active) + 2  # safety limit

        action_count = 0
        while action_count < max_actions:
            action_count += 1
            player = self.players[self.current_player_index]

            if player.is_folded or player.is_all_in:
                self.current_player_index = self._next_active_index(self.current_player_index)
                continue

            # If only one active player, award pot
            if len(self._active_players()) <= 1:
                await self._award_pot_to_last_player()
                return

            # Check if betting is closed
            if self._betting_is_closed(last_raiser_idx, acted_count):
                break

            if player.player_type == PlayerType.AGENT:
                # Run agent decision in executor to avoid blocking event loop
                action = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._get_agent_decision,
                    player,
                )
                action.player_id = player.player_id
                await self._apply_action(player, action)
            else:
                # Human: yield and wait for apply_human_action to be called
                logger.info(f"Waiting for human action: {player.player_id}")
                await self._broadcast("state_update", self.state.to_dict())
                return  # Control returns; apply_human_action will continue

            # Check if someone raised; update last raiser
            last_action = self.hand_history[-1] if self.hand_history else {}
            if last_action.get("action") == ActionType.RAISE.value:
                last_raiser_idx = self.current_player_index
                acted_count = 1
            else:
                acted_count += 1

            self.current_player_index = self._next_active_index(self.current_player_index)

        # Betting round complete: advance phase
        await self._advance_phase()

    async def _continue_after_human_action(self) -> None:
        """Resume betting round after human acts. Called by apply_human_action."""
        await self._run_betting_round()

    def _get_agent_decision(self, player: Player) -> Action:
        """Blocking call to agent decision (runs in executor)."""
        agent = self._agents[player.player_id]
        return agent.decide(
            hole_cards=player.hole_cards,
            community_cards=self.community_cards,
            pot=self.pot,
            current_bet=self.current_bet,
            my_stack=player.stack,
            my_bet_this_round=player.bet_this_round,
            position=self._position_label(self.current_player_index),
            history=self.hand_history[-5:],
            phase=self.phase.value,
        )

    async def _apply_action(self, player: Player, action: Action) -> None:
        """Apply a validated action from any player."""
        to_call = max(0, self.current_bet - player.bet_this_round)

        if action.action_type == ActionType.FOLD:
            player.is_folded = True
            logger.info(f"{player.player_id} folds")

        elif action.action_type == ActionType.CHECK:
            if to_call > 0:
                raise ValueError(f"Cannot check when there's a bet of {to_call}")
            logger.info(f"{player.player_id} checks")

        elif action.action_type == ActionType.CALL:
            chips = min(to_call, player.stack)
            player.stack -= chips
            player.bet_this_round += chips
            self.pot += chips
            if player.stack == 0:
                player.is_all_in = True
            logger.info(f"{player.player_id} calls {chips}")

        elif action.action_type in (ActionType.RAISE, ActionType.ALL_IN):
            total = min(action.amount + to_call, player.stack)
            if action.action_type == ActionType.ALL_IN:
                total = player.stack
            chips = total
            player.stack -= chips
            player.bet_this_round += chips
            self.pot += chips
            self.current_bet = max(self.current_bet, player.bet_this_round)
            if player.stack == 0:
                player.is_all_in = True
            logger.info(f"{player.player_id} raises to {player.bet_this_round}")

        self.hand_history.append(action.to_dict())
        await self._broadcast("action", {
            "player_id": player.player_id,
            "action": action.action_type.value,
            "amount": action.amount,
            "pot": self.pot,
        })

        # Check if only one player remains
        active = self._active_players()
        if len(active) == 1:
            await self._award_pot_to_last_player()
            return

        # If human just acted, continue the round
        if player.player_type == PlayerType.HUMAN:
            self.current_player_index = self._next_active_index(self.current_player_index)
            await self._continue_after_human_action()

    async def _advance_phase(self) -> None:
        """Move to the next game phase after betting is complete."""
        phase = self.phase
        if phase == GamePhase.PRE_FLOP:
            self.phase = GamePhase.FLOP_DEAL
        elif phase == GamePhase.FLOP_BET:
            self.phase = GamePhase.TURN_DEAL
        elif phase == GamePhase.TURN_BET:
            self.phase = GamePhase.RIVER_DEAL
        elif phase == GamePhase.RIVER_BET:
            await self._showdown()
            return
        else:
            logger.warning(f"Unexpected phase advance from {phase}")
            return

        logger.info(f"Advanced to phase: {self.phase}")
        await self._broadcast("state_update", self.state.to_dict())

    async def _showdown(self) -> None:
        self.phase = GamePhase.SHOWDOWN
        active = [p for p in self.players if not p.is_folded]

        if len(active) == 1:
            result = HandResult(
                winner_ids=[active[0].player_id],
                hand_ranks={active[0].player_id: ""},
                pot=self.pot,
                folded_win=True,
            )
        else:
            # Evaluate all hands
            scores: Dict[str, int] = {}
            hand_names: Dict[str, str] = {}
            for p in active:
                if len(p.hole_cards) == 2 and len(self.community_cards) >= 3:
                    score = evaluate(p.hole_cards, self.community_cards)
                    scores[p.player_id] = score
                    hand_names[p.player_id] = hand_rank_name(score)

            if not scores:
                # No valid hands (shouldn't happen)
                result = HandResult(
                    winner_ids=[active[0].player_id],
                    hand_ranks={},
                    pot=self.pot,
                )
            else:
                best_score = min(scores.values())
                winners = [pid for pid, s in scores.items() if s == best_score]
                result = HandResult(
                    winner_ids=winners,
                    hand_ranks=hand_names,
                    pot=self.pot,
                )

        # Award pot
        share = self.pot // len(result.winner_ids)
        remainder = self.pot % len(result.winner_ids)
        for i, pid in enumerate(result.winner_ids):
            player = self._player_by_id(pid)
            if player:
                player.stack += share + (remainder if i == 0 else 0)

        self.pot = 0
        self.last_result = result
        logger.info(f"Showdown: winners={result.winner_ids}, pot={result.pot}")
        await self._broadcast("hand_result", result.to_dict())
        await self._broadcast("state_update", self.state.to_dict(reveal_all=True))

        self.phase = GamePhase.IDLE

    async def _award_pot_to_last_player(self) -> None:
        """Award pot to the only non-folded player (everyone else folded)."""
        active = self._active_players()
        if not active:
            return
        winner = active[0]
        winner.stack += self.pot
        self.pot = 0
        result = HandResult(
            winner_ids=[winner.player_id],
            hand_ranks={},
            pot=self.pot,
            folded_win=True,
        )
        self.last_result = result
        self.phase = GamePhase.IDLE
        await self._broadcast("hand_result", result.to_dict())
        await self._broadcast("state_update", self.state.to_dict())

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _build_players(self) -> List[Player]:
        players = [
            Player("A", "Agent Alpha", PlayerType.AGENT, self.starting_stack,
                   AgentProfile.TAG, station_id="A"),
            Player("B", "Agent Beta", PlayerType.AGENT, self.starting_stack,
                   AgentProfile.LAG, station_id="B"),
        ]
        if self.mode in (GameMode.PLAYER, GameMode.TRAINING):
            players.append(
                Player("human", "You", PlayerType.HUMAN, self.starting_stack)
            )
        if self.mode == GameMode.TRAINING:
            # Remove Agent B
            players = [p for p in players if p.player_id != "B"]
        return players

    def _post_blind(self, player: Player, amount: int) -> None:
        chips = min(amount, player.stack)
        player.stack -= chips
        player.bet_this_round = chips
        self.pot += chips
        if player.stack == 0:
            player.is_all_in = True

    def _player_at_offset(self, offset: int) -> Player:
        idx = (self.dealer_index + offset) % len(self.players)
        return self.players[idx]

    def _active_players(self) -> List[Player]:
        return [p for p in self.players if not p.is_folded]

    def _betting_is_closed(self, last_raiser_idx: int, acted_count: int) -> bool:
        """Returns True when everyone has acted and bets are equal."""
        active = [p for p in self.players if not p.is_folded and not p.is_all_in]
        if len(active) <= 1:
            return True
        if last_raiser_idx == -1:
            return acted_count >= len(active)
        return acted_count >= len(active)

    def _next_active_index(self, current: int) -> int:
        n = len(self.players)
        for i in range(1, n + 1):
            idx = (current + i) % n
            if not self.players[idx].is_folded:
                return idx
        return current

    def _player_by_station(self, station_id: str) -> Optional[Player]:
        for p in self.players:
            if p.station_id == station_id:
                return p
        return None

    def _player_by_id(self, player_id: str) -> Optional[Player]:
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    @property
    def _human_player(self) -> Optional[Player]:
        for p in self.players:
            if p.player_type == PlayerType.HUMAN:
                return p
        return None

    @property
    def _dealer_player(self) -> Player:
        return self.players[self.dealer_index % len(self.players)]

    @property
    def current_player_id(self) -> Optional[str]:
        if self.phase == GamePhase.IDLE:
            return None
        try:
            return self.players[self.current_player_index].player_id
        except IndexError:
            return None

    def _position_label(self, idx: int) -> str:
        offset = (idx - self.dealer_index) % len(self.players)
        labels = {0: "dealer", 1: "sb", 2: "bb", 3: "utg"}
        return labels.get(offset, "middle")

    @property
    def state(self) -> GameState:
        return GameState(
            phase=self.phase,
            mode=self.mode,
            players=self.players,
            dealer_index=self.dealer_index,
            community_cards=self.community_cards,
            pot=self.pot,
            current_bet=self.current_bet,
            current_player_id=self.current_player_id,
            hand_history=self.hand_history,
            hand_number=self.hand_number,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            last_result=self.last_result,
        )


async def _noop_broadcast(event_type: str, payload: Dict) -> None:
    pass
