from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .models import (
    Card,
    CardType,
    ColorMode,
    GameState,
    PlacementContext,
    PlayerState,
    RouteState,
)


# ---------------------------------------------------------------------------
# Extended placement context (interference needs a target channel)
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
            if card.card_type == CardType.INTERFERENCE:
                for ch in state.config.channels:
                    ctx = ExtendedPlacementContext(target_channel=ch)
                    plays.append((card, ctx))
            elif card.card_type == CardType.ACK:
                if open_routes:
                    for route in open_routes:
                        ctx = PlacementContext(target_route_id=route.route_id)
                        plays.append((card, ctx))
                else:
                    plays.append((card, PlacementContext()))
            else:
                ctx = PlacementContext()
                plays.append((card, ctx))

        return plays if plays else self._fallback_play(state, player)

    def _fallback_play(
        self,
        state: GameState,
        player: PlayerState,
    ) -> list[tuple[Card, PlacementContext]]:
        # If somehow no legal plays (shouldn't normally happen), return first card with null ctx
        if player.hand:
            return [(player.hand[0], PlacementContext())]
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
        if route.length >= cfg.route_max_hops:
            return False
        if card.output_channel in state.tableau.interfered_channels:
            return False
        return True

    def _estimate_endpoint_value(
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
        if card.card_type == CardType.BROADCAST:
            base *= card.special("multiplier", cfg.broadcast_multiplier)
        if card.card_type == CardType.ACK:
            # ACK ends the route; score is its own value
            pass
        return base

    def _route_endpoint_value(self, route: RouteState, state: GameState) -> float:
        if not route.endpoint_card_id:
            return 0.0
        card = state.lookup_card(route.endpoint_card_id)
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
# 2. GreedyEndpoint
# ---------------------------------------------------------------------------

class GreedyEndpoint(PlayerPolicy):
    name = "greedy_endpoint"

    def choose_play(self, state: GameState, player: PlayerState) -> tuple[Card, PlacementContext]:
        plays = self.legal_plays(state, player)
        open_routes = self._open_routes(state)

        best_score = -1.0
        best_plays: list[tuple[Card, PlacementContext]] = []

        for card, ctx in plays:
            score = 0.0
            if card.card_type == CardType.INTERFERENCE:
                pass  # interference never scores directly
            elif card.card_type in (CardType.ACK, CardType.BROADCAST):
                for route in open_routes:
                    if self._can_card_extend_route(card, route, state):
                        v = self._estimate_endpoint_value(card, route, state)
                        if v > score:
                            score = v
                            ctx = PlacementContext(target_route_id=route.route_id)
            else:
                for route in open_routes:
                    if self._can_card_extend_route(card, route, state):
                        v = self._estimate_endpoint_value(card, route, state)
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
        return GreedyEndpoint().choose_play(state, player)

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
            val = self._route_endpoint_value(route, state)
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
        # Prefer interference on the target route's output channel
        last_out = target_route.last_output_channel
        if last_out:
            for card, ctx in plays:
                if card.card_type == CardType.INTERFERENCE:
                    jam_ctx = ExtendedPlacementContext(target_channel=last_out)
                    return card, jam_ctx

        # Otherwise: find a route card that outputs to the same channel (creates collision)
        if last_out:
            for card, ctx in plays:
                if card.card_type not in (CardType.INTERFERENCE, CardType.ACK):
                    if card.output_channel == last_out:
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

        # 1. Complete a route (play endpoint on route at min_length - 1)
        for card, ctx in plays:
            if card.card_type in (CardType.ACK, CardType.BROADCAST):
                for route in open_routes:
                    if route.length >= cfg.route_min_length - 1:
                        if self._can_card_extend_route(card, route, state):
                            return card, PlacementContext(target_route_id=route.route_id)

        # 2. Extend route anchored on a seed card
        seed_ids = {c.card_id for c in state.tableau.seed_cards}
        for card, ctx in plays:
            if card.card_type in (CardType.ACK, CardType.INTERFERENCE):
                continue
            for route in open_routes:
                if route.card_ids and route.card_ids[0] in seed_ids:
                    if self._can_card_extend_route(card, route, state):
                        return card, PlacementContext(target_route_id=route.route_id)

        # 3. Extend any valid route
        for card, ctx in plays:
            if card.card_type in (CardType.ACK, CardType.INTERFERENCE):
                continue
            for route in open_routes:
                if self._can_card_extend_route(card, route, state):
                    # Prefer routes not in interfered channels
                    if card.output_channel not in state.tableau.interfered_channels:
                        return card, PlacementContext(target_route_id=route.route_id)

        # 4. Start a new route anchored to seed (play onto a free seed channel)
        for card, ctx in plays:
            if card.card_type in (CardType.ACK, CardType.INTERFERENCE):
                continue
            for seed in state.tableau.seed_cards:
                if card.input_channel == seed.output_channel:
                    if card.output_channel not in state.tableau.interfered_channels:
                        return card, PlacementContext()

        # 5. Random fallback
        return self._choose_random(plays, state)

    def _color_preference_score(
        self, card: Card, route: RouteState, state: GameState
    ) -> float:
        return 0.0


# ---------------------------------------------------------------------------
# 5. ColorAwareRouteBuilder
# ---------------------------------------------------------------------------

class ColorAwareRouteBuilder(RouteBuilder):
    name = "color_aware_route_builder"

    def choose_play(self, state: GameState, player: PlayerState) -> tuple[Card, PlacementContext]:
        cfg = state.config
        if cfg.color_mode == ColorMode.IGNORE:
            return super().choose_play(state, player)

        plays = self.legal_plays(state, player)
        open_routes = self._open_routes(state)

        best_score = -1.0
        best_play: tuple[Card, PlacementContext] | None = None

        for card, ctx in plays:
            if card.card_type in (CardType.ACK, CardType.INTERFERENCE):
                continue
            for route in open_routes:
                if self._can_card_extend_route(card, route, state):
                    ep_val = self._estimate_endpoint_value(card, route, state)
                    color_bonus = self._color_preference_score(card, route, state)
                    total = ep_val + color_bonus
                    if total > best_score:
                        best_score = total
                        best_play = (card, PlacementContext(target_route_id=route.route_id))

        if best_play is not None:
            return best_play

        return super().choose_play(state, player)

    def _color_preference_score(
        self, card: Card, route: RouteState, state: GameState
    ) -> float:
        cfg = state.config
        if cfg.color_mode == ColorMode.IGNORE or not route.colors_in_route:
            return 0.0
        dominant = max(set(route.colors_in_route), key=route.colors_in_route.count)
        if card.color == dominant:
            return float(cfg.color_bonus_same_route)
        return 0.0
