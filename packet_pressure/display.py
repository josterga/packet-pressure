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


# ---------------------------------------------------------------------------
# Card block rendering  (returns a list of lines, all same width)
# ---------------------------------------------------------------------------

_CARD_WIDTH = 18  # inner content width — wide enough for full card IDs + CH labels
_CARD_BORDER = "─" * _CARD_WIDTH


import re as _re

def _strip_ansi(s: str) -> str:
    return _re.sub(r"\033\[[0-9;]*m", "", s)


def render_card_lines(card: "Card", config: "GameConfig") -> list[str]:
    """Return lines representing the card as a terminal block."""
    w = _CARD_WIDTH

    def pad(s: str, width: int = w) -> str:
        padding = width - len(_strip_ansi(s))
        return s + " " * max(0, padding)

    in_tag = channel_tag(card.input_channel, config)
    out_tag = channel_tag(card.output_channel, config)

    # Line 1: IN / OUT header — left-align IN, right-align OUT within card width
    in_label = f"IN {in_tag}"
    out_label = f"OUT {out_tag}"
    in_plain = _strip_ansi(in_label)
    out_plain = _strip_ansi(out_label)
    # Total visible = 1 (lead) + in + gap + out + 1 (trail) = w
    gap = max(1, w - len(in_plain) - len(out_plain) - 2)
    header = " " + in_label + " " * gap + out_label + " "

    # Line 2: card type indicator
    from .models import CardType
    if card.card_type == CardType.ACK:
        type_line = pad("  ─── ACK ───  ")
    elif card.card_type == CardType.BROADCAST:
        mult = card.special("multiplier", 2)
        type_line = pad(f"  BCST  ×{mult}    ")
    elif card.card_type == CardType.INTERFERENCE:
        type_line = pad("  JAM  ≋≋≋≋   ")
    else:
        # Route: show channel arrow
        if card.input_channel and card.output_channel:
            arrow = f"  {channel_tag(card.input_channel, config)} → {channel_tag(card.output_channel, config)}"
        else:
            arrow = ""
        type_line = pad(arrow)

    # Line 3: packet value
    val_str = f"  PKT  {card.packet_value:<6}"
    val_line = pad(val_str)

    # Line 4: owner / card id
    owner = card.owner_id or ""
    owner_line = pad(f"  {owner:<4}  {card.card_id}")

    top    = f"┌{'─' * w}┐"
    bot    = f"└{'─' * w}┘"
    sep    = f"│{'─' * w}│"

    def row(content: str) -> str:
        return f"│{content}│"

    return [
        top,
        row(pad(header)),
        sep,
        row(type_line),
        row(val_line),
        sep,
        row(owner_line),
        bot,
    ]


def render_cards_row(cards: "list[Card]", config: "GameConfig",
                     labels: list[str] | None = None) -> str:
    """Render a horizontal row of card blocks with optional labels above."""
    if not cards:
        return "  (none)"

    all_lines = [render_card_lines(c, config) for c in cards]
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

def render_tableau(state: "GameState") -> str:
    cfg = state.config
    lines: list[str] = []

    # Seeds
    seed_cards = state.tableau.seed_cards
    if seed_cards:
        lines.append(_bold("  SEEDS"))
        lines.append(render_cards_row(seed_cards, cfg))
        lines.append("")

    # Routes
    open_routes = [r for r in state.tableau.routes if r.is_valid]
    invalid_routes = [r for r in state.tableau.routes if not r.is_valid]

    if open_routes:
        lines.append(_bold("  ROUTES"))
        for route in open_routes:
            lines.append(_render_route_line(route, state))
        lines.append("")

    if invalid_routes:
        lines.append(_dim("  BROKEN"))
        for route in invalid_routes:
            lines.append(_dim(f"    {route.route_id}  ✗  {route.termination_reason.value}"))
        lines.append("")

    if not open_routes and not invalid_routes and not seed_cards:
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

    if route.endpoint_card_id:
        ep = state.lookup_card(route.endpoint_card_id)
        if ep:
            owner = f" · {ep.owner_id}" if ep.owner_id else ""
            status += f"  endpoint PKT {ep.packet_value}{owner}"

    return "    " + status


# ---------------------------------------------------------------------------
# Hand rendering
# ---------------------------------------------------------------------------

def render_hand(player: "PlayerState", state: "GameState",
                hints: list[str] | None = None) -> str:
    if not player.hand:
        return "  (hand empty)"
    labels = [str(i + 1) for i in range(len(player.hand))]
    block = render_cards_row(player.hand, state.config, labels=labels)
    lines = [block]
    if hints:
        hint_row = ""
        for hint in hints:
            width = _CARD_WIDTH + 2 + 2  # card width + borders + gap
            hint_row += hint[:width].ljust(width)
        lines.append("  " + hint_row)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scores + header
# ---------------------------------------------------------------------------

def render_scores(state: "GameState", human_index: int = 0) -> str:
    parts = []
    for i, p in enumerate(state.players):
        label = "you" if i == human_index else p.policy_name
        parts.append(f"{_bold(label)}  {p.score}")
    return "  " + "  │  ".join(parts)


def render_round_header(state: "GameState") -> str:
    cfg = state.config
    return (
        f"\n{'━' * 60}\n"
        f"  {_bold('PACKET PRESSURE')}  ·  "
        f"Round {state.round_number} of {cfg.max_rounds}  ·  "
        f"Score to win: {cfg.score_to_win}\n"
        f"{'━' * 60}"
    )


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
        if ct == "interference":
            return f"  {player}  played {card.card_id}  JAM"
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

    if etype == "INTERFERENCE_APPLIED":
        ch = event.get("channel", "?")
        return f"  {player}  jammed channel {channel_symbol(ch, cfg)}"

    if etype == "SCORE_AWARDED":
        pid = event.get("player_id", "?")
        score = event.get("score", 0)
        route = event.get("route_id", "?")
        return f"  {_bold('SCORE')}  {pid} +{score}  ({route} len {event.get('route_length', '?')})"

    return None
