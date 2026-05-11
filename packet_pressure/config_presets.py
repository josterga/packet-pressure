from .models import GameConfig

DEFAULT_CONFIG = GameConfig()

FAST_CONFIG = GameConfig(
    player_count=3,
    score_to_win=1200,
    max_rounds=8,
    starting_hand_size=4,
    draw_per_turn=1,
    turns_per_player_per_round=1,
    channels=("01", "02"),
    channel_shapes=("circle", "square"),
    channel_colors=("teal", "orange"),
    seed_cards_per_round=2,
    route_min_length=2,
    route_max_hops=2,
    deck_size=60,
)

COMPETITIVE_CONFIG = GameConfig(
    player_count=5,
    score_to_win=3000,
    max_rounds=20,
    channels=("01", "02", "03", "04"),
    channel_shapes=("circle", "square", "triangle", "diamond"),
    channel_colors=("teal", "orange", "purple", "red"),
    seed_cards_per_round=4,
    broadcast_multiplier=3,
    deck_size=100,
)

NO_SPECIAL_CONFIG = GameConfig(
    special_distribution=(
        ("ack", 0.0),
        ("broadcast", 0.0),
        ("interference", 0.0),
    ),
)
