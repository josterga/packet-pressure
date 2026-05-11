# Packet Pressure

A card-game simulation framework for studying routing and packet-forwarding strategies.

## Game Overview

Players compete to score points by building packet routes across shared network channels. Each turn a player plays a card from their hand to extend a route, terminate it, or disrupt opponents. The first player to reach `score_to_win` points wins; if no one does, the game ends after `max_rounds`.

**Default config:** 4 players, 80-card deck, 5-card starting hand, first to 20 points.

## Card Types

| Type | Effect |
|---|---|
| `ROUTE` | Extend a packet route from one channel to another |
| `ACK` | Terminate a route and collect its score |
| `BROADCAST` | Terminate a route with a score multiplier |
| `INTERFERENCE` | Jam a channel, invalidating active routes through it |

## Install

```bash
pip install -r requirements.txt
```

Dependencies: `numpy`, `matplotlib`, `seaborn`, `pytest`.

## Usage

```bash
python -m packet_pressure.run_experiment [OPTIONS]
```

Key flags:

| Flag | Default | Description |
|---|---|---|
| `--preset` | `default` | Config preset: `default`, `fast`, `competitive`, `no_special` |
| `--policies` | `random greedy denial builder` | Space-separated list of player policies |
| `--n-games` | `200` | Number of games per batch |
| `--seed` | `42` | Master seed for reproducibility |
| `--workers` | `1` | Parallel workers for batch runs |
| `--output-dir` | `./results` | Where to write results and plots |
| `--no-plots` | — | Skip chart generation |
| `--interactive` | — | Play as a human against AI opponents |
| `--human-index` | `0` | Which player slot the human takes |

## Config Presets

| Preset | Players | Score to win | Rounds | Deck |
|---|---|---|---|---|
| `default` | 4 | 20 | 15 | 80 |
| `fast` | 3 | 12 | 8 | 60 |
| `competitive` | 5 | 30 | 20 | 100 |
| `no_special` | 4 | 20 | 15 | 80 (ROUTE only) |

## Policies

| Name | Strategy |
|---|---|
| `random` | Picks a random legal play |
| `greedy` | Maximises immediate score |
| `denial` | Prioritises blocking opponents via collisions |
| `builder` | Focuses on completing long routes |
| `color_builder` | Like `builder`, with color-bonus awareness |

## Reproducibility

Pass `--seed N` for a fully deterministic run. A master seed generates per-game seeds, so the entire batch is reproducible from one number. Omitting `--seed` uses OS entropy (different each run).

## Parameter Sweep

Sweep any `GameConfig` field across a range of values:

```bash
python -m packet_pressure.run_experiment \
  --sweep-param broadcast_multiplier \
  --sweep-values 1 2 3 4 \
  --n-games 500 --seed 0
```

Results for each value are written as separate batches under `--output-dir`.

## Running Tests

```bash
pytest tests/
```
