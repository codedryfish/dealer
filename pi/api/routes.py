"""
routes.py — REST API endpoints for D.E.A.L.E.R.

All endpoints return JSON. Error responses use standard HTTP status codes.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from dealer_engine.models import Action, ActionType, AgentProfile, Card, GameMode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CardsPayload(BaseModel):
    station_id: str          # "A" or "B"
    cards: List[str]         # ["AH", "KD"]


class CommunityPayload(BaseModel):
    cards: List[str]         # ["5S", "9C", "QH"] (flop) or ["TC"] (turn/river)


class HumanActionPayload(BaseModel):
    action: str              # "fold", "check", "call", "raise", "all_in"
    amount: Optional[int] = 0


class ModePayload(BaseModel):
    mode: str                # "observer", "player", "training"


class AgentProfilePayload(BaseModel):
    station_id: str
    profile: str             # "TAG", "LAG", "Nit", "Fish", "Maniac"


class BlindsPayload(BaseModel):
    small_blind: int
    big_blind: int


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _game(request: Request):
    """Get the DealerGame instance from app state."""
    return request.app.state.game


def _parse_cards(card_strings: List[str]) -> List[Card]:
    try:
        return [Card.from_str(s) for s in card_strings]
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/state")
async def get_state(request: Request):
    """Return full current game state."""
    game = _game(request)
    return game.state.to_dict()


@router.post("/new-hand")
async def new_hand(request: Request):
    """Start a new hand. Rotates dealer, posts blinds, transitions to DEALING."""
    game = _game(request)
    try:
        state = await game.start_new_hand()
        return state.to_dict()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/cards")
async def receive_hole_cards(payload: CardsPayload, request: Request):
    """
    Called by ESP32 agent stations when hole cards are placed on the reader.
    Triggers PRE_FLOP betting once all stations have reported.
    """
    game = _game(request)
    cards = _parse_cards(payload.cards)
    try:
        state = await game.receive_hole_cards(payload.station_id, cards)
        return state.to_dict()
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/community")
async def receive_community_cards(payload: CommunityPayload, request: Request):
    """
    Called by the community ESP32 station when community cards are read.
    Works for flop (3 cards), turn (1), and river (1).
    """
    game = _game(request)
    cards = _parse_cards(payload.cards)
    try:
        state = await game.receive_community_cards(cards)
        return state.to_dict()
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/action/{station_id}")
async def get_agent_action(station_id: str, request: Request):
    """
    Polled by ESP32 stations to get the latest action for their agent.
    Returns the most recent action from hand_history for this player.
    """
    game = _game(request)
    player = game._player_by_station(station_id)
    if player is None:
        raise HTTPException(status_code=404, detail=f"No player at station {station_id}")

    # Find most recent action for this player
    for action in reversed(game.hand_history):
        if action.get("player_id") == player.player_id:
            return {"action": action.get("action"), "amount": action.get("amount", 0)}

    return {"action": "waiting", "amount": 0}


@router.post("/human-action")
async def human_action(payload: HumanActionPayload, request: Request):
    """
    Called by companion app or physical buttons for the human player's action.
    """
    game = _game(request)
    try:
        action_type = ActionType(payload.action)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid action: {payload.action!r}")

    action = Action(action_type=action_type, amount=payload.amount or 0)
    try:
        state = await game.apply_human_action(action)
        return state.to_dict()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/mode")
async def set_mode(payload: ModePayload, request: Request):
    """Switch game mode. Only allowed when IDLE."""
    game = _game(request)
    try:
        mode = GameMode(payload.mode)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid mode: {payload.mode!r}")
    try:
        await game.set_mode(mode)
        return {"ok": True, "mode": mode.value}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/agent-profile")
async def set_agent_profile(payload: AgentProfilePayload, request: Request):
    """Assign an agent personality profile to a station."""
    game = _game(request)
    try:
        profile = AgentProfile(payload.profile)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid profile: {payload.profile!r}")
    try:
        await game.set_agent_profile(payload.station_id, profile)
        return {"ok": True, "station_id": payload.station_id, "profile": profile.value}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/blinds")
async def set_blinds(payload: BlindsPayload, request: Request):
    """Update blind levels. Takes effect on next hand."""
    game = _game(request)
    if payload.small_blind <= 0 or payload.big_blind <= payload.small_blind:
        raise HTTPException(status_code=422, detail="big_blind must be > small_blind > 0")
    game.small_blind = payload.small_blind
    game.big_blind = payload.big_blind
    return {"ok": True, "small_blind": payload.small_blind, "big_blind": payload.big_blind}


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "DEALER"}
