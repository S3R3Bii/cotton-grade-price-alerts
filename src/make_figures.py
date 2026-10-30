"""Plot controlled mixture effects and report each value's source and geometry."""

import csv
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "svg.fonttype": "none",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.labelcolor": "#233b49",
        "text.color": "#233b49",
        "axes.edgecolor": "#a5b2b7",
        "savefig.facecolor": "white",
    }
)
BLUE = "#235d72"
ORANGE = "#b65f27"
GREY = "#6a7b82"


def read(name):
    return list(csv.DictReader((ROOT / name).open(encoding="utf-8", newline="")))


def finish(fig, axes, name, items, limits):
    fig.canvas.draw()
    height = fig.get_figheight() * 72
    scale = 72 / fig.dpi
    entries = []
    for artist, query, value, gid in items:
        artist.set_gid(gid)
        vertices = artist.get_path().transformed(artist.get_transform()).vertices
        entries.append(
            dict(
                id=gid,
                query=query,
                value_exact=str(value),
                vertices_svg=[
                    [float(x * scale), float(height - y * scale)] for x, y in vertices
                ],
            )
        )
    for index, ax in enumerate(axes):
        ax.patch.set_gid("data-area-" + str(index))
    paths = []
    for ext in ["pdf", "svg", "png"]:
        p = ROOT / "figures" / f"{name}.{ext}"
        fig.savefig(p, dpi=160 if ext == "png" else 100)
        if ext == 'svg':
            p.write_bytes(('\n'.join(line.rstrip() for line in p.read_text(encoding='utf-8').splitlines())+'\n').encode())
        paths.append(p)
    plt.close(fig)
    return dict(
        figure=name,
        axes=limits,
        items=entries,
        files={
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths
        },
    )


