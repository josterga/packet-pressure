import dataclasses
import pytest
import numpy as np
from packet_pressure.deck import DeckBuilder
from packet_pressure.models import (
    Card,
    CardType,
    GameConfig,
    RouteState,
    TableauState,
    TerminationReason,
)


def test_game_config_frozen():
    cfg = GameConfig()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        cfg.player_count = 99  # type: ignore


def test_game_config_replace():
    cfg = GameConfig()
    cfg2 = dataclasses.replace(cfg, player_count=5)
    assert cfg2.player_count == 5
    assert cfg.player_count == 4


def test_game_config_defaults():
    cfg = GameConfig()
    assert cfg.channels == ("01", "02", "03")
    assert cfg.route_min_length == 2
    assert cfg.route_max_hops == 3


def test_game_config_channel_helpers():
    cfg = GameConfig()
    assert cfg.channel_index("01") == 0
    assert cfg.channel_shape("01") == "circle"
    assert cfg.channel_color("01") == "teal"
    assert cfg.channel_index("99") is None


def test_card_frozen():
    card = Card(
        card_id="PKT-0001",
        card_type=CardType.RELAY,
        input_channel="01",
        output_channel="02",
        packet_value=200,
        color="red",
    )
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        card.packet_value = 999  # type: ignore


def test_card_with_owner():
    card = Card(
        card_id="PKT-0001",
        card_type=CardType.RELAY,
        input_channel="01",
        output_channel="02",
        packet_value=200,
        color="red",
    )
    assert card.owner_id is None
    owned = card.with_owner("P0")
    assert owned.owner_id == "P0"
    assert card.owner_id is None  # original unchanged


def test_card_special_accessor():
    card = Card(
        card_id="AMP-0001",
        card_type=CardType.AMPLIFIER,
        input_channel="01",
        output_channel="02",
        packet_value=300,
        color="blue",
        special_properties=(("multiplier", 2),),
    )
    assert card.special("multiplier") == 2
    assert card.special("nonexistent", default=99) == 99


def test_terminal_card_channels():
    card = Card(
        card_id="TERM-0001",
        card_type=CardType.TERMINAL,
        input_channel="ANY",
        output_channel="TERM",
        packet_value=400,
        color="green",
    )
    assert card.input_channel == "ANY"
    assert card.output_channel == "TERM"


def test_route_state_properties():
    r = RouteState(
        route_id="R-0001",
        card_ids=["C1", "C2"],
        channels_in_route=["01", "02"],
        entry_channel="01",
        length=2,
    )
    assert r.last_output_channel == "02"
    assert r.first_input_channel == "01"
    assert r.is_open() is True


def test_route_state_closed():
    r = RouteState(route_id="R-0001", termination_reason=TerminationReason.TERMINAL)
    assert r.is_open() is False


def test_tableau_next_route_id():
    t = TableauState()
    id1 = t.next_route_id()
    id2 = t.next_route_id()
    assert id1 == "R-0001"
    assert id2 == "R-0002"


def test_relay_card_id_prefix():
    cfg = GameConfig()
    deck = DeckBuilder(cfg, np.random.default_rng(0)).build()
    relay_ids = [c.card_id for c in deck if c.card_type == CardType.RELAY]
    assert len(relay_ids) > 0
    assert all(cid.startswith("REL-") for cid in relay_ids)
