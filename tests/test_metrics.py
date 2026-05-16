import dataclasses
import numpy as np

from packet_pressure.config_presets import FAST_CONFIG
from packet_pressure.deck import DeckBuilder
from packet_pressure.engine import GameEngine
from packet_pressure.metrics import GameMetrics, MetricsCollector
from packet_pressure.models import Card, CardType, EVT_CARD_PLAYED, GameConfig
from packet_pressure.policies import RandomLegal
from packet_pressure.simulation import run_simulation


class TestMetricsCollector:
    def _get_metrics(self, seed=42):
        return run_simulation(FAST_CONFIG, [RandomLegal()] * 3, seed=seed)

    def test_returns_game_metrics_instance(self):
        m = self._get_metrics()
        assert isinstance(m, GameMetrics)

    def test_final_scores_are_nonnegative(self):
        m = self._get_metrics()
        for score in m.final_scores.values():
            assert score >= 0

    def test_player_count_matches_config(self):
        m = self._get_metrics()
        assert len(m.final_scores) == FAST_CONFIG.player_count

    def test_winner_is_valid_player(self):
        m = self._get_metrics()
        assert m.winner in m.final_scores or m.winner is None

    def test_route_length_nonnegative(self):
        m = self._get_metrics()
        assert m.avg_route_length >= 0

    def test_rates_between_0_and_1(self):
        m = self._get_metrics()
        for field_name in (
            "pct_routes_stopped_by_hop_limit",
            "amplifier_score_rate",
            "terminal_steal_rate",
            "seed_node_utilization_rate",
            "turn_pct_extending_vs_starting",
        ):
            val = getattr(m, field_name)
            assert 0.0 <= val <= 1.0, f"{field_name} = {val} out of [0,1]"

    def test_policy_names_recorded(self):
        m = self._get_metrics()
        assert len(m.policy_names) == 3
        assert all(n == "random_legal" for n in m.policy_names)

    def test_total_rounds_within_max(self):
        m = self._get_metrics()
        assert 1 <= m.total_rounds_played <= FAST_CONFIG.max_rounds


def _make_engine(config=None, n=3):
    config = config or dataclasses.replace(GameConfig(), player_count=n)
    policies = [RandomLegal()] * n
    rng = np.random.default_rng(0)
    return GameEngine(config, policies, DeckBuilder(config, rng).build(), np.random.default_rng(0))


def _log_card_played(s, card):
    """Simulate the EVT_CARD_PLAYED log entry that _apply_play() would emit."""
    s.log(EVT_CARD_PLAYED, card_id=card.card_id, card_type=card.card_type.value,
          player_id=card.owner_id or "", legal_move_count=0)


class TestAmplifierScoreRate:
    def test_nonzero_when_amplifier_is_exit_node_at_scoring(self):
        # Build a 2-hop route where the amplifier IS the exit node at end-of-round
        # scoring. amplifier_score_rate must be > 0.
        cfg = dataclasses.replace(GameConfig(), player_count=3, route_min_length=2,
                                  amplifier_multiplier=2)
        engine = _make_engine(cfg, n=3)
        s = engine.state

        relay = Card("M-R1", CardType.RELAY, "01", "02", 100, "red", owner_id="P0")
        amp = Card("M-AMP1", CardType.AMPLIFIER, "02", "03", 200, "red",
                   owner_id="P1", special_properties=(("multiplier", 2),))
        for c in (relay, amp):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
            _log_card_played(s, c)
        engine._try_start_route(relay)
        engine._update_routes(amp)

        assert s.tableau.routes[0].exit_node_id == "M-AMP1"
        engine._end_of_round_scoring()

        collector = MetricsCollector(s, game_seed=0)
        m = collector.collect()
        assert m.amplifier_plays == 1
        assert m.amplifier_score_rate > 0.0

    def test_zero_when_amplifier_not_exit_node(self):
        # Amplifier is extended past — it's no longer the exit node, so it should
        # not count toward amplifier_score_rate.
        cfg = dataclasses.replace(GameConfig(), player_count=3, route_min_length=2,
                                  amplifier_multiplier=2)
        engine = _make_engine(cfg, n=3)
        s = engine.state

        relay = Card("M-R2", CardType.RELAY, "01", "02", 100, "red", owner_id="P0")
        amp = Card("M-AMP2", CardType.AMPLIFIER, "02", "03", 200, "red",
                   owner_id="P1", special_properties=(("multiplier", 2),))
        ext = Card("M-R3", CardType.RELAY, "03", "04", 150, "red", owner_id="P2")
        for c in (relay, amp, ext):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
            _log_card_played(s, c)
        engine._try_start_route(relay)
        engine._update_routes(amp)
        engine._update_routes(ext)

        assert s.tableau.routes[0].exit_node_id == "M-R3"
        engine._end_of_round_scoring()

        collector = MetricsCollector(s, game_seed=0)
        m = collector.collect()
        assert m.amplifier_plays == 1
        assert m.amplifier_score_rate == 0.0


class TestTerminalStealRate:
    def test_nonzero_when_terminal_closes_multi_owner_route(self):
        # P0 starts the route, P1 plays the terminal — owner_sequence has 2 distinct
        # owners, so this is a steal. terminal_steal_rate must be > 0.
        cfg = dataclasses.replace(GameConfig(), player_count=3, route_min_length=2)
        engine = _make_engine(cfg, n=3)
        s = engine.state

        relay = Card("ST-R1", CardType.RELAY, "01", "02", 100, "red", owner_id="P0")
        term = Card("ST-T1", CardType.TERMINAL, "ANY", "TERM", 400, "red", owner_id="P1")
        for c in (relay, term):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
            _log_card_played(s, c)
        engine._try_start_route(relay)
        engine._update_routes(term)

        route = s.tableau.routes[0]
        assert route.termination_reason.value == "terminal"
        assert len(set(route.owner_sequence)) == 2

        engine._end_of_round_scoring()
        collector = MetricsCollector(s, game_seed=0)
        m = collector.collect()
        assert m.terminal_plays == 1
        assert m.terminal_steal_rate > 0.0

    def test_zero_when_terminal_closes_single_owner_route(self):
        # P0 owns every card including the terminal — not a steal.
        cfg = dataclasses.replace(GameConfig(), player_count=3, route_min_length=2)
        engine = _make_engine(cfg, n=3)
        s = engine.state

        relay = Card("ST-R2", CardType.RELAY, "01", "02", 100, "red", owner_id="P0")
        term = Card("ST-T2", CardType.TERMINAL, "ANY", "TERM", 400, "red", owner_id="P0")
        for c in (relay, term):
            s.register_card(c)
            s.tableau.active_cards[c.card_id] = c
            _log_card_played(s, c)
        engine._try_start_route(relay)
        engine._update_routes(term)

        engine._end_of_round_scoring()
        collector = MetricsCollector(s, game_seed=0)
        m = collector.collect()
        assert m.terminal_plays == 1
        assert m.terminal_steal_rate == 0.0
