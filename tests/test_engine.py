"""
Engine tests: route extension rules, collision, noise, scoring, determinism.
Uses small hand-crafted game states to test individual rules in isolation.
"""
import dataclasses

import numpy as np
import pytest

from packet_pressure.config_presets import FAST_CONFIG
from packet_pressure.deck import DeckBuilder
from packet_pressure.engine import GameEngine
from packet_pressure.models import (
    Card,
    CardType,
    GameConfig,
    GameState,
    PlacementContext,
    PlayerState,
    RouteState,
    TableauState,
    TerminationReason,
)
from packet_pressure.policies import RandomLegal
from packet_pressure.simulation import run_simulation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_card(card_id, card_type=CardType.RELAY, in_ch="01", out_ch="02",
              value=100, color="red", owner=None, **kwargs):
    return Card(
        card_id=card_id,
        card_type=card_type,
        input_channel=in_ch,
        output_channel=out_ch,
        packet_value=value,
        color=color,
        owner_id=owner,
        **kwargs,
    )


def make_engine(config=None, n_policies=4):
    config = config or GameConfig()
    config = dataclasses.replace(config, player_count=n_policies)
    policies = [RandomLegal() for _ in range(n_policies)]
    rng = np.random.default_rng(42)
    deck = DeckBuilder(config, rng).build()
    return GameEngine(config, policies, deck, np.random.default_rng(42))


# ---------------------------------------------------------------------------
# Route extension
# ---------------------------------------------------------------------------

