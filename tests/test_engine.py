"""
Engine tests: route extension rules, collision, interference, scoring, determinism.
Uses small hand-crafted game states to test individual rules in isolation.
"""
import dataclasses

import numpy as np
import pytest

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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_card(card_id, card_type=CardType.ROUTE, in_ch="01", out_ch="02",
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
        # Manually place a seed and a route
        seed = make_card("SEED-0001", CardType.ROUTE, in_ch="01", out_ch="02", owner="P0")
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
        assert route.endpoint_card_id == "PKT-9001"

    def test_channel_mismatch_does_not_extend(self):
        engine = make_engine(n_policies=3)
        s = engine.state
        seed = make_card("SEED-0002", CardType.ROUTE, in_ch="01", out_ch="02", owner="P0")
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
        cfg = dataclasses.replace(GameConfig(), route_max_hops=3, player_count=3)
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


# ---------------------------------------------------------------------------
# ACK
# ---------------------------------------------------------------------------

class TestACK:
    def test_ack_wildcard_extends_any_route(self):
        engine = make_engine(n_policies=3)
        s = engine.state

        # Route ending on "03"
        c1 = make_card("PKT-ACK1", in_ch="01", out_ch="03", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)

        ack = Card(
            card_id="ACK-0001",
            card_type=CardType.ACK,
            input_channel="ANY",
            output_channel="TERM",
            packet_value=400,
            color="red",
            owner_id="P1",
        )
        s.register_card(ack)
        s.tableau.active_cards[ack.card_id] = ack
        engine._update_routes(ack)

        route = s.tableau.routes[0]
        assert route.termination_reason == TerminationReason.ACK
        assert route.endpoint_card_id == "ACK-0001"

    def test_ack_scores_if_min_length_met(self):
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("PKT-ACK2", in_ch="01", out_ch="02", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)

        ack = Card("ACK-0002", CardType.ACK, "ANY", "TERM", 400, "blue", owner_id="P1")
        s.register_card(ack)
        s.tableau.active_cards[ack.card_id] = ack
        engine._update_routes(ack)

        route = s.tableau.routes[0]
        assert route.length == 2
        assert route.is_scoring_candidate is True


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------

class TestBroadcast:
    def test_broadcast_multiplier_applied(self):
        cfg = dataclasses.replace(GameConfig(), broadcast_multiplier=3, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("PKT-BC1", in_ch="01", out_ch="02", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)

        bcst = Card(
            card_id="BCST-0001",
            card_type=CardType.BROADCAST,
            input_channel="02",
            output_channel="03",
            packet_value=200,
            color="red",
            owner_id="P1",
            special_properties=(("multiplier", 3),),
        )
        s.register_card(bcst)
        s.tableau.active_cards[bcst.card_id] = bcst
        engine._update_routes(bcst)

        route = s.tableau.routes[0]
        # Broadcast no longer terminates — route stays active, multiplier applies at scoring
        assert route.termination_reason == TerminationReason.ACTIVE
        assert route.endpoint_card_id == "BCST-0001"
        owner, score = engine._score_route(route)
        assert owner == "P1"
        assert score == 600  # 200 * 3


# ---------------------------------------------------------------------------
# Interference
# ---------------------------------------------------------------------------

class TestInterference:
    def test_interference_marks_channel(self):
        engine = make_engine(n_policies=3)
        s = engine.state
        engine._apply_interference("03")
        assert "03" in s.tableau.interfered_channels

    def test_interference_removes_cards_on_channel(self):
        # JAM only affects scoring-eligible routes (length >= route_min_length)
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("PKT-JAM1", in_ch="01", out_ch="02", owner="P0")
        c2 = make_card("PKT-JAM2", in_ch="02", out_ch="03", owner="P0")
        for c in (c1, c2):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
        engine._try_start_route(c1)
        engine._update_routes(c2)

        assert s.tableau.routes[0].length == 2

        engine._apply_interference("03")

        assert "PKT-JAM2" not in s.tableau.active_cards
        assert "PKT-JAM2" in s.tableau.collided_card_ids

    def test_interference_spares_short_routes(self):
        # Routes shorter than route_min_length are not affected by JAM
        cfg = dataclasses.replace(GameConfig(), route_min_length=2, player_count=3)
        engine = make_engine(config=cfg, n_policies=3)
        s = engine.state

        c1 = make_card("PKT-SHORT", in_ch="01", out_ch="03", owner="P0")
        s.register_card(c1)
        s.tableau.active_cards[c1.card_id] = c1
        engine._try_start_route(c1)

        assert s.tableau.routes[0].length == 1

        engine._apply_interference("03")

        # Card survives — route is length 1, below min_length
        assert "PKT-SHORT" in s.tableau.active_cards


# ---------------------------------------------------------------------------
# End-of-round scoring
# ---------------------------------------------------------------------------

class TestScoring:
    def test_endpoint_card_value_scores(self):
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
        assert route.endpoint_card_id == "PKT-SC2"

        # Only endpoint value counts
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
        # P1's endpoint, then verify first_player_index becomes 1 after scoring.
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

        # Route 1: P1 endpoint, value 300
        a1 = make_card("PKT-T1", in_ch="01", out_ch="02", value=100, owner="P0")
        a2 = make_card("PKT-T2", in_ch="02", out_ch="03", value=300, owner="P1")
        # Route 2: P2 endpoint, value 300 (tie)
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
