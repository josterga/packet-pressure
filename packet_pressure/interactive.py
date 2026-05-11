from __future__ import annotations

import time

import numpy as np

from .deck import DeckBuilder
from .display import (
    channel_symbol,
    render_event,
    render_hand,
    render_round_header,
    render_scores,
    render_tableau,
)
from .engine import GameEngine
from .models import (
    CardType,
    EVT_CARD_DRAWN,
    GameConfig,
    GameState,
    PlacementContext,
    PlayerState,
)
from .policies import ExtendedPlacementContext, PlayerPolicy


class HumanPolicy(PlayerPolicy):
    name = "human"

    def __init__(self, human_index: int = 0) -> None:
        self._human_index = human_index

    def choose_play(
        self, state: GameState, player: PlayerState
    ) -> tuple[object, PlacementContext]:
        # Drawn cards for this turn are the most recent CARD_DRAWN events for this player
        drawn = [
            state.lookup_card(e["card_id"])
            for e in reversed(state.event_log)
            if e.get("event") == EVT_CARD_DRAWN and e.get("player") == player.player_id
            and state.lookup_card(e.get("card_id", "")) is not None
        ]
        # Only show cards drawn in this exact turn (stop at first non-draw event going back)
        this_turn_drawn = []
        for e in reversed(state.event_log):
            if e.get("player") != player.player_id:
                continue
            if e.get("event") != EVT_CARD_DRAWN:
                break
            card = state.lookup_card(e.get("card_id", ""))
            if card:
                this_turn_drawn.append(card)

        self._print_turn(state, player, list(reversed(this_turn_drawn)))

        while True:
            try:
                raw = input(f"\n  Play card [1-{len(player.hand)}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Quitting.")
                raise SystemExit(0)

            if not raw.isdigit():
                print("  Enter a number.")
                continue
            idx = int(raw) - 1
            if idx < 0 or idx >= len(player.hand):
                print(f"  Enter a number between 1 and {len(player.hand)}.")
                continue

            card = player.hand[idx]

            if card.card_type == CardType.INTERFERENCE:
                channel = self._prompt_channel(state)
                return card, ExtendedPlacementContext(target_channel=channel)

            if card.card_type == CardType.ACK:
                open_routes = [r for r in state.tableau.routes if r.is_open()]
                if not open_routes:
                    print("  No open routes to ACK.")
                    continue
                route_id = self._prompt_route(state, open_routes)
                return card, PlacementContext(target_route_id=route_id)

            # Use the best matching context from legal_plays
            plays = self.legal_plays(state, player)
            matching = [(c, ctx) for c, ctx in plays if c.card_id == card.card_id]
            ctx = matching[0][1] if matching else PlacementContext()
            return card, ctx

    def _print_turn(
        self, state: GameState, player: PlayerState, drawn: list
    ) -> None:
        print(render_round_header(state))
        print(f"  Your turn  ·  {player.player_id}")
        print(render_scores(state, human_index=self._human_index))
        print()
        print(render_tableau(state))

        if drawn:
            cfg = state.config
            parts = []
            for card in drawn:
                in_sym = channel_symbol(card.input_channel, cfg) if card.input_channel else "—"
                out_sym = channel_symbol(card.output_channel, cfg) if card.output_channel else "—"
                parts.append(f"{card.card_id}  {in_sym}→{out_sym}  PKT {card.packet_value}")
            print(f"  DRAWN:  {',  '.join(parts)}\n")

        hints = self._build_hints(state, player)
        print("  YOUR HAND")
        print(render_hand(player, state, hints=hints))

    def _build_hints(self, state: GameState, player: PlayerState) -> list[list[str]]:
        open_routes = [r for r in state.tableau.routes if r.is_open()]
        cfg = state.config
        hints = []

        for card in player.hand:
            card_hints: list[str] = []

            if card.card_type == CardType.INTERFERENCE:
                for ch in cfg.channels:
                    card_hints.append(f"→ jam CH{ch}")

            elif card.card_type == CardType.ACK:
                for route in open_routes:
                    new_len = route.length + 1
                    scoring = new_len >= cfg.route_min_length
                    card_hints.append(
                        f"→ ACK {route.route_id} len {route.length}{'  ✓' if scoring else ''}"
                    )
                if not card_hints:
                    card_hints = ["→ (no open routes)"]

            else:
                for route in open_routes:
                    if not self._can_card_extend_route(card, route, state):
                        continue
                    if card.card_type == CardType.BROADCAST:
                        card_hints.append(
                            f"→ BCST {route.route_id} ×{cfg.broadcast_multiplier} len {route.length}"
                        )
                    else:
                        card_hints.append(f"→ extend {route.route_id} (len {route.length})")
                if not card_hints:
                    card_hints = ["→ new route"]

            hints.append(card_hints)

        return hints

    def _prompt_route(self, state: GameState, open_routes: list) -> str:
        from .display import _render_route_line
        print()
        for i, route in enumerate(open_routes):
            print(f"  [{i + 1}]  {_render_route_line(route, state).strip()}")
        while True:
            try:
                raw = input(f"  ACK which route [1-{len(open_routes)}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                raise SystemExit(0)
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(open_routes):
                    return open_routes[idx].route_id
            print(f"  Enter a number between 1 and {len(open_routes)}.")

    def _prompt_channel(self, state: GameState) -> str:
        channels = state.config.channels
        opts = "  ".join(f"{channel_symbol(ch, state.config)} {ch}" for ch in channels)
        print(f"\n  Jam which channel?  {opts}")
        while True:
            try:
                raw = input("  Channel: ").strip()
            except (EOFError, KeyboardInterrupt):
                raise SystemExit(0)
            if raw in channels:
                return raw
            print(f"  Enter one of: {', '.join(channels)}")


# ---------------------------------------------------------------------------
# InteractiveGame runner
# ---------------------------------------------------------------------------

class InteractiveGame:
    """
    Drives a single interactive game. Wraps GameEngine's private round/turn
    methods directly so we can inject display logic between turns.
    """

    def __init__(
        self,
        config: GameConfig,
        human_index: int,
        ai_policies: list[PlayerPolicy],
        seed: int | None = None,
        opponent_delay: float = 0.5,
        solo: bool = False,
    ) -> None:
        self.config = config
        self.human_index = human_index
        self.opponent_delay = opponent_delay
        self.solo = solo

        if solo:
            all_policies: list[PlayerPolicy] = [
                HumanPolicy(human_index=i) for i in range(config.player_count)
            ]
        else:
            if len(ai_policies) != config.player_count - 1:
                raise ValueError(
                    f"Expected {config.player_count - 1} AI policies "
                    f"(total players {config.player_count} minus 1 human), "
                    f"got {len(ai_policies)}"
                )
            human_policy = HumanPolicy(human_index=human_index)
            all_policies = list(ai_policies)
            all_policies.insert(human_index, human_policy)

        rng = np.random.default_rng(seed)
        deck = DeckBuilder(config, rng).build()
        self._engine = GameEngine(config, all_policies, deck, rng)

    def run(self) -> GameState:
        state = self._engine.state
        print("\n  Welcome to Packet Pressure!")
        if self.solo:
            players = "  ·  ".join(p.player_id for p in state.players)
            print(f"  Solo mode — players: {players}")
        else:
            print(f"  You are {state.players[self.human_index].player_id}")
        print(f"  First to {self.config.score_to_win} pts wins  ·  {self.config.max_rounds} rounds max")
        input("\n  Press Enter to start…")

        while not self._engine._is_terminal():
            self._run_round(state)

        self._print_game_over(state)
        return state

    def _run_round(self, state: GameState) -> None:
        engine = self._engine
        cfg = self.config

        # Mirror GameEngine._run_round logic exactly, but with display hooks
        state.round_number += 1
        state.turn_number = 0
        engine._begin_round()

        for _ in range(cfg.turns_per_player_per_round):
            for p_idx in range(cfg.player_count):
                if engine._is_terminal():
                    return
                state.current_player_index = p_idx
                log_before = len(state.event_log)

                engine._run_turn(p_idx)
                state.turn_number += 1

                new_events = state.event_log[log_before:]
                if self.solo or p_idx == self.human_index:
                    self._print_human_turn_result(new_events, state)
                else:
                    self._print_opponent_turn(new_events, state, p_idx)
                    if self.opponent_delay > 0:
                        time.sleep(self.opponent_delay)
                self._print_between_turns(state)

        engine._end_of_round_scoring()
        self._print_round_end(state)
        engine._discard_tableau()
        engine._advance_round()

    def _print_between_turns(self, state: GameState) -> None:
        print()
        hi = -1 if self.solo else self.human_index
        print(render_scores(state, human_index=hi))
        print()
        print(render_tableau(state))

    def _print_human_turn_result(self, events: list[dict], state: GameState) -> None:
        lines = []
        for evt in events:
            rendered = render_event(evt, state)
            if rendered:
                lines.append(rendered.strip())
        if lines:
            print()
            for line in lines:
                print(f"  {line}")

    def _print_opponent_turn(
        self, events: list[dict], state: GameState, p_idx: int
    ) -> None:
        policy_name = self._engine.policies[p_idx].name
        player_id = state.players[p_idx].player_id

        key_lines = []
        for evt in events:
            rendered = render_event(evt, state)
            if rendered and any(
                kw in rendered
                for kw in ("played", "jammed", "SCORE", "invalidated", "terminated", "collision")
            ):
                key_lines.append(rendered.strip())

        if key_lines:
            print(f"  {player_id} [{policy_name}]:")
            for line in key_lines[:3]:
                print(f"    {line}")

    def _print_round_end(self, state: GameState) -> None:
        print(f"\n{'─' * 60}")
        print(f"  End of Round {state.round_number}")
        print(render_scores(state, human_index=self.human_index))

        scored = [
            e for e in state.event_log
            if e.get("event") == "SCORE_AWARDED"
            and e.get("round") == state.round_number
        ]
        if scored:
            for e in scored:
                pid = e.get("player_id", "?")
                score = e.get("score", 0)
                route = e.get("route_id", "?")
                length = e.get("route_length", "?")
                print(f"    +{score}  {pid}  ({route}  len {length})")
        else:
            print("    (no scoring routes this round)")

        print(f"{'─' * 60}\n")
        if not self._engine._is_terminal():
            input("  Press Enter for next round…")

    def _print_game_over(self, state: GameState) -> None:
        print(f"\n{'━' * 60}")
        print(f"  {'  G A M E   O V E R  ':━^58}")
        print(f"{'━' * 60}\n")

        ranked = sorted(state.players, key=lambda p: p.score, reverse=True)
        for rank, p in enumerate(ranked):
            tag = ""
            if not self.solo and state.players.index(p) == self.human_index:
                tag = " ← you"
            print(f"  #{rank + 1}  {p.player_id} [{p.policy_name}]{'':>4}{p.score}{tag}")

        winner = ranked[0]
        print()
        if self.solo:
            print(f"  {winner.player_id} wins with {winner.score} points!")
        else:
            you = state.players[self.human_index]
            if you.player_id == winner.player_id:
                print(f"  You won with {you.score} points!")
            else:
                print(f"  {winner.player_id} wins with {winner.score}.  Your score: {you.score}")
        print()
