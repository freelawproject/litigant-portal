"""
Rebuild comparison JSON and Matplotlib charts from saved evidence only.
"""

import json
from collections import Counter
from pathlib import Path
from statistics import mean, median, pstdev

from .judge import score
from .schema import (
    DIMENSIONS,
    Grade,
    Weights,
    fingerprint,
    verify_references,
    write_json,
)


def cost_total(calls: list[dict]) -> float | None:
    if not calls or any(call.get("cost_usd") is None for call in calls):
        return None
    return sum(call["cost_usd"] for call in calls)


def token_total(calls: list[dict], kind: str) -> int | None:
    if not calls or any(call.get(kind) is None for call in calls):
        return None
    return sum(call[kind] for call in calls)


def paired_success(rows: list[dict], cases: list[dict]) -> dict:
    """
    Count correct answers to both versions only when their answer keys differ.
    """
    definitions = {case["id"]: case for case in cases}
    attempts = {(row["case_id"], row["repeat"]): row for row in rows}
    evaluated, passed = 0, 0
    for (case_id, repeat), left in attempts.items():
        if not case_id.startswith("chickens-") or not case_id.endswith("-a"):
            continue
        other = case_id[:-1] + "b"
        right = attempts.get((other, repeat))
        if (
            not right
            or definitions[case_id]["facts"] == definitions[other]["facts"]
        ):
            continue
        if left["score"] is None or right["score"] is None:
            continue
        evaluated += 1
        passed += bool(
            left["critical_facts_answered"]
            and right["critical_facts_answered"]
        )
    return {
        "graded_pairs": evaluated,
        "both_correct": passed,
        "rate": passed / evaluated if evaluated else None,
    }


