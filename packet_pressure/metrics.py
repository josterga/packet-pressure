from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .models import (
    EVT_CARD_PLAYED,
    EVT_COLLISION,
    EVT_INTERFERENCE_APPLIED,
    EVT_ROUND_END,
    EVT_ROUND_START,
    EVT_ROUTE_EXTENDED,
    EVT_ROUTE_INVALIDATED,
    EVT_ROUTE_STARTED,
    EVT_ROUTE_TERMINATED,
    EVT_SCORE_AWARDED,
    CardType,
    GameConfig,
    GameState,
    TerminationReason,
)


@dataclass
class GameMetrics:
    game_seed: int
    policy_names: list[str]
    config_summary: dict

    total_rounds_played: int
    winner: str | None
    final_scores: dict[str, int]

    avg_score_per_round: float
    score_distribution_by_position: dict[int, float]

    scoring_routes_count: int
    avg_route_length: float
    route_length_histogram: dict[int, int]
    pct_routes_stopped_by_hop_limit: float
    pct_invalid_loop_attempts: float
    pct_endpoint_return_attempts: float

    collision_count_per_round: float
    collision_count_by_channel: dict[str, int]
    interference_plays: int
    ack_plays: int
    broadcast_plays: int

    broadcast_score_rate: float
    ack_steal_rate: float

    seed_utilization_rate: float
    dead_rounds_count: int
    turn_pct_extending_vs_starting: float

    avg_legal_moves_per_turn: float = 0.0


@dataclass
class BatchResult:
    config: GameConfig
    policy_names: list[str]
    n_games: int
    games: list[GameMetrics]

    win_rates: dict[str, float] = field(default_factory=dict)
    avg_final_scores: dict[str, float] = field(default_factory=dict)
    score_variance: dict[str, float] = field(default_factory=dict)
    avg_total_rounds: float = 0.0
    collision_avg: float = 0.0
    route_length_avg: float = 0.0
    dead_round_rate: float = 0.0
    avg_scoring_routes: float = 0.0
    avg_legal_moves_per_turn: float = 0.0

    def __post_init__(self) -> None:
        self._aggregate()

    def _aggregate(self) -> None:
        if not self.games:
            return

        n = len(self.games)
        win_counts: dict[str, int] = defaultdict(int)
        scores_by_policy: dict[str, list[float]] = defaultdict(list)

        for gm in self.games:
            if gm.winner is not None:
                # Map player_id winner back to policy name via position
                try:
                    pos = list(gm.final_scores.keys()).index(gm.winner)
                    winning_policy = gm.policy_names[pos]
                    win_counts[winning_policy] += 1
                except (ValueError, IndexError):
                    win_counts[gm.winner] += 1
            for policy_name, score in zip(gm.policy_names, gm.final_scores.values()):
                scores_by_policy[policy_name].append(float(score))

        for policy in self.policy_names:
            self.win_rates[policy] = win_counts.get(policy, 0) / n

        for policy, scores in scores_by_policy.items():
            self.avg_final_scores[policy] = sum(scores) / len(scores)
            mean = sum(scores) / len(scores)
            self.score_variance[policy] = sum((s - mean) ** 2 for s in scores) / len(scores)

        self.avg_total_rounds = sum(gm.total_rounds_played for gm in self.games) / n
        self.collision_avg = sum(gm.collision_count_per_round for gm in self.games) / n
        self.route_length_avg = sum(gm.avg_route_length for gm in self.games) / n
        self.dead_round_rate = sum(gm.dead_rounds_count for gm in self.games) / (
            sum(gm.total_rounds_played for gm in self.games) or 1
        )
        self.avg_scoring_routes = sum(gm.scoring_routes_count for gm in self.games) / n
        self.avg_legal_moves_per_turn = sum(gm.avg_legal_moves_per_turn for gm in self.games) / n


