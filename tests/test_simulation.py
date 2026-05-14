import dataclasses
import pytest

from packet_pressure.config_presets import DEFAULT_CONFIG, FAST_CONFIG
from packet_pressure.models import GameConfig
from packet_pressure.policies import GreedyExitNode, RandomLegal, RouteBuilder
from packet_pressure.simulation import run_batch, run_simulation, sweep_parameter


def default_policies(n=4):
    return [RandomLegal()] * n


class TestRunSimulation:
    def test_returns_game_metrics(self):
        from packet_pressure.metrics import GameMetrics
        m = run_simulation(FAST_CONFIG, [RandomLegal()] * 3, seed=1)
        assert isinstance(m, GameMetrics)
        assert m.total_rounds_played >= 1
        assert m.winner is not None

    def test_deterministic(self):
        p = [RandomLegal()] * 3
        m1 = run_simulation(FAST_CONFIG, p, seed=55)
        m2 = run_simulation(FAST_CONFIG, p, seed=55)
        assert m1.winner == m2.winner
        assert m1.final_scores == m2.final_scores

    def test_different_seeds_vary(self):
        p = [RandomLegal()] * 3
        results = [run_simulation(FAST_CONFIG, p, seed=s) for s in range(20)]
        winners = [r.winner for r in results]
        assert len(set(winners)) > 1


class TestRunBatch:
    def test_batch_length(self):
        batch = run_batch(FAST_CONFIG, [RandomLegal()] * 3, n_games=10, seed=0)
        assert len(batch.games) == 10

    def test_batch_win_rates_sum_near_one(self):
        policies = [RandomLegal(), GreedyExitNode(), RouteBuilder()]
        batch = run_batch(FAST_CONFIG, policies, n_games=30, seed=7)
        total = sum(batch.win_rates.values())
        assert abs(total - 1.0) < 0.01

    def test_batch_deterministic(self):
        p = [RandomLegal()] * 3
        b1 = run_batch(FAST_CONFIG, p, n_games=5, seed=123)
        b2 = run_batch(FAST_CONFIG, p, n_games=5, seed=123)
        for m1, m2 in zip(b1.games, b2.games):
            assert m1.winner == m2.winner
            assert m1.final_scores == m2.final_scores


class TestSweepParameter:
    def test_sweep_returns_correct_count(self):
        results = sweep_parameter(
            FAST_CONFIG, "route_min_length", [2, 3], [RandomLegal()] * 3, n_games=5, seed=0
        )
        assert len(results) == 2

    def test_sweep_uses_correct_config(self):
        results = sweep_parameter(
            FAST_CONFIG, "seed_nodes_per_round", [1, 2], [RandomLegal()] * 3, n_games=5, seed=0
        )
        assert results[0].config.seed_nodes_per_round == 1
        assert results[1].config.seed_nodes_per_round == 2

    def test_sweep_invalid_param_raises(self):
        with pytest.raises(ValueError, match="not a valid GameConfig field"):
            sweep_parameter(
                FAST_CONFIG, "nonexistent_field", [1, 2],
                [RandomLegal()] * 3, n_games=5, seed=0
            )

    def test_base_config_unchanged_after_sweep(self):
        original_min = FAST_CONFIG.route_min_length
        sweep_parameter(
            FAST_CONFIG, "route_min_length", [1, 4], [RandomLegal()] * 3, n_games=3, seed=0
        )
        assert FAST_CONFIG.route_min_length == original_min
