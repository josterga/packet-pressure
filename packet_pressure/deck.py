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
        n_terminal = int(self.config.deck_size * special_dist.get("terminal", 0.0))
        n_amplifier = int(self.config.deck_size * special_dist.get("amplifier", 0.0))
        n_noise = int(self.config.deck_size * special_dist.get("noise", 0.0))
        n_filter = int(self.config.deck_size * special_dist.get("filter", 0.0))
        n_special = n_terminal + n_amplifier + n_noise + n_filter
        # Seed nodes are drawn from regular relay nodes at round start — no separate pool
        n_relay = max(0, self.config.deck_size - n_special)

        cards: list[Card] = []
        idx = 0

        relay_nodes = self._build_relay_nodes(n_relay, idx)
        cards.extend(relay_nodes)
        idx += len(relay_nodes)

        terminal_nodes = self._build_terminal_nodes(n_terminal, idx)
        cards.extend(terminal_nodes)
        idx += len(terminal_nodes)

        amplifier_nodes = self._build_amplifier_nodes(n_amplifier, idx)
        cards.extend(amplifier_nodes)
        idx += len(amplifier_nodes)

        noise_nodes = self._build_noise_nodes(n_noise, idx)
        cards.extend(noise_nodes)
        idx += len(noise_nodes)

        filter_nodes = self._build_filter_nodes(n_filter, idx)
        cards.extend(filter_nodes)

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
        seed_nodes = cfg.seed_nodes_per_round * cfg.max_rounds
        slack = cfg.starting_hand_size * cfg.player_count
        return hand_cards + draw_cards + seed_nodes + slack

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _exact_sequence(self, items: list, weights: np.ndarray, count: int) -> list:
        """Return a shuffled list of exactly `count` items drawn proportionally from weights."""
        w = weights / weights.sum()
        counts = np.round(w * count).astype(int)
        diff = count - counts.sum()
        counts[int(np.argmax(w))] += diff
        seq = [items[i] for i, n in enumerate(counts) for _ in range(n)]
        self.rng.shuffle(seq)
        return seq

    def _all_channel_pairs(self) -> list[tuple[str, str]]:
        ch = self.config.channels
        return [(i, o) for i in ch for o in ch if i != o]

    # ------------------------------------------------------------------
    # Private builders
    # ------------------------------------------------------------------

    def _build_relay_nodes(self, count: int, start_id: int) -> list[Card]:
        channels = self.config.channels
        colors = self.config.colors
        packet_values = self.config.packet_values
        dist = self.config.relay_node_distribution
        exact = self.config.relay_node_exact_distribution

        if exact and dist:
            pairs = [d[0] for d in dist]
            weights = np.array([d[1] for d in dist], dtype=float)
            pair_seq = self._exact_sequence(pairs, weights, count)
            val_items = sorted(set(packet_values))
            val_weights = np.array([packet_values.count(v) for v in val_items], dtype=float)
            val_seq = self._exact_sequence(val_items, val_weights, count)
            cards = []
            for i, ((in_ch, out_ch), pv) in enumerate(zip(pair_seq, val_seq)):
                color = str(self.rng.choice(colors))
                cards.append(Card(
                    card_id=f"PKT-{start_id + i:04d}",
                    card_type=CardType.RELAY,
                    input_channel=in_ch,
                    output_channel=out_ch,
                    packet_value=pv,
                    color=color,
                ))
            return cards

        if dist:
            pairs = [d[0] for d in dist]
            weights = np.array([d[1] for d in dist], dtype=float)
            weights /= weights.sum()
        else:
            pairs = [(i, o) for i in channels for o in channels if i != o]
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
                card_type=CardType.RELAY,
                input_channel=in_ch,
                output_channel=out_ch,
                packet_value=pv,
                color=color,
            ))
        return cards

    def _build_terminal_nodes(self, count: int, start_id: int) -> list[Card]:
        colors = self.config.colors
        packet_values = self.config.terminal_packet_values
        exact = self.config.relay_node_exact_distribution

        if exact:
            val_items = sorted(set(packet_values))
            val_weights = np.array([packet_values.count(v) for v in val_items], dtype=float)
            val_seq = self._exact_sequence(val_items, val_weights, count)
        else:
            val_seq = [int(self.rng.choice(packet_values)) for _ in range(count)]

        cards = []
        for i, pv in enumerate(val_seq):
            color = str(self.rng.choice(colors))
            cards.append(Card(
                card_id=f"TERM-{start_id + i:04d}",
                card_type=CardType.TERMINAL,
                input_channel="ANY",
                output_channel="TERM",
                packet_value=int(pv),
                color=color,
            ))
        return cards

    def _build_amplifier_nodes(self, count: int, start_id: int) -> list[Card]:
        channels = self.config.channels
        colors = self.config.colors
        packet_values = self.config.packet_values
        multiplier = self.config.amplifier_multiplier
        exact = self.config.relay_node_exact_distribution

        if exact:
            all_pairs = self._all_channel_pairs()
            pair_weights = np.ones(len(all_pairs), dtype=float)
            pair_seq = self._exact_sequence(all_pairs, pair_weights, count)
            val_items = sorted(set(packet_values))
            val_weights = np.array([packet_values.count(v) for v in val_items], dtype=float)
            val_seq = self._exact_sequence(val_items, val_weights, count)
            cards = []
            for i, ((in_ch, out_ch), pv) in enumerate(zip(pair_seq, val_seq)):
                color = str(self.rng.choice(colors))
                cards.append(Card(
                    card_id=f"AMP-{start_id + i:04d}",
                    card_type=CardType.AMPLIFIER,
                    input_channel=in_ch,
                    output_channel=out_ch,
                    packet_value=int(pv),
                    color=color,
                    special_properties=(("multiplier", multiplier),),
                ))
            return cards

        cards = []
        for i in range(count):
            cid = f"AMP-{start_id + i:04d}"
            in_ch = str(self.rng.choice(channels))
            out_options = [c for c in channels if c != in_ch]
            out_ch = str(self.rng.choice(out_options)) if out_options else in_ch
            pv = int(self.rng.choice(packet_values))
            color = str(self.rng.choice(colors))
            cards.append(Card(
                card_id=cid,
                card_type=CardType.AMPLIFIER,
                input_channel=in_ch,
                output_channel=out_ch,
                packet_value=pv,
                color=color,
                special_properties=(("multiplier", multiplier),),
            ))
        return cards

    def _build_noise_nodes(self, count: int, start_id: int) -> list[Card]:
        channels = self.config.channels
        colors = self.config.colors
        cards = []
        for i in range(count):
            cid = f"NOISE-{start_id + i:04d}"
            target_ch = str(self.rng.choice(channels))
            color = str(self.rng.choice(colors))
            cards.append(Card(
                card_id=cid,
                card_type=CardType.NOISE,
                input_channel=None,
                output_channel=target_ch,
                packet_value=0,
                color=color,
            ))
        return cards

    def _build_filter_nodes(self, count: int, start_id: int) -> list[Card]:
        channels = self.config.channels
        colors = self.config.colors
        packet_values = self.config.packet_values
        exact = self.config.relay_node_exact_distribution

        if exact:
            all_pairs = self._all_channel_pairs()
            pair_weights = np.ones(len(all_pairs), dtype=float)
            pair_seq = self._exact_sequence(all_pairs, pair_weights, count)
            val_items = sorted(set(packet_values))
            val_weights = np.array([packet_values.count(v) for v in val_items], dtype=float)
            val_seq = self._exact_sequence(val_items, val_weights, count)
            cards = []
            for i, ((in_ch, out_ch), pv) in enumerate(zip(pair_seq, val_seq)):
                color = str(self.rng.choice(colors))
                cards.append(Card(
                    card_id=f"FLT-{start_id + i:04d}",
                    card_type=CardType.FILTER,
                    input_channel=in_ch,
                    output_channel=out_ch,
                    packet_value=int(pv),
                    color=color,
                ))
            return cards

        cards = []
        for i in range(count):
            cid = f"FLT-{start_id + i:04d}"
            in_ch = str(self.rng.choice(channels))
            out_options = [c for c in channels if c != in_ch]
            out_ch = str(self.rng.choice(out_options)) if out_options else in_ch
            pv = int(self.rng.choice(packet_values))
            color = str(self.rng.choice(colors))
            cards.append(Card(
                card_id=cid,
                card_type=CardType.FILTER,
                input_channel=in_ch,
                output_channel=out_ch,
                packet_value=pv,
                color=color,
            ))
        return cards
