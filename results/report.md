# Packet Pressure Simulation Report

### Configuration

- Players: 4
- Score to win: 1200
- Max rounds: 8
- Channels: 01, 02
- Route min length: 2
- Route max hops: 3
- Games simulated: 3

### Win Rates

| Policy | Win Rate | Avg Score | Score Variance |
|---|---|---|---|
| random_legal | 0.0% | 433 | 162222 |
| greedy_exit_node | 0.0% | 133 | 35556 |
| denial_collision | 66.7% | 1000 | 526667 |
| route_builder | 33.3% | 700 | 206667 |

### Game Quality Metrics

- Avg rounds per game: 3.7
- Avg route length: 2.25
- Dead round rate: 27.3%
- Avg scoring routes per game: 5.0
- Avg collisions per round: 0.52

### Key Observations

- Dominant policy: **denial_collision** (66.7% win rate)
- Routes barely exceed minimum length — consider reducing route_min_length or increasing hand size
