# Packet Pressure

> Routes don't belong to their builders — they belong to whoever exits them.

**Packet Pressure** is a competitive card game for 3–5 players built on a packet-switching network.
Each round, players chain relay nodes across shared channels to build routing paths, but the points go to the finisher, not the architect. Extend what others started, or build something worth stealing.

*Every card you play either builds your lead or hands it to someone else.*

## How to Play

### Goal
Be the first player to reach the score target (default: 2000 pts). If no one reaches it, whoever has the most points after the final round wins.

### Setup
Each round starts by dealing **seed nodes** face-up into the shared tableau — one seed per channel, drawn from the top of the shuffled deck. Seed nodes are ordinary relay nodes; the only thing special about them is when they enter play. Because seed nodes must each occupy a distinct output channel, the number of seeds equals the number of channels — which is always fewer than the number of players. One player per round gets no anchor route and must extend or terminate an existing one. Each player holds a starting hand of cards.

### On Your Turn
1. **Draw** one card from the deck into your hand.
2. **Play** one card from your hand onto the tableau. Each card occupies a node in the route.

### Channels
The number of channels defines the network's **bandwidth** — how many routes can exist simultaneously. With N channels (and no channel reuse within a route), the natural maximum route length is also N nodes. The default network has three channels: **CH01** (teal), **CH02** (orange), **CH03** (purple). Relay nodes carry traffic *from* one channel *to* another. A node's **input channel** is where it receives; its **output channel** is where it forwards.

### Building Routes
A route is a chain of nodes where each node's output channel matches the next node's input channel:

```
[CH01→CH02] → [CH02→CH03] → [CH03→CH01]
```

Any player can extend any open route. Whoever plays the **exit node** (the last node in the route when it terminates or scores at round end) earns the points — even if they didn't start the route. The game rewards being the finisher, not the builder.

Routes must be at least **2 nodes long** to score. Routes are capped at **6 hops** by default (2 in the `fast` preset, matching its 2-channel network). In practice the channel-reuse rule hits the natural ceiling first: a 3-channel network can produce at most 3-node routes. One loop-prevention rule applies:
- A node cannot appear twice in the same route (`no_loops`)
- A route cannot output to a channel it has already visited (prevents channel loops within the route)

### Scoring
Score is awarded at **end of round** for eligible routes. Only the **exit node's packet value** scores — there is no cumulative sum. The player who owns the exit node collects those points.

At round end, **all valid routes of at least 2 nodes score**, whether they were explicitly terminated (by a terminal node, amplifier node, or hitting the hop limit) or still open. A route that was never terminated simply scores with whoever owns its current exit node. Routes shorter than 2 nodes are lost without scoring. After scoring, the entire tableau is discarded — only player hands carry over. Hands are then topped back up to the starting hand size before the next round begins.

The player who scored the most points in a round goes first in the next round. Going first is a disadvantage — you act before others can react to what you build. On a tied round (multiple players share the highest score), turn order is unchanged.

---

## Card Types

### Relay Node
Forwards a packet from one channel to another. Extends an existing route whose last output channel matches this node's input channel, or starts a new route if it doesn't match any open route.

- **Input channel**: must match the route's current tail
- **Output channel**: becomes the new tail; cannot be a channel the route has already visited
- **Packet value**: scores if this node is the exit node

### Terminal Node
Terminates a chosen route immediately. Input is `ANY` (matches any open route). Output is `TERM`.

- Only playable on routes that are already ≥ 2 nodes — terminal node is a steal/close card, not a route-builder
- When played, you choose which eligible open route to terminate
- The terminal node becomes the exit node, so **the terminal node's own packet value** is what scores — even if you played no other node in the route
- The terminated route stays visible in the tableau but can no longer be extended; it scores at end of round

### Amplifier Node
Extends a route like a relay node — input channel must match the route's current tail, output channel becomes the new tail. If the amplifier node is the exit node when scoring happens, the score is `packet_value × multiplier` (default ×2) instead of the raw value.

- Higher reward than a plain relay node when you hold the exit node
- Can be extended further by other nodes (it does not terminate the route)
- Self-loop channel pairs (in = out) are not generated

