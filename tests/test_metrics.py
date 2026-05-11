from packet_pressure.config_presets import FAST_CONFIG
from packet_pressure.metrics import GameMetrics, MetricsCollector
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
            "broadcast_score_rate",
            "ack_steal_rate",
            "seed_utilization_rate",
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
