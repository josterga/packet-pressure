```
⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠
⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘

       P A C K E T   P R E S S U R E
       Extend the route. Own the endpoint.

⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕
⊕─⇒─⊘─⊣─⚠─⊕─⇒─⊘─⊣─⚠─⊕─⇒─⊘─⊣─⚠─⊕─⇒─⊘─⊣─⚠
```

A competitive routing game where routes are public infrastructure and endpoints are private wins. · 3–5 players · ~30–45 min

## Overview

Packet Pressure is a competitive card game built on a packet-switching network. Each round, players chain relay nodes across shared channels to build routing paths — but points go to the finisher, not the architect. Extend what others started, or build something worth stealing.

Every card you play either builds your lead or hands it to someone else.

## What's in the Box

- Card deck — relay nodes, amplifiers, filters, terminals, and noise cards
- This guidebook

## Goal

Be the first player to reach 2,000 points. If no one reaches the target, whoever has the most points after the final round wins.

## Setting Up

1. Shuffle the full deck.
2. Deal seed nodes face-up into the shared play area (the tableau) — one per channel. With the default 3-channel network, 3 seed nodes enter play. Seed nodes are always relay, amplifier, or filter cards — terminal and noise cards are never dealt as seeds.
3. Deal each player a starting hand of 4 cards.
4. The player to the left of the dealer goes first.

Why fewer seeds than players? Because channels < players, at least one player each round has no anchor route — they must extend or steal an existing one.

## The Tableau

The tableau is the shared play area where all routes are built. Routes are open (extendable) or closed (scored and done).

## Channels

The network runs on three channels:

| Channel | Color  |
|---------|--------|
| CH01    | Teal   |
| CH02    | Orange |
| CH03    | Purple |

Channels define how cards connect. Every node has an input channel (where it receives a packet) and an output channel (where it forwards one). A route is a chain where each node's output matches the next node's input.

Example route:

```
[CH01→CH02] → [CH02→CH03] → [CH03→CH01]
```

## Your Turn

Each turn has two steps — in order:

1. **Draw** one card from the deck into your hand.
   If the deck is empty, shuffle the discard pile face-down. Play never stalls for cards.

2. **Play** one card from your hand onto the tableau.
   Extend an existing open route, or start a new one (if the concurrent cap allows).

## Building Routes

A route is a chain of nodes where each node's output channel matches the next node's input channel. Routes grow one card per turn — anyone can extend any open route. Each card added to a route counts as one hop.

Key rules:

- Routes must be at least 2 nodes long to score.
- Routes are capped at 4 hops (3 hops in the fast preset).
- A route cannot visit the same channel twice — no channel loops within a route.
- No more than 3 routes can be open at the same time (one per channel). Once a route closes, its slot frees up.

**Passing your turn:** You may only pass if the concurrent cap is full and none of your cards can extend any open route. You still draw a card; you just don't play one.

## Carried Routes

Open routes that are too short to score (under 2 nodes) at round end carry over into the next round. Each carried route reduces the seed count for that round by one, keeping the open-route cap intact. Carried routes remain in the tableau and can be extended normally.

## Scoring

Points are awarded at the end of every round.

Only the exit node's packet value scores — there is no cumulative sum across the whole route. The player who owns the exit node collects those points.

- **Exit node** = the last node in a route when it scores (whoever played it owns it)
- Any route of ≥ 2 nodes scores at round end, whether it was explicitly terminated or left open
- Routes under 2 nodes never score that round — they carry over instead

After scoring:

- All scored routes are discarded
- Carried routes stay in the tableau
- Hands are topped back up to 4 cards before the next round begins

Going first is a disadvantage — you act before others can react to your builds. The player who scored the most points in a round goes first next round. On a tie, turn order is unchanged.

---

## Card Types

### ⇒ Relay Node

Forwards a packet from one channel to another. The backbone of every route.

```
┌──────────────────┐
│ IN CH01 CH02 OUT │
│──────────────────│
│  ⇒               │
│  PKT  200        │
│──────────────────│
│        PKT-0001  │
└──────────────────┘
```

- To extend a route: your card's input channel must match the route's current tail
- Output channel becomes the new tail; cannot be a channel the route has already visited
- If no open route can be extended and the cap isn't full, this card starts a new route
- Scores only if it's the exit node at round end

### ⊣ Terminal Node

Closes any open route immediately and claims its points.

```
┌──────────────────┐
│ IN ANY   END OUT │
│──────────────────│
│  ⊣  ─ TERM ─     │
│  PKT  500        │
│──────────────────│
│        TERM-0001 │
└──────────────────┘
```

- Matches any open route (no channel check required)
- Only playable on routes already ≥ 2 nodes long — you can't close a stub
- You declare which eligible route to terminate
- The terminal node's own packet value is what scores — even if you never played another card in that route
- Cannot start a new route

