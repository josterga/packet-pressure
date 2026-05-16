# Packet Pressure Simulation Report

## Sweep: amplifier_multiplier = 1

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
| random_legal | 7.0% | 890 | 400308 |
| greedy_exit_node | 33.6% | 1591 | 453763 |
| denial_collision | 20.6% | 1405 | 435799 |
| route_builder | 38.8% | 1703 | 432613 |

### Game Quality Metrics

- Avg rounds per game: 3.3
- Avg route length: 2.78
- Dead round rate: 4.0%
- Avg scoring routes per game: 13.3
- Avg collisions per round: 0.64

### Key Observations

- Dominant policy: **route_builder** (38.8% win rate)

## Sweep: amplifier_multiplier = 2

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
| random_legal | 8.0% | 963 | 439616 |
| greedy_exit_node | 33.0% | 1612 | 476551 |
| denial_collision | 24.2% | 1389 | 543828 |
| route_builder | 34.8% | 1673 | 454312 |

### Game Quality Metrics

- Avg rounds per game: 3.1
- Avg route length: 2.78
- Dead round rate: 3.5%
- Avg scoring routes per game: 12.6
- Avg collisions per round: 0.62

### Key Observations

- Dominant policy: **route_builder** (34.8% win rate)

## Sweep: amplifier_multiplier = 3

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
| random_legal | 9.2% | 875 | 530815 |
| greedy_exit_node | 26.6% | 1519 | 624084 |
| denial_collision | 25.4% | 1433 | 608797 |
| route_builder | 38.8% | 1777 | 605782 |

### Game Quality Metrics

- Avg rounds per game: 2.9
- Avg route length: 2.76
- Dead round rate: 3.2%
- Avg scoring routes per game: 11.9
- Avg collisions per round: 0.56

### Key Observations

- Dominant policy: **route_builder** (38.8% win rate)

## Sweep: amplifier_multiplier = 4

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
| random_legal | 7.4% | 894 | 616586 |
| greedy_exit_node | 32.0% | 1643 | 808965 |
| denial_collision | 24.8% | 1420 | 793504 |
| route_builder | 35.8% | 1733 | 773957 |

### Game Quality Metrics

- Avg rounds per game: 2.8
- Avg route length: 2.77
- Dead round rate: 2.1%
- Avg scoring routes per game: 11.5
- Avg collisions per round: 0.62

### Key Observations

- Dominant policy: **route_builder** (35.8% win rate)
