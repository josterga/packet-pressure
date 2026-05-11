from __future__ import annotations

import concurrent.futures
import dataclasses
from typing import Any

import numpy as np

from .deck import DeckBuilder
from .engine import GameEngine
from .metrics import BatchResult, GameMetrics, MetricsCollector
from .models import GameConfig
from .policies import PlayerPolicy


def run_simulation(
    config: GameConfig,
    policies: list[PlayerPolicy],
    seed: int | None = None,
) -> GameMetrics:
    rng = np.random.default_rng(seed)
    deck = DeckBuilder(config, rng).build()
    engine = GameEngine(config, policies, deck, rng)
    final_state = engine.run()
    return MetricsCollector(final_state, game_seed=seed or 0).collect()


def run_batch(
    config: GameConfig,
    policies: list[PlayerPolicy],
    n_games: int,
    seed: int | None = None,
    n_workers: int = 1,
) -> BatchResult:
    seeds = _make_per_game_seeds(seed, n_games)
    policy_names = [p.name for p in policies]

    if n_workers > 1:
        args = [(config, policies, s) for s in seeds]
        with concurrent.futures.ProcessPoolExecutor(max_workers=n_workers) as ex:
            games = list(ex.map(_run_single, args))
    else:
        games = [run_simulation(config, policies, s) for s in seeds]

    return BatchResult(
        config=config,
        policy_names=policy_names,
        n_games=n_games,
        games=games,
    )


def sweep_parameter(
    base_config: GameConfig,
    param_name: str,
    values: list[Any],
    policies: list[PlayerPolicy],
    n_games: int,
    seed: int | None = None,
    n_workers: int = 1,
) -> list[BatchResult]:
    valid_fields = {f.name for f in dataclasses.fields(GameConfig)}
    if param_name not in valid_fields:
        raise ValueError(
            f"'{param_name}' is not a valid GameConfig field. "
            f"Valid fields: {sorted(valid_fields)}"
        )

    results = []
    rng = np.random.default_rng(seed)
    sweep_seeds = [int(rng.integers(2**31)) for _ in values]

    for value, sweep_seed in zip(values, sweep_seeds):
        variant = dataclasses.replace(base_config, **{param_name: value})
        batch = run_batch(variant, policies, n_games, seed=sweep_seed, n_workers=n_workers)
        results.append(batch)

    return results


def _make_per_game_seeds(master_seed: int | None, n_games: int) -> list[int]:
    rng = np.random.default_rng(master_seed)
    return [int(x) for x in rng.integers(2**31, size=n_games)]


def _run_single(args: tuple) -> GameMetrics:
    config, policies, seed = args
    return run_simulation(config, policies, seed)
