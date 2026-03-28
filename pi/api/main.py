"""
main.py — FastAPI application factory for D.E.A.L.E.R.

Serves:
  - REST API on /api/*
  - WebSocket on /ws
  - Static web app files from pi/web/
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from dealer_engine.game import DealerGame
from dealer_engine.models import GameMode
from .routes import router
from .ws import WebSocketManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

WEB_DIR = Path(__file__).parent.parent / "web"


def create_app(
    mode: GameMode = GameMode.OBSERVER,
    small_blind: int = 50,
    big_blind: int = 100,
    starting_stack: int = 1000,
) -> FastAPI:
    app = FastAPI(
        title="D.E.A.L.E.R.",
        description="Digitally Enhanced Agent-Led Entertainment Rig — Poker API",
        version="0.1.0",
    )

    # CORS: allow any origin on the Pi's local network
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # WebSocket manager (singleton shared across requests)
    ws_manager = WebSocketManager()

    # Poker engine (broadcast_fn hooks into WS manager)
    async def broadcast(event_type: str, payload: dict) -> None:
        await ws_manager.broadcast(event_type, payload)

    game = DealerGame(
        mode=mode,
        small_blind=small_blind,
        big_blind=big_blind,
        starting_stack=starting_stack,
        broadcast_fn=broadcast,
    )

    # Store on app state for access in route handlers
    app.state.game = game
    app.state.ws_manager = ws_manager

    # REST routes
    app.include_router(router)

    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws_manager.connect(ws)
        # Send current state immediately on connect
        await ws.send_json({"type": "state_update", "data": game.state.to_dict()})
        try:
            while True:
                # Keep connection alive; clients can send pings
                data = await ws.receive_text()
                if data == "ping":
                    await ws.send_text("pong")
        except WebSocketDisconnect:
            ws_manager.disconnect(ws)

    # Serve static web app
    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    else:
        logger.warning(f"Web directory not found: {WEB_DIR}")

    @app.on_event("startup")
    async def on_startup():
        logger.info("D.E.A.L.E.R. API starting up")
        logger.info(f"Mode: {mode.value}, Blinds: {small_blind}/{big_blind}, Stack: {starting_stack}")

    return app


# ---------------------------------------------------------------------------
# Entry point (uvicorn runs this)
# ---------------------------------------------------------------------------

app = create_app(
    mode=GameMode(os.getenv("DEALER_MODE", "observer")),
    small_blind=int(os.getenv("DEALER_SB", "50")),
    big_blind=int(os.getenv("DEALER_BB", "100")),
    starting_stack=int(os.getenv("DEALER_STACK", "1000")),
)
