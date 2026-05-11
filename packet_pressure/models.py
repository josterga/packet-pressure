from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CardType(str, Enum):
    ROUTE = "route"
    ACK = "ack"
    BROADCAST = "broadcast"
    INTERFERENCE = "interference"


class TerminationReason(str, Enum):
    ACTIVE = "active"
    ACK = "ack"
    BROADCAST = "broadcast"
    COLLISION = "collision"
    INTERFERENCE = "interference"
    HOP_LIMIT = "hop_limit"
    LOOP_DETECTED = "loop_detected"
    RETURN_TO_FIRST = "return_to_first_hop"


# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

EVT_ROUND_START = "ROUND_START"
EVT_ROUND_END = "ROUND_END"
EVT_CARD_DRAWN = "CARD_DRAWN"
EVT_CARD_PLAYED = "CARD_PLAYED"
EVT_COLLISION = "COLLISION"
EVT_INTERFERENCE_APPLIED = "INTERFERENCE_APPLIED"
EVT_ROUTE_STARTED = "ROUTE_STARTED"
EVT_ROUTE_EXTENDED = "ROUTE_EXTENDED"
EVT_ROUTE_TERMINATED = "ROUTE_TERMINATED"
EVT_ROUTE_INVALIDATED = "ROUTE_INVALIDATED"
EVT_SCORE_AWARDED = "SCORE_AWARDED"
EVT_GAME_OVER = "GAME_OVER"


# ---------------------------------------------------------------------------
# GameConfig
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GameConfig:
    player_count: int = 4
    score_to_win: int = 2000
    max_rounds: int = 15

    channels: tuple[str, ...] = ("01", "02", "03")
    channel_shapes: tuple[str, ...] = ("circle", "square", "triangle")
    channel_colors: tuple[str, ...] = ("teal", "orange", "purple")

    colors: tuple[str, ...] = ("red", "blue", "green", "yellow")

    starting_hand_size: int = 5
    draw_per_turn: int = 1
    turns_per_player_per_round: int = 1
    seed_cards_per_round: int = 3

    route_min_length: int = 2
    route_max_hops: int = 6

    deck_size: int = 80

    no_loops: bool = True
    no_return_to_first_hop: bool = False

    broadcast_multiplier: int = 2
    interference_scope: str = "single"

    special_distribution: tuple[tuple[str, float], ...] = (
        ("ack", 0.10),
        ("broadcast", 0.08),
        ("interference", 0.07),
    )
    route_card_distribution: tuple[tuple[tuple[str, str], float], ...] = ()
    packet_values: tuple[int, ...] = (100, 100, 200, 200, 300, 400, 500, 600, 700)

    def channel_index(self, ch: str) -> int | None:
        try:
            return self.channels.index(ch)
        except ValueError:
            return None

    def channel_shape(self, ch: str) -> str | None:
        idx = self.channel_index(ch)
        if idx is None or idx >= len(self.channel_shapes):
            return None
        return self.channel_shapes[idx]

    def channel_color(self, ch: str) -> str | None:
        idx = self.channel_index(ch)
        if idx is None or idx >= len(self.channel_colors):
            return None
        return self.channel_colors[idx]

    def special_dist_dict(self) -> dict[str, float]:
        return dict(self.special_distribution)


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Card:
    card_id: str
    card_type: CardType
    input_channel: str | None
    output_channel: str | None
    packet_value: int
    color: str
    owner_id: str | None = None
    special_properties: tuple[tuple[str, Any], ...] = ()

    def special(self, key: str, default: Any = None) -> Any:
        return dict(self.special_properties).get(key, default)

    def with_owner(self, owner_id: str) -> Card:
        return dataclasses.replace(self, owner_id=owner_id)


# ---------------------------------------------------------------------------
# PlacementContext
# ---------------------------------------------------------------------------

@dataclass
class PlacementContext:
    target_route_id: str | None = None


# ---------------------------------------------------------------------------
# PlayerState
# ---------------------------------------------------------------------------

@dataclass
class PlayerState:
    player_id: str
    score: int = 0
    hand: list[Card] = field(default_factory=list)
    play_history: list[str] = field(default_factory=list)
    policy_name: str = "unset"


# ---------------------------------------------------------------------------
# RouteState
# ---------------------------------------------------------------------------

@dataclass
class RouteState:
    route_id: str
    card_ids: list[str] = field(default_factory=list)
    owner_sequence: list[str] = field(default_factory=list)
    channels_in_route: list[str] = field(default_factory=list)  # output channels per hop
    entry_channel: str | None = None  # input channel of the first card in the route
    is_valid: bool = True
    is_scoring_candidate: bool = False
    endpoint_card_id: str | None = None
    length: int = 0
    termination_reason: TerminationReason = TerminationReason.ACTIVE

    @property
    def last_output_channel(self) -> str | None:
        return self.channels_in_route[-1] if self.channels_in_route else None

    @property
    def first_input_channel(self) -> str | None:
        return self.entry_channel

    def is_open(self) -> bool:
        return self.is_valid and self.termination_reason == TerminationReason.ACTIVE


# ---------------------------------------------------------------------------
# TableauState
# ---------------------------------------------------------------------------

@dataclass
class TableauState:
    active_cards: dict[str, Card] = field(default_factory=dict)
    seed_cards: list[Card] = field(default_factory=list)
    routes: list[RouteState] = field(default_factory=list)
    interfered_channels: set[str] = field(default_factory=set)
    collided_card_ids: set[str] = field(default_factory=set)
    _route_counter: int = field(default=0, repr=False)

    def next_route_id(self) -> str:
        self._route_counter += 1
        return f"R-{self._route_counter:04d}"


# ---------------------------------------------------------------------------
# GameState
# ---------------------------------------------------------------------------

@dataclass
class GameState:
    config: GameConfig
    players: list[PlayerState]
    deck: list[Card]
    discard: list[Card]
    tableau: TableauState
    round_number: int = 0
    turn_number: int = 0
    current_player_index: int = 0
    event_log: list[dict] = field(default_factory=list)
    rng: Any = field(default=None, repr=False)
    _terminal: bool = field(default=False, repr=False)
    _card_registry: dict[str, Card] = field(default_factory=dict, repr=False)

    def log(self, event_type: str, **kwargs: Any) -> None:
        player_id = (
            self.players[self.current_player_index].player_id
            if self.players else None
        )
        self.event_log.append({
            "round": self.round_number,
            "turn": self.turn_number,
            "player": player_id,
            "event": event_type,
            **kwargs,
        })

    def register_card(self, card: Card) -> None:
        self._card_registry[card.card_id] = card

    def lookup_card(self, card_id: str) -> Card | None:
        return self._card_registry.get(card_id)
