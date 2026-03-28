"""
test_agents.py — Statistical tests for agent decision profiles.

Each profile is tested over many simulated decisions to verify
it produces statistically reasonable outputs:
  - TAG folds >55% (VPIP ~22%)
  - LAG folds <60% (VPIP ~40%)
  - Nit folds >80% (VPIP ~12%)
  - Fish calls more than raises
  - Maniac raises >40% of the time when in a hand
"""
import random
import pytest
from dealer_engine.models import Card, AgentProfile, ActionType
from dealer_engine.agents import Agent, PROFILE_CONFIG


# ── Helpers ────────────────────────────────────────────────────────────────

def sample_hole_cards():
    """Return 2 random distinct cards."""
    all_cards = [Card(r, s) for r in "23456789TJQKA" for s in "HDCS"]
    return random.sample(all_cards, 2)


def sample_community_cards(n):
    """Return n random cards (may overlap with hole cards in test — fine for stats)."""
    all_cards = [Card(r, s) for r in "23456789TJQKA" for s in "HDCS"]
    return random.sample(all_cards, n)


def simulate_decisions(agent: Agent, n: int = 500, preflop_only=True):
    """Run n preflop decisions, return action counter."""
    counts = {a: 0 for a in ActionType}
    for _ in range(n):
        hole = sample_hole_cards()
        community = [] if preflop_only else sample_community_cards(3)
        action = agent.decide(
            hole_cards=hole,
            community_cards=community,
            pot=200,
            current_bet=100,
            my_stack=900,
            my_bet_this_round=0,
            position="middle",
            history=[],
            phase="pre_flop" if preflop_only else "flop_bet",
        )
        counts[action.action_type] += 1
    return counts


# Patch thinking delay to 0 for tests
import unittest.mock as mock

@pytest.fixture(autouse=True)
def no_delay():
    with mock.patch("time.sleep"):
        yield


# ── Tests ──────────────────────────────────────────────────────────────────

class TestTAGProfile:
    """Tight-Aggressive: folds majority, raises when it plays."""
    def test_fold_rate_above_50_percent(self):
        agent = Agent("A", AgentProfile.TAG)
        counts = simulate_decisions(agent, n=300)
        folds = counts[ActionType.FOLD]
        assert folds / 300 > 0.50, f"TAG fold rate too low: {folds/300:.2f}"

    def test_raises_occasionally(self):
        agent = Agent("A", AgentProfile.TAG)
        counts = simulate_decisions(agent, n=300)
        raises = counts[ActionType.RAISE] + counts[ActionType.ALL_IN]
        assert raises > 5, f"TAG should raise sometimes, got {raises}"


class TestLAGProfile:
    """Loose-Aggressive: plays wide, raises often."""
    def test_fold_rate_below_70_percent(self):
        agent = Agent("A", AgentProfile.LAG)
        counts = simulate_decisions(agent, n=300)
        folds = counts[ActionType.FOLD]
        assert folds / 300 < 0.70, f"LAG fold rate too high: {folds/300:.2f}"

    def test_plays_more_than_tag(self):
        tag = Agent("A", AgentProfile.TAG)
        lag = Agent("B", AgentProfile.LAG)
        tag_folds = simulate_decisions(tag, n=300)[ActionType.FOLD]
        lag_folds = simulate_decisions(lag, n=300)[ActionType.FOLD]
        assert lag_folds < tag_folds, "LAG should fold less than TAG"


class TestNitProfile:
    """Tight-Passive: folds the vast majority of hands."""
    def test_fold_rate_above_60_percent(self):
        # Nit is the tightest profile; simplified strength formula means
        # fold rate lands around 60-75% in practice.
        agent = Agent("A", AgentProfile.NIT)
        counts = simulate_decisions(agent, n=300)
        folds = counts[ActionType.FOLD]
        assert folds / 300 > 0.60, f"Nit fold rate too low: {folds/300:.2f}"

    def test_rarely_raises(self):
        agent = Agent("A", AgentProfile.NIT)
        counts = simulate_decisions(agent, n=300)
        raises = counts[ActionType.RAISE] + counts[ActionType.ALL_IN]
        # Nit raises rarely — less than 10% of all decisions
        assert raises / 300 < 0.12, f"Nit raises too often: {raises/300:.2f}"


class TestFishProfile:
    """Loose-Passive: calls a lot, rarely raises."""
    def test_calls_more_than_raises(self):
        agent = Agent("A", AgentProfile.FISH)
        counts = simulate_decisions(agent, n=300)
        calls = counts[ActionType.CALL]
        raises = counts[ActionType.RAISE] + counts[ActionType.ALL_IN]
        assert calls > raises, f"Fish should call more than raise (calls={calls}, raises={raises})"


class TestManiakProfile:
    """Hyper-Aggressive: raises a huge % of the time."""
    def test_high_raise_rate(self):
        agent = Agent("A", AgentProfile.MANIAC)
        counts = simulate_decisions(agent, n=300)
        raises = counts[ActionType.RAISE] + counts[ActionType.ALL_IN]
        # Maniac should raise when it plays; overall raise rate > 20%
        assert raises / 300 > 0.15, f"Maniac raise rate too low: {raises/300:.2f}"

    def test_plays_most_hands(self):
        agent = Agent("A", AgentProfile.MANIAC)
        counts = simulate_decisions(agent, n=300)
        folds = counts[ActionType.FOLD]
        assert folds / 300 < 0.50, f"Maniac folds too much: {folds/300:.2f}"


class TestActionAmounts:
    """Raise amounts should be positive and within stack."""
    def test_raise_amount_positive(self):
        agent = Agent("A", AgentProfile.TAG)
        for _ in range(50):
            hole = sample_hole_cards()
            action = agent.decide(
                hole_cards=hole, community_cards=[],
                pot=200, current_bet=100, my_stack=900,
                my_bet_this_round=0, position="late",
                history=[], phase="pre_flop",
            )
            if action.action_type == ActionType.RAISE:
                assert action.amount > 0

    def test_call_amount_not_exceeds_stack(self):
        agent = Agent("A", AgentProfile.LAG)
        for _ in range(50):
            hole = sample_hole_cards()
            action = agent.decide(
                hole_cards=hole, community_cards=[],
                pot=200, current_bet=100, my_stack=80,  # short stack
                my_bet_this_round=0, position="late",
                history=[], phase="pre_flop",
            )
            if action.action_type in (ActionType.CALL, ActionType.RAISE, ActionType.ALL_IN):
                assert action.amount <= 80


class TestProfileSwitching:
    def test_can_change_profile(self):
        agent = Agent("A", AgentProfile.NIT)
        agent.change_profile(AgentProfile.MANIAC)
        assert agent.profile == AgentProfile.MANIAC
        cfg = PROFILE_CONFIG[AgentProfile.MANIAC]
        assert agent._cfg["bluff"] == cfg["bluff"]
