from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .models import (
    Card,
    CardType,
    GameState,
    PlacementContext,
    PlayerState,
    RouteState,
)


# ---------------------------------------------------------------------------
# Extended placement context (noise node needs a target channel)
# ---------------------------------------------------------------------------

@dataclass
class ExtendedPlacementContext(PlacementContext):
    target_channel: str | None = None


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class PlayerPolicy(ABC):
    name: str = "base"

    @abstractmethod
    def choose_play(
        self,
        state: GameState,
        player: PlayerState,
    ) -> tuple[Card, PlacementContext]:
        ...

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def legal_plays(
        self,
        state: GameState,
        player: PlayerState,
    ) -> list[tuple[Card, PlacementContext]]:
        plays: list[tuple[Card, PlacementContext]] = []
        tableau_ids = set(state.tableau.active_cards)

        open_routes = [r for r in state.tableau.routes if r.is_open()]

        for card in player.hand:
            if card.card_id in tableau_ids:
                continue
            if card.card_type == CardType.NOISE:
                scoring_card_ids: set[str] = set()
                for r in state.tableau.routes:
                    if r.is_valid and r.length >= state.config.route_min_length:
                        scoring_card_ids.update(r.card_ids)
                target_channels: set[str] = set()
                for cid in scoring_card_ids:
                    c = state.lookup_card(cid)
                    if c and c.output_channel and c.output_channel not in ("TERM",):
                        target_channels.add(c.output_channel)
                for ch in target_channels:
                    plays.append((card, ExtendedPlacementContext(target_channel=ch)))
            elif card.card_type == CardType.TERMINAL:
                for route in open_routes:
                    if route.length >= state.config.route_min_length:
                        ctx = PlacementContext(target_route_id=route.route_id)
                        plays.append((card, ctx))
            else:
                valid_route_count = sum(1 for r in state.tableau.routes if r.is_valid)
                cap_reached = valid_route_count >= state.config.seed_nodes_per_round
                extendable = [
                    r for r in open_routes
                    if self._can_card_extend_route(card, r, state)
                ]
                if extendable:
                    for route in extendable:
                        plays.append((card, PlacementContext(target_route_id=route.route_id)))
                elif not cap_reached:
                    plays.append((card, PlacementContext()))

        return plays if plays else self._fallback_play(state, player)

    def _fallback_play(
        self,
        state: GameState,
        player: PlayerState,
    ) -> list[tuple[Card, PlacementContext]]:
        if player.hand:
            return [(player.hand[0], PlacementContext(pass_turn=True))]
        raise RuntimeError(f"Player {player.player_id} has no cards to play")

    # ------------------------------------------------------------------
    # Shared estimation helpers
    # ------------------------------------------------------------------

    def _open_routes(self, state: GameState) -> list[RouteState]:
        return [r for r in state.tableau.routes if r.is_open()]

    def _can_card_extend_route(self, card: Card, route: RouteState, state: GameState) -> bool:
        cfg = state.config
        last_out = route.last_output_channel
        if last_out is None:
            return False
        if card.input_channel != "ANY" and card.input_channel != last_out:
            return False
        if cfg.no_loops and card.card_id in route.card_ids:
            return False
        if cfg.no_return_to_first_hop and route.first_input_channel is not None:
            if card.output_channel == route.first_input_channel:
                return False
        if card.output_channel and card.output_channel in route.channels_in_route:
            return False
        if route.length >= cfg.route_max_hops:
            return False
        if card.output_channel in state.tableau.noisy_channels:
            return False
        return True

    def _estimate_exit_node_value(
        self,
        card: Card,
        route: RouteState,
        state: GameState,
    ) -> float:
        cfg = state.config
        new_length = route.length + 1
        if new_length < cfg.route_min_length:
            return 0.0

        base = float(card.packet_value)
        if card.card_type == CardType.AMPLIFIER:
            base *= card.special("multiplier", cfg.amplifier_multiplier)
        if card.card_type == CardType.TERMINAL:
            # Terminal node ends the route; score is its own value
            pass
        return base

    def _route_exit_node_value(self, route: RouteState, state: GameState) -> float:
        if not route.exit_node_id:
            return 0.0
        card = state.lookup_card(route.exit_node_id)
        if card is None:
            return 0.0
        return float(card.packet_value)

    def _choose_random(
        self,
        plays: list[tuple[Card, PlacementContext]],
        state: GameState,
    ) -> tuple[Card, PlacementContext]:
        idx = int(state.rng.integers(len(plays)))
        return plays[idx]


# ---------------------------------------------------------------------------
# 1. RandomLegal
# ---------------------------------------------------------------------------

class RandomLegal(PlayerPolicy):
    name = "random_legal"

    def choose_play(self, state: GameState, player: PlayerState) -> tuple[Card, PlacementContext]:
        plays = self.legal_plays(state, player)
        return self._choose_random(plays, state)


# ---------------------------------------------------------------------------
# 2. GreedyExitNode
# ---------------------------------------------------------------------------

