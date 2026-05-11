from __future__ import annotations

import numpy as np

from .models import Card, CardType, GameConfig


class DeckBuilder:
    def __init__(self, config: GameConfig, rng: np.random.Generator) -> None:
        self.config = config
        self.rng = rng

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def build(self) -> list[Card]:
        special_dist = self.config.special_dist_dict()
        n_ack = int(self.config.deck_size * special_dist.get("ack", 0.0))
        n_broadcast = int(self.config.deck_size * special_dist.get("broadcast", 0.0))
        n_interference = int(self.config.deck_size * special_dist.get("interference", 0.0))
        n_seed = self.config.seed_cards_per_round * self.config.max_rounds
        n_special = n_ack + n_broadcast + n_interference
        n_route = max(0, self.config.deck_size - n_special - n_seed)

        cards: list[Card] = []
        idx = 0

        route_cards = self._build_route_cards(n_route, idx)
        cards.extend(route_cards)
        idx += len(route_cards)

        ack_cards = self._build_ack_cards(n_ack, idx)
        cards.extend(ack_cards)
        idx += len(ack_cards)

        broadcast_cards = self._build_broadcast_cards(n_broadcast, idx)
        cards.extend(broadcast_cards)
        idx += len(broadcast_cards)

        interference_cards = self._build_interference_cards(n_interference, idx)
        cards.extend(interference_cards)
        idx += len(interference_cards)

        seed_cards = self._build_seed_cards(n_seed, idx)
        cards.extend(seed_cards)

        self.rng.shuffle(cards)  # type: ignore[arg-type]
        return list(cards)

    def total_deck_size(self) -> int:
        cfg = self.config
        hand_cards = cfg.starting_hand_size * cfg.player_count
        draw_cards = (
            cfg.draw_per_turn
            * cfg.turns_per_player_per_round
            * cfg.player_count
            * cfg.max_rounds
        )
        seed_cards = cfg.seed_cards_per_round * cfg.max_rounds
        slack = cfg.starting_hand_size * cfg.player_count
        return hand_cards + draw_cards + seed_cards + slack

    # ------------------------------------------------------------------
    # Private builders
    # ------------------------------------------------------------------

    def _build_route_cards(self, count: int, start_id: int) -> list[Card]:
        channels = self.config.channels
        colors = self.config.colors
        packet_values = self.config.packet_values
        dist = self.config.route_card_distribution

        if dist:
            pairs = [d[0] for d in dist]
            weights = np.array([d[1] for d in dist], dtype=float)
            weights /= weights.sum()
        else:
            pairs = [(i, o) for i in channels for o in channels]
            weights = np.ones(len(pairs), dtype=float) / len(pairs)

        cards = []
        for i in range(count):
            cid = f"PKT-{start_id + i:04d}"
            pair_idx = int(self.rng.choice(len(pairs), p=weights))
            in_ch, out_ch = pairs[pair_idx]
            pv = int(self.rng.choice(packet_values))
            color = str(self.rng.choice(colors))
            cards.append(Card(
                card_id=cid,
                card_type=CardType.ROUTE,
                input_channel=in_ch,
                output_channel=out_ch,
                packet_value=pv,
                color=color,
            ))
        return cards

    def _build_ack_cards(self, count: int, start_id: int) -> list[Card]:
        colors = self.config.colors
        packet_values = self.config.packet_values
        cards = []
        for i in range(count):
            cid = f"ACK-{start_id + i:04d}"
            pv = int(self.rng.choice(packet_values))
            color = str(self.rng.choice(colors))
            cards.append(Card(
                card_id=cid,
                card_type=CardType.ACK,
                input_channel="ANY",
                output_channel="TERM",
                packet_value=pv,
                color=color,
            ))
        return cards

    def _build_broadcast_cards(self, count: int, start_id: int) -> list[Card]:
        channels = self.config.channels
        colors = self.config.colors
        packet_values = self.config.packet_values
        multiplier = self.config.broadcast_multiplier
        cards = []
        for i in range(count):
            cid = f"BCST-{start_id + i:04d}"
            in_ch = str(self.rng.choice(channels))
            out_ch = str(self.rng.choice(channels))
            pv = int(self.rng.choice(packet_values))
            color = str(self.rng.choice(colors))
            cards.append(Card(
                card_id=cid,
                card_type=CardType.BROADCAST,
                input_channel=in_ch,
                output_channel=out_ch,
                packet_value=pv,
                color=color,
                special_properties=(("multiplier", multiplier),),
            ))
        return cards

    def _build_interference_cards(self, count: int, start_id: int) -> list[Card]:
        colors = self.config.colors
        cards = []
        for i in range(count):
            cid = f"JAM-{start_id + i:04d}"
            color = str(self.rng.choice(colors))
            cards.append(Card(
                card_id=cid,
                card_type=CardType.INTERFERENCE,
                input_channel=None,
                output_channel=None,
                packet_value=0,
                color=color,
            ))
        return cards

    def _build_seed_cards(self, count: int, start_id: int) -> list[Card]:
        channels = self.config.channels
        colors = self.config.colors
        packet_values = self.config.packet_values
        dist = self.config.route_card_distribution

        if dist:
            pairs = [d[0] for d in dist]
            weights = np.array([d[1] for d in dist], dtype=float)
            weights /= weights.sum()
        else:
            pairs = [(i, o) for i in channels for o in channels]
            weights = np.ones(len(pairs), dtype=float) / len(pairs)

        cards = []
        for i in range(count):
            cid = f"SEED-{start_id + i:04d}"
            pair_idx = int(self.rng.choice(len(pairs), p=weights))
            in_ch, out_ch = pairs[pair_idx]
            pv = int(self.rng.choice(packet_values))
            color = str(self.rng.choice(colors))
            cards.append(Card(
                card_id=cid,
                card_type=CardType.SEED,
                input_channel=in_ch,
                output_channel=out_ch,
                packet_value=pv,
                color=color,
            ))
        return cards
