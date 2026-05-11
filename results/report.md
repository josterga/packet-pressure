# Packet Pressure Simulation Report

### Configuration

- Players: 4
- Score to win: 1200
- Max rounds: 8
- Channels: 01, 02, 03
- Route min length: 2
- Route max hops: 4
- Collision mode: output_only
- Color mode: ignore
- Games simulated: 50

### Win Rates

| Policy | Win Rate | Avg Score | Score Variance |
|---|---|---|---|
| random_legal | 6.0% | 484 | 148144 |
| greedy_endpoint | 30.0% | 842 | 318836 |
| denial_collision | 12.0% | 420 | 300000 |
| route_builder | 52.0% | 1254 | 745284 |

### Game Quality Metrics

- Avg rounds per game: 3.3
- Avg route length: 2.18
- Dead round rate: 9.1%
- Avg scoring routes per game: 7.3
- Avg collisions per round: 0.35

### Key Observations

- Dominant policy: **route_builder** (52.0% win rate)
- Routes barely exceed minimum length — consider reducing route_min_length or increasing hand size
