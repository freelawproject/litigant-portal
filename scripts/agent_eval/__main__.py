"""
Command-line entry point; live calls occur only for run and judge.
"""

import argparse
import os
import sys
from pathlib import Path

from .schema import HERE, ROOT, Config, Weights, read_config


def main():
    parser = argparse.ArgumentParser(
        description="Compare raw, old, and new agent outputs."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser(
        "run", help="Run live systems and grade their answers."
    )
    run.add_argument("--config", type=Path, default=HERE / "config.yml")
    run.add_argument("--output", type=Path, default=ROOT / "evals")
    run.add_argument("--systems", nargs="+")
    run.add_argument("--models", nargs="+")
    run.add_argument("--cases", nargs="+")
    run.add_argument("--repetitions", type=int)
    run.add_argument("--slug")
    run.add_argument("--no-judge", action="store_true")
    grading = commands.add_parser(
        "judge", help="Grade saved answers with a new judgment batch."
    )
    grading.add_argument("run", type=Path)
    grading.add_argument("--model")
    grading.add_argument("--retry-failed", action="store_true")
    grading.add_argument("--dry-run", action="store_true")
    recover = commands.add_parser(
        "recover", help="Revalidate saved judge responses without API calls."
    )
    recover.add_argument("run", type=Path)
    recover.add_argument("--dry-run", action="store_true")
    report = commands.add_parser(
        "report", help="Rebuild or compare reports without API calls."
    )
    report.add_argument("runs", nargs="+", type=Path)
    report.add_argument("--facts-weight", type=float)
    report.add_argument("--output", type=Path)
    restore = commands.add_parser(
        "restore", help="Restore fixture settings after a hard-killed run."
    )
    restore.add_argument("run", type=Path)
    worker = commands.add_parser("_worker", help=argparse.SUPPRESS)
    worker.add_argument("run", type=Path)
    worker.add_argument("record", type=Path)
    worker.add_argument("--grading", action="store_true")
    args = parser.parse_args()
    from . import runner
    from .report import report_runs

    if args.command == "_worker":
        runner.worker(args.run.resolve(), args.record.resolve(), args.grading)
        return 0
    if args.command == "restore":
        from .remote import ContainerWorker

        with ContainerWorker(args.run.resolve()) as remote:
            remote.request("restore")
        return 0
    if args.command == "report":
        weights = None
        if args.facts_weight is not None:
            weights = Weights(
                facts=args.facts_weight, qualitative=1 - args.facts_weight
            )
        report_runs([run.resolve() for run in args.runs], weights, args.output)
        return 0
    if args.command == "recover":
        run = args.run.resolve()
        runner.recover_run(run, dry_run=args.dry_run)
        if not args.dry_run:
            report_runs([run])
        return 0
    if args.command == "run":
        config = read_config(args.config).model_dump()
        for field in ("systems", "models", "cases", "repetitions", "slug"):
            if getattr(args, field) is not None:
                config[field] = getattr(args, field)
        config = Config.model_validate(config)
        if "raw" in config.systems or not args.no_judge:
            require_key()
        run = runner.run_suite(config, args.output.resolve())
        if not args.no_judge:
            runner.judge_run(run)
    else:
        run = args.run.resolve()
        runner.judge_run(
            run,
            args.model,
            retry_failed=args.retry_failed,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            return 0
    reports = report_runs([run])
    incomplete = int(
        any(
            row["execution_failures"]
            or row["missing"]
            or (row["ungraded"] and not getattr(args, "no_judge", False))
            for row in reports[0]["systems"]
        )
    )
    if incomplete:
        print(
            "Evaluation incomplete; see grading counts above. "
            "Use 'recover RUN' for offline recovery, then "
            "'judge RUN --retry-failed' for unresolved judgments.",
            file=sys.stderr,
        )
    return incomplete


def require_key():
    if not os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "").strip():
        raise ValueError(
            "Set AWS_BEARER_TOKEN_BEDROCK locally for raw calls and judging."
        )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(
            "Interrupted; saved attempts remain available for judge/report.",
            file=sys.stderr,
        )
        sys.exit(130)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"agent-eval: {exc}", file=sys.stderr)
        sys.exit(1)
