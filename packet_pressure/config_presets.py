from .models import GameConfig

DEFAULT_CONFIG = GameConfig()

FAST_CONFIG = GameConfig(
    player_count=3,
    score_to_win=1200,
    max_rounds=4,
    starting_hand_size=4,
    draw_per_turn=1,
    turns_per_player_per_round=2,
    channels=("01", "02"),
    channel_shapes=("circle", "square"),
    channel_colors=("teal", "orange"),
    seed_nodes_per_round=2,
    route_min_length=2,
    route_max_hops=3,
    deck_size=60,
)

COMPETITIVE_CONFIG = GameConfig(
    player_count=5,
    score_to_win=3000,
    max_rounds=6,
    turns_per_player_per_round=4,
    channels=("01", "02", "03", "04"),
    channel_shapes=("circle", "square", "triangle", "diamond"),
    channel_colors=("teal", "orange", "purple", "red"),
    seed_nodes_per_round=4,
    amplifier_multiplier=3,
    deck_size=100,
)

NO_SPECIAL_CONFIG = GameConfig(
    special_distribution=(
        ("terminal", 0.0),
        ("amplifier", 0.0),
        ("noise", 0.0),
        ("filter", 0.0),
    ),
)
