/**
 * app.js — D.E.A.L.E.R. companion web app
 * Vanilla JS, WebSocket, no framework.
 * Connects to ws://dealer.local/ws and http://dealer.local/api/*
 */

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const API = `${location.protocol}//${location.host}/api`;
const WS_URL = `ws://${location.host}/ws`;
const PROFILES = ["TAG", "LAG", "Nit", "Fish", "Maniac"];
const SUIT_SYMBOLS = { H: "♥", D: "♦", C: "♣", S: "♠" };
const RED_SUITS = new Set(["H", "D"]);

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let state = null;
let ws = null;
let sessionStats = {
  handsPlayed: 0,
  results: [], // [{winner, pot, hand_rank}]
};
let handHistoryLog = [];

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const $ = id => document.getElementById(id);

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------
function connectWS() {
  ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    $("connection-status").textContent = "⚡ Connected";
    $("connection-status").className = "connection-status connected";
  };
  ws.onmessage = evt => {
    const msg = JSON.parse(evt.data);
    if (msg.type === "state_update") {
      state = msg.data;
      render();
    } else if (msg.type === "hand_result") {
      handleHandResult(msg.data);
    } else if (msg.type === "action") {
      flashAction(msg.data);
    }
  };
  ws.onclose = () => {
    $("connection-status").textContent = "⚡ Disconnected — reconnecting…";
    $("connection-status").className = "connection-status";
    setTimeout(connectWS, 3000);
  };
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
async function apiPost(path, body = {}) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    console.error(`API error ${path}:`, err);
    setStatus(err.detail || "API error");
  }
  return res.json().catch(() => null);
}

