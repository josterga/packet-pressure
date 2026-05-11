# Packet Pressure Simulation Report

### Configuration

- Players: 4
- Score to win: 12
- Max rounds: 8
- Channels: 01, 02, 03, 04, 05
- Route min length: 2
- Route max hops: 4
- Collision mode: output_only
- Color mode: ignore
- Games simulated: 50

### Win Rates

| Policy | Win Rate | Avg Score | Score Variance |
|---|---|---|---|
| random_legal | 6.0% | 26 | 9524 |
| greedy_endpoint | 32.0% | 162 | 100756 |
| denial_collision | 18.0% | 114 | 65204 |
| route_builder | 44.0% | 238 | 110756 |

### Game Quality Metrics

- Avg rounds per game: 1.7
- Avg route length: 0.00
- Dead round rate: 41.2%
- Avg scoring routes per game: 1.3
- Avg collisions per round: 1.48

### Key Observations

- Dominant policy: **route_builder** (44.0% win rate)
- ⚠ High dead round rate (>30%) — consider increasing seed cards or reducing route_min_length
- Routes barely exceed minimum length — consider reducing route_min_length or increasing hand size