def main():
    premiums = read("results/held/source_premiums.csv")
    summary = read("results/held/summary.csv")
    detail = read("results/held/by_market_case.csv")
    figures = []
    markets = list(
        json.loads((ROOT / "data/market_bindings.json").read_text())["2024-2025"]
    )
    fig, ax = plt.subplots(figsize=(10, 4.35))
    fig.subplots_adjust(left=0.33, right=0.965, bottom=0.17, top=0.86)
    items = []
    stats = []
    for i, market in enumerate(markets):
        values = sorted(
            Fraction(r["composition_only_mean_change"]) * 100
            for r in premiums
            if r["market"] == market
        )
        median = values[len(values) // 2]
        lo, hi = values[0], values[-1]
        stats.append((median, lo, hi))
        bar = ax.barh(i, float(median), height=0.46, color=BLUE, zorder=2)[0]
        items.append(
            (
                bar,
                dict(kind="composition_median", market=market),
                median,
                "composition-median-" + str(i),
            )
        )
        line = ax.plot([float(lo), float(hi)], [i, i], color=ORANGE, lw=2.0, zorder=3)[
            0
        ]
        items.append(
            (
                line,
                dict(kind="composition_range", market=market),
                lo,
                "composition-range-" + str(i),
            )
        )
        ax.text(float(hi) + 0.1, i, f"{float(median):.3f}%", va="center", fontsize=9)
    xmax = max(float(s[2]) for s in stats) + 1.35
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.7, 6.7)
    ax.invert_yaxis()
    ax.set_yticks(range(7), markets)
    ax.tick_params(axis="y", length=0, labelsize=9)
    ax.set_xlabel("Authored equal-weight mixture change (%)")
    ax.grid(axis="x", alpha=0.18, zorder=0)
    fig.suptitle(
        "Adding a different quality can move a price average",
        x=0.33,
        ha="left",
        y=0.965,
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.33,
        0.895,
        "Bars: median    Orange line: observed min–max across 251 quote-days",
        fontsize=9,
        color=GREY,
    )
    figures.append(
        finish(
            fig,
            [ax],
            "composition_effects",
            items,
            [dict(xlim=[0, xmax], ylim=[6.7, -0.7])],
        )
    )
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.2, top=0.79, wspace=0.3)
    items = []
    thresholds = ["1/100", "1/50", "1/20"]
    for axis_index, (ax, numerator, denominator, title) in enumerate(
        [
            (
                axes[0],
                "fp",
                lambda r: int(r["fp"]) + int(r["tn"]),
                "False alerts among authored negatives",
            ),
            (
                axes[1],
                "fn",
                lambda r: int(r["fn"]) + int(r["tp"]),
                "Missed alerts among authored positives",
            ),
        ]
    ):
        for i, threshold in enumerate(thresholds):
            row = next(
                r
                for r in summary
                if r["rule"] == "grade_blind"
                and r["threshold"] == threshold
                and r["expansion"] == "1"
                and r["identity_mode"] == "normal"
            )
            den = denominator(row)
            value = Fraction(int(row[numerator]), den) * 100
            bar = ax.bar(
                i,
                float(value),
                width=0.58,
                color=ORANGE if numerator == "fp" else BLUE,
                zorder=2,
            )[0]
            items.append(
                (
                    bar,
                    dict(kind="error_rate", numerator=numerator, threshold=threshold),
                    value,
                    f"error-{numerator}-{i}",
                )
            )
            ax.text(
                i,
                float(value) + 2,
                f"{int(row[numerator]):,}/{den:,}",
                ha="center",
                va="bottom",
                fontsize=9,
            )
        ax.set_xticks(range(3), ["1%", "2%", "5%"])
        ax.set_xlim(-0.6, 2.6)
        ax.set_ylim(0, 116)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_xlabel("Fixed alert threshold")
        ax.set_ylabel("Conditional case rate (%)")
        ax.set_title(title, fontsize=11, loc="left", pad=14)
        ax.grid(axis="y", alpha=0.18, zorder=0)
    fig.suptitle(
        "Grade-blind errors in added-quality snapshots",
        x=0.08,
        ha="left",
        y=0.97,
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.08,
        0.865,
        "2024–2025 source pairs; seven equally enumerated authored signed changes",
        fontsize=9,
        color=GREY,
    )
    figures.append(
        finish(
            fig,
            list(axes),
            "alert_errors",
            items,
            [
                dict(xlim=[-0.6, 2.6], ylim=[0, 116]),
                dict(xlim=[-0.6, 2.6], ylim=[0, 116]),
            ],
        )
    )
    fig, ax = plt.subplots(figsize=(10, 3.7))
    fig.subplots_adjust(left=0.09, right=0.98, bottom=0.2, top=0.78)
    items = []
    modes = ["normal", "missing_base", "changed_quality"]
    for ri, rule in enumerate(["grade_blind", "quality_matched"]):
        for i, mode in enumerate(modes):
            selected = [
                r for r in summary if r["rule"] == rule and r["identity_mode"] == mode
            ]
            total = sum(int(r["cases"]) for r in selected)
            emitted = total - sum(int(r["abstain"]) for r in selected)
            value = Fraction(emitted, total) * 100
            bar = ax.bar(
                i + (-0.18 if ri == 0 else 0.18),
                float(value),
                width=0.32,
                color=ORANGE if ri == 0 else BLUE,
                label=(
                    "Grade-blind"
                    if ri == 0 and i == 0
                    else "Quality-matched" if ri == 1 and i == 0 else None
                ),
                zorder=2,
            )[0]
            items.append(
                (
                    bar,
                    dict(kind="coverage", rule=rule, identity_mode=mode),
                    value,
                    f"coverage-{ri}-{i}",
                )
            )
            ax.text(
                i + (-0.18 if ri == 0 else 0.18),
                float(value) + 2,
                f"{emitted:,}\n/{total:,}",
                ha="center",
                va="bottom",
                fontsize=9,
            )
    ax.set_xticks(
        range(3), ["Original identity present", "Base removed", "Base quality changed"]
    )
    ax.set_xlim(-0.6, 2.6)
    ax.set_ylim(0, 132)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("Cases with an emitted comparison (%)")
    ax.grid(axis="y", alpha=0.18, zorder=0)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.19), ncol=2, frameon=False)
    fig.suptitle(
        "Unknown identity requires an unavailable result",
        x=0.09,
        ha="left",
        y=0.98,
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.09,
        0.86,
        "Authored failure cases; emitting a number does not establish the same-quality comparison",
        fontsize=9,
        color=GREY,
    )
    figures.append(
        finish(
            fig,
            [ax],
            "identity_coverage",
            items,
            [dict(xlim=[-0.6, 2.6], ylim=[0, 132])],
        )
    )
    (ROOT / "figures/value_map.json").write_bytes(
        (json.dumps(figures, indent=2) + "\n").encode()
    )
    print("FIGURES_CREATED", len(figures), sum(len(f["items"]) for f in figures))


if __name__ == "__main__":
    main()