### Noise
Disrupts a channel, destroying all nodes in **scoring-eligible routes** (≥ 2 nodes) that output to that channel. Those routes are immediately invalidated.

- Only playable when at least one scoring-eligible route exists; the target channel must be one used by a node in such a route
- Routes shorter than 2 nodes are not affected — noise is precision disruption, not a blanket nuke
- Also invalidates your own scoring routes if they output to the noised channel

### Filter Node
Extends a route like a relay node — input channel must match the route's current tail, output channel becomes the new tail. If a noise card targets the filter node's input channel, the entire route is immune: the noise is absorbed without invalidating any cards.

- Protects the route it's part of from noise targeting its input channel
- Works passively — no player action required to activate the filter
- Can be extended further; it does not terminate the route

### Visual reference

In the terminal UI, each card's left border is colored by input channel and right border by output channel (teal = CH01, orange = CH02, purple = CH03).

**Relay node** — forwards a packet from one channel to another.

```
┌──────────────────┐
│ IN CH01   CH02 OUT│
│──────────────────│
│  PKT  200        │
│──────────────────│
│        PKT-0001  │
└──────────────────┘
```

**Terminal node** — closes any open route immediately; earns points on its own packet value.

```
┌──────────────────┐
│ IN ANY    END OUT│
│──────────────────│
│  ─── TERM ──     │
│  PKT  500        │
│──────────────────│
│        TERM-0001 │
└──────────────────┘
```

**Amplifier node** — extends a route; multiplies packet value (×2 default) if it's the exit node at scoring.

```
┌──────────────────┐
│ IN CH02   CH03 OUT│
│──────────────────│
│  AMP   ×2        │
│  PKT  300        │
│──────────────────│
│        AMP-0001  │
└──────────────────┘
```

**Noise** — disrupts a channel, invalidating all scoring-eligible routes that output to it.

```
┌──────────────────┐
│ IN  --    --  OUT│
│──────────────────│
│  NOISE ≋≋≋≋      │
│  PKT  0          │
│──────────────────│
│       NOISE-0001 │
└──────────────────┘
```

**Filter node** — extends a route and absorbs noise targeting its input channel, protecting the route.

```
┌──────────────────┐
│ IN CH01   CH02 OUT│
│──────────────────│
│  FLT-CH01        │
│  PKT  200        │
│──────────────────│
│        FLT-0001  │
└──────────────────┘
```

---

## Collisions

Collisions are **route-scoped only** — nodes in different routes do not collide with each other.

Within a route, a node cannot output to a channel the route has already visited. If a node would create a channel loop (e.g., a route already passed through CH02, and a new node would output back to CH02), it cannot extend that route and instead starts a new one.

Seed nodes are dealt with unique output channels to prevent immediate conflicts at round start.

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

| Preset | Players | Channels | Seed nodes/round | Score to win | Rounds | Deck | Max hops |
|---|---|---|---|---|---|---|---|
| `default` | 4 | 3 | 3 | 2000 | 15 | 80 | 6 |
| `fast` | 3 | 2 | 2 | 1200 | 8 | 60 | 2 |
| `competitive` | 5 | 4 | 4 | 3000 | 20 | 100 | 6 |
| `no_special` | 4 | 3 | 3 | 2000 | 15 | 80 (relay only) | 6 |

Seed nodes per round equal the channel count — always one fewer than the player count. One player per round competes without an anchor route.

`competitive` uses amplifier multiplier ×3 (all other presets use the default ×2).

## Policies

| Name | Strategy |
|---|---|
| `random` | Picks a random legal play |
| `greedy` | Maximises immediate score |
| `denial` | Prioritises disrupting opponents via noise; falls back to terminal-node-stealing scoreable routes |
| `builder` | Focuses on completing long routes |

## Interactive Play

`--interactive` puts you in one player slot; AIs fill the rest. `--solo` gives you control of every player's turn — useful for learning rules and exploring game states without AI noise.

Player count in interactive and solo modes is determined by `--policies` (default: `greedy denial`), giving 3 players total. Pass `--policies greedy denial builder` for 4, etc. The preset's player count is ignored in these modes.

