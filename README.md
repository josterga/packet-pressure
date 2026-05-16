```
⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠
⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘

       P A C K E T   P R E S S U R E
       Extend the route. Hold the endpoint.

⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕
⊕─⇒─⊘─⊣─⚠─⊕─⇒─⊘─⊣─⚠─⊕─⇒─⊘─⊣─⚠─⊕─⇒─⊘─⊣─⚠
```

A competitive routing game — routes are shared infrastructure. Anyone can extend them, anyone can steal them. You gain points by holding the endpoint at round end. · 3–5 players · ~20 min

## Quickstart

```bash
pip install .
packet-pressure --interactive          # play against AI opponents
packet-pressure --solo                 # hot-seat with a friend
```

Or run an AI simulation and see win-rate analytics:

```bash
packet-pressure --preset fast --n-games 200
```

Full install and CLI reference: [Install](#install) · [Usage](#usage)

---

## Overview

Packet Pressure is a competitive card game of contested route-building. Routes are shared infrastructure — any player can extend any open route at any time. Points go to the finisher, not the architect: whoever holds the endpoint node when a route closes scores it. Chain relay cards across shared channels to build routes worth stealing, or use terminal and noise cards to close routes on your terms. Every card you play either builds your lead or hands it to someone else.

## Goal

Be the first player to reach 2,000 points. If no one reaches the target, whoever has the most points after the final round wins. On a tie, the player earliest in seat order wins.

## Setting Up

1. Shuffle the full deck.
2. Deal seed nodes face-up into the shared play area (the tableau) — one fewer than the player count. With the default 4-player game, 3 seed nodes enter play. Seed nodes are always relay, amplifier, or filter cards — terminal and noise cards are never dealt as seeds.
3. Deal each player a starting hand of 4 cards.
4. The player to the left of the dealer goes first.

Why fewer seeds than players? Seeds per round = player count − 1, so one player each round has no seed to extend from — they must contest an existing route from the start.

## The Tableau

The tableau is the shared play area where all routes are built. Routes are open (extendable) or closed (no longer extendable). A route **closes** when it reaches the hop limit or a terminal node is played on it; both types score at round end. Noise **destroys** a route instead — destroyed routes don't score and don't carry over.

## Channels

The network runs on three channels:

| Channel | Color  |
|---------|--------|
| CH01    | Teal   |
| CH02    | Orange |
| CH03    | Purple |

Channels define how cards connect. Every relay node has an input channel (where it receives a packet) and an output channel (where it forwards one). A route is a chain where each node's output matches the next node's input.

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

## Rounds

Each round lasts **3 turns per player**, cycling through all players in order. The round ends after every player completes their third turn — then scoring happens, cards are discarded, and each player draws back up to 4 cards before the next round begins.

Three turns per player matches the hop limit: with 3 channels and a max of one hop per channel, any route can grow to at most 3 nodes.

A standard game lasts **5 rounds**. The first player to reach 2,000 points wins immediately; if no one hits that target, whoever has the most points after round 5 wins.

## Building Routes

A route is a chain of nodes where each node's output channel matches the next node's input channel. Routes grow one card per turn — anyone can extend any open route. Each card added to a route counts as one hop.

Only relay, amplifier, and filter cards can start a new route. Terminal and noise cards cannot — they only interact with existing routes.

Key rules:

- Routes must be at least 2 nodes long to score.
- Each channel may be used as an **output** at most once per route — this caps route length at the number of channels (3 by default). Channels can appear in any order; the only constraint is that no channel has already been used as a card's output in that route. The entry channel (input of the first card) is not counted, so a route can output back to it later.
- No more than [player count] routes can be open at the same time. Routes **close** when terminated by a terminal card or when they reach the hop limit — they can no longer be extended but stay in the tableau until round end. Closed routes do **not** count against the open-route cap, and can still be noised. A route broken by noise is **destroyed**: it's removed immediately, doesn't score, and doesn't carry over. The total number of open routes in the tableau can never exceed the player count.

## Route Ownership

There is no locked ownership. Whoever played the current endpoint node is in position to score — that's it. The moment another player extends the route, scoring position passes to them. There are no other ownership effects: no player can block others from extending a route they "built," and no scoring bonuses are tied to who started it.

Whoever holds the endpoint holds the points.

Any player can extend any open route. The player who places the last card — the **endpoint** — scores it. Every route is contested until it closes.

## Carried Routes

Open routes that are too short to score (under 2 nodes) at round end carry over into the next round. Each carried route reduces the seed count for that round by one, keeping the open-route cap intact. Carried routes remain in the tableau and can be extended normally.

## Scoring

Points are awarded at the end of every round.

Only the exit node's packet value scores — there is no cumulative sum across the whole route. The player who holds the exit node collects those points.

- **Exit node** = the last node in a route when it scores (whoever played it holds it)
- Any route of ≥ 2 nodes scores at round end, whether it was explicitly terminated or left open
- Routes under 2 nodes never score that round — they carry over instead

After scoring:

- All scored routes are discarded
- Carried routes stay in the tableau
- Hands are topped back up to 4 cards before the next round begins

The player who scored the most points in a round goes first next round. On a tie, turn order is unchanged.

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
│        REL-0001  │
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
- Not playable on full routes (those that have reached the hop limit) — those can only score at round end or be noised
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
- If a noise card is played targeting the filter's input channel, the route is immune — noise is absorbed, no cards are destroyed
- Noise targeting any other channel provides no protection
- No action required; protection is automatic
- Does not terminate the route; can be extended further

Use filters to insure your investment. A long route is a tempting noise target — a well-placed filter removes that threat.

### ⚠ Noise

Disrupts a specific channel, destroying all scoring-eligible routes (≥ 2 nodes) that output to it. Each noise card targets a fixed channel determined when the card is created — you don't choose the channel at play time.

```
┌──────────────────┐
│ IN  --  CH01 OUT │
│──────────────────│
│  ⚠  ≋≋ CH01      │
│  PKT  0          │
│──────────────────│
│       NOISE-0001 │
└──────────────────┘
```

- The target channel is fixed and shown on the card — it cannot be changed when played
- Playable only when at least one scoring-eligible route outputs to the card's fixed channel
- All eligible routes outputting to that channel are immediately destroyed; their cards go to the discard pile. "Outputting to" means the route's **current exit channel** (its tail) — a route that passed through that channel earlier but now exits at a different channel is not affected.
- Destroyed routes do not carry over to the next round — they are gone
- Routes shorter than 2 nodes are not affected
- Watch out: noise destroys any route outputting to that channel, including your own
- Filter nodes absorb noise aimed at their input channel, making those routes immune

A noise card is only as strong as the channel it targets. If no scoring route outputs to your card's channel, you can't play it.

---

## Collisions

Collisions are route-scoped only — nodes in different routes never interfere with each other. If a card cannot extend any open route (because all existing routes have already visited its output channel), it must start a new one instead (if the cap allows). 

## Passing

You may only pass if you have no legal play. See **Quick Reference: Legal Plays** for what qualifies.

You still draw a card on a pass. You simply don't place anything in the tableau that turn.

---

## Quick Reference: Legal Plays

A **legal play** is any card in your hand that has at least one valid target in the current tableau. A card is legal if:

- It can extend a compatible open route (input channel matches the route's tail, output channel unvisited in that route, route not full)
- It can start a new route (route cap not reached, card type is relay/amplifier/filter)
- It is a terminal and at least one open, non-full route has ≥ 2 nodes
- It is a noise card and at least one scoring-eligible route outputs to the card's fixed channel

If none of your cards qualify, you must pass.

| Your card       | What it can do |
|-----------------|----------------|
| ⇒ Relay         | Extend a matching open route; or start a new route if route cap allows |
| ⊕ Amplifier     | Same as relay; ×2 score if exit node at round end |
| ⊘ Filter        | Same as relay; absorbs noise targeting its input channel |
| ⊣ Terminal      | Terminate any open, non-full route ≥ 2 nodes; earns terminal's own packet value |
| ⚠ Noise         | Destroy all scoring-eligible routes whose output channel matches the card's fixed channel |

To extend a route, your card must:

- Have an input channel matching the route's current tail (or be ANY)
- Output to a channel the route hasn't yet visited (routes visit each channel at most once)

---

## Example Round

3 players: Aura, Bo, Cleo. 3 channels, default settings.

**Setup:** Two seed nodes are dealt face-up into the tableau — they belong to no one:

- `[CH01→CH02]`
- `[CH02→CH03]`

**Turn 1 – Aura** draws, plays ⊕ `[CH02→CH03] ×2` — extending the first seed:
```
[CH01→CH02] → [CH02→CH03]⊕
```
The amplifier sits at the tail. Aura holds the endpoint — if this scores now, she collects double the amplifier's packet value.

**Turn 2 – Bo** draws, plays ⇒ `[CH03→CH01]` — extending the second seed:
```
[CH02→CH03] → [CH03→CH01]
```
This route is now 2 nodes and scoring-eligible. Bo holds the endpoint.

**Turn 3 – Cleo** draws, plays ⊣ TERM (PKT 500) — targeting the first route.
The route closes immediately. Cleo now holds the endpoint. The terminal's 500 pts score at round end — not the amplifier's doubled value. Aura built the route; Cleo collects it.

**Round end:** Both routes score. Cleo collects 500 pts. Bo collects their exit node's packet value. Aura scores nothing — she never held an endpoint when it mattered. Cleo goes first next round — a dubious honor.

---

## Presets

| Setting              | Default   | fast      |
|----------------------|-----------|-----------|
| Score target         | 2,000 pts | 1,200 pts |
| Max hops per route   | 3         | 3         |
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
| `--print-cards` | — | Render one example of each card type as ANSI blocks and exit |
| `--print-deck` | — | Render the full deck as ANSI card blocks and exit |
| `--interactive` | — | Play as a human against AI opponents |
| `--solo` | — | Hot-seat mode: human controls every player's turn |
| `--human-index` | `0` | Which player slot the human takes (interactive mode) |
| `--opponent-delay` | `0.5` | Pause in seconds after each AI turn |

## Config Presets

| Preset | Players | Channels | Seed nodes/round | Max routes | Score to win | Rounds | Deck | Max hops |
|---|---|---|---|---|---|---|---|---|
| `default` | 4 | 3 | 3 | 4 | 2000 | 5 | 80 | 3 |
| `fast` | 3 | 3 | 2 | 3 | 1200 | 4 | 60 | 3 |
| `competitive` | 5 | 4 | 4 | 5 | 3000 | 6 | 100 | 4 |
| `no_special` | 4 | 3 | 3 | 4 | 2000 | 5 | 80 (relay only) | 3 |
| `print` | 4 | 3 | 3 | 4 | 2000 | 5 | 80 (fixed distribution) | 3 |

Three rules govern routing across all presets: seeds per round = player count − 1 (one player each round has no seed to extend from the start); max concurrent open routes = player count; hop limit = channel count (routes cannot revisit a channel, so these two constraints are equivalent).

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
# How does seed count affect win rates? (hop limit = channel count, not sweepable directly)
python -m packet_pressure.run_experiment \
  --sweep-param seed_nodes_per_round --sweep-values 1 2 3 \
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

---

© 2026 Packet Pressure — licensed under [CC BY-NC 4.0](LICENSE). Commercial use requires permission.