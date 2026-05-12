from __future__ import annotations

import csv
import dataclasses
import math
from pathlib import Path
from typing import Any

from .metrics import BatchResult, GameMetrics

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _MATPLOTLIB = True
except ImportError:
    _MATPLOTLIB = False

try:
    import seaborn as sns
    _SEABORN = True
except ImportError:
    _SEABORN = False


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def export_csv(
    batch_result: BatchResult,
    path: str | Path,
    *,
    per_game: bool = True,
    aggregate: bool = True,
) -> None:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    if per_game:
        _write_per_game_csv(batch_result, path / "game_results.csv")
    if aggregate:
        _write_aggregate_csv(batch_result, path / "batch_summary.csv")


def _write_per_game_csv(batch_result: BatchResult, filepath: Path) -> None:
    if not batch_result.games:
        return
    rows = []
    for gm in batch_result.games:
        row: dict[str, Any] = {
            "game_seed": gm.game_seed,
            "winner": gm.winner or "",
            "total_rounds_played": gm.total_rounds_played,
            "avg_score_per_round": round(gm.avg_score_per_round, 2),
            "scoring_routes_count": gm.scoring_routes_count,
            "avg_route_length": round(gm.avg_route_length, 2),
            "pct_routes_stopped_by_hop_limit": round(gm.pct_routes_stopped_by_hop_limit, 3),
            "collision_count_per_round": round(gm.collision_count_per_round, 3),
            "noise_plays": gm.noise_plays,
            "terminal_plays": gm.terminal_plays,
            "amplifier_plays": gm.amplifier_plays,
            "amplifier_score_rate": round(gm.amplifier_score_rate, 3),
            "terminal_steal_rate": round(gm.terminal_steal_rate, 3),
            "seed_node_utilization_rate": round(gm.seed_node_utilization_rate, 3),
            "dead_rounds_count": gm.dead_rounds_count,
            "turn_pct_extending_vs_starting": round(gm.turn_pct_extending_vs_starting, 3),
            "avg_legal_moves_per_turn": round(gm.avg_legal_moves_per_turn, 2),
        }
        for i, (pid, score) in enumerate(gm.final_scores.items()):
            row[f"score_p{i}"] = score
        rows.append(row)

    fieldnames = list(rows[0].keys()) if rows else []
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_aggregate_csv(batch_result: BatchResult, filepath: Path) -> None:
    br = batch_result
    row: dict[str, Any] = {
        "n_games": br.n_games,
        "policy_names": "|".join(br.policy_names),
        "avg_total_rounds": round(br.avg_total_rounds, 2),
        "collision_avg": round(br.collision_avg, 3),
        "route_length_avg": round(br.route_length_avg, 2),
        "dead_round_rate": round(br.dead_round_rate, 3),
        "avg_scoring_routes": round(br.avg_scoring_routes, 2),
        "avg_legal_moves_per_turn": round(br.avg_legal_moves_per_turn, 2),
    }
    for policy in br.policy_names:
        safe = policy.replace(" ", "_")
        row[f"win_rate_{safe}"] = round(br.win_rates.get(policy, 0.0), 3)
        row[f"avg_score_{safe}"] = round(br.avg_final_scores.get(policy, 0.0), 1)
        row[f"score_variance_{safe}"] = round(br.score_variance.get(policy, 0.0), 1)

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)


def export_sweep_csv(
    sweep_results: list[BatchResult],
    param_name: str,
    values: list[Any],
    path: str | Path,
) -> None:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    filepath = path / f"sweep_{param_name}.csv"

    rows = []
    for value, br in zip(values, sweep_results):
        base_row: dict[str, Any] = {
            param_name: value,
            "n_games": br.n_games,
            "avg_total_rounds": round(br.avg_total_rounds, 2),
            "collision_avg": round(br.collision_avg, 3),
            "route_length_avg": round(br.route_length_avg, 2),
            "dead_round_rate": round(br.dead_round_rate, 3),
        }
        for policy in br.policy_names:
            safe = policy.replace(" ", "_")
            base_row[f"win_rate_{safe}"] = round(br.win_rates.get(policy, 0.0), 3)
            base_row[f"avg_score_{safe}"] = round(br.avg_final_scores.get(policy, 0.0), 1)
        rows.append(base_row)

    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def write_markdown_report(
    batch_result_or_list: BatchResult | list[BatchResult],
    path: str | Path,
    *,
    sweep_param: str | None = None,
    sweep_values: list[Any] | None = None,
) -> None:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    filepath = path / "report.md"

    if isinstance(batch_result_or_list, list):
        results = batch_result_or_list
    else:
        results = [batch_result_or_list]

    lines: list[str] = ["# Packet Pressure Simulation Report\n"]

    for idx, br in enumerate(results):
        if sweep_param and sweep_values:
            lines.append(f"## Sweep: {sweep_param} = {sweep_values[idx]}\n")
        elif len(results) > 1:
            lines.append(f"## Config {idx + 1}\n")

        cfg = br.config
        lines.append("### Configuration\n")
        lines.append(f"- Players: {cfg.player_count}")
        lines.append(f"- Score to win: {cfg.score_to_win}")
        lines.append(f"- Max rounds: {cfg.max_rounds}")
        lines.append(f"- Channels: {', '.join(cfg.channels)}")
        lines.append(f"- Route min length: {cfg.route_min_length}")
        lines.append(f"- Route max hops: {cfg.route_max_hops}")
        lines.append(f"- Games simulated: {br.n_games}\n")

        lines.append("### Win Rates\n")
        lines.append("| Policy | Win Rate | Avg Score | Score Variance |")
        lines.append("|---|---|---|---|")
        for policy in br.policy_names:
            wr = br.win_rates.get(policy, 0.0)
            avg = br.avg_final_scores.get(policy, 0.0)
            var = br.score_variance.get(policy, 0.0)
            lines.append(f"| {policy} | {wr:.1%} | {avg:.0f} | {var:.0f} |")
        lines.append("")

        lines.append("### Game Quality Metrics\n")
        lines.append(f"- Avg rounds per game: {br.avg_total_rounds:.1f}")
        lines.append(f"- Avg route length: {br.route_length_avg:.2f}")
        lines.append(f"- Dead round rate: {br.dead_round_rate:.1%}")
        lines.append(f"- Avg scoring routes per game: {br.avg_scoring_routes:.1f}")
        lines.append(f"- Avg collisions per round: {br.collision_avg:.2f}")
        lines.append("")

        # Observations
        lines.append("### Key Observations\n")
        top_policy = max(br.policy_names, key=lambda p: br.win_rates.get(p, 0.0))
        lines.append(f"- Dominant policy: **{top_policy}** ({br.win_rates.get(top_policy, 0.0):.1%} win rate)")
        if br.dead_round_rate > 0.3:
            lines.append("- ⚠ High dead round rate (>30%) — consider increasing seed nodes per round or reducing route_min_length")
        if br.collision_avg > 2.0:
            lines.append("- High collision rate — output channel distribution may be too concentrated")
        if br.route_length_avg < cfg.route_min_length + 0.5:
            lines.append("- Routes barely exceed minimum length — consider reducing route_min_length or increasing hand size")
        lines.append("")

    filepath.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def plot_win_rates(
    batch_result: BatchResult,
    ax: Any = None,
) -> Any:
    if not _MATPLOTLIB:
        raise ImportError("matplotlib is required for plotting")
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 4))
    policies = batch_result.policy_names
    rates = [batch_result.win_rates.get(p, 0.0) for p in policies]
    ax.bar(policies, rates, color="steelblue", edgecolor="white")
    ax.set_ylabel("Win Rate")
    ax.set_title("Win Rates by Policy")
    ax.set_ylim(0, 1)
    for i, r in enumerate(rates):
        ax.text(i, r + 0.01, f"{r:.1%}", ha="center", fontsize=9)
    return fig or ax.figure


