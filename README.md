# Packet Pressure

A card-game simulation framework for studying routing and packet-forwarding strategies.

## How to Play

### Goal
Be the first player to reach the score target (default: 2000 pts). If no one reaches it, whoever has the most points after the final round wins.

### Setup
Each round starts by dealing **seed cards** face-up into the shared tableau — one seed per channel, drawn from the top of the shuffled deck. Seeds are ordinary route cards; the only thing special about them is when they enter play. Because seeds must each occupy a distinct output channel, the number of seeds equals the number of channels — which is always fewer than the number of players. One player per round gets no anchor route and must extend or terminate an existing one. Each player holds a starting hand of cards.

### On Your Turn
1. **Draw** one card from the deck into your hand.
2. **Play** one card from your hand onto the tableau.

### Channels
The number of channels defines the network's **bandwidth** — how many routes can exist simultaneously. With N channels (and no channel reuse within a route), the natural maximum route length is also N cards. The default network has three channels: **CH01** (teal), **CH02** (orange), **CH03** (purple). Route cards carry traffic *from* one channel *to* another. A card's **input channel** is where it receives; its **output channel** is where it forwards.

### Building Routes
A route is a chain of cards where each card's output channel matches the next card's input channel:

```
[CH01→CH02] → [CH02→CH03] → [CH03→CH01]
```

Any player can extend any open route. Whoever plays the **endpoint card** (the last card in the route when it terminates or scores at round end) earns the points — even if they didn't start the route. The game rewards being the finisher, not the builder.

Routes must be at least **2 cards long** to score. Routes are capped at **6 hops** by default (2 in the `fast` preset, matching its 2-channel network). In practice the channel-reuse rule hits the natural ceiling first: a 3-channel network can produce at most 3-card routes. One loop-prevention rule applies:
- A card cannot appear twice in the same route (`no_loops`)
- A route cannot output to a channel it has already visited (prevents channel loops within the route)

### Scoring
Score is awarded at **end of round** for eligible routes. Only the **endpoint card's packet value** scores — there is no cumulative sum. The player who owns the endpoint collects those points.

At round end, **all valid routes of at least 2 cards score**, whether they were explicitly terminated (by ACK, Broadcast, or hitting the hop limit) or still open. A route that was never terminated simply scores with whoever owns its current endpoint card. Routes shorter than 2 cards are lost without scoring. After scoring, the entire tableau is discarded — only player hands carry over. Hands are then topped back up to the starting hand size before the next round begins.

---

## Card Types

### Route Card
Forwards a packet from one channel to another. Extends an existing route whose last output channel matches this card's input channel, or starts a new route if it doesn't match any open route.

- **Input channel**: must match the route's current tail
- **Output channel**: becomes the new tail; cannot be a channel the route has already visited
- **Packet value**: scores if this card is the endpoint

### ACK
Terminates a chosen route immediately. Input is `ANY` (matches any open route). Output is `TERM`.

- When played, you choose which open route to ACK
- The ACK card becomes the endpoint of that route, so **the ACK card's own packet value** is what scores — even if you played no other card in the route
- Route must be ≥ 2 cards (including the ACK) to score
- The terminated route stays visible in the tableau but can no longer be extended; it scores at end of round

### Broadcast
Extends a route like a Route card — input channel must match the route's current tail, output channel becomes the new tail. If the Broadcast card is the endpoint when scoring happens, the score is `packet_value × multiplier` (default ×2) instead of the raw value.

- Higher reward than a plain Route card when you hold the endpoint
- Can be extended further by other cards (it does not terminate the route)
- Self-loop channel pairs (in = out) are not generated

### Interference (JAM)
Jams a channel, destroying all cards in **scoring-eligible routes** (≥ 2 cards) that output to that channel. Those routes are immediately invalidated.

- Only playable when at least one scoring-eligible route exists; the target channel must be one used by a card in such a route
- Routes shorter than 2 cards are not affected — JAM is precision disruption, not a blanket nuke
- Also invalidates your own scoring routes if they output to the jammed channel

---

## Collisions

Collisions are **route-scoped only** — cards in different routes do not collide with each other.

Within a route, a card cannot output to a channel the route has already visited. If a card would create a channel loop (e.g., a route already passed through CH02, and a new card would output back to CH02), it cannot extend that route and instead starts a new one.

Seed cards are dealt with unique output channels to prevent immediate conflicts at round start.

---

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
| `--policies` | `random greedy denial builder` | Space-separated AI policy list |
| `--n-games` | `200` | Number of games per batch |
| `--seed` | random | Master RNG seed (omit for a different game each run) |
| `--workers` | `1` | Parallel workers for batch runs |
| `--output-dir` | `./results` | Where to write results and plots |
| `--no-plots` | — | Skip chart generation |
| `--interactive` | — | Play as a human against AI opponents |
| `--solo` | — | Hot-seat mode: human controls every player's turn |
| `--human-index` | `0` | Which player slot the human takes (interactive mode) |
| `--opponent-delay` | `0.5` | Pause in seconds after each AI turn |

## Config Presets

| Preset | Players | Channels | Seeds/round | Score to win | Rounds | Deck | Max hops |
|---|---|---|---|---|---|---|---|
| `default` | 4 | 3 | 3 | 2000 | 15 | 80 | 6 |
| `fast` | 3 | 2 | 2 | 1200 | 8 | 60 | 2 |
| `competitive` | 5 | 4 | 4 | 3000 | 20 | 100 | 6 |
| `no_special` | 4 | 3 | 3 | 2000 | 15 | 80 (ROUTE only) | 6 |

Seeds per round equal the channel count — always one fewer than the player count. One player per round competes without an anchor route.

`competitive` uses broadcast multiplier ×3 (all other presets use the default ×2).

## Policies

| Name | Strategy |
|---|---|
| `random` | Picks a random legal play |
| `greedy` | Maximises immediate score |
| `denial` | Prioritises disrupting opponents via JAM; falls back to ACK-stealing scoreable routes |
| `builder` | Focuses on completing long routes |

## Interactive Play

`--interactive` puts you in one player slot; AIs fill the rest. `--solo` gives you control of every player's turn — useful for learning rules and exploring game states without AI interference.

Player count in interactive and solo modes is determined by `--policies` (default: `greedy denial`), giving 3 players total. Pass `--policies greedy denial builder` for 4, etc. The preset's player count is ignored in these modes.

Each turn shows your full hand with all legal plays listed per card. After you play, the result (extension, block, JAM, etc.) prints immediately before opponent turns.

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

Results for each value are written as separate batches under `--output-dir`. Batch CSV output includes `avg_legal_moves_per_turn` — a measure of game branching factor useful for tuning.

## Running Tests

```bash
pytest tests/
```