class MetricsCollector:
    def __init__(self, state: GameState, game_seed: int) -> None:
        self.state = state
        self.game_seed = game_seed

    def collect(self) -> GameMetrics:
        s = self.state
        cfg = s.config
        events = self._parse_events()

        # Basic game info
        winner = self._find_winner(events)
        final_scores = {p.player_id: p.score for p in s.players}
        total_rounds = s.round_number

        # Scoring
        score_events = events.get(EVT_SCORE_AWARDED, [])
        total_score = sum(e.get("score", 0) for e in score_events)
        avg_score_per_round = total_score / total_rounds if total_rounds else 0.0

        score_by_pos = {i: float(p.score) for i, p in enumerate(s.players)}

        # Route metrics
        route_metrics = self._compute_route_metrics(events)

        # Collision
        collision_events = events.get(EVT_COLLISION, [])
        collision_by_ch: dict[str, int] = defaultdict(int)
        for e in collision_events:
            ch = e.get("channel", "?")
            collision_by_ch[ch] += 1
        collision_count_per_round = len(collision_events) / total_rounds if total_rounds else 0.0

        # Special card plays
        play_events = events.get(EVT_CARD_PLAYED, [])
        legal_counts = [e["legal_move_count"] for e in play_events if "legal_move_count" in e]
        avg_legal_moves = sum(legal_counts) / len(legal_counts) if legal_counts else 0.0
        ack_plays = sum(1 for e in play_events if e.get("card_type") == CardType.ACK.value)
        broadcast_plays = sum(1 for e in play_events if e.get("card_type") == CardType.BROADCAST.value)
        interference_plays = sum(1 for e in play_events if e.get("card_type") == CardType.INTERFERENCE.value)

        # Broadcast score rate
        term_events = events.get(EVT_ROUTE_TERMINATED, [])
        broadcast_terms = [e for e in term_events if e.get("reason") == "broadcast"]
        broadcast_score_rate = (
            sum(1 for e in broadcast_terms if e.get("scoring")) / broadcast_plays
            if broadcast_plays else 0.0
        )

        # ACK steal rate (ack terminated a route it didn't start)
        ack_terms = [e for e in term_events if e.get("reason") == "ack"]
        ack_steals = 0
        for e in ack_terms:
            route_id = e.get("route_id")
            route = next((r for r in s.tableau.routes if r.route_id == route_id), None)
            if route and route.owner_sequence and len(set(route.owner_sequence)) > 1:
                ack_steals += 1
        ack_steal_rate = ack_steals / ack_plays if ack_plays else 0.0

        # Seed utilization
        seed_in_routes = route_metrics.get("seed_in_scored_routes", 0)
        total_seeds = cfg.seed_cards_per_round * total_rounds
        seed_utilization_rate = seed_in_routes / total_seeds if total_seeds else 0.0

        # Dead rounds (rounds with no scoring routes)
        scored_rounds = len({e.get("round") for e in score_events})
        dead_rounds = total_rounds - scored_rounds

        # Turn extending vs starting
        extend_events = events.get(EVT_ROUTE_EXTENDED, [])
        start_events = events.get(EVT_ROUTE_STARTED, [])
        total_route_events = len(extend_events) + len(start_events)
        turn_pct = len(extend_events) / total_route_events if total_route_events else 0.0

        return GameMetrics(
            game_seed=self.game_seed,
            policy_names=[p.policy_name for p in s.players],
            config_summary={
                "player_count": cfg.player_count,
                "route_min_length": cfg.route_min_length,
                "route_max_hops": cfg.route_max_hops,
            },
            total_rounds_played=total_rounds,
            winner=winner,
            final_scores=final_scores,
            avg_score_per_round=avg_score_per_round,
            score_distribution_by_position=score_by_pos,
            scoring_routes_count=len(score_events),
            avg_route_length=route_metrics.get("avg_length", 0.0),
            route_length_histogram=route_metrics.get("length_histogram", {}),
            pct_routes_stopped_by_hop_limit=route_metrics.get("pct_hop_limit", 0.0),
            pct_invalid_loop_attempts=route_metrics.get("pct_loop", 0.0),
            pct_endpoint_return_attempts=route_metrics.get("pct_return_first", 0.0),
            collision_count_per_round=collision_count_per_round,
            collision_count_by_channel=dict(collision_by_ch),
            interference_plays=interference_plays,
            ack_plays=ack_plays,
            broadcast_plays=broadcast_plays,
            broadcast_score_rate=broadcast_score_rate,
            ack_steal_rate=ack_steal_rate,
            seed_utilization_rate=seed_utilization_rate,
            dead_rounds_count=dead_rounds,
            turn_pct_extending_vs_starting=turn_pct,
            avg_legal_moves_per_turn=avg_legal_moves,
        )

    def _parse_events(self) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for e in self.state.event_log:
            grouped[e["event"]].append(e)
        return dict(grouped)

    def _find_winner(self, events: dict[str, list[dict]]) -> str | None:
        players_by_score = sorted(
            self.state.players, key=lambda p: p.score, reverse=True
        )
        if not players_by_score:
            return None
        top = players_by_score[0]
        # Check if score target was reached
        if top.score >= self.state.config.score_to_win:
            return top.player_id
        # If max_rounds hit, highest score wins
        return top.player_id if self.state.round_number >= self.state.config.max_rounds else None

    def _compute_route_metrics(self, events: dict[str, list[dict]]) -> dict:
        term_events = events.get(EVT_ROUTE_TERMINATED, [])
        invalidated_events = events.get(EVT_ROUTE_INVALIDATED, [])
        score_events = events.get(EVT_SCORE_AWARDED, [])

        all_route_lengths: list[int] = []
        hop_limit_count = 0
        loop_count = 0
        return_first_count = 0

        for e in term_events:
            reason = e.get("reason", "")
            if reason == "hop_limit":
                hop_limit_count += 1

        for e in invalidated_events:
            reason = e.get("reason", "")
            if reason == "loop_detected":
                loop_count += 1
            elif reason == "return_to_first_hop":
                return_first_count += 1

        # Route lengths are stored directly in SCORE_AWARDED events (routes are discarded each round)
        for e in score_events:
            length = e.get("route_length")
            if length is not None:
                all_route_lengths.append(int(length))

        total_term = len(term_events) or 1
        total_inval = len(invalidated_events) or 1

        length_histogram: dict[int, int] = defaultdict(int)
        for length in all_route_lengths:
            length_histogram[length] += 1

        avg_length = sum(all_route_lengths) / len(all_route_lengths) if all_route_lengths else 0.0

        return {
            "avg_length": avg_length,
            "length_histogram": dict(length_histogram),
            "pct_hop_limit": hop_limit_count / total_term,
            "pct_loop": loop_count / total_inval,
            "pct_return_first": return_first_count / total_inval,
            "seed_in_scored_routes": 0,  # simplified; full tracking would need card registry
        }