def summarize(run: Path, weights: Weights | None = None) -> dict:
    manifest = json.loads((run / "manifest.json").read_text())
    verify_references(run, manifest)
    weights = weights or Weights.model_validate(manifest["config"]["weights"])
    folders = sorted((run / "judgments").glob("*/batch.json"))
    batch_path = folders[-1] if folders else None
    batch = (
        json.loads(batch_path.read_text()) if batch_path else {"judgments": {}}
    )
    records = []
    for relative in manifest["attempts"]:
        row = json.loads((run / relative).read_text())
        judgment = None
        if relative in batch["judgments"]:
            judgment = json.loads(
                (batch_path.parent / batch["judgments"][relative]).read_text()
            )
        scored = None
        if judgment and judgment["status"] == "completed":
            scored = score(
                Grade.model_validate(judgment["grade"]),
                judgment["score"]["deal_breakers"],
                weights,
            )
        overall = scored["overall"] if scored else None
        quality = scored["uncapped"] if scored else None
        if row["status"] in {"error", "interrupted"}:
            overall = quality = 0
        records.append(
            {
                "attempt": relative,
                "case_id": row["case"]["id"],
                "repeat": row["repeat"],
                "group": row["case"]["group"],
                "system": row["system"],
                "model": row["model"],
                "status": row["status"],
                "overall": overall,
                "quality": quality,
                "score": scored,
                "critical_facts_answered": bool(scored)
                and not scored["deal_breakers"]
                and all(
                    next(
                        fact
                        for fact in judgment["grade"]["facts"]
                        if fact["fact_id"] == expected["id"]
                    )["status"]
                    == "supported"
                    for expected in row["case"]["facts"]
                    if expected["critical"]
                ),
                "judge_status": judgment["status"] if judgment else "ungraded",
                "cost_usd": cost_total(row["calls"]),
                "known_cost_usd": sum(
                    call["cost_usd"]
                    for call in row["calls"]
                    if call.get("cost_usd") is not None
                ),
                "auxiliary_failures": [
                    {
                        key: call.get(key)
                        for key in ("model", "error", "error_message")
                    }
                    for call in row["calls"]
                    if row["system"] == "old"
                    and call.get("error")
                    and not call.get("request", {}).get("stream")
                ],
                "input_tokens": token_total(row["calls"], "input_tokens"),
                "output_tokens": token_total(row["calls"], "output_tokens"),
                "call_count": len(row["calls"]),
                "judge_cost_usd": cost_total(judgment["calls"])
                if judgment
                else None,
                "elapsed_seconds": row.get("elapsed_seconds"),
                "first_text_seconds": row.get("first_text_seconds"),
                "corpus_load_observed": row.get("detail", {}).get(
                    "corpus_load_observed", False
                ),
            }
        )
    summaries = []
    for system in manifest["config"]["systems"]:
        for model in manifest["config"]["models"]:
            for group in dict.fromkeys(
                case["group"] for case in manifest["cases"]
            ):
                rows = [
                    row
                    for row in records
                    if (row["system"], row["model"], row["group"])
                    == (system, model, group)
                ]
                planned = (
                    sum(case["group"] == group for case in manifest["cases"])
                    * manifest["config"]["repetitions"]
                )
                graded = [row for row in rows if row["score"] is not None]
                scores = [
                    row["overall"]
                    for row in rows
                    if row["overall"] is not None
                ]
                quality_scores = [
                    row["quality"]
                    for row in rows
                    if row["quality"] is not None
                ]
                costs = [
                    row["cost_usd"]
                    for row in rows
                    if row["cost_usd"] is not None
                ]
                gates = Counter()
                for row in graded:
                    gates.update(
                        {
                            failure["category"]
                            for failure in row["score"]["deal_breakers"]
                        }
                    )
                summaries.append(
                    {
                        "system": system,
                        "model": model,
                        "group": group,
                        "planned": planned,
                        "recorded": len(rows),
                        "graded": len(graded),
                        "execution_failures": sum(
                            row["status"] in {"error", "interrupted"}
                            for row in rows
                        ),
                        "ungraded": sum(
                            row["overall"] is None for row in rows
                        ),
                        "missing": planned - len(rows),
                        "overall": mean(scores)
                        if len(scores) == planned
                        else None,
                        "score_stddev": pstdev(scores)
                        if len(scores) == planned
                        else None,
                        "quality": mean(quality_scores)
                        if len(quality_scores) == planned
                        else None,
                        "quality_stddev": pstdev(quality_scores)
                        if len(quality_scores) == planned
                        else None,
                        "critical_failure_count": sum(
                            bool(row["score"]["deal_breakers"])
                            for row in graded
                        ),
                        "auxiliary_failure_count": sum(
                            len(row["auxiliary_failures"]) for row in rows
                        ),
                        "dimensions": {
                            name: mean(
                                row["score"]["dimensions"][name]
                                for row in graded
                            )
                            if graded
                            else None
                            for name in DIMENSIONS
                        },
                        "deal_breakers": dict(gates),
                        "deal_breaker_rate": sum(
                            bool(row["score"]["deal_breakers"])
                            for row in graded
                        )
                        / len(graded)
                        if graded
                        else None,
                        "outcomes": dict(
                            Counter(
                                row["score"]["answer_outcome"]
                                for row in graded
                            )
                        ),
                        "corpus_loads_observed": sum(
                            row["corpus_load_observed"] for row in rows
                        ),
                        "source_attribution": dict(
                            Counter(
                                row["score"]["source_attribution"]
                                for row in graded
                            )
                        ),
                        "changed_corpus_pairs": paired_success(
                            rows, manifest["cases"]
                        ),
                        "mean_cost_usd": mean(costs)
                        if len(costs) == planned
                        else None,
                        "known_cost_usd": sum(
                            row["known_cost_usd"] for row in rows
                        ),
                        "unknown_cost_attempts": planned - len(costs),
                        "median_seconds": median(values)
                        if (
                            values := [
                                row["elapsed_seconds"]
                                for row in rows
                                if row["elapsed_seconds"] is not None
                            ]
                        )
                        else None,
                        "median_first_text_seconds": median(values)
                        if (
                            values := [
                                row["first_text_seconds"]
                                for row in rows
                                if row["first_text_seconds"] is not None
                            ]
                        )
                        else None,
                    }
                )
    all_batches = []
    for path in folders:
        content = json.loads(path.read_text())
        for name in content["judgments"].values():
            all_batches.extend(
                json.loads((path.parent / name).read_text())["calls"]
            )
    return {
        "report_version": 2,
        "run": run.name,
        "benchmark_id": manifest["benchmark_id"],
        "scoring_version": manifest["scoring_version"],
        "weights": weights.model_dump(),
        "judgment_batch": batch_path.parent.name if batch_path else None,
        "judge_model": batch.get("config", {})
        .get("model_ids", {})
        .get(batch.get("config", {}).get("judge_model")),
        "system_totals": {
            "known_cost_usd": sum(row["known_cost_usd"] for row in records),
            "unknown_cost_attempts": sum(
                row["cost_usd"] is None for row in records
            ),
            "call_count": sum(row["call_count"] for row in records),
        },
        "evaluator_totals_all_batches": {
            "known_cost_usd": sum(
                call["cost_usd"]
                for call in all_batches
                if call.get("cost_usd") is not None
            ),
            "unknown_cost_calls": sum(
                call.get("cost_usd") is None for call in all_batches
            ),
            "call_count": len(all_batches),
        },
        "systems": summaries,
        "attempts": records,
        "notes": [
            "Real-case accuracy is relative to repository references, not independently verified law.",
            "Fictional results measure adherence to invented corpus content.",
            "Quality is the weighted score before gates; overall retains the critical-failure zero.",
            "Overall is unavailable until every planned attempt is scored or an execution failure.",
            "Dimension means and deal-breaker rates use graded answers; see graded counts.",
            "Costs are estimates. Missing usage/pricing is unknown, not zero.",
            "Score variation describes attempts; it is not a confidence interval.",
        ],
    }