class TestRouteExtension:
    def test_channel_match_extends(self):
        engine = make_engine(n_policies=3)
        s = engine.state
        # Manually place a seed node and a relay node
        seed = make_card("SEED-0001", CardType.RELAY, in_ch="01", out_ch="02", owner="P0")
        s.tableau.active_cards[seed.card_id] = seed
        s.register_card(seed)
        engine._try_start_route(seed)
        assert len(s.tableau.routes) == 1
        route = s.tableau.routes[0]
        assert route.length == 1
        assert route.last_output_channel == "02"

        # Place a card that matches
        card = make_card("PKT-9001", in_ch="02", out_ch="03", owner="P1")
        s.tableau.active_cards[card.card_id] = card
        s.register_card(card)
        engine._update_routes(card)

        assert route.length == 2
        assert route.exit_node_id == "PKT-9001"

    def test_channel_mismatch_does_not_extend(self):
        engine = make_engine(n_policies=3)
        s = engine.state
        seed = make_card("SEED-0002", CardType.RELAY, in_ch="01", out_ch="02", owner="P0")
        s.tableau.active_cards[seed.card_id] = seed
        s.register_card(seed)
        engine._try_start_route(seed)

        card = make_card("PKT-9002", in_ch="03", out_ch="04", owner="P1")
        s.tableau.active_cards[card.card_id] = card
        s.register_card(card)
        engine._update_routes(card)

        # Should have started a new route, not extended
        assert len(s.tableau.routes) == 2
        assert s.tableau.routes[0].length == 1

    def test_hop_limit_terminates(self):
        cfg = dataclasses.replace(GameConfig(), player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        # Build a 2-card chain
        c1 = make_card("PKT-A", in_ch="01", out_ch="02", owner="P0")
        c2 = make_card("PKT-B", in_ch="02", out_ch="03", owner="P0")
        c3 = make_card("PKT-C", in_ch="03", out_ch="04", owner="P0")
        for c in (c1, c2, c3):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c

        engine._try_start_route(c1)
        engine._update_routes(c2)
        engine._update_routes(c3)

        route = s.tableau.routes[0]
        assert route.length == 3
        assert route.termination_reason == TerminationReason.HOP_LIMIT

    def test_no_loop_prevents_duplicate_card(self):
        cfg = dataclasses.replace(GameConfig(), no_loops=True, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("PKT-LOOP", in_ch="01", out_ch="02", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)

        # Attempt to extend with the same card
        can = engine._can_extend(s.tableau.routes[0], c1)
        assert can is False

    def test_no_return_to_first_hop(self):
        cfg = dataclasses.replace(GameConfig(), no_return_to_first_hop=True, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("PKT-R1", in_ch="01", out_ch="02", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)

        # Card that outputs to first card's input channel (01 is first_input_channel)
        c_return = make_card("PKT-R2", in_ch="02", out_ch="01", owner="P1")
        s.register_card(c_return)
        can = engine._can_extend(s.tableau.routes[0], c_return)
        assert can is False

    def test_no_output_channel_reuse(self):
        engine = make_engine(n_policies=3)
        s = engine.state

        # Route starts with output channel "01" in channels_in_route
        c1 = make_card("PKT-A", in_ch="03", out_ch="01", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)

        # c2 input matches route tail ("01"), but output "01" already in channels_in_route
        c2 = make_card("PKT-B", in_ch="01", out_ch="01", owner="P1")
        s.register_card(c2)
        can = engine._can_extend(s.tableau.routes[0], c2)
        assert can is False


# ---------------------------------------------------------------------------
# Terminal node
# ---------------------------------------------------------------------------

class TestTerminalNode:
    def test_terminal_wildcard_extends_any_route(self):
        engine = make_engine(n_policies=3)
        s = engine.state

        # Route ending on "03"
        c1 = make_card("PKT-T1", in_ch="01", out_ch="03", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)

        term = Card(
            card_id="TERM-0001",
            card_type=CardType.TERMINAL,
            input_channel="ANY",
            output_channel="TERM",
            packet_value=400,
            color="red",
            owner_id="P1",
        )
        s.register_card(term)
        s.tableau.active_cards[term.card_id] = term
        engine._update_routes(term)

        route = s.tableau.routes[0]
        assert route.termination_reason == TerminationReason.TERMINAL
        assert route.exit_node_id == "TERM-0001"

    def test_terminal_scores_if_min_length_met(self):
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("PKT-T2", in_ch="01", out_ch="02", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)

        term = Card("TERM-0002", CardType.TERMINAL, "ANY", "TERM", 400, "blue", owner_id="P1")
        s.register_card(term)
        s.tableau.active_cards[term.card_id] = term
        engine._update_routes(term)

        route = s.tableau.routes[0]
        assert route.length == 2
        assert route.is_scoring_candidate is True


# ---------------------------------------------------------------------------
# Amplifier node
# ---------------------------------------------------------------------------

class TestAmplifierNode:
    def test_amplifier_multiplier_applied(self):
        cfg = dataclasses.replace(GameConfig(), amplifier_multiplier=3, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("PKT-A1", in_ch="01", out_ch="02", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)

        amp = Card(
            card_id="AMP-0001",
            card_type=CardType.AMPLIFIER,
            input_channel="02",
            output_channel="03",
            packet_value=200,
            color="red",
            owner_id="P1",
            special_properties=(("multiplier", 3),),
        )
        s.register_card(amp)
        s.tableau.active_cards[amp.card_id] = amp
        engine._update_routes(amp)

        route = s.tableau.routes[0]
        # Amplifier does not terminate — route stays active, multiplier applies at scoring
        assert route.termination_reason == TerminationReason.ACTIVE
        assert route.exit_node_id == "AMP-0001"
        owner, score = engine._score_route(route)
        assert owner == "P1"
        assert score == 600  # 200 * 3


# ---------------------------------------------------------------------------
# Noise node
# ---------------------------------------------------------------------------

class TestNoiseNode:
    def test_noise_fires_and_clears(self):
        # Noise invalidates routes immediately but does not persist in noisy_channels
        engine = make_engine(n_policies=3)
        s = engine.state
        engine._apply_noise("03")
        assert "03" not in s.tableau.noisy_channels

    def test_noise_removes_cards_on_channel(self):
        # Noise targets interior channels only (channels_in_route[:-1], not the exit hop)
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("PKT-N1", in_ch="01", out_ch="02", owner="P0")
        c2 = make_card("PKT-N2", in_ch="02", out_ch="03", owner="P0")
        for c in (c1, c2):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
        engine._try_start_route(c1)
        engine._update_routes(c2)

        assert s.tableau.routes[0].length == 2

        # "02" is the interior hop; "03" is exit and cannot be targeted
        engine._apply_noise("02")

        assert "PKT-N1" not in s.tableau.active_cards
        assert "PKT-N1" in s.tableau.collided_card_ids

    def test_noise_spares_short_routes(self):
        # Routes shorter than route_min_length are not affected by noise
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("PKT-SHORT", in_ch="01", out_ch="03", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)

        assert s.tableau.routes[0].length == 1

        engine._apply_noise("03")

        # Card survives — route is length 1, below min_length
        assert "PKT-SHORT" in s.tableau.active_cards


# ---------------------------------------------------------------------------
# End-of-round scoring
# ---------------------------------------------------------------------------

class TestScoring:
    def test_exit_node_value_scores(self):
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("PKT-SC1", in_ch="01", out_ch="02", value=100, owner="P0")
        c2 = make_card("PKT-SC2", in_ch="02", out_ch="03", value=300, owner="P1")
        for c in (c1, c2):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c

        engine._try_start_route(c1)
        engine._update_routes(c2)

        route = s.tableau.routes[0]
        assert route.length == 2
        assert route.exit_node_id == "PKT-SC2"

        # Only exit node value counts
        owner, score = engine._score_route(route)
        assert score == 300
        assert owner == "P1"


# ---------------------------------------------------------------------------
# Full game determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_seed_same_result(self):
        from packet_pressure.simulation import run_simulation
        from packet_pressure.config_presets import FAST_CONFIG
        from packet_pressure.policies import RandomLegal

        policies = [RandomLegal(), RandomLegal(), RandomLegal()]
        m1 = run_simulation(FAST_CONFIG, policies, seed=99)
        m2 = run_simulation(FAST_CONFIG, policies, seed=99)

        assert m1.winner == m2.winner
        assert m1.final_scores == m2.final_scores
        assert m1.total_rounds_played == m2.total_rounds_played

    def test_different_seeds_can_differ(self):
        from packet_pressure.simulation import run_simulation
        from packet_pressure.config_presets import FAST_CONFIG
        from packet_pressure.policies import RandomLegal

        policies = [RandomLegal(), RandomLegal(), RandomLegal()]
        results = [run_simulation(FAST_CONFIG, policies, seed=s) for s in range(10)]
        scores = [r.final_scores for r in results]
        # At least some games should differ
        assert len(set(str(s) for s in scores)) > 1


# ---------------------------------------------------------------------------
# Turn order rotation
# ---------------------------------------------------------------------------

class TestTurnOrderRotation:
    def test_winner_goes_first_next_round(self):
        # Force a round where P1 scores by seeding a 2-card route ending with
        # P1's exit node, then verify first_player_index becomes 1 after scoring.
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3,
                                  winner_goes_first=True, max_rounds=2)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        # Manually build a scoring route owned by P1
        c1 = make_card("PKT-R1", in_ch="01", out_ch="02", value=100, owner="P0")
        c2 = make_card("PKT-R2", in_ch="02", out_ch="03", value=500, owner="P1")
        for c in (c1, c2):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
        engine._try_start_route(c1)
        engine._update_routes(c2)

        assert s.first_player_index == 0
        engine._end_of_round_scoring()
        # P1 scored, so first_player_index should now be 1
        assert s.first_player_index == 1

    def test_no_rotation_when_disabled(self):
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3,
                                  winner_goes_first=False, max_rounds=2)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("PKT-N1", in_ch="01", out_ch="02", value=100, owner="P0")
        c2 = make_card("PKT-N2", in_ch="02", out_ch="03", value=500, owner="P2")
        for c in (c1, c2):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
        engine._try_start_route(c1)
        engine._update_routes(c2)

        engine._end_of_round_scoring()
        assert s.first_player_index == 0

    def test_tie_leaves_first_player_unchanged(self):
        # Two players score equally — no rotation, first_player_index stays 0
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3,
                                  winner_goes_first=True, max_rounds=2)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        # Route 1: P1 exit node, value 300
        a1 = make_card("PKT-T1", in_ch="01", out_ch="02", value=100, owner="P0")
        a2 = make_card("PKT-T2", in_ch="02", out_ch="03", value=300, owner="P1")
        # Route 2: P2 exit node, value 300 (tie)
        b1 = make_card("PKT-T3", in_ch="03", out_ch="01", value=100, owner="P0")
        b2 = make_card("PKT-T4", in_ch="01", out_ch="02", value=300, owner="P2")
        for c in (a1, a2, b1, b2):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
        engine._try_start_route(a1)
        engine._update_routes(a2)
        engine._try_start_route(b1)
        engine._update_routes(b2)

        engine._end_of_round_scoring()
        assert s.first_player_index == 0


# ---------------------------------------------------------------------------
# Filter node
# ---------------------------------------------------------------------------

class TestFilterNode:
    def test_filter_can_start_route(self):
        engine = make_engine(n_policies=3)
        s = engine.state
        flt = make_card("FLT-X1", CardType.FILTER, in_ch="01", out_ch="02", owner="P0")
        s.register_card(flt)
        s.tableau.active_cards[flt.card_id] = flt
        engine._try_start_route(flt)
        assert len(s.tableau.routes) == 1
        assert s.tableau.routes[0].length == 1

    def test_filter_absorbs_noise_on_input_channel(self):
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("REL-X1", in_ch="01", out_ch="02", owner="P0")
        flt = make_card("FLT-X2", CardType.FILTER, in_ch="02", out_ch="03", owner="P0")
        for c in (c1, flt):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
        engine._try_start_route(c1)
        engine._update_routes(flt)
        assert s.tableau.routes[0].length == 2

        engine._apply_noise("02")  # filter's input channel — absorbed

        assert s.tableau.routes[0].is_valid

    def test_filter_does_not_protect_other_channels(self):
        # Filter (input="02") absorbs noise on "02" but not "03".
        # Needs a 3-hop route so "03" is an interior channel that can be targeted.
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("REL-X2", in_ch="01", out_ch="02", owner="P0")
        flt = make_card("FLT-X3", CardType.FILTER, in_ch="02", out_ch="03", owner="P0")
        c3 = make_card("REL-X3", in_ch="03", out_ch="01", owner="P0")
        for c in (c1, flt, c3):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
        engine._try_start_route(c1)
        engine._update_routes(flt)
        engine._update_routes(c3)
        # channels_in_route=["02","03","01"]; interior=["02","03"]
        assert s.tableau.routes[0].length == 3

        engine._apply_noise("03")  # interior channel; filter input is "02", not "03"

        assert not s.tableau.routes[0].is_valid


# ---------------------------------------------------------------------------
# Terminal node (additional)
# ---------------------------------------------------------------------------

class TestTerminalNodeExtra:
    def test_terminal_cannot_start_route(self):
        engine = make_engine(n_policies=3)
        s = engine.state
        term = Card("TERM-X1", CardType.TERMINAL, "ANY", "TERM", 400, "red")
        s.register_card(term)
        engine._try_start_route(term)
        assert len(s.tableau.routes) == 0

    def test_terminal_value_scores_not_predecessor(self):
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("REL-T1", in_ch="01", out_ch="02", value=300, owner="P0")
        term = Card("TERM-T1", CardType.TERMINAL, "ANY", "TERM", 500, "red", owner_id="P1")
        for c in (c1, term):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
        engine._try_start_route(c1)
        engine._update_routes(term)

        route = s.tableau.routes[0]
        assert route.exit_node_id == "TERM-T1"
        owner, score = engine._score_route(route)
        assert score == 500  # terminal's value, not the relay's 300
        assert owner == "P1"


# ---------------------------------------------------------------------------
# Amplifier node (additional)
# ---------------------------------------------------------------------------

class TestAmplifierNodeExtra:
    def test_amplifier_multiplier_lost_when_extended(self):
        cfg = dataclasses.replace(GameConfig(), amplifier_multiplier=2, route_min_length=2,
                                  player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("REL-A1", in_ch="01", out_ch="02", value=100, owner="P0")
        amp = Card("AMP-A1", CardType.AMPLIFIER, "02", "03", 200, "red",
                   owner_id="P1", special_properties=(("multiplier", 2),))
        c3 = make_card("REL-A2", in_ch="03", out_ch="01", value=150, owner="P2")
        for c in (c1, amp, c3):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
        engine._try_start_route(c1)
        engine._update_routes(amp)
        engine._update_routes(c3)

        route = s.tableau.routes[0]
        assert route.exit_node_id == "REL-A2"
        owner, score = engine._score_route(route)
        assert score == 150  # relay's face value — amplifier bonus is gone


# ---------------------------------------------------------------------------
# Noise node (additional)
# ---------------------------------------------------------------------------

class TestNoiseNodeExtra:
    def test_noise_does_not_carry_route(self):
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("REL-NC1", in_ch="01", out_ch="02", owner="P0")
        c2 = make_card("REL-NC2", in_ch="02", out_ch="03", owner="P0")
        for c in (c1, c2):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
        engine._try_start_route(c1)
        engine._update_routes(c2)
        assert s.tableau.routes[0].length == 2

        engine._apply_noise("02")  # target interior channel "02", not exit "03"
        assert not s.tableau.routes[0].is_valid

        engine._discard_tableau()
        assert len(s.tableau.routes) == 0


# ---------------------------------------------------------------------------
# Carried routes
# ---------------------------------------------------------------------------

class TestCarriedRoutes:
    def test_stub_carries_to_next_round(self):
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("REL-CR1", in_ch="01", out_ch="02", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)
        assert s.tableau.routes[0].length == 1

        engine._discard_tableau()
        assert len(s.tableau.routes) == 1
        assert s.tableau.routes[0].carried is True

    def test_carried_route_can_be_extended(self):
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("REL-CR2", in_ch="01", out_ch="02", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)
        engine._discard_tableau()

        c2 = make_card("REL-CR3", in_ch="02", out_ch="03", owner="P1")
        s.register_card(c2)
        s.tableau.active_cards[c2.card_id] = c2
        engine._update_routes(c2)
        assert s.tableau.routes[0].length == 2

    def test_carried_route_reduces_seed_count(self):
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3,
                                  seed_nodes_per_round=2, max_rounds=2)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state
        s.round_number = 0

        c1 = make_card("REL-CR4", in_ch="01", out_ch="02", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)
        engine._discard_tableau()
        assert len(s.tableau.routes) == 1

        s.round_number += 1
        engine._begin_round()
        # 1 carried stub already open, so only 1 new seed dealt (2 - 1 = 1)
        assert len(s.tableau.routes) == 2


# ---------------------------------------------------------------------------
# Route cap
# ---------------------------------------------------------------------------

class TestRouteCap:
    def test_new_route_blocked_when_cap_full(self):
        cfg = dataclasses.replace(GameConfig(), player_count=2)
        engine = make_engine(config=cfg, n_policies=2)
        s = engine.state

        c1 = make_card("REL-CAP1", in_ch="01", out_ch="02", owner="P0")
        c2 = make_card("REL-CAP2", in_ch="03", out_ch="01", owner="P0")
        for c in (c1, c2):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
        engine._try_start_route(c1)
        engine._try_start_route(c2)
        assert len(s.tableau.routes) == 2  # cap = player_count = 2

        c3 = make_card("REL-CAP3", in_ch="03", out_ch="02", owner="P1")
        s.register_card(c3)
        s.tableau.active_cards[c3.card_id] = c3
        engine._try_start_route(c3)
        assert len(s.tableau.routes) == 2  # still capped

    def test_cap_slot_freed_after_route_closes(self):
        cfg = dataclasses.replace(GameConfig(), player_count=2, route_min_length=2)
        engine = make_engine(config=cfg, n_policies=2)
        s = engine.state

        # Fill cap: 2 routes
        c1 = make_card("REL-SL1", in_ch="01", out_ch="02", owner="P0")
        c2 = make_card("REL-SL2", in_ch="03", out_ch="01", owner="P0")
        for c in (c1, c2):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
        engine._try_start_route(c1)
        engine._try_start_route(c2)

        # Extend route 0 to length 2
        c_ext = make_card("REL-SL3", in_ch="02", out_ch="03", owner="P0")
        s.register_card(c_ext)
        s.tableau.active_cards[c_ext.card_id] = c_ext
        engine._update_routes(c_ext)
        route0_id = s.tableau.routes[0].route_id

        # Close route 0 with a terminal
        term = Card("TERM-SL1", CardType.TERMINAL, "ANY", "TERM", 400, "red",
                    owner_id="P1",
                    special_properties=(("target_route_id", route0_id),))
        s.register_card(term)
        s.tableau.active_cards[term.card_id] = term
        engine._update_routes(term)
        assert not s.tableau.routes[0].is_open()

        # A new route can now be started (cap freed)
        c_new = make_card("REL-SL4", in_ch="02", out_ch="03", owner="P1")
        s.register_card(c_new)
        s.tableau.active_cards[c_new.card_id] = c_new
        engine._try_start_route(c_new)
        open_routes = [r for r in s.tableau.routes if r.is_open()]
        assert len(open_routes) == 2


# ---------------------------------------------------------------------------
# Round / turn structure
# ---------------------------------------------------------------------------

class TestRoundStructure:
    def test_hands_refilled_at_round_end(self):
        cfg = dataclasses.replace(GameConfig(), starting_hand_size=4, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        s.players[0].hand.clear()
        assert len(s.players[0].hand) == 0

        engine._advance_round()
        assert len(s.players[0].hand) == 4

    def test_deck_reshuffles_from_discard_when_empty(self):
        cfg = dataclasses.replace(GameConfig(), player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        s.discard.extend(s.deck)
        s.deck.clear()
        assert len(s.deck) == 0

        drawn = engine._draw_n(s, 1)
        assert len(drawn) == 1


# ---------------------------------------------------------------------------
# Win condition
# ---------------------------------------------------------------------------

class TestWinCondition:
    def test_game_ends_when_score_target_reached(self):
        cfg = dataclasses.replace(FAST_CONFIG, score_to_win=1, player_count=3)
        policies = [RandomLegal(), RandomLegal(), RandomLegal()]
        rng = np.random.default_rng(0)
        deck = DeckBuilder(cfg, rng).build()
        engine = GameEngine(cfg, policies, deck, np.random.default_rng(0))
        engine.run()
        assert engine.state._terminal is True
        assert any(p.score >= 1 for p in engine.state.players)

    def test_game_ends_at_max_rounds(self):
        metrics = run_simulation(
            dataclasses.replace(FAST_CONFIG, max_rounds=1, score_to_win=999_999),
            [RandomLegal(), RandomLegal(), RandomLegal()],
            seed=7,
        )
        assert metrics.total_rounds_played == 1
