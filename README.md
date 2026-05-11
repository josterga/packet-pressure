# Packet Pressure

A card-game simulation framework for studying routing and packet-forwarding strategies.

## How to Play

### Goal
Be the first player to reach the score target (default: 20 pts). If no one reaches it, whoever has the most points after the final round wins.

### Setup
Each round starts by dealing **seed cards** face-up into the shared tableau — these are ordinary route cards drawn from the top of the shuffled deck. Seeds bootstrap the network so players have something to build on immediately. Each player then holds a hand of cards.

### On Your Turn
1. **Draw** one card from the deck into your hand.
2. **Play** one card from your hand onto the tableau.

Playing a card can do one of four things depending on card type (see below). After you play, the tableau is checked for collisions, then routes are updated.

### Channels
The network has five channels: **CH01** (teal), **CH02** (orange), **CH03** (purple), **CH04** (red), **CH05** (blue). Route cards carry traffic *from* one channel *to* another. A card's **input channel** is where it receives, its **output channel** is where it forwards.

### Building Routes
A route is a chain of cards where each card's output channel matches the next card's input channel:

```
[CH01→CH02] → [CH02→CH03] → [CH03→CH04]
```

Any player can extend any open route. Whoever plays the **endpoint card** (the last card when a route terminates or scores) earns the points — even if they didn't start the route.

Routes must be at least **2 cards long** to score. Routes are capped at **6 hops** and cannot loop back to their starting channel.

### Scoring
Score is awarded at **end of round** for eligible routes. Only the **endpoint card's packet value** scores — there is no cumulative sum. The player who owns the endpoint collects those points.

Routes that are still open (not yet terminated) carry over to the next round.

### End of Round
All cards on the tableau are discarded at round end. Any route that didn't score this round is gone. Players keep their hands. New seeds are dealt and play continues.

---

## Card Types

### Route Card
Forwards a packet from one channel to another. Extends an existing route whose last output channel matches this card's input channel, or starts a new route from any seed card.

- **Input channel**: must match the route's current tail
- **Output channel**: becomes the new tail
- **Packet value**: scores if this card is the endpoint

### ACK
Terminates a route immediately. Input is `ANY` (matches any open route's tail). Output is `TERM` (route ends here).

- Whoever plays the ACK claims the route's score — even if they played no other card in that route
- Route must be ≥ 2 cards to score

### Broadcast
Terminates a route and applies a **score multiplier** (default ×2). Input channel must match the route's current tail like a normal route card.

- The Broadcast card's own packet value × multiplier is the score
- Useful for ending a long route with a high-value card

### Interference (JAM)
Jams a channel you choose. All cards currently outputting to that channel are **immediately removed** from the tableau and any routes they belong to are invalidated.

- Powerful disruption tool — can wreck an opponent's long route at the last moment
- Also affects your own cards if they output to the jammed channel

---

## Collisions

If two or more cards in the tableau share the same **output channel**, they collide — both are removed immediately and their routes are invalidated. This includes seeds.

Collisions happen after every card played, so placing a card onto an already-contested channel destroys both cards. Use this deliberately to deny opponents, or avoid it to protect your own routes.

Seed cards are dealt with unique output channels to prevent instant collisions at round start.

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
| `--seed` | random | Master seed for reproducibility (omit for a different game each run) |
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
