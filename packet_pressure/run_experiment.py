from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analysis import create_dashboard, export_csv, export_sweep_csv, write_markdown_report
from .config_presets import (
    COMPETITIVE_CONFIG,
    DEFAULT_CONFIG,
    FAST_CONFIG,
    NO_SPECIAL_CONFIG,
)
from .models import GameConfig
from .policies import (
    ColorAwareRouteBuilder,
    DenialCollision,
    GreedyEndpoint,
    RandomLegal,
    RouteBuilder,
)
from .simulation import run_batch, sweep_parameter

_PRESET_MAP = {
    "default": DEFAULT_CONFIG,
    "fast": FAST_CONFIG,
    "competitive": COMPETITIVE_CONFIG,
    "no_special": NO_SPECIAL_CONFIG,
}

_POLICY_MAP = {
    "random": RandomLegal(),
    "greedy": GreedyEndpoint(),
    "denial": DenialCollision(),
    "builder": RouteBuilder(),
    "color_builder": ColorAwareRouteBuilder(),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Packet Pressure batch simulator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--preset",
        choices=list(_PRESET_MAP),
        default="default",
        help="Named GameConfig preset",
    )
    parser.add_argument("--n-games", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--policies",
        nargs="+",
        choices=list(_POLICY_MAP),
        default=["random", "greedy", "denial", "builder"],
    )
    parser.add_argument(
        "--sweep-param",
        type=str,
        default=None,
        metavar="FIELD",
        help="GameConfig field name to sweep",
    )
    parser.add_argument(
        "--sweep-values",
        nargs="+",
        type=str,
        default=None,
        metavar="VALUE",
        help="Values for the sweep parameter (auto-cast to field type)",
    )
    parser.add_argument("--output-dir", type=str, default="./results")
    parser.add_argument("--no-plots", action="store_true")

    args = parser.parse_args(argv)

    config: GameConfig = _PRESET_MAP[args.preset]
    policies = [_POLICY_MAP[p] for p in args.policies]

    # Adjust player_count to match number of policies
    if len(policies) != config.player_count:
        import dataclasses
        config = dataclasses.replace(config, player_count=len(policies))

    output = Path(args.output_dir)

    if args.sweep_param:
        if not args.sweep_values:
            print("--sweep-values is required when --sweep-param is set", file=sys.stderr)
            return 1

        import dataclasses as _dc
        field_map = {f.name: f for f in _dc.fields(config)}
        if args.sweep_param not in field_map:
            print(f"Unknown config field: {args.sweep_param}", file=sys.stderr)
            return 1

        field_type = field_map[args.sweep_param].type
        cast_values = _cast_sweep_values(args.sweep_values, field_type)

        print(
            f"Sweeping {args.sweep_param} over {cast_values} "
            f"({args.n_games} games each) …"
        )
        sweep_results = sweep_parameter(
            config,
            args.sweep_param,
            cast_values,
            policies,
            n_games=args.n_games,
            seed=args.seed,
            n_workers=args.workers,
        )
        export_sweep_csv(sweep_results, args.sweep_param, cast_values, output)
        write_markdown_report(
            sweep_results, output,
            sweep_param=args.sweep_param,
            sweep_values=cast_values,
        )
        if not args.no_plots:
            try:
                from .analysis import plot_sweep
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                fig = plot_sweep(sweep_results, args.sweep_param, cast_values)
                fig.savefig(output / f"sweep_{args.sweep_param}.png", dpi=120)
                plt.close(fig)
            except ImportError:
                pass
        print(f"Results written to {output}/")

    else:
        print(f"Running {args.n_games} games with policies {args.policies} …")
        batch = run_batch(
            config, policies,
            n_games=args.n_games,
            seed=args.seed,
            n_workers=args.workers,
        )
        export_csv(batch, output)
        write_markdown_report(batch, output)
        if not args.no_plots:
            try:
                create_dashboard(batch, output)
            except ImportError:
                pass

        print(f"\n=== Results ({args.n_games} games) ===")
        for policy in batch.policy_names:
            wr = batch.win_rates.get(policy, 0.0)
            avg = batch.avg_final_scores.get(policy, 0.0)
            print(f"  {policy:<30} win={wr:.1%}  avg_score={avg:.0f}")
        print(f"  avg_route_length={batch.route_length_avg:.2f}")
        print(f"  dead_round_rate={batch.dead_round_rate:.1%}")
        print(f"\nResults written to {output}/")

    return 0


def _cast_sweep_values(raw: list[str], field_type: type | str) -> list:
    # Attempt int → float → str cast
    results = []
    for v in raw:
        try:
            results.append(int(v))
            continue
        except ValueError:
            pass
        try:
            results.append(float(v))
            continue
        except ValueError:
            pass
        results.append(v)
    return results


if __name__ == "__main__":
    sys.exit(main())
