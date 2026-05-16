"""
Terminal rendering for interactive play.
ANSI colors match the card sketch visual language (teal/orange/purple/red/blue per channel).
Falls back to plain ASCII when NO_COLOR is set or stdout is not a tty.
"""
from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Card, GameConfig, GameState, PlayerState, RouteState

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"

# ANSI color codes by channel_colors order: teal, orange, purple, red, blue
_CHANNEL_ANSI = {
    "teal":   "\033[36m",
    "orange": "\033[33m",
    "purple": "\033[35m",
    "red":    "\033[31m",
    "blue":   "\033[34m",
    "green":  "\033[32m",
}


def _c(text: str, code: str) -> str:
    if not _USE_COLOR:
        return text
    return f"{code}{text}{_RESET}"


def _bold(text: str) -> str:
    return _c(text, _BOLD)


def _dim(text: str) -> str:
    return _c(text, _DIM)


def print_splash() -> None:
    _TEAL   = _CHANNEL_ANSI["teal"]
    _ORANGE = _CHANNEL_ANSI["orange"]
    _PURPLE = _CHANNEL_ANSI["purple"]
    _RED    = _CHANNEL_ANSI["red"]
    _GREEN  = _CHANNEL_ANSI["green"]

    # Icons and colors are independent cycles.
    # icon = syms[(c - r) % 5]  → diagonal shift each row
    # color = bg_colors[(r + c) % 3]  → 3-color cycle independent of icon type
    _syms = ["⇒", "⊘", "⚠", "⊕", "⊣"]
    _bg_colors = [_TEAL, _ORANGE, _PURPLE]

    import shutil
    term_width = shutil.get_terminal_size().columns
    n_cols = term_width // 3  # each cell is " X " = 3 chars (⚠ is double-width but close enough)
    n_rows = 5
    for r in range(n_rows):
        parts = []
        for c in range(n_cols):
            sym   = _syms[(c - r) % 5]
            color = _bg_colors[(r + c) % 3]
            parts.append(" " + _c(sym, f"{_DIM}{color}") + " ")
        print("".join(parts))

    # Hero icon row — each card type in its own full color, not dimmed
    print()
    hero = "  ·  ".join([
        _c("⇒", f"{_BOLD}{_TEAL}"),
        _c("⊕", f"{_BOLD}{_PURPLE}"),
        _c("⊘", f"{_BOLD}{_GREEN}"),
        _c("⊣", f"{_BOLD}{_ORANGE}"),
        _c("⚠", f"{_BOLD}{_RED}"),
    ])
    print(f"  {hero}")
    print()
    print(f"  {_bold('PACKET PRESSURE')}")
    print(f"  {_dim('Extend the route. Hold the endpoint.')}")
    print()