The steal card. Drop a terminal on someone's nearly-finished route and walk away with everything they built.

### ⊕ Amplifier Node

Extends a route like a relay — but if it's the exit node when the round scores, the packet value is doubled (×2 by default).

```
┌──────────────────┐
│ IN CH02 CH03 OUT │
│──────────────────│
│  ⊕  AMP  ×2      │
│  PKT  300        │
│──────────────────│
│        AMP-0001  │
└──────────────────┘
```

- Input/output rules identical to a relay node
- Multiplier only activates if the amplifier is the exit node at scoring — if anyone plays on top of it, the bonus is lost and the new exit node scores at face value
- Does not terminate the route; can be extended further

Protect your amplifiers. Leaving one exposed at the tail of a route is an invitation for someone to extend past it and steal the bonus.

### ⊘ Filter Node

Extends a route like a relay — but passively shields the entire route from noise targeting its input channel.

```
┌──────────────────┐
│ IN CH01 CH02 OUT │
│──────────────────│
│  ⊘  FLT-CH01     │
│  PKT  200        │
│──────────────────│
│        FLT-0001  │
└──────────────────┘
```

- Input/output rules identical to a relay node
- If a noise card targets the filter's input channel, the route is immune — noise is absorbed, no cards are destroyed
- Noise targeting any other channel provides no protection
- No action required; protection is automatic
- Does not terminate the route; can be extended further

Use filters to insure your investment. A long route is a tempting noise target — a well-placed filter removes that threat.

### ⚠ Noise

Disrupts a channel, destroying all scoring-eligible routes (≥ 2 nodes) that output to that channel.

```
┌──────────────────┐
│ IN  --   --  OUT │
│──────────────────│
│  ⚠  NOISE ≋≋     │
│  PKT  0          │
│──────────────────│
│       NOISE-0001 │
└──────────────────┘
```

- Playable only when at least one scoring-eligible route exists
- Choose a target channel — all eligible routes outputting to it are immediately invalidated
- Routes shorter than 2 nodes are not affected (noise is precision disruption, not a blanket wipe)
- Watch out: noise can destroy your own routes too if they output to the targeted channel
- Filter nodes absorb noise aimed at their input channel, making those routes immune

Noise is a scalpel, not a bomb. It hits the output channel — so check which routes you're also killing before you play it.

---

## Collisions & Channel Loops

Collisions are route-scoped only — nodes in different routes never interfere with each other.

Within a single route, no card can output to a channel the route has already visited. If playing a card would create a channel loop, that card cannot extend that route — it must start a new one instead (if the cap allows).

Example: A route that already passed through CH02 cannot have a new node output back to CH02.

## Passing

You may only pass your turn if all of the following are true simultaneously:

- No scoring-eligible routes are open (no terminal plays available)
- No valid noise target exists
- None of your cards can extend any open route
- The concurrent cap is full (no room to start a new route)

You still draw a card on a pass. You simply don't place anything in the tableau that turn.

---

## Quick Reference: Legal Plays

| Your card       | What it can do |
|-----------------|----------------|
| ⇒ Relay         | Extend a matching open route; or start a new route if cap allows |
| ⊕ Amplifier     | Same as relay; ×2 score if exit node at round end |
| ⊘ Filter        | Same as relay; absorbs noise targeting its input channel |
| ⊣ Terminal      | Terminate any open route ≥ 2 nodes; earns terminal's own packet value |
| ⚠ Noise         | Invalidate all scoring-eligible routes outputting to a chosen channel |

To extend a route, your card must:

- Have an input channel matching the route's current tail (or be ANY)
- Not repeat a card already in that route
- Output to a channel the route hasn't yet visited
- Not push the route over the hop limit (4 by default)

---

## Example Round

3 players: Aura, Bo, Cleo. 3 channels, default settings.

**Setup:** Three seed nodes are dealt face-up:

- `[CH01→CH02]` — Aura's anchor
- `[CH02→CH03]` — Bo's anchor
- `[CH03→CH01]` — unanchored (Cleo must extend an existing route)

**Turn 1 – Aura** draws, plays ⊕ `[CH02→CH03] ×2` extending her route:
```
[CH01→CH02] → [CH02→CH03]⊕
```
The amplifier sits at the tail. If this is the exit node at round end, it scores double.

**Turn 2 – Bo** draws, plays ⇒ `[CH03→CH01]` extending their route:
```
[CH02→CH03] → [CH03→CH01]
```
Bo's route is now 2 nodes — scoring-eligible.

**Turn 3 – Cleo** draws, plays ⊣ TERM (PKT 500) — targeting Aura's route.
Aura's route closes immediately. The terminal's 500 pts score at round end, not the amplifier's doubled value. Cleo just stole Aura's route for 500 points.

**Round end:** Both closed routes score. Cleo collects 500 pts. Bo collects their exit node's packet value. Aura scores nothing. Cleo goes first next round — a dubious honor.

