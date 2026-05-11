# Packet Pressure

A card-game simulation framework for studying routing and packet-forwarding strategies.

## How to Play

### Goal
Be the first player to reach the score target (default: 2000 pts). If no one reaches it, whoever has the most points after the final round wins.

### Setup
Each round starts by dealing **seed cards** face-up into the shared tableau — one seed per player, drawn from the top of the shuffled deck. Seeds are ordinary route cards; the only thing special about them is when they enter play. Each player holds a starting hand of cards.

### On Your Turn
1. **Draw** one card from the deck into your hand.
2. **Play** one card from your hand onto the tableau.

### Channels
The network has three channels by default: **CH01** (teal), **CH02** (orange), **CH03** (purple). The number of channels is configurable — competitive presets use more. Route cards carry traffic *from* one channel *to* another. A card's **input channel** is where it receives; its **output channel** is where it forwards.

### Building Routes
A route is a chain of cards where each card's output channel matches the next card's input channel:

```
[CH01→CH02] → [CH02→CH03] → [CH03→CH01]
```

Any player can extend any open route. Whoever plays the **endpoint card** (the last card in the route when it terminates or scores at round end) earns the points — even if they didn't start the route. The game rewards being the finisher, not the builder.

Routes must be at least **2 cards long** to score. Routes are capped at **6 hops** by default (4 in the `fast` preset). One loop-prevention rule applies:
- A card cannot appear twice in the same route (`no_loops`)
- A route cannot output to a channel it has already visited (prevents channel loops within the route)

### Scoring
Score is awarded at **end of round** for eligible routes. Only the **endpoint card's packet value** scores — there is no cumulative sum. The player who owns the endpoint collects those points.

Open routes that haven't scored are **lost at round end** — the entire tableau is discarded. Only player hands persist between rounds. Finish routes within the round or lose them.

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
- Whoever plays the ACK claims that route's score — even if they played no other card in it
- Route must be ≥ 2 cards to score
- The terminated route stays visible in the tableau but can no longer be extended; it scores at end of round

### Broadcast
Terminates a route and applies a **score multiplier** (default ×2). Input channel must match the route's current tail.

- The Broadcast card's own packet value × multiplier is the score
- Higher risk than ACK (must channel-match) but higher reward

### Interference (JAM)
Jams a channel you choose. All cards currently outputting to that channel are immediately removed from the tableau and their routes are invalidated.

- Strong disruption — can wreck an opponent's long route at any time
- Also destroys your own cards if they output to the jammed channel

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

| Preset | Players | Seeds/round | Score to win | Rounds | Deck | Channels | Max hops |
|---|---|---|---|---|---|---|---|
| `default` | 4 | 4 | 2000 | 15 | 80 | 3 | 6 |
| `fast` | 3 | 3 | 1200 | 8 | 60 | 3 | 4 |
| `competitive`¹ | 5 | 5 | 3000 | 20 | 100 | 6 | 6 |
| `no_special` | 4 | 4 | 2000 | 15 | 80 (ROUTE only) | 3 | 6 |

Seeds per round match player count so every player has a fair chance of an opening move.

¹ `competitive` uses broadcast multiplier ×3 (all other presets use the default ×2).

## Policies

| Name | Strategy |
|---|---|
| `random` | Picks a random legal play |
| `greedy` | Maximises immediate score |
| `denial` | Prioritises disrupting opponents via JAM |
| `builder` | Focuses on completing long routes |
| `color_builder` | Like `builder`, with color-bonus awareness |

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
