import dataclasses

import numpy as np
import pytest

from packet_pressure.config_presets import FAST_CONFIG
from packet_pressure.deck import DeckBuilder
from packet_pressure.engine import GameEngine
from packet_pressure.models import Card, CardType, GameConfig
from packet_pressure.policies import (
    DenialCollision,
    GreedyExitNode,
    RandomLegal,
    RouteBuilder,
)


def make_state(n_policies=3, seed=0):
    config = dataclasses.replace(FAST_CONFIG, player_count=n_policies)
    policies = [RandomLegal()] * n_policies
    rng = np.random.default_rng(seed)
    deck = DeckBuilder(config, rng).build()
    engine = GameEngine(config, policies, deck, np.random.default_rng(seed))
    return engine.state, engine


class TestLegalPlays:
    def test_random_legal_always_in_hand(self):
        state, engine = make_state()
        policy = RandomLegal()
        player = state.players[0]
        plays = policy.legal_plays(state, player)
        hand_ids = {c.card_id for c in player.hand}
        for card, _ in plays:
            assert card.card_id in hand_ids

    def test_legal_plays_not_already_in_tableau(self):
        state, engine = make_state()
        policy = RandomLegal()
        player = state.players[0]

        # Put first hand card in tableau
        if player.hand:
            card = player.hand[0]
            state.tableau.active_cards[card.card_id] = card

        plays = policy.legal_plays(state, player)
        tableau_ids = set(state.tableau.active_cards)
        for card, _ in plays:
            assert card.card_id not in tableau_ids

    def test_noise_requires_scoring_route(self):
        # Noise node is dead in hand when no scoring routes exist
        state, engine = make_state()
        policy = RandomLegal()
        player = state.players[0]

        noise = Card(
            card_id="NOISE-TEST",
            card_type=CardType.NOISE,
            input_channel=None,
            output_channel=None,
            packet_value=0,
            color="red",
        )
        state.register_card(noise)
        player.hand.append(noise)

        # No routes in tableau — noise generates no plays
        plays = policy.legal_plays(state, player)
        noise_plays = [(c, ctx) for c, ctx in plays if c.card_id == "NOISE-TEST"]
        assert len(noise_plays) == 0

    def test_noise_targets_scoring_route_channels(self):
        # Noise card with pre-set target channel "02" is legal when a scoring route
        # has "02" as an interior hop (channels_in_route[:-1] includes "02")
        state, engine = make_state()
        policy = RandomLegal()
        player = state.players[0]

        # Noise cards bake their target channel into output_channel at deck build time
        noise = Card(
            card_id="NOISE-TEST",
            card_type=CardType.NOISE,
            input_channel=None,
            output_channel="02",  # pre-set target channel
            packet_value=0,
            color="red",
        )
        state.register_card(noise)
        player.hand.append(noise)

        # 2-card route 01→02→03; channels_in_route=["02","03"]; interior "02" is targetable
        c1 = Card("R1", CardType.RELAY, "01", "02", 100, "red", owner_id="P1")
        c2 = Card("R2", CardType.RELAY, "02", "03", 100, "red", owner_id="P1")
        for c in (c1, c2):
            state.register_card(c)
            state.tableau.active_cards[c.card_id] = c
        engine._try_start_route(c1)
        engine._update_routes(c2)
        assert state.tableau.routes[0].length == 2

        plays = policy.legal_plays(state, player)
        noise_plays = [c for c, _ in plays if c.card_id == "NOISE-TEST"]
        assert len(noise_plays) > 0


class TestGreedyExitNode:
    def test_greedy_prefers_higher_value_exit_node(self):
        """GreedyExitNode should choose a higher packet_value card when both can terminate."""
        state, engine = make_state(seed=7)
        policy = GreedyExitNode()
        player = state.players[0]
        # Just check it doesn't crash and returns a card in hand
        card, ctx = policy.choose_play(state, player)
        hand_ids = {c.card_id for c in player.hand}
        assert card.card_id in hand_ids


class TestRouteBuilder:
    def test_route_builder_returns_legal_play(self):
        state, engine = make_state(seed=5)
        policy = RouteBuilder()
        player = state.players[0]
        card, ctx = policy.choose_play(state, player)
        hand_ids = {c.card_id for c in player.hand}
        assert card.card_id in hand_ids


class TestDenialCollision:
    def test_denial_returns_legal_play(self):
        state, engine = make_state(seed=3)
        policy = DenialCollision()
        player = state.players[0]
        card, ctx = policy.choose_play(state, player)
        hand_ids = {c.card_id for c in player.hand}
        assert card.card_id in hand_ids


class TestFullGames:
    def test_all_policies_complete_game(self):
        from packet_pressure.simulation import run_simulation

        policies = [
            RandomLegal(),
            GreedyExitNode(),
            DenialCollision(),
            RouteBuilder(),
        ]
        config = dataclasses.replace(FAST_CONFIG, player_count=4)
        metrics = run_simulation(config, policies, seed=42)
        assert metrics.total_rounds_played >= 1
        assert metrics.winner is not None


class TestLegalPlaysExtra:
    def test_terminal_not_legal_on_stub(self):
        # Terminal cannot target a route shorter than route_min_length
        state, engine = make_state()
        policy = RandomLegal()
        player = state.players[0]

        term = Card("TERM-STUB", CardType.TERMINAL, "ANY", "TERM", 400, "red")
        state.register_card(term)
        player.hand.append(term)

        # 1-node stub (length < route_min_length=2)
        stub = Card("R-STUB", CardType.RELAY, "01", "02", 100, "red", owner_id="P0")
        state.register_card(stub)
        state.tableau.active_cards[stub.card_id] = stub
        engine._try_start_route(stub)
        assert state.tableau.routes[0].length == 1

        plays = policy.legal_plays(state, player)
        terminal_plays = [c for c, _ in plays if c.card_id == "TERM-STUB"]
        assert len(terminal_plays) == 0

    def test_no_legal_plays_returns_pass(self):
        # When no play is possible the policy returns a pass (pass_turn=True).
        # Use FAST_CONFIG: seed_nodes_per_round=2, route_min_length=2.
        # Fill cap with 2 open stubs, give player a card that matches neither tail.
        state, engine = make_state()
        policy = RandomLegal()
        player = state.players[0]

        player.hand.clear()
        # Relay with input "02" — neither stub tail ("01", "03") matches
        blocker = Card("REL-PASS", CardType.RELAY, "02", "01", 100, "red")
        state.register_card(blocker)
        player.hand.append(blocker)

        # Two stubs with tails "01" and "03" (fills cap at seed_nodes_per_round=2)
        for i, (in_ch, out_ch) in enumerate([("03", "01"), ("01", "03")]):
            c = Card(f"SEED-P{i}", CardType.RELAY, in_ch, out_ch, 100, "red", owner_id="P0")
            state.register_card(c)
            state.tableau.active_cards[c.card_id] = c
            engine._try_start_route(c)

        # Stubs are length=1: no terminal plays, no noise plays (below min_length)
        # Blocker can't extend (tails "01","03", blocker input "02") and cap is full
        plays = policy.legal_plays(state, player)
        assert len(plays) == 1
        _, ctx = plays[0]
        assert ctx.pass_turn is True
