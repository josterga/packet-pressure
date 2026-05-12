```
⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠
⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘

       P A C K E T   P R E S S U R E
       the exit node takes everything.

⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕─⊘─⊣─⚠─⇒─⊕
⊕─⇒─⊘─⊣─⚠─⊕─⇒─⊘─⊣─⚠─⊕─⇒─⊘─⊣─⚠─⊕─⇒─⊘─⊣─⚠
```

**Packet Pressure** is a competitive card game for 3–5 players built on a packet-switching network.
Each round, players chain relay nodes across shared channels to build routing paths, but the points go to the finisher, not the architect. Extend what others started, or build something worth stealing.

*Every card you play either builds your lead or hands it to someone else.*

## How to Play

### Goal
Be the first player to reach the score target (default: 2000 pts). If no one reaches it, whoever has the most points after the final round wins.

### Setup
Each round starts by dealing **seed nodes** face-up into the shared tableau — one seed per channel, drawn from the top of the shuffled deck. Seed nodes are ordinary relay nodes; the only thing special about them is when they enter play. Because seed nodes must each occupy a distinct output channel, the number of seeds equals the number of channels — which is always fewer than the number of players. One player per round gets no anchor route and must extend or terminate an existing one. Each player holds a starting hand of **4 cards**.

### On Your Turn
1. **Draw** one card from the deck into your hand. If the deck is empty, the discard pile is reshuffled face-down and becomes the new deck — the game never stalls for cards.
2. **Play** one card from your hand onto the tableau. Each card occupies a node in the route.

### Channels
The number of channels defines the network's **bandwidth** — how many routes can exist simultaneously. With N channels (and no channel reuse within a route), the natural maximum route length is also N nodes. The default network has three channels: **CH01** (teal), **CH02** (orange), **CH03** (purple). Relay nodes carry traffic *from* one channel *to* another. A node's **input channel** is where it receives; its **output channel** is where it forwards.

### Building Routes
A route is a chain of nodes where each node's output channel matches the next node's input channel:

```
[CH01→CH02] → [CH02→CH03] → [CH03→CH01]
```

Any player can extend any open route. Whoever plays the **exit node** (the last node in the route when it terminates or scores at round end) earns the points — even if they didn't start the route. The game rewards being the finisher, not the builder.

Routes must be at least **2 nodes long** to score. Routes are capped at **6 hops** by default (3 in the `fast` preset). In practice the channel-reuse rule hits the natural ceiling first: a 3-channel network can produce at most 3-node routes. One loop-prevention rule applies:
- A node cannot appear twice in the same route (`no_loops`)
- A route cannot output to a channel it has already visited (prevents channel loops within the route)

At most `seed_nodes_per_round` routes can be open simultaneously. Once a route closes — by hitting the hop limit or being terminated — its slot frees up and a new route can start. A player **passes their turn** only if the concurrent cap is full and no card in hand can extend any open route — they still draw and keep the card, but nothing is played to the tableau that turn.

Open routes shorter than `route_min_length` (typically single-node stubs) are not discarded at round end — they carry over into the next round. Each carried route reduces the seed count for that round by one, keeping the concurrent cap intact. Carried routes appear under **CARRIED** in the tableau and can be extended normally.

### Scoring
Score is awarded at **end of round** for eligible routes. Only the **exit node's packet value** scores — there is no cumulative sum. The player who owns the exit node collects those points.

At round end, **all valid routes of at least 2 nodes score**, whether they were explicitly terminated (by a terminal node, amplifier node, or hitting the hop limit) or still open. A route that was never terminated simply scores with whoever owns its current exit node. Routes shorter than `route_min_length` never score — they carry over into the next round instead (see Building Routes). After scoring, the tableau is discarded except for any carried routes — only player hands otherwise carry over. Hands are then topped back up to the starting hand size before the next round begins.

The player who scored the most points in a round goes first in the next round. Going first is a disadvantage — you act before others can react to what you build. On a tied round (multiple players share the highest score), turn order is unchanged.

---

## Valid Moves Reference

Conditions and the actions each card type may legally take. All checks are enforced by `policies.legal_plays()` when generating moves and by `engine._can_extend()` / `engine._try_start_route()` when resolving them.

### 1. Concurrent route cap

| Condition | Relay ⇒ / Amplifier ⊕ / Filter ⊘ | Terminal ⊣ | Noise ⚠ |
|-----------|----------------------------------|------------|---------|
| open routes < `seed_nodes_per_round` | extend an existing route **or** start a new route | see §5 | see §6 |
| open routes = `seed_nodes_per_round` (cap full) | extend an existing route only — cannot start | see §5 | see §6 |

### 2. Relay node ⇒ — extension checks (all must pass)

`policies._can_card_extend_route()` · `engine._can_extend()`

| # | Condition | When it applies |
|---|-----------|-----------------|
| 1 | `card.input_channel ∈ {ANY, route.last_output_channel}` | always |
| 2 | `card.card_id ∉ route.card_ids` | `no_loops = True` (default on) |
| 3 | `card.output_channel ∉ route.channels_in_route` | always |
| 4 | `card.output_channel ≠ route.first_input_channel` | `no_return_to_first_hop = True` (default off) |
| 5 | `route.length < route_max_hops` | always |

If no open route passes all five checks and the cap is not reached → the card **starts a new route**.  
If no open route passes and the cap is full → the card is **unplayable this turn**.  
No special effect on scoring; packet value scores only if this is the exit node at scoring time.

### 3. Amplifier node ⊕ — same extension checks as §2, plus scoring bonus

| Condition | Effect |
|-----------|--------|
| Amplifier is the exit node when scoring | score = `packet_value × amplifier_multiplier` (default ×2) |
| Another node is played on top of it | bonus is lost; the new exit node scores at its own face value |