def print_how_to_play(config: "GameConfig") -> None:
    _TEAL   = _CHANNEL_ANSI["teal"]
    _ORANGE = _CHANNEL_ANSI["orange"]
    _PURPLE = _CHANNEL_ANSI["purple"]
    _RED    = _CHANNEL_ANSI["red"]
    _GREEN  = _CHANNEL_ANSI["green"]

    def _section(title: str) -> None:
        print(f"\n  {_bold(title)}")

    def _row(symbol: str, color: str, label: str, desc: str) -> None:
        sym = _c(symbol, color) if color else symbol
        print(f"    {sym}  {_bold(label)} — {_dim(desc)}")

    print()
    print(f"  {_bold('HOW TO PLAY')}")

    _section("GOAL")
    print("    " + _dim("First to reach the score target wins. If no one does,"))
    print("    " + _dim("most points after the final round wins."))

    _section("YOUR TURN")
    print("    " + _dim("Draw one card, then play one card onto the tableau."))
    print("    " + _dim("Cards extend open routes or start new ones."))

    _section("ROUTES")
    print("    " + _dim("A route chains when each node's output channel matches"))
    print("    " + _dim("the next node's input channel. Routes need 2+ nodes to"))
    print("    " + _dim(f"score. Max {config.route_max_hops} hops; max {config.max_open_routes} routes open at once."))
    print("    " + _dim("No channel can appear twice in the same route."))

    _section("CARRY")
    print("    " + _dim("Routes under 2 nodes at round end carry into the next"))
    print("    " + _dim("round — they don't score and aren't discarded."))

    _section("ROUND STRUCTURE")
    print("    " + _dim(f"Each player takes {config.turns_per_player_per_round} turns per round. After all turns,"))
    print("    " + _dim("routes score and hands refill."))

    _section("PASSING")
    print("    " + _dim("You may only pass if you have no legal play. You still draw."))

    _section("CARD TYPES")
    _row("⇒", _TEAL,   "Relay",     "extends a route (input → output); starts new if cap allows and can't extend any")
    _row("⊣", _ORANGE, "Terminal",  "closes any open route (≥ 2 nodes); terminal's own value scores")
    _row("⊕", _PURPLE, "Amplifier", "extends like a relay; if exit node at scoring, value ×2")
    _row("⚠", _RED,    "Noise",     "targets a fixed channel; destroys all scoring routes that output to it — including your own; only legal when such a route exists")
    _row("⊘", _GREEN,  "Filter",    "extends like a relay; if noise targets its input channel, the whole route is immune on that channel only")

    _section("SCORING")
    print("    " + _dim("At round end, all valid routes (≥ 2 nodes) score."))
    print("    " + _dim("Only the exit node's packet value counts — no sum."))
    print("    " + _dim("The exit node's owner collects the points."))

    _section("TURN ORDER")
    print("    " + _dim("Round winner goes first next round. On a tie, order is unchanged."))
    print()


def channel_symbol(ch: str, config: "GameConfig") -> str:
    """Return colored channel label — pure ASCII so terminal width is always predictable."""
    if ch == "ANY":
        return _c("ANY", "\033[37m")
    if ch == "TERM":
        return _c("END", "\033[37m")
    idx = config.channel_index(ch)
    if idx is None:
        return f"CH{ch}"
    color_name = config.channel_colors[idx] if idx < len(config.channel_colors) else ""
    ansi = _CHANNEL_ANSI.get(color_name, "")
    label = f"CH{ch}"
    if not ansi or not _USE_COLOR:
        return label
    return f"{ansi}{label}{_RESET}"


def channel_tag(ch: str | None, config: "GameConfig") -> str:
    if ch is None:
        return " -- "
    return channel_symbol(ch, config)


def _border_ansi(ch: str | None, config: "GameConfig") -> str:
    """Return the ANSI color code for a channel's border, or '' if not applicable."""
    if not _USE_COLOR or ch is None or ch in ("ANY", "TERM"):
        return ""
    idx = config.channel_index(ch)
    if idx is None or idx >= len(config.channel_colors):
        return ""
    return _CHANNEL_ANSI.get(config.channel_colors[idx], "")


# ---------------------------------------------------------------------------
# Card block rendering  (returns a list of lines, all same width)
# ---------------------------------------------------------------------------

_CARD_WIDTH = 18  # inner content width — wide enough for full card IDs + CH labels
_CARD_BORDER = "─" * _CARD_WIDTH


import re as _re

def _strip_ansi(s: str) -> str:
    return _re.sub(r"\033\[[0-9;]*m", "", s)


