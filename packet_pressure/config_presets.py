from .models import CollisionResolutionTiming, ColorMode, GameConfig

DEFAULT_CONFIG = GameConfig()

FAST_CONFIG = GameConfig(
    player_count=3,
    score_to_win=12,
    max_rounds=8,
    starting_hand_size=4,
    draw_per_turn=1,
    turns_per_player_per_round=1,
    seed_cards_per_round=2,
    route_min_length=2,
    route_max_hops=4,
    deck_size=60,
)

COMPETITIVE_CONFIG = GameConfig(
    player_count=5,
    score_to_win=30,
    max_rounds=20,
    channels=("01", "02", "03", "04", "05", "06"),
    channel_shapes=("circle", "square", "triangle", "diamond", "hexagon", "star"),
    channel_colors=("teal", "orange", "purple", "red", "blue", "green"),
    broadcast_multiplier=3,
    color_mode=ColorMode.SCORING_BONUS,
    color_bonus_same_route=2,
    collision_resolution_timing=CollisionResolutionTiming.END_OF_ROUND,
    deck_size=100,
)

NO_SPECIAL_CONFIG = GameConfig(
    special_distribution=(
        ("ack", 0.0),
        ("broadcast", 0.0),
        ("interference", 0.0),
    ),
    color_mode=ColorMode.IGNORE,
)

COLOR_SWEEP_BASE = GameConfig(
    color_mode=ColorMode.SCORING_BONUS,
    color_bonus_same_route=0,
    color_bonus_multiplier=1.0,
)
