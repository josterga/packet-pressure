# Packet Pressure Simulation Report

### Configuration

- Players: 4
- Score to win: 2000
- Max rounds: 5
- Channels: 01, 02, 03
- Route min length: 2
- Route max hops: 3
- Games simulated: 500

### Win Rates

| Policy | Win Rate | Avg Score | Score Variance |
|---|---|---|---|
| random_legal | 8.8% | 984 | 474090 |
| greedy_exit_node | 32.2% | 1593 | 515114 |
| denial_collision | 22.2% | 1409 | 499259 |
| route_builder | 36.8% | 1739 | 435028 |

### Game Quality Metrics

- Avg rounds per game: 3.1
- Avg route length: 2.77
- Dead round rate: 3.2%
- Avg scoring routes per game: 13.0
- Avg collisions per round: 0.58

### Key Observations

- Dominant policy: **route_builder** (36.8% win rate)
