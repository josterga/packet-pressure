from __future__ import annotations

import dataclasses
from collections import defaultdict
from typing import TYPE_CHECKING

import numpy as np

from .models import (
    EVT_CARD_DRAWN,
    EVT_CARD_PLAYED,
    EVT_COLLISION,
    EVT_GAME_OVER,
    EVT_INTERFERENCE_APPLIED,
    EVT_ROUND_END,
    EVT_ROUND_START,
    EVT_ROUTE_EXTENDED,
    EVT_ROUTE_INVALIDATED,
    EVT_ROUTE_STARTED,
    EVT_ROUTE_TERMINATED,
    EVT_SCORE_AWARDED,
    Card,
    CardType,
    CollisionMode,
    CollisionResolutionTiming,
    ColorMode,
    GameConfig,
    GameState,
    PlacementContext,
    PlayerState,
    RouteState,
    TableauState,
    TerminationReason,
)

if TYPE_CHECKING:
    from .policies import PlayerPolicy


class GameEngine:
    def __init__(
        self,
        config: GameConfig,
        policies: list[PlayerPolicy],
        deck: list[Card],
        rng: np.random.Generator,
    ) -> None:
        if len(policies) != config.player_count:
            raise ValueError(
                f"Expected {config.player_count} policies, got {len(policies)}"
            )
        self.config = config
        self.policies = policies
        self._initial_deck = list(deck)
        self._rng = rng
        self.state: GameState = self._build_initial_state()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> GameState:
        while not self._is_terminal():
            self._run_round()
        return self.state

    def step_round(self) -> GameState:
        if not self._is_terminal():
            self._run_round()
        return self.state

    def step_turn(self) -> GameState:
        s = self.state
        if self._is_terminal():
            return s
        p_idx = s.current_player_index
        self._run_turn(p_idx)
        next_idx = (p_idx + 1) % self.config.player_count
        s.current_player_index = next_idx
        return s

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _build_initial_state(self) -> GameState:
        cfg = self.config
        players = []
        for i in range(cfg.player_count):
            p = PlayerState(
                player_id=f"P{i}",
                policy_name=self.policies[i].name,
            )
            players.append(p)

        state = GameState(
            config=cfg,
            players=players,
            deck=list(self._initial_deck),
            discard=[],
            tableau=TableauState(),
            rng=self._rng,
        )

        # Register all cards so the state can look them up by ID
        for card in self._initial_deck:
            state.register_card(card)

        # Deal starting hands
        for p in players:
            drawn = self._draw_n(state, cfg.starting_hand_size)
            p.hand.extend(drawn)

        return state

    # ------------------------------------------------------------------
    # Round-level
    # ------------------------------------------------------------------

    def _run_round(self) -> None:
        s = self.state
        s.round_number += 1
        s.turn_number = 0
        self._begin_round()

        for _ in range(self.config.turns_per_player_per_round):
            for p_idx in range(self.config.player_count):
                if self._is_terminal():
                    return
                s.current_player_index = p_idx
                self._run_turn(p_idx)
                s.turn_number += 1

        self._end_of_round_scoring()
        self._discard_tableau()
        self._advance_round()

    def _begin_round(self) -> None:
        s = self.state
        s.log(EVT_ROUND_START, round=s.round_number)
        # Draw route cards only as seeds — skip specials back to bottom of deck.
        seed_cards: list[Card] = []
        skipped: list[Card] = []
        needed = self.config.seed_cards_per_round
        while len(seed_cards) < needed and s.deck:
            card = s.deck.pop(0)
            if card.card_type != CardType.ROUTE:
                skipped.append(card)
                continue
            # Reject seeds that share an output channel with an already-accepted seed
            if any(c.output_channel == card.output_channel for c in seed_cards):
                skipped.append(card)
                continue
            seed_cards.append(card)
        # Return skipped cards to the bottom of the deck
        s.deck.extend(skipped)
        s.tableau.seed_cards = seed_cards
        for card in seed_cards:
            s.tableau.active_cards[card.card_id] = card
        for card in seed_cards:
            self._try_start_route(card)

    def _advance_round(self) -> None:
        # Replenish hands up to starting_hand_size
        cfg = self.config
        s = self.state
        for p in s.players:
            deficit = cfg.starting_hand_size - len(p.hand)
            if deficit > 0:
                drawn = self._draw_n(s, deficit)
                p.hand.extend(drawn)

    # ------------------------------------------------------------------
    # Turn-level
    # ------------------------------------------------------------------

    def _run_turn(self, player_index: int) -> None:
        s = self.state
        player = s.players[player_index]

        # 1. Draw
        drawn = self._draw_n(s, self.config.draw_per_turn)
        for card in drawn:
            player.hand.append(card)
            s.log(EVT_CARD_DRAWN, card_id=card.card_id, card_type=card.card_type.value)

        # 2. Policy chooses
        policy = self.policies[player_index]
        legal_count = len(policy.legal_plays(s, player))
        card, context = policy.choose_play(s, player)

        # 3. Validate
        if card not in player.hand:
            raise RuntimeError(f"Policy {policy.name} chose a card not in hand: {card.card_id}")

        # 4. Remove from hand, assign owner, add to tableau
        player.hand.remove(card)
        player.play_history.append(card.card_id)

        target_channel = getattr(context, "target_channel", None)
        target_route_id = getattr(context, "target_route_id", None)
        owned_card = self._apply_play(player_index, card, target_channel, legal_count, target_route_id)

        # 5. Resolve card effects
        self._resolve_card_effects(owned_card)

        # 7. Update routes
        self._update_routes(owned_card)

    def _apply_play(self, player_index: int, card: Card, target_channel: str | None,
                    legal_count: int = 0, target_route_id: str | None = None) -> Card:
        s = self.state
        player_id = s.players[player_index].player_id
        owned = card.with_owner(player_id)
        s.register_card(owned)

        extra: list[tuple[str, object]] = []
        if card.card_type == CardType.INTERFERENCE and target_channel:
            extra.append(("target_channel", target_channel))
        if card.card_type == CardType.ACK and target_route_id:
            extra.append(("target_route_id", target_route_id))
        if extra:
            owned = dataclasses.replace(owned, special_properties=tuple(extra))
            s.register_card(owned)

        s.tableau.active_cards[owned.card_id] = owned
        s.log(
            EVT_CARD_PLAYED,
            card_id=owned.card_id,
            card_type=owned.card_type.value,
            player_id=player_id,
            legal_move_count=legal_count,
        )
        return owned

    def _resolve_card_effects(self, card: Card) -> None:
        if card.card_type == CardType.INTERFERENCE:
            target = card.special("target_channel")
            if target:
                self._apply_interference(target)

    def _apply_interference(self, channel: str) -> None:
        s = self.state
        s.tableau.interfered_channels.add(channel)
        s.log(EVT_INTERFERENCE_APPLIED, channel=channel)

        # Remove any active cards currently outputting to this channel
        to_remove = [
            cid for cid, c in s.tableau.active_cards.items()
            if c.output_channel == channel
        ]
        for cid in to_remove:
            del s.tableau.active_cards[cid]
            s.tableau.collided_card_ids.add(cid)
            s.log(EVT_COLLISION, reason="interference", channel=channel, card_id=cid)

        # Invalidate routes that have been broken
        for route in s.tableau.routes:
            if route.is_valid and any(
                cid in s.tableau.collided_card_ids for cid in route.card_ids
            ):
                route.is_valid = False
                route.termination_reason = TerminationReason.INTERFERENCE
                s.log(EVT_ROUTE_INVALIDATED, route_id=route.route_id, reason="interference")

    def _check_collisions(self) -> None:
        s = self.state
        cfg = self.config
        output_map: dict[str, list[str]] = defaultdict(list)

        for cid, card in s.tableau.active_cards.items():
            if card.card_type == CardType.INTERFERENCE:
                continue
            if card.output_channel and card.output_channel not in ("TERM",):
                # Skip cards whose output is an already-interfered channel (handled by interference)
                output_map[card.output_channel].append(cid)

            if cfg.collision_mode == CollisionMode.INPUT_AND_OUTPUT:
                if card.input_channel and card.input_channel not in ("ANY",):
                    # We'll check input collisions separately via a second pass
                    pass

        colliders: set[str] = set()
        for ch, cids in output_map.items():
            if len(cids) >= 2:
                colliders.update(cids)
                s.log(EVT_COLLISION, reason="output_collision", channel=ch, card_ids=cids)

        if cfg.collision_mode == CollisionMode.INPUT_AND_OUTPUT:
            input_map: dict[str, list[str]] = defaultdict(list)
            for cid, card in s.tableau.active_cards.items():
                if card.input_channel and card.input_channel not in ("ANY",):
                    input_map[card.input_channel].append(cid)
            for ch, cids in input_map.items():
                if len(cids) >= 2:
                    colliders.update(cids)
                    s.log(EVT_COLLISION, reason="input_collision", channel=ch, card_ids=cids)

        for cid in colliders:
            s.tableau.collided_card_ids.add(cid)
            s.tableau.active_cards.pop(cid, None)

        if colliders:
            for route in s.tableau.routes:
                if route.is_valid and any(cid in colliders for cid in route.card_ids):
                    route.is_valid = False
                    route.termination_reason = TerminationReason.COLLISION
                    s.log(EVT_ROUTE_INVALIDATED, route_id=route.route_id, reason="collision")

    def _update_routes(self, new_card: Card) -> None:
        s = self.state

        if new_card.card_id in s.tableau.collided_card_ids:
            return
        if new_card.card_type == CardType.INTERFERENCE:
            return

        target_route_id = new_card.special("target_route_id")

        extended_any = False
        for route in s.tableau.routes:
            if not route.is_open():
                continue
            # ACK with a specific target only terminates that one route
            if target_route_id and route.route_id != target_route_id:
                continue
            if self._can_extend(route, new_card):
                self._extend_route(route, new_card)
                extended_any = True

        if not extended_any:
            self._try_start_route(new_card)

    def _try_start_route(self, card: Card) -> None:
        if card.card_type in (CardType.ACK, CardType.INTERFERENCE):
            return
        if card.card_id in self.state.tableau.collided_card_ids:
            return

        s = self.state
        route = RouteState(
            route_id=s.tableau.next_route_id(),
            card_ids=[card.card_id],
            owner_sequence=[card.owner_id or ""],
            colors_in_route=[card.color],
            channels_in_route=[card.output_channel] if card.output_channel else [],
            entry_channel=card.input_channel,
            endpoint_card_id=card.card_id,
            length=1,
        )
        # Check if already at hop limit after one card
        if route.length >= s.config.route_max_hops:
            route.termination_reason = TerminationReason.HOP_LIMIT
            route.is_scoring_candidate = route.length >= s.config.route_min_length

        # Check if output channel is interfered
        if card.output_channel and card.output_channel in s.tableau.interfered_channels:
            route.is_valid = False
            route.termination_reason = TerminationReason.INTERFERENCE

        s.tableau.routes.append(route)
        s.log(EVT_ROUTE_STARTED, route_id=route.route_id, card_id=card.card_id)

    def _can_extend(self, route: RouteState, card: Card) -> bool:
        cfg = self.config
        s = self.state

        # Channel match: card input must match route's last output (or ACK wildcard)
        last_out = route.last_output_channel
        if last_out is None:
            return False

        if card.input_channel != "ANY" and card.input_channel != last_out:
            return False

        # No-loops: card must not already be in route
        if cfg.no_loops and card.card_id in route.card_ids:
            s.log(EVT_ROUTE_INVALIDATED, route_id=route.route_id, reason="loop_detected",
                  card_id=card.card_id)
            return False

        # No-return-to-first-hop: card output must not equal first route channel
        if cfg.no_return_to_first_hop and route.first_input_channel is not None:
            if card.output_channel == route.first_input_channel:
                return False

        # No output channel reuse within this route (prevents channel loops)
        if card.output_channel and card.output_channel in route.channels_in_route:
            return False

        # Hop limit
        if route.length >= cfg.route_max_hops:
            return False

        return True

    def _extend_route(self, route: RouteState, card: Card) -> None:
        s = self.state
        cfg = self.config

        route.card_ids.append(card.card_id)
        route.owner_sequence.append(card.owner_id or "")
        route.colors_in_route.append(card.color)
        if card.output_channel and card.output_channel not in ("TERM",):
            route.channels_in_route.append(card.output_channel)
        route.endpoint_card_id = card.card_id
        route.length += 1

        s.log(EVT_ROUTE_EXTENDED, route_id=route.route_id, card_id=card.card_id,
              length=route.length)

        # Check termination conditions
        if card.card_type == CardType.ACK:
            route.termination_reason = TerminationReason.ACK
            route.is_scoring_candidate = route.length >= cfg.route_min_length
            s.log(EVT_ROUTE_TERMINATED, route_id=route.route_id, reason="ack",
                  scoring=route.is_scoring_candidate)

        elif card.card_type == CardType.BROADCAST:
            route.termination_reason = TerminationReason.BROADCAST
            route.is_scoring_candidate = route.length >= cfg.route_min_length
            s.log(EVT_ROUTE_TERMINATED, route_id=route.route_id, reason="broadcast",
                  scoring=route.is_scoring_candidate)

        elif route.length >= cfg.route_max_hops:
            route.termination_reason = TerminationReason.HOP_LIMIT
            route.is_scoring_candidate = route.length >= cfg.route_min_length
            s.log(EVT_ROUTE_TERMINATED, route_id=route.route_id, reason="hop_limit",
                  scoring=route.is_scoring_candidate)

        # Check if new output channel is interfered
        if card.output_channel and card.output_channel in s.tableau.interfered_channels:
            route.is_valid = False
            route.termination_reason = TerminationReason.INTERFERENCE
            s.log(EVT_ROUTE_INVALIDATED, route_id=route.route_id, reason="interference_channel")

    # ------------------------------------------------------------------
    # End-of-round scoring
    # ------------------------------------------------------------------

    def _end_of_round_scoring(self) -> None:
        s = self.state
        cfg = self.config

        # Mark all still-open valid routes as scoring candidates if long enough
        for route in s.tableau.routes:
            if route.is_open() and route.length >= cfg.route_min_length:
                route.is_scoring_candidate = True

        # Score all candidates
        for route in s.tableau.routes:
            if not route.is_valid or not route.is_scoring_candidate:
                continue
            if route.length < cfg.route_min_length:
                continue

            player_id, score = self._score_route(route)
            if player_id and score > 0:
                for p in s.players:
                    if p.player_id == player_id:
                        p.score += score
                        break
                s.log(EVT_SCORE_AWARDED, route_id=route.route_id, player_id=player_id,
                      score=score, endpoint_card_id=route.endpoint_card_id,
                      route_length=route.length,
                      termination_reason=route.termination_reason.value)

        # Check win condition
        for p in s.players:
            if p.score >= cfg.score_to_win:
                s._terminal = True
                s.log(EVT_GAME_OVER, winner=p.player_id, score=p.score)
                return

        s.log(EVT_ROUND_END, round=s.round_number)

    def _score_route(self, route: RouteState) -> tuple[str | None, int]:
        s = self.state
        cfg = self.config

        endpoint_card = s.lookup_card(route.endpoint_card_id) if route.endpoint_card_id else None
        if endpoint_card is None:
            return None, 0

        base_score = endpoint_card.packet_value

        if endpoint_card.card_type == CardType.BROADCAST:
            multiplier = endpoint_card.special("multiplier", cfg.broadcast_multiplier)
            base_score = base_score * multiplier

        if cfg.color_mode == ColorMode.SCORING_BONUS:
            base_score = self._apply_color_bonus(route, base_score)

        owner = endpoint_card.owner_id
        return owner, base_score

    def _apply_color_bonus(self, route: RouteState, base_score: int) -> int:
        cfg = self.config
        if not route.colors_in_route:
            return base_score
        dominant = max(set(route.colors_in_route), key=route.colors_in_route.count)
        monochrome_count = route.colors_in_route.count(dominant)
        if monochrome_count == len(route.colors_in_route):
            return int(base_score * cfg.color_bonus_multiplier) + cfg.color_bonus_same_route
        return base_score

    def _discard_tableau(self) -> None:
        s = self.state
        for card in s.tableau.active_cards.values():
            s.discard.append(card)
        s.tableau.active_cards.clear()
        s.tableau.seed_cards.clear()
        s.tableau.routes.clear()
        s.tableau.interfered_channels.clear()
        s.tableau.collided_card_ids.clear()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _draw_n(self, state: GameState, n: int) -> list[Card]:
        drawn = []
        for _ in range(n):
            if not state.deck:
                # Reshuffle discard into deck
                if state.discard:
                    state.deck = list(state.discard)
                    state.discard.clear()
                    state.rng.shuffle(state.deck)  # type: ignore[arg-type]
                else:
                    break
            card = state.deck.pop(0)
            drawn.append(card)
        return drawn

    def _is_terminal(self) -> bool:
        s = self.state
        if s._terminal:
            return True
        if s.round_number >= self.config.max_rounds:
            if not s._terminal:
                # Find highest scorer
                winner = max(s.players, key=lambda p: p.score)
                s._terminal = True
                s.log(EVT_GAME_OVER, winner=winner.player_id,
                      score=winner.score, reason="max_rounds")
            return True
        return False