def render_card_lines(card: "Card", config: "GameConfig", dim: bool = False) -> list[str]:
    """Return lines representing the card as a terminal block."""
    w = _CARD_WIDTH

    def pad(s: str, width: int = w) -> str:
        padding = width - len(_strip_ansi(s))
        return s + " " * max(0, padding)

    in_tag = channel_tag(card.input_channel, config)
    out_tag = channel_tag(card.output_channel, config)

    # Header: "IN CH02    CH03 OUT" — IN flush-left, OUT flush-right
    in_label = f"IN {in_tag}"
    out_label = f"{out_tag} OUT"
    in_plain = _strip_ansi(in_label)
    out_plain = _strip_ansi(out_label)
    gap = max(1, w - len(in_plain) - len(out_plain) - 2)
    header = " " + in_label + " " * gap + out_label + " "

    # Card type indicator (ROUTE cards get no body line — borders show direction)
    from .models import CardType
    if card.card_type == CardType.TERMINAL:
        type_line: str | None = pad("  ⊣  ─ TERM ─   ")
    elif card.card_type == CardType.AMPLIFIER:
        mult = card.special("multiplier", 2)
        type_line = pad(f"  ⊕  AMP  ×{mult}  ")
    elif card.card_type == CardType.NOISE:
        ch_sym = channel_symbol(card.output_channel, config) if card.output_channel else "??"
        type_line = pad(f"  ⚠  ≋≋ {ch_sym}    ")
    elif card.card_type == CardType.FILTER:
        type_line = pad(f"  ⊘  FLT-CH{card.input_channel} ")
    else:
        type_line = pad("  ⇒             ")

    # Packet value
    val_line = pad(f"  PKT  {card.packet_value:<6}")

    # Owner / card id
    owner = card.owner_id or ""
    owner_line = pad(f"  {owner:<4}  {card.card_id}")

    # Colored border chars — left = input channel color, right = output channel color
    # Skip colors when dim=True so the caller's _dim() wrapper isn't broken by nested RESETs
    in_ansi = "" if dim else _border_ansi(card.input_channel, config)
    out_ansi = "" if dim else _border_ansi(card.output_channel, config)
    L = _c("│", in_ansi) if in_ansi else "│"
    R = _c("│", out_ansi) if out_ansi else "│"
    top = f"{_c('┌', in_ansi) if in_ansi else '┌'}{'─' * w}{_c('┐', out_ansi) if out_ansi else '┐'}"
    bot = f"{_c('└', in_ansi) if in_ansi else '└'}{'─' * w}{_c('┘', out_ansi) if out_ansi else '┘'}"
    sep = f"{L}{'─' * w}{R}"

    def row(content: str) -> str:
        return f"{L}{content}{R}"

    lines = [top, row(pad(header)), sep]
    if type_line is not None:
        lines.append(row(type_line))
    lines += [row(val_line), sep, row(owner_line), bot]
    return lines


def render_cards_row(cards: "list[Card]", config: "GameConfig",
                     labels: list[str] | None = None, dim: bool = False) -> str:
    """Render a horizontal row of card blocks with optional labels above."""
    if not cards:
        return "  (none)"

    all_lines = [render_card_lines(c, config, dim=dim) for c in cards]
    height = max(len(lines) for lines in all_lines)

    # Pad each card block to the same height
    for lines in all_lines:
        while len(lines) < height:
            lines.append(" " * (_CARD_WIDTH + 2))

    rows = []

    # Optional numbered labels above each card
    if labels:
        label_row = ""
        for i, (card, lbl) in enumerate(zip(cards, labels)):
            lbl_text = f"[{lbl}]"
            width = _CARD_WIDTH + 2  # include borders
            label_row += lbl_text.center(width) + "  "
        rows.append(label_row)

    for line_idx in range(height):
        row = "  ".join(block[line_idx] for block in all_lines)
        rows.append(row)

    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Tableau rendering
# ---------------------------------------------------------------------------

def _route_channel_chain(route: "RouteState", cfg: "GameConfig") -> str:
    parts = []
    if route.entry_channel:
        parts.append(channel_symbol(route.entry_channel, cfg))
    for ch in route.channels_in_route:
        parts.append(channel_symbol(ch, cfg))
    from .models import TerminationReason
    if route.termination_reason != TerminationReason.ACTIVE:
        parts.append(_dim("END"))
    return " → ".join(parts)


def render_route_block(route: "RouteState", state: "GameState") -> str:
    cfg = state.config
    scoring = " ✓" if route.is_scoring_candidate else ""
    chain = _route_channel_chain(route, cfg)
    header = f"  {_bold(route.route_id)}  [len {route.length}{scoring}]  {chain}"

    cards = [state.lookup_card(cid) for cid in route.card_ids]
    cards = [c for c in cards if c is not None]
    card_row = render_cards_row(cards, cfg) if cards else "  (no cards)"

    return header + "\n" + card_row