---

## Presets

| Setting              | Default   | fast      |
|----------------------|-----------|-----------|
| Score target         | 2,000 pts | 1,200 pts |
| Max hops per route   | 4         | 3         |
| Channels             | 3         | 3         |
| Amplifier multiplier | ×2        | ×2        |
| Starting hand size   | 4         | 4         |

## Strategy Notes

- You don't need to build routes to win — a well-timed terminal or noise can be more valuable than anything you construct yourself.
- Amplifiers are traps for opponents — play them when you can close quickly, or use a terminal to cash out before someone extends past the multiplier.
- Noise is symmetric — before targeting a channel, check whether your own routes output to it.
- Carry-over routes shift tempo — a stubbed route that carries is a resource for next round, but it also narrows the opening for new seeds.
- Going first is a liability — after a big-scoring round, your best play may be to set up rather than cash out, forcing others to show their hands first.

⇒─⊕─⊘─⊣─⚠ — Relay. Amplify. Terminate. — ⚠─⊣─⊘─⊕─⇒

---

## Install

```bash
# Game only
pip install .

# Game + dev tools (pytest)
pip install ".[dev]"
```

Or install dependencies directly:

```bash
pip install -r requirements.txt          # runtime only
pip install -r requirements-dev.txt      # runtime + pytest
```

## Usage

```bash
python -m packet_pressure.run_experiment [OPTIONS]
```

Key flags:

| Flag | Default | Description |
|---|---|---|
| `--preset` | `default` | Config preset: `default`, `fast`, `competitive`, `no_special`, `print` |
| `--policies` | `random greedy denial builder` | Space-separated AI policy list |
| `--n-games` | `200` | Number of games per batch |
| `--seed` | random | Master RNG seed (omit for a different game each run) |
| `--workers` | `1` | Parallel workers for batch runs |
| `--output-dir` | `./results` | Where to write results and plots |
| `--no-plots` | — | Skip chart generation |
| `--dump-deck` | — | Print the full deck as JSON and exit (no simulation runs) |
| `--interactive` | — | Play as a human against AI opponents |
| `--solo` | — | Hot-seat mode: human controls every player's turn |
| `--human-index` | `0` | Which player slot the human takes (interactive mode) |
| `--opponent-delay` | `0.5` | Pause in seconds after each AI turn |

## Config Presets

| Preset | Players | Channels | Seed nodes/round | Score to win | Rounds | Deck | Max hops |
|---|---|---|---|---|---|---|---|
| `default` | 4 | 3 | 3 | 2000 | 5 | 80 | 4 |
| `fast` | 3 | 3 | 2 | 1200 | 4 | 60 | 3 |
| `competitive` | 5 | 4 | 4 | 3000 | 6 | 100 | 6 |
| `no_special` | 4 | 3 | 3 | 2000 | 5 | 80 (relay only) | 4 |
| `print` | 4 | 3 | 3 | 2000 | 5 | 80 (fixed distribution) | 4 |

Seed nodes per round equal the channel count for default/competitive — always one fewer than the player count. One player per round competes without an anchor route. The `fast` preset uses 2 seeds across 3 channels.

`competitive` uses amplifier multiplier ×3 (all other presets use the default ×2).

The `print` preset produces a deterministic deck suited for physical printing. Channel pairs and packet values are allocated proportionally rather than sampled randomly — every run yields the same card counts regardless of seed:

| Card type | Count | Detail |
|---|---|---|
| Relay | 60 | 10 per channel pair (6 pairs: CH01↔CH02, CH01↔CH03, CH02↔CH03) |
| Terminal | 8 | ANY → TERM; 2 each at 400 / 500 / 600 / 700 pts |
| Amplifier | 4 | 1 per pair from CH01→02, CH01→03, CH02→01, CH02→03 |
| Filter | 4 | 1 per pair from CH03→01, CH03→02, CH01→02, CH01→03 |
| Noise | 4 | No channel assignment |

Packet values across the 60 relay nodes: 12×100, 13×200, 7×300, 7×400, 7×500, 7×600, 7×700. Use `--seed N` to also fix the order cards appear in the shuffled deck.

## Policies

| Name | Strategy |
|---|---|
| `random` | Picks a random legal play |
| `greedy` | Maximises immediate score |
| `denial` | Prioritises disrupting opponents via noise; falls back to terminal-node-stealing scoreable routes |
| `builder` | Focuses on completing long routes |

## Interactive Play

`--interactive` puts you in one player slot; AIs fill the rest. `--solo` gives you control of every player's turn — useful for learning rules and exploring game states without AI noise.

Player count in interactive and solo modes is determined by `--policies` (default: `greedy denial` → 3 players total). Pass `--policies greedy denial builder` for 4, etc. The preset's player count is ignored in these modes.

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
