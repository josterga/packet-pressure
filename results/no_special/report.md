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
| random_legal | 4.6% | 898 | 355117 |
| greedy_exit_node | 42.8% | 1749 | 353779 |
| denial_collision | 21.0% | 1456 | 448629 |
| route_builder | 31.6% | 1667 | 356944 |

### Game Quality Metrics

- Avg rounds per game: 3.3
- Avg route length: 2.77
- Dead round rate: 1.9%
- Avg scoring routes per game: 16.4
- Avg collisions per round: 0.00

### Key Observations

- Dominant policy: **greedy_exit_node** (42.8% win rate)