def plot_score_distribution(
    batch_result: BatchResult,
    ax: Any = None,
) -> Any:
    if not _MATPLOTLIB:
        raise ImportError("matplotlib is required for plotting")
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 4))

    policy_scores: dict[str, list[float]] = {p: [] for p in batch_result.policy_names}
    for gm in batch_result.games:
        for policy, score in zip(gm.policy_names, gm.final_scores.values()):
            policy_scores[policy].append(float(score))

    data = [policy_scores[p] for p in batch_result.policy_names]
    ax.boxplot(data, labels=batch_result.policy_names)
    ax.set_ylabel("Final Score")
    ax.set_title("Score Distribution by Policy")
    return fig or ax.figure


def plot_route_length_histogram(
    batch_result: BatchResult,
    ax: Any = None,
) -> Any:
    if not _MATPLOTLIB:
        raise ImportError("matplotlib is required for plotting")
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 4))

    combined: dict[int, int] = {}
    for gm in batch_result.games:
        for length, count in gm.route_length_histogram.items():
            combined[length] = combined.get(length, 0) + count

    if combined:
        lengths = sorted(combined.keys())
        counts = [combined[l] for l in lengths]
        ax.bar(lengths, counts, color="darkorange", edgecolor="white")
    ax.set_xlabel("Route Length")
    ax.set_ylabel("Count")
    ax.set_title("Route Length Histogram")
    return fig or ax.figure


def plot_sweep(
    sweep_results: list[BatchResult],
    param_name: str,
    values: list[Any],
    metric: str = "win_rates",
    policy_filter: list[str] | None = None,
) -> Any:
    if not _MATPLOTLIB:
        raise ImportError("matplotlib is required for plotting")
    fig, ax = plt.subplots(figsize=(9, 5))

    if not sweep_results:
        return fig

    policies = policy_filter or sweep_results[0].policy_names

    for policy in policies:
        y_vals = []
        for br in sweep_results:
            if metric == "win_rates":
                y_vals.append(br.win_rates.get(policy, 0.0))
            elif metric == "avg_final_scores":
                y_vals.append(br.avg_final_scores.get(policy, 0.0))
            else:
                y_vals.append(getattr(br, metric, 0.0))
        ax.plot(values, y_vals, marker="o", label=policy)

    ax.set_xlabel(param_name)
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} vs {param_name}")
    ax.legend()
    return fig


def create_dashboard(
    batch_result: BatchResult,
    path: str | Path,
) -> None:
    if not _MATPLOTLIB:
        raise ImportError("matplotlib is required for plotting")
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Packet Pressure Simulation Dashboard", fontsize=14)

    plot_win_rates(batch_result, ax=axes[0, 0])
    plot_score_distribution(batch_result, ax=axes[0, 1])
    plot_route_length_histogram(batch_result, ax=axes[1, 0])

    # 4th panel: collision and dead rounds summary
    ax = axes[1, 1]
    summary_labels = ["Collision/Round", "Dead Round Rate", "Avg Route Len"]
    summary_vals = [
        batch_result.collision_avg,
        batch_result.dead_round_rate,
        batch_result.route_length_avg,
    ]
    ax.barh(summary_labels, summary_vals, color="teal", edgecolor="white")
    ax.set_title("Game Quality Metrics")

    suffix = ".pdf" if str(path).endswith(".pdf") else ""
    fig_path = path / f"dashboard{suffix or '.png'}"
    plt.tight_layout()
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)
