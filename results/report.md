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
- Games simulated: 200

### Win Rates

| Policy | Win Rate | Avg Score | Score Variance |
|---|---|---|---|
| random_legal | 8.0% | 26 | 11548 |
| greedy_endpoint | 27.5% | 196 | 182738 |
| denial_collision | 13.0% | 86 | 66368 |
| route_builder | 51.5% | 255 | 98375 |

### Game Quality Metrics

- Avg rounds per game: 1.8
- Avg route length: 2.12
- Dead round rate: 45.0%
- Avg scoring routes per game: 1.5
- Avg collisions per round: 1.49

### Key Observations

- Dominant policy: **route_builder** (51.5% win rate)
- ⚠ High dead round rate (>30%) — consider increasing seed cards or reducing route_min_length
- Routes barely exceed minimum length — consider reducing route_min_length or increasing hand size