Each turn shows your full hand with all legal plays listed per node. After you play, the result (extension, block, noise, etc.) prints immediately before opponent turns.

## Reproducibility

Pass `--seed N` for a fully deterministic run. A master seed generates per-game seeds, so the entire batch is reproducible from one number. Omitting `--seed` uses OS entropy (different each run).

## Parameter Sweep

Sweep any `GameConfig` field across a range of values:

```bash
python -m packet_pressure.run_experiment \
  --sweep-param amplifier_multiplier \
  --sweep-values 1 2 3 4 \
  --n-games 500 --seed 0
```

Results for each value are written as separate batches under `--output-dir`. Batch CSV output includes `avg_legal_moves_per_turn` — a measure of game branching factor useful for tuning.

## Testing & Tuning

### Running the suite

```bash
pytest tests/                        # all tests
pytest tests/test_engine.py -v       # one file, verbose
pytest -k "NoiseNode"                # one class by name
```

### What each suite verifies

| File | What you learn |
|---|---|
| `test_engine.py` | Core rule correctness: channel matching, hop limit, loop prevention, terminal node wildcard/scoring, amplifier multiplier at scoring, noise precision (spares routes shorter than `route_min_length`), exit-node-only scoring, full-game determinism |
| `test_simulation.py` | Simulation harness: `run_simulation` returns valid `GameMetrics`, batch win rates sum to ~1, `sweep_parameter` updates config correctly and leaves the base config unchanged |
| `test_metrics.py` | Metric validity: scores non-negative, winner valid, 5 rate metrics ∈ [0,1], policy names recorded, round count within `max_rounds` |
| `test_models.py` | Data integrity: frozen dataclasses reject mutation, `Card`/`Route`/`Tableau` state, ID generation |
| `test_policies.py` | AI legal-move safety: every policy returns a node from the player's hand, noise requires a scoring-eligible target, all 4 policies complete a full game without errors |

### Key batch metrics and what they signal

After a batch run, the CSV output and printed summary include these fields:

| Metric | High value means | Low value means |
|---|---|---|
| `pct_routes_stopped_by_hop_limit` | Hop limit is the binding constraint — routes are dense | Routes are being stolen (terminal) or noised before they max out |
| `amplifier_score_rate` | Amplifier nodes are frequently the exit node when scoring | Amplifier nodes are getting extended past or noised |
| `terminal_steal_rate` | Terminal node is used aggressively to close opponents' routes | Players are either building or noising instead |
| `seed_node_utilization_rate` | Seed nodes regularly get extended into scoring routes | Lots of orphaned single-node seeds (no one extended them) |
| `turn_pct_extending_vs_starting` | Players build on existing routes more than they start fresh | Players frequently start isolated routes |
| `avg_legal_moves_per_turn` | High branching factor — game state is complex | Few choices per turn — useful floor for tuning |

### What to tune and how

Use `--sweep-param` to vary a single `GameConfig` field across values and compare results:

```bash
# Does the hop limit actually constrain routes?
python -m packet_pressure.run_experiment \
  --sweep-param route_max_hops --sweep-values 2 3 4 6 \
  --n-games 500 --seed 0

# How much does the amplifier multiplier shift win rates?
python -m packet_pressure.run_experiment \
  --sweep-param amplifier_multiplier --sweep-values 1 2 3 4 \
  --n-games 500 --seed 0

# Does player count change strategy balance?
python -m packet_pressure.run_experiment \
  --sweep-param player_count --sweep-values 2 3 4 5 \
  --n-games 500 --seed 0
```

Each sweep value runs as a separate batch under `--output-dir`, producing per-value CSVs and plots.

### Game mode quick reference

| Mode | Command | What it does |
|---|---|---|
| AI batch | `python -m packet_pressure.run_experiment` | N games, all AI, outputs stats and plots |
| Human vs AI | `--interactive` | You play one slot; AI fills the rest |
| Solo / hot-seat | `--solo` | You control every player's turn — no AI |
| Deterministic | add `--seed 42` | Any mode becomes fully reproducible |

In both interactive modes, player count is set by `--policies` (default: `greedy denial` → 3 players total). Add more policy names for more players. The preset's player count is ignored.