def render_tableau(state: "GameState") -> str:
    from .models import TerminationReason
    cfg = state.config
    lines: list[str] = []

    all_active    = [r for r in state.tableau.routes if r.is_valid and r.termination_reason == TerminationReason.ACTIVE]
    carried_routes = [r for r in all_active if r.carried]
    active_routes  = [r for r in all_active if not r.carried]
    done_routes    = [r for r in state.tableau.routes if r.is_valid and r.termination_reason != TerminationReason.ACTIVE]
    invalid_routes = [r for r in state.tableau.routes if not r.is_valid]

    if carried_routes:
        lines.append(_dim("  ── CARRIED ──"))
        for route in carried_routes:
            lines.append(render_route_block(route, state))
            lines.append("")

    for route in active_routes:
        lines.append(render_route_block(route, state))
        lines.append("")

    if done_routes:
        lines.append(_dim("  ── DONE ──"))
        for route in done_routes:
            chain = _route_channel_chain(route, cfg)
            scoring = " ✓" if route.is_scoring_candidate else ""
            header = _dim(f"  {route.route_id}  [{route.termination_reason.value}{scoring}]  {chain}")
            cards = [state.lookup_card(cid) for cid in route.card_ids]
            cards = [c for c in cards if c is not None]
            card_row = render_cards_row(cards, cfg, dim=True) if cards else ""
            lines.append(header)
            if card_row:
                for ln in card_row.splitlines():
                    lines.append(_dim(ln))
            lines.append("")

    if invalid_routes:
        lines.append(_dim("  ── BROKEN ──"))
        for route in invalid_routes:
            chain = _route_channel_chain(route, cfg)
            header = _dim(f"  {route.route_id}  ✗  {route.termination_reason.value}  {chain}")
            cards = [state.lookup_card(cid) for cid in route.card_ids]
            cards = [c for c in cards if c is not None]
            card_row = render_cards_row(cards, cfg, dim=True) if cards else ""
            lines.append(header)
            if card_row:
                for ln in card_row.splitlines():
                    lines.append(_dim(ln))
            lines.append("")

    # Defensive: show any active cards not accounted for in any route
    all_route_card_ids: set[str] = set()
    for route in state.tableau.routes:
        all_route_card_ids.update(route.card_ids)
    unrouted = [c for c in state.tableau.active_cards.values()
                if c.card_id not in all_route_card_ids]
    if unrouted:
        lines.append(_dim("  (unrouted)"))
        lines.append(render_cards_row(unrouted, cfg))
        lines.append("")

    if not active_routes and not done_routes and not invalid_routes and not unrouted:
        lines.append(_dim("  (tableau empty)"))

    return "\n".join(lines)


def _render_route_line(route: "RouteState", state: "GameState") -> str:
    cfg = state.config
    cards = [state.lookup_card(cid) for cid in route.card_ids]
    cards = [c for c in cards if c is not None]

    channel_chain = " → ".join(
        channel_symbol(ch, cfg) for ch in route.channels_in_route
    )

    scoring = " ✓" if route.is_scoring_candidate else ""
    status = f"  {_bold(route.route_id)}  [len {route.length}{scoring}]  {channel_chain}"

    if route.exit_node_id:
        ep = state.lookup_card(route.exit_node_id)
        if ep:
            owner = f" · {ep.owner_id}" if ep.owner_id else ""
            status += f"  exit node PKT {ep.packet_value}{owner}"

    return "    " + status


# ---------------------------------------------------------------------------
# Hand rendering
# ---------------------------------------------------------------------------