Amplifier does **not** terminate the route. Can be extended further.

### 4. Filter node ⊘ — same extension checks as §2, plus noise immunity

| Condition | Effect |
|-----------|--------|
| Noise targets `filter.input_channel` | entire route is immune — no cards destroyed, route stays valid |
| Noise targets any other channel | filter provides no protection |

The filter must be **in the route** to grant immunity. Protection is passive; no player action needed. Filter does not terminate the route and can be extended.

### 5. Terminal node ⊣ — terminate a scoring-eligible route

`policies.legal_plays()` lines 69-73 · `engine._apply_play()` line 223

| Condition | Required |
|-----------|----------|
| Route must be open | `is_valid = True` and not yet terminated |
| Route must be scoring-eligible | `route.length ≥ route_min_length` (default 2) |

Player must declare which eligible route to terminate. Input is `ANY`, so it always passes the channel check. Scores its **own** packet value as exit node regardless of who built the route. A terminal card cannot start a new route.

### 6. Noise card ⚠ — disrupt a channel

`policies.legal_plays()` lines 57-68 · `engine._apply_noise()`

| Condition | Required |
|-----------|----------|
| Scoring-eligible routes exist | ≥ 1 route with `is_valid = True` and `length ≥ route_min_length` |
| Target channel | output channel of any card in a scoring-eligible route (not `TERM`) |

One legal play is generated per distinct valid target channel. Noise **does not** affect routes shorter than `route_min_length`. A route containing a Filter node whose `input_channel` equals the targeted channel is fully immune. May destroy your own scoring routes if they output to the targeted channel and are not filter-shielded.

### 7. Pass turn

All of the following must hold simultaneously:

- No terminal plays available (no scoring-eligible open routes)
- No noise plays available (no valid target channel exists)
- No relay / amplifier / filter card in hand can extend any open route
- Concurrent cap is full (no room to start a new route)

The player still draws a card but does not place one on the tableau.

---

## Card Types

### Relay Node ⇒
Forwards a packet from one channel to another. Extends an existing open route whose last output channel matches this node's input channel. If no open route can be extended (channel mismatch, channel loop, hop limit, or card-reuse rule) and the concurrent cap is not reached, starts a new route instead.

- **Input channel**: must match the route's current tail
- **Output channel**: becomes the new tail; cannot be a channel the route has already visited
- **Packet value**: scores if this node is the exit node

### Terminal Node ⊣
Terminates a chosen route immediately. Input is `ANY` (matches any open route). Output is `TERM`.

- Only playable on routes that are already ≥ 2 nodes — terminal node is a steal/close card, not a route-builder
- When played, you declare which eligible open route to terminate; a route is eligible if it is open and already ≥ 2 nodes long
- The terminal node becomes the exit node, so **the terminal node's own packet value** is what scores — even if you played no other node in the route
- The terminated route stays visible in the tableau but can no longer be extended; it scores at end of round

### Amplifier Node ⊕
Extends a route like a relay node — input channel must match the route's current tail, output channel becomes the new tail. If the amplifier node is the exit node when scoring happens, the score is `packet_value × multiplier` (default ×2) instead of the raw value.

- The multiplier **only applies if the amplifier is the exit node at scoring time** — if another player extends the route past it, the bonus is lost and the new exit node scores at face value
- Can be extended further by other nodes (it does not terminate the route)
- Self-loop channel pairs (in = out) are not generated

### Noise ⚠
Disrupts a channel, destroying all nodes in **scoring-eligible routes** (≥ 2 nodes) that output to that channel. Those routes are immediately invalidated.

- Only playable when at least one scoring-eligible route exists; the target channel must be one used by a node in such a route
- Routes shorter than 2 nodes are not affected — noise is precision disruption, not a blanket nuke
- Also invalidates your own scoring routes if they output to the noised channel

### Filter Node ⊘
Extends a route like a relay node — input channel must match the route's current tail, output channel becomes the new tail. If a noise card targets the filter node's input channel, the entire route is immune: the noise is absorbed without invalidating any cards.

- Protects the route it's part of from noise targeting its input channel
- Works passively — no player action required to activate the filter
- Can be extended further; it does not terminate the route

### Visual reference

In the terminal UI, each card's left border is colored by input channel and right border by output channel (teal = CH01, orange = CH02, purple = CH03).

**Relay node** ⇒ — forwards a packet from one channel to another.

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

**Terminal node** ⊣ — closes any open route immediately; earns points on its own packet value.

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

**Amplifier node** ⊕ — extends a route; multiplies packet value (×2 default) if it's the exit node at scoring.

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

**Noise** ⚠ — disrupts a channel, invalidating all scoring-eligible routes that output to it.

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

**Filter node** ⊘ — extends a route and absorbs noise targeting its input channel, protecting the route.

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

---

## Collisions

Collisions are **route-scoped only** — nodes in different routes do not collide with each other.

Within a route, a node cannot output to a channel the route has already visited. If a node would create a channel loop (e.g., a route already passed through CH02, and a new node would output back to CH02), it cannot extend that route and instead starts a new one.

Seed nodes are dealt with unique output channels to prevent immediate conflicts at round start.

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
| `default` | 4 | 3 | 3 | 2000 | 15 | 80 | 4 |
| `fast` | 3 | 2 | 2 | 1200 | 8 | 60 | 2 |
| `competitive` | 5 | 4 | 4 | 3000 | 20 | 100 | 6 |
| `no_special` | 4 | 3 | 3 | 2000 | 15 | 80 (relay only) | 4 |
| `print` | 4 | 3 | 3 | 2000 | 15 | 80 (fixed distribution) | 4 |

Seed nodes per round equal the channel count — always one fewer than the player count. One player per round competes without an anchor route.

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