class GreedyExitNode(PlayerPolicy):
    name = "greedy_exit_node"

    def choose_play(self, state: GameState, player: PlayerState) -> tuple[Card, PlacementContext]:
        plays = self.legal_plays(state, player)
        open_routes = self._open_routes(state)

        best_score = -1.0
        best_plays: list[tuple[Card, PlacementContext]] = []

        for card, ctx in plays:
            score = 0.0
            if card.card_type == CardType.NOISE:
                pass  # noise never scores directly
            elif card.card_type in (CardType.TERMINAL, CardType.AMPLIFIER):
                for route in open_routes:
                    if self._can_card_extend_route(card, route, state):
                        v = self._estimate_exit_node_value(card, route, state)
                        if v > score:
                            score = v
                            ctx = PlacementContext(target_route_id=route.route_id)
            else:
                for route in open_routes:
                    if self._can_card_extend_route(card, route, state):
                        v = self._estimate_exit_node_value(card, route, state)
                        if v > score:
                            score = v
                            ctx = PlacementContext(target_route_id=route.route_id)

            if score > best_score:
                best_score = score
                best_plays = [(card, ctx)]
            elif score == best_score:
                best_plays.append((card, ctx))

        if best_plays:
            return self._choose_random(best_plays, state)
        return self._choose_random(plays, state)


# ---------------------------------------------------------------------------
# 3. DenialCollision
# ---------------------------------------------------------------------------

class DenialCollision(PlayerPolicy):
    name = "denial_collision"

    _threshold: float = 50.0  # denial value must exceed self-gain by this much

    def choose_play(self, state: GameState, player: PlayerState) -> tuple[Card, PlacementContext]:
        plays = self.legal_plays(state, player)

        target_route, denial_value = self._best_opponent_route(state, player)

        if target_route is not None and denial_value >= self._threshold:
            denial_play = self._find_denial_play(state, player, target_route, plays)
            if denial_play is not None:
                return denial_play

        # Fall back to greedy
        return GreedyExitNode().choose_play(state, player)

    def _best_opponent_route(
        self,
        state: GameState,
        player: PlayerState,
    ) -> tuple[RouteState | None, float]:
        best_route = None
        best_value = 0.0
        open_routes = self._open_routes(state)
        for route in open_routes:
            if not route.owner_sequence:
                continue
            last_owner = route.owner_sequence[-1]
            if last_owner == player.player_id:
                continue
            val = self._route_exit_node_value(route, state)
            if val > best_value:
                best_value = val
                best_route = route
        return best_route, best_value

    def _find_denial_play(
        self,
        state: GameState,
        player: PlayerState,
        target_route: RouteState,
        plays: list[tuple[Card, PlacementContext]],
    ) -> tuple[Card, PlacementContext] | None:
        # Prefer noise on the target route's output channel
        last_out = target_route.last_output_channel
        if last_out:
            for card, ctx in plays:
                if card.card_type == CardType.NOISE:
                    noise_ctx = ExtendedPlacementContext(target_channel=last_out)
                    return card, noise_ctx

        # Fallback: terminate the route to steal its score before the opponent can claim it
        if target_route.length >= state.config.route_min_length:
            for card, ctx in plays:
                if card.card_type == CardType.TERMINAL:
                    return card, PlacementContext(target_route_id=target_route.route_id)

        return None


# ---------------------------------------------------------------------------
# 4. RouteBuilder
# ---------------------------------------------------------------------------

class RouteBuilder(PlayerPolicy):
    name = "route_builder"

    def choose_play(self, state: GameState, player: PlayerState) -> tuple[Card, PlacementContext]:
        plays = self.legal_plays(state, player)
        open_routes = self._open_routes(state)
        cfg = state.config

        # 1. Complete a route (play exit node on route at min_length - 1)
        for card, ctx in plays:
            if card.card_type in (CardType.TERMINAL, CardType.AMPLIFIER):
                for route in open_routes:
                    if route.length >= cfg.route_min_length - 1:
                        if self._can_card_extend_route(card, route, state):
                            return card, PlacementContext(target_route_id=route.route_id)

        # 2. Extend route anchored on a seed node
        seed_node_ids = {c.card_id for c in state.tableau.seed_nodes}
        for card, ctx in plays:
            if card.card_type in (CardType.TERMINAL, CardType.NOISE):
                continue
            for route in open_routes:
                if route.card_ids and route.card_ids[0] in seed_node_ids:
                    if self._can_card_extend_route(card, route, state):
                        return card, PlacementContext(target_route_id=route.route_id)

        # 3. Extend any valid route
        for card, ctx in plays:
            if card.card_type in (CardType.TERMINAL, CardType.NOISE):
                continue
            for route in open_routes:
                if self._can_card_extend_route(card, route, state):
                    # Prefer routes not in noisy channels
                    if card.output_channel not in state.tableau.noisy_channels:
                        return card, PlacementContext(target_route_id=route.route_id)

        # 4. Start a new route anchored to seed node (play onto a free seed channel)
        for card, ctx in plays:
            if card.card_type in (CardType.TERMINAL, CardType.NOISE):
                continue
            for seed in state.tableau.seed_nodes:
                if card.input_channel == seed.output_channel:
                    if card.output_channel not in state.tableau.noisy_channels:
                        return card, PlacementContext()

        # 5. Random fallback
        return self._choose_random(plays, state)

    def _color_preference_score(
        self, card: Card, route: RouteState, state: GameState
    ) -> float:
        return 0.0
