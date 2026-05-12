from .models import GameConfig

DEFAULT_CONFIG = GameConfig()

FAST_CONFIG = GameConfig(
    player_count=3,
    score_to_win=1200,
    max_rounds=4,
    starting_hand_size=4,
    draw_per_turn=1,
    turns_per_player_per_round=2,
    channels=("01", "02", "03"),
    channel_shapes=("circle", "square", "triangle"),
    channel_colors=("teal", "orange", "purple"),
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
    route_max_hops=6,
    amplifier_multiplier=3,
    deck_size=100,
)

PRINT_CONFIG = GameConfig(
    relay_node_exact_distribution=True,
    relay_node_distribution=(
        (("01", "02"), 1.0),
        (("01", "03"), 1.0),
        (("02", "01"), 1.0),
        (("02", "03"), 1.0),
        (("03", "01"), 1.0),
        (("03", "02"), 1.0),
    ),
    special_distribution=(
        ("terminal", 0.10),
        ("amplifier", 0.05),
        ("noise", 0.05),
        ("filter", 0.05),
    ),
)

NO_SPECIAL_CONFIG = GameConfig(
    special_distribution=(
        ("terminal", 0.0),
        ("amplifier", 0.0),
        ("noise", 0.0),
        ("filter", 0.0),
    ),
)