async function apiGet(path) {
  const res = await fetch(`${API}${path}`);
  return res.json().catch(() => null);
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------
function render() {
  if (!state) return;
  renderPhase();
  renderPot();
  renderCommunityCards();
  renderPlayers();
  renderActionPanel();
}

function renderPhase() {
  $("phase-badge").textContent = (state.phase || "IDLE").toUpperCase().replace("_", " ");
}

function renderPot() {
  $("pot-amount").textContent = state.pot || 0;
}

function renderCommunityCards() {
  const container = $("community-cards");
  container.innerHTML = "";
  const cards = state.community_cards || [];
  for (const c of cards) {
    container.appendChild(buildCard(c));
  }
  // Placeholder slots
  for (let i = cards.length; i < 5; i++) {
    const slot = document.createElement("div");
    slot.className = "card hidden";
    container.appendChild(slot);
  }
}

function renderPlayers() {
  const container = $("players-area");
  container.innerHTML = "";
  const players = state.players || [];
  for (const p of players) {
    container.appendChild(buildPlayerRow(p));
  }
}

function buildPlayerRow(p) {
  const row = document.createElement("div");
  row.className = "player-row" +
    (p.player_id === state.current_player_id ? " active-player" : "") +
    (p.is_folded ? " folded" : "");

  const info = document.createElement("div");
  info.className = "player-info";

  const name = document.createElement("div");
  name.className = "player-name";
  name.textContent = p.name + (p.is_folded ? " (folded)" : "") + (p.is_all_in ? " 🔥 ALL-IN" : "");
  info.appendChild(name);

  const stack = document.createElement("div");
  stack.className = "player-stack";
  stack.textContent = `Stack: ${p.stack}`;
  info.appendChild(stack);

  if (p.bet_this_round > 0) {
    const bet = document.createElement("div");
    bet.className = "player-bet";
    bet.textContent = `Bet: ${p.bet_this_round}`;
    info.appendChild(bet);
  }

  row.appendChild(info);

  // Cards
  const cardsDiv = document.createElement("div");
  cardsDiv.className = "player-cards";
  const cards = p.hole_cards || [];
  if (cards.length === 0) {
    for (let i = 0; i < 2; i++) {
      const slot = document.createElement("div");
      slot.className = "card hidden";
      cardsDiv.appendChild(slot);
    }
  } else {
    for (const c of cards) {
      cardsDiv.appendChild(buildCard(c === "??" ? null : c));
    }
  }
  row.appendChild(cardsDiv);

  // Status
  const status = document.createElement("div");
  status.className = "player-status" +
    (p.player_id === state.current_player_id && !p.is_folded ? " thinking" : "");
  if (p.player_id === state.current_player_id && !p.is_folded) {
    status.textContent = p.player_type === "agent" ? "Thinking…" : "Your turn";
  }
  row.appendChild(status);

  return row;
}

function buildCard(code) {
  const el = document.createElement("div");
  if (!code) {
    el.className = "card hidden";
    return el;
  }
  const rank = code[0];
  const suit = code[1];
  el.className = "card" + (RED_SUITS.has(suit) ? (suit === "H" ? " hearts" : " diamonds") : "");
  el.innerHTML = `<span>${rank}</span><span class="suit-symbol">${SUIT_SYMBOLS[suit] || suit}</span>`;
  return el;
}

function renderActionPanel() {
  const panel = $("action-panel");
  const human = state && state.players
    ? state.players.find(p => p.player_type === "human")
    : null;

  const isHumanTurn = human && state.current_player_id === human.player_id && !human.is_folded;
  panel.style.display = isHumanTurn ? "block" : "none";

  if (!isHumanTurn || !human) return;

  const toCall = Math.max(0, state.current_bet - (human.bet_this_round || 0));
  const canCheck = toCall === 0;

  $("btn-check").disabled = !canCheck;
  $("btn-call").disabled = canCheck;
  $("call-amount").textContent = toCall > 0 ? toCall : "";

  const maxRaise = human.stack;
  const minRaise = Math.max(toCall * 2, state.big_blind || 100);
  const slider = $("raise-slider");
  slider.min = minRaise;
  slider.max = maxRaise;
  slider.value = Math.min(Math.max(slider.value, minRaise), maxRaise);
  $("raise-amount").textContent = slider.value;
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------
async function act(action, amount = 0) {
  await apiPost("/human-action", { action, amount: Number(amount) });
}

// ---------------------------------------------------------------------------
// Hand result
// ---------------------------------------------------------------------------
function handleHandResult(result) {
  sessionStats.handsPlayed++;
  sessionStats.results.push(result);

  const entry = {
    num: sessionStats.handsPlayed,
    winner_ids: result.winner_ids,
    pot: result.pot,
    hand_ranks: result.hand_ranks || {},
    folded_win: result.folded_win,
  };
  handHistoryLog.unshift(entry);
  renderHistory();
  renderStats();

  setStatus(`Hand #${entry.num} — Winner: ${result.winner_ids.join(", ")} (pot: ${result.pot})`);
}

function flashAction(data) {
  setStatus(`${data.player_id}: ${data.action.toUpperCase()} ${data.amount > 0 ? data.amount : ""}`);
}

function setStatus(msg) {
  $("status-msg").textContent = msg;
  clearTimeout(setStatus._timer);
  setStatus._timer = setTimeout(() => { $("status-msg").textContent = ""; }, 6000);
}

// ---------------------------------------------------------------------------
// Stats view
// ---------------------------------------------------------------------------
function renderStats() {
  const grid = $("stats-grid");
  grid.innerHTML = "";

  const addStat = (label, value, name) => {
    const card = document.createElement("div");
    card.className = "stat-card";
    card.innerHTML = `<div class="stat-label">${label}</div>
      <div class="stat-value">${value}</div>
      <div class="stat-name">${name || ""}</div>`;
    grid.appendChild(card);
  };

  addStat("HANDS", sessionStats.handsPlayed, "Played");

  if (sessionStats.results.length > 0) {
    const maxPot = Math.max(...sessionStats.results.map(r => r.pot));
    addStat("BIGGEST POT", maxPot, "chips");

    // Count wins per player
    const wins = {};
    for (const r of sessionStats.results) {
      for (const id of (r.winner_ids || [])) {
        wins[id] = (wins[id] || 0) + 1;
      }
    }
    const sorted = Object.entries(wins).sort((a, b) => b[1] - a[1]);
    if (sorted.length > 0) {
      addStat("LEADING", sorted[0][1], sorted[0][0]);
    }
  }
}

// ---------------------------------------------------------------------------
// History view
// ---------------------------------------------------------------------------
function renderHistory() {
  const list = $("hand-history-list");
  list.innerHTML = "";
  if (handHistoryLog.length === 0) {
    list.innerHTML = '<p class="muted">No hands played yet.</p>';
    return;
  }
  for (const h of handHistoryLog) {
    const el = document.createElement("div");
    el.className = "hand-entry";
    const ranks = Object.entries(h.hand_ranks)
      .map(([id, name]) => `${id}: ${name}`).join(", ");
    el.innerHTML = `
      <span class="hand-num">Hand #${h.num}</span>
      <span class="hand-winner"> — Winner: ${h.winner_ids.join(", ")}${h.folded_win ? " (fold)" : ""}</span>
      <span class="hand-pot"> — Pot: ${h.pot}</span>
      ${ranks ? `<div style="color:var(--muted);font-size:11px;margin-top:2px">${ranks}</div>` : ""}
    `;
    list.appendChild(el);
  }
}

// ---------------------------------------------------------------------------
// Admin setup
// ---------------------------------------------------------------------------
function setupAdmin() {
  // Populate profile selects
  for (const selectId of ["profile-A", "profile-B"]) {
    const sel = $(selectId);
    sel.innerHTML = "";
    for (const p of PROFILES) {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      sel.appendChild(opt);
    }
  }
  // Default: A=TAG, B=LAG
  $("profile-A").value = "TAG";
  $("profile-B").value = "LAG";

  $("profile-A").addEventListener("change", () =>
    apiPost("/agent-profile", { station_id: "A", profile: $("profile-A").value }));
  $("profile-B").addEventListener("change", () =>
    apiPost("/agent-profile", { station_id: "B", profile: $("profile-B").value }));

  $("btn-set-blinds").addEventListener("click", () =>
    apiPost("/blinds", { small_blind: Number($("sb-input").value), big_blind: Number($("bb-input").value) }));

  $("btn-new-hand").addEventListener("click", () => apiPost("/new-hand"));

  // Mode buttons
  document.querySelectorAll(".mode-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      await apiPost("/mode", { mode: btn.dataset.mode });
    });
  });
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------
function setupNav() {
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
      btn.classList.add("active");
      $(`view-${btn.dataset.view}`).classList.add("active");
    });
  });
}

// ---------------------------------------------------------------------------
// Action button wiring
// ---------------------------------------------------------------------------
function setupActions() {
  $("btn-fold").addEventListener("click", () => act("fold"));
  $("btn-check").addEventListener("click", () => act("check"));
  $("btn-call").addEventListener("click", () => {
    const human = state && state.players ? state.players.find(p => p.player_type === "human") : null;
    const toCall = human ? Math.max(0, state.current_bet - (human.bet_this_round || 0)) : 0;
    act("call", toCall);
  });
  $("btn-raise").addEventListener("click", () => act("raise", $("raise-slider").value));
  $("raise-slider").addEventListener("input", () => {
    $("raise-amount").textContent = $("raise-slider").value;
  });
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
(async () => {
  setupNav();
  setupAdmin();
  setupActions();
  connectWS();

  // Load initial state via REST fallback
  const s = await apiGet("/state");
  if (s) { state = s; render(); }
})();
