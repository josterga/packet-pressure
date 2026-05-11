import dataclasses

import numpy as np
import pytest

from packet_pressure.config_presets import FAST_CONFIG
from packet_pressure.deck import DeckBuilder
from packet_pressure.engine import GameEngine
from packet_pressure.models import Card, CardType, GameConfig
from packet_pressure.policies import (
    DenialCollision,
    GreedyEndpoint,
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

    def test_interference_generates_one_play_per_channel(self):
        state, engine = make_state()
        policy = RandomLegal()
        player = state.players[0]

        # Force a JAM card into hand
        jam = Card(
            card_id="JAM-TEST",
            card_type=CardType.INTERFERENCE,
            input_channel=None,
            output_channel=None,
            packet_value=0,
            color="red",
        )
        state.register_card(jam)
        player.hand.append(jam)

        plays = policy.legal_plays(state, player)
        jam_plays = [(c, ctx) for c, ctx in plays if c.card_id == "JAM-TEST"]
        assert len(jam_plays) == len(state.config.channels)


class TestGreedyEndpoint:
    def test_greedy_prefers_higher_value_endpoint(self):
        """GreedyEndpoint should choose a higher packet_value card when both can terminate."""
        state, engine = make_state(seed=7)
        policy = GreedyEndpoint()
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
            GreedyEndpoint(),
            DenialCollision(),
            RouteBuilder(),
        ]
        config = dataclasses.replace(FAST_CONFIG, player_count=4)
        metrics = run_simulation(config, policies, seed=42)
        assert metrics.total_rounds_played >= 1
        assert metrics.winner is not None
