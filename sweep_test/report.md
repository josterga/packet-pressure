# Packet Pressure Simulation Report

## Sweep: broadcast_multiplier = 1

### Configuration

- Players: 4
- Score to win: 12
- Max rounds: 8
- Channels: 01, 02, 03, 04, 05
- Route min length: 2
- Route max hops: 4
- Collision mode: output_only
- Color mode: ignore
- Games simulated: 100

### Win Rates

| Policy | Win Rate | Avg Score | Score Variance |
|---|---|---|---|
| random_legal | 12.0% | 71 | 51259 |
| greedy_endpoint | 30.0% | 177 | 107171 |
| denial_collision | 10.0% | 48 | 22896 |
| route_builder | 48.0% | 253 | 113891 |

### Game Quality Metrics

- Avg rounds per game: 1.7
- Avg route length: 2.14
- Dead round rate: 41.5%
- Avg scoring routes per game: 1.4
- Avg collisions per round: 1.47

### Key Observations

- Dominant policy: **route_builder** (48.0% win rate)
- ⚠ High dead round rate (>30%) — consider increasing seed cards or reducing route_min_length
- Routes barely exceed minimum length — consider reducing route_min_length or increasing hand size

## Sweep: broadcast_multiplier = 2

### Configuration

- Players: 4
- Score to win: 12
- Max rounds: 8
- Channels: 01, 02, 03, 04, 05
- Route min length: 2
- Route max hops: 4
- Collision mode: output_only
- Color mode: ignore
- Games simulated: 100

### Win Rates

| Policy | Win Rate | Avg Score | Score Variance |
|---|---|---|---|
| random_legal | 8.0% | 43 | 22451 |
| greedy_endpoint | 34.0% | 191 | 104619 |
| denial_collision | 13.0% | 72 | 50816 |
| route_builder | 45.0% | 261 | 117179 |

### Game Quality Metrics

- Avg rounds per game: 1.9
- Avg route length: 2.09
- Dead round rate: 48.5%
- Avg scoring routes per game: 1.5
- Avg collisions per round: 1.52

### Key Observations

- Dominant policy: **route_builder** (45.0% win rate)
- ⚠ High dead round rate (>30%) — consider increasing seed cards or reducing route_min_length
- Routes barely exceed minimum length — consider reducing route_min_length or increasing hand size

## Sweep: broadcast_multiplier = 3

### Configuration

- Players: 4
- Score to win: 12
- Max rounds: 8
- Channels: 01, 02, 03, 04, 05
- Route min length: 2
- Route max hops: 4
- Collision mode: output_only
- Color mode: ignore
- Games simulated: 100

### Win Rates

| Policy | Win Rate | Avg Score | Score Variance |
|---|---|---|---|
| random_legal | 12.0% | 66 | 40444 |
| greedy_endpoint | 28.0% | 146 | 110884 |
| denial_collision | 15.0% | 78 | 56116 |
| route_builder | 45.0% | 244 | 100264 |

### Game Quality Metrics

- Avg rounds per game: 1.8
- Avg route length: 2.09
- Dead round rate: 45.7%
- Avg scoring routes per game: 1.4
- Avg collisions per round: 1.54

### Key Observations

- Dominant policy: **route_builder** (45.0% win rate)
- ⚠ High dead round rate (>30%) — consider increasing seed cards or reducing route_min_length
- Routes barely exceed minimum length — consider reducing route_min_length or increasing hand size

## Sweep: broadcast_multiplier = 4

### Configuration

- Players: 4
- Score to win: 12
- Max rounds: 8
- Channels: 01, 02, 03, 04, 05
- Route min length: 2
- Route max hops: 4
- Collision mode: output_only
- Color mode: ignore
- Games simulated: 100

### Win Rates

| Policy | Win Rate | Avg Score | Score Variance |
|---|---|---|---|
| random_legal | 15.0% | 100 | 99200 |
| greedy_endpoint | 38.0% | 325 | 339275 |
| denial_collision | 13.0% | 76 | 60224 |
| route_builder | 34.0% | 202 | 135996 |

### Game Quality Metrics

- Avg rounds per game: 1.9
- Avg route length: 2.14
- Dead round rate: 48.5%
- Avg scoring routes per game: 1.4
- Avg collisions per round: 1.44

### Key Observations

- Dominant policy: **greedy_endpoint** (38.0% win rate)
- ⚠ High dead round rate (>30%) — consider increasing seed cards or reducing route_min_length
- Routes barely exceed minimum length — consider reducing route_min_length or increasing hand size