def render_hand(player: "PlayerState", state: "GameState",
                hints: "list[list[str]] | None" = None) -> str:
    if not player.hand:
        return "  (hand empty)"
    labels = [str(i + 1) for i in range(len(player.hand))]
    block = render_cards_row(player.hand, state.config, labels=labels)
    lines = [block]
    if hints:
        col_width = _CARD_WIDTH + 2 + 2
        max_lines = max(len(h) for h in hints)
        for i in range(max_lines):
            row = ""
            for card_hints in hints:
                h = card_hints[i] if i < len(card_hints) else ""
                row += h[:col_width].ljust(col_width)
            lines.append("  " + row)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scores + header
# ---------------------------------------------------------------------------

def render_scores(state: "GameState", human_index: int = 0) -> str:
    parts = []
    for i, p in enumerate(state.players):
        label = "you" if (human_index >= 0 and i == human_index) else p.player_id
        parts.append(f"{_bold(label)}  {p.score}")
    return "  " + "  │  ".join(parts)


def render_round_header(state: "GameState") -> str:
    cfg = state.config
    turns_total = cfg.turns_per_player_per_round * cfg.player_count
    display_turn = min(state.turn_number + 1, turns_total)
    turn_info = f"  ·  Turn {display_turn} of {turns_total}" if cfg.turns_per_player_per_round > 1 else ""
    plain = (
        f"  PACKET PRESSURE  ·  "
        f"Round {state.round_number} of {cfg.max_rounds}{turn_info}  ·  "
        f"Score to win: {cfg.score_to_win}"
    )
    bar = "━" * max(60, len(plain))
    content = (
        f"  {_bold('PACKET PRESSURE')}  ·  "
        f"Round {state.round_number} of {cfg.max_rounds}{turn_info}  ·  "
        f"Score to win: {cfg.score_to_win}"
    )
    return f"\n{bar}\n{content}\n{bar}"


# ---------------------------------------------------------------------------
# Event summary (for opponent turns)
# ---------------------------------------------------------------------------

_SKIP_EVENTS = {
    "ROUND_START", "ROUND_END", "CARD_DRAWN",
    "ROUTE_STARTED", "GAME_OVER",
}


def render_event(event: dict, state: "GameState") -> str | None:
    etype = event.get("event", "")
    if etype in _SKIP_EVENTS:
        return None

    player = event.get("player", "?")
    cfg = state.config

    if etype == "CARD_PLAYED":
        card = state.lookup_card(event.get("card_id", ""))
        if card is None:
            return None
        ct = event.get("card_type", "")
        if ct == "noise":
            ch_sym = channel_symbol(card.output_channel, cfg) if card.output_channel else "?"
            return f"  {player}  played {card.card_id}  NOISE {ch_sym}"
        in_ch = channel_tag(card.input_channel, cfg)
        out_ch = channel_tag(card.output_channel, cfg)
        return f"  {player}  played {card.card_id}  {in_ch}→{out_ch}  PKT {card.packet_value}"

    if etype == "ROUTE_EXTENDED":
        return f"  {player}  extended {event.get('route_id')}  (len {event.get('length')})"

    if etype == "ROUTE_TERMINATED":
        scoring = " ✓ scoring" if event.get("scoring") else ""
        return f"  {player}  terminated {event.get('route_id')}  [{event.get('reason')}]{scoring}"

    if etype == "ROUTE_INVALIDATED":
        return _dim(f"  {player}  route {event.get('route_id')} invalidated [{event.get('reason')}]")

    if etype == "COLLISION":
        ch = event.get("channel", "?")
        return _dim(f"  ⚡ collision on channel {channel_symbol(ch, cfg)}")

    if etype == "NOISE_APPLIED":
        ch = event.get("channel", "?")
        return f"  {player}  noised channel {channel_symbol(ch, cfg)}"

    if etype == "SCORE_AWARDED":
        pid = event.get("player_id", "?")
        score = event.get("score", 0)
        route = event.get("route_id", "?")
        return f"  {_bold('SCORE')}  {pid} +{score}  ({route} len {event.get('route_length', '?')})"

    if etype == "PASS_TURN":
        pid = event.get("player_id", player)
        return _dim(f"  {pid}  passed (no legal plays)")

    return None