def charts(reports: list[dict], output: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.lines import Line2D

    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {"font.size": 10, "axes.spines.top": False, "axes.spines.right": False}
    )
    colors = {"raw": "#64748b", "old": "#e09f3e", "new": "#168aad"}
    markers = {"raw": "o", "old": "s", "new": "^"}
    failure_legend = Line2D(
        [],
        [],
        marker="o",
        linestyle="none",
        color="#ff0000",
        label="Critical failure",
    )
    for group in ("real", "fictional"):
        rows, labels = [], []
        for report in reports:
            for row in report["systems"]:
                if row["group"] == group:
                    rows.append(row)
                    label = f"{row['system']} / {row['model']}"
                    if len(reports) > 1:
                        label += f"\n{report['run']}"
                    labels.append(label)
        if not rows:
            continue
        palette = [colors[row["system"]] for row in rows]
        quality_colors = [
            "#ff0000"
            if row["critical_failure_count"]
            else colors[row["system"]]
            for row in rows
        ]
        counted_labels = [
            f"{label}\nn={row['planned']}; critical={row['critical_failure_count']}/{row['graded']}"
            for label, row in zip(labels, rows, strict=True)
        ]
        x = np.arange(len(rows))

        def save(fig, name, group=group):
            fig.savefig(
                output / f"{group}-{name}.png", dpi=180, bbox_inches="tight"
            )
            plt.close(fig)

        fig, ax = plt.subplots(
            figsize=(max(8, len(rows) * 1.3), 4.8), layout="constrained"
        )
        for i, row in enumerate(rows):
            if row["quality"] is None:
                ax.text(
                    i,
                    4,
                    "ungraded /\nincomplete",
                    ha="center",
                    color="#64748b",
                )
            else:
                ax.errorbar(
                    i,
                    row["quality"],
                    yerr=row["quality_stddev"],
                    color=quality_colors[i],
                    marker=markers[row["system"]],
                    markersize=8,
                    capsize=3,
                )
                ax.annotate(
                    f"{row['quality']:.1f}",
                    (i, row["quality"]),
                    xytext=(0, 9),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8,
                )
        ax.set(
            xticks=x,
            xticklabels=counted_labels,
            ylim=(0, 110),
            xlim=(-0.5, len(rows) - 0.5),
            ylabel="Weighted quality (0–100)",
            title=f"{group.title()} cases · quality before critical-failure gates",
        )
        ax.tick_params(axis="x", labelrotation=20)
        ax.grid(axis="y", alpha=0.15)
        ax.legend(handles=[failure_legend], loc="lower right", frameon=False)
        save(fig, "quality")

        fig, ax = plt.subplots(
            figsize=(max(8, len(rows) * 1.3), 4.8), layout="constrained"
        )
        bottom = np.zeros(len(rows))
        for outcome, color in (
            ("answered", "#168aad"),
            ("partial", "#e09f3e"),
            ("deferred", "#64748b"),
            ("execution failure", "#c44536"),
            ("ungraded/missing", "#e2e8f0"),
        ):
            amounts = []
            for row in rows:
                count = row["outcomes"].get(outcome, 0)
                if outcome == "execution failure":
                    count = row["execution_failures"]
                elif outcome == "ungraded/missing":
                    count = row["ungraded"] + row["missing"]
                amounts.append(100 * count / row["planned"])
            ax.bar(x, amounts, bottom=bottom, label=outcome, color=color)
            bottom += amounts
        ax.set(
            xticks=x,
            xticklabels=labels,
            ylim=(0, 100),
            ylabel="Percent of planned attempts",
            title=f"{group.title()} cases · answer outcomes (correctness scored separately)",
        )
        ax.tick_params(axis="x", labelrotation=20)
        ax.legend(
            loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, fontsize=8
        )
        save(fig, "outcomes")

        fig, ax = plt.subplots(
            figsize=(10, max(3, len(rows) * 0.6)), layout="constrained"
        )
        matrix = np.array(
            [
                [
                    row["dimensions"][name]
                    if row["dimensions"][name] is not None
                    else np.nan
                    for name in DIMENSIONS
                ]
                for row in rows
            ]
        )
        im = ax.imshow(matrix, vmin=0, vmax=100, cmap="YlGnBu", aspect="auto")
        for i in range(len(rows)):
            for j in range(len(DIMENSIONS)):
                value = matrix[i, j]
                ax.text(
                    j,
                    i,
                    "—" if np.isnan(value) else f"{value:.0f}",
                    ha="center",
                    va="center",
                    color="white" if value > 65 else "#1e293b",
                )
        ax.set(
            xticks=range(len(DIMENSIONS)),
            xticklabels=DIMENSIONS,
            yticks=x,
            yticklabels=labels,
            title=f"{group.title()} cases · dimensions before gates (graded answers)",
        )
        ax.tick_params(axis="x", labelrotation=25)
        fig.colorbar(im, ax=ax, label="Score")
        save(fig, "dimensions")

        unknown_rows = [
            i
            for i, row in enumerate(rows)
            if row["mean_cost_usd"] is None and row["quality"] is not None
        ]
        if unknown_rows:
            fig, (ax, unknown_ax) = plt.subplots(
                1,
                2,
                figsize=(11, 5.5),
                sharey=True,
                layout="constrained",
                gridspec_kw={
                    "width_ratios": [3, max(1, len(unknown_rows) * 0.7)]
                },
            )
            unknown_ax.set(
                title="Cost unavailable",
                xticks=range(len(unknown_rows)),
                xticklabels=[counted_labels[i] for i in unknown_rows],
                xlim=(-0.6, len(unknown_rows) - 0.4),
            )
            unknown_ax.tick_params(axis="x", labelrotation=20, labelsize=8)
            unknown_ax.grid(axis="y", alpha=0.15)
            for position, i in enumerate(unknown_rows):
                row = rows[i]
                unknown_ax.scatter(
                    position,
                    row["quality"],
                    s=85,
                    color=quality_colors[i],
                    marker=markers[row["system"]],
                )
                unknown_ax.annotate(
                    f"{row['quality']:.1f}",
                    (position, row["quality"]),
                    xytext=(0, 9),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8,
                )
        else:
            fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")
        for i, row in enumerate(rows):
            if row["mean_cost_usd"] is not None and row["quality"] is not None:
                ax.scatter(
                    row["mean_cost_usd"],
                    row["quality"],
                    s=85,
                    color=quality_colors[i],
                    marker=markers[row["system"]],
                )
                ax.annotate(
                    counted_labels[i],
                    (row["mean_cost_usd"], row["quality"]),
                    xytext=(5, 6 + i % 2 * 9),
                    textcoords="offset points",
                    fontsize=8,
                )
        ax.set(
            xlabel="Mean estimated system cost per attempt (USD)\nJudge cost excluded",
            ylabel="Weighted quality (0–100)",
            ylim=(-5, 110),
        )
        fig.suptitle(
            f"{group.title()} cases · cost versus quality before gates"
        )
        if not any(
            row["mean_cost_usd"] is not None and row["quality"] is not None
            for row in rows
        ):
            ax.text(
                0.5,
                0.5,
                "No complete cost/quality pairs",
                ha="center",
                transform=ax.transAxes,
            )
            ax.set_xticks([])
        ax.legend(handles=[failure_legend], loc="lower right", frameon=False)
        ax.margins(x=0.4)
        ax.grid(alpha=0.15)
        save(fig, "cost-quality")

        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
        for ax, field, title, unit in (
            (axes[0], "median_seconds", "Response latency", "Median seconds"),
            (axes[1], "mean_cost_usd", "System cost", "Mean estimated USD"),
        ):
            ax.bar(
                x,
                [
                    row[field] if row[field] is not None else np.nan
                    for row in rows
                ],
                color=palette,
            )
            ax.set(xticks=x, xticklabels=labels, ylabel=unit, title=title)
            ax.tick_params(axis="x", labelrotation=35)
            ax.grid(axis="y", alpha=0.15)
        fig.suptitle(f"{group.title()} cases · operational measurements")
        save(fig, "operations")

        categories = (
            "citation",
            "hard_fact",
            "legal_direction",
            "missed_escalation",
            "unsupported_claim",
        )
        fig, ax = plt.subplots(
            figsize=(10, max(3, len(rows) * 0.6)), layout="constrained"
        )
        failures = np.array(
            [
                [
                    100 * row["deal_breakers"].get(cat, 0) / row["graded"]
                    if row["graded"]
                    else np.nan
                    for cat in categories
                ]
                for row in rows
            ]
        )
        im = ax.imshow(failures, vmin=0, vmax=100, cmap="OrRd", aspect="auto")
        for i in range(len(rows)):
            for j in range(len(categories)):
                value = failures[i, j]
                ax.text(
                    j,
                    i,
                    "—" if np.isnan(value) else f"{value:.0f}%",
                    ha="center",
                    va="center",
                    color="white" if value > 65 else "#1e293b",
                )
        ax.set(
            xticks=range(len(categories)),
            xticklabels=categories,
            yticks=x,
            yticklabels=labels,
            title=f"{group.title()} cases · deal breakers (% of graded answers)",
        )
        ax.tick_params(axis="x", labelrotation=20)
        fig.colorbar(im, ax=ax, label="Percent")
        save(fig, "deal-breakers")


def report_runs(
    runs: list[Path],
    weights: Weights | None = None,
    output: Path | None = None,
):
    reports = [summarize(run, weights) for run in runs]
    if len({report["benchmark_id"] for report in reports}) != 1:
        raise ValueError(
            "Runs have different case/reference/rubric versions; report them separately."
        )
    if len({fingerprint(report["weights"]) for report in reports}) != 1:
        raise ValueError(
            "Runs have different weights; supply a common --facts-weight."
        )
    if len({report["judge_model"] for report in reports}) != 1:
        raise ValueError(
            "Runs use different judge models; rejudge with the same model before comparing."
        )
    if output is None:
        if len(runs) == 1 and weights is None:
            output = runs[0]
        else:
            signature = fingerprint(
                {
                    "runs": [str(run) for run in runs],
                    "weights": reports[0]["weights"],
                }
            )[:12]
            output = runs[0] / "reports" / signature
    write_json(
        output / "summary.json",
        reports[0] if len(reports) == 1 else {"runs": reports},
    )
    charts(reports, output / "charts")
    print(f"Report: {output / 'summary.json'}", flush=True)
    return reports
