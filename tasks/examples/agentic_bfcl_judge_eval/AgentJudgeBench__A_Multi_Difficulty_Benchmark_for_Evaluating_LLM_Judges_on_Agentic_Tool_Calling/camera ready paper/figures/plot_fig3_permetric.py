"""
Regenerates Figure 3 (fig:permetric) of AgentJudgeBench: per-metric alignment
(with / without GT) across judges, now including Prometheus-2 as a 7th,
judge-specialised reference bar, shown alongside the six main judges.

Data source: Table tab:e4-permetric (sections/appendix.tex), which reports
mu^m_{j,r,c} * 100 averaged across all (generator, difficulty) configurations.

Usage:
    python plot_fig3_permetric.py
Writes: per_metric_both.pdf (same filename/location the paper's LaTeX embeds).
"""

import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Data (Table tab:e4-permetric)
# ---------------------------------------------------------------------------
METRICS = ["Tool\nSelection", "Parameter\nStructure", "Sequence\nAccuracy", "Query\nCoverage"]

JUDGES = [
    "GPT-5.4",
    "Claude",
    "Gemini-2.5-Pro",
    "QwQ-32B",
    "GPT-OSS-20B",
    "GPT-OSS-120B",
    "Prometheus-2",
]

WITH_GT = {
    "GPT-5.4":        [83.8, 90.0, 72.3, 94.0],
    "Claude":         [86.4, 86.5, 78.0, 92.7],
    "Gemini-2.5-Pro": [82.6, 89.4, 64.2, 93.3],
    "QwQ-32B":        [88.5, 89.8, 84.8, 93.9],
    "GPT-OSS-20B":    [70.7, 89.0, 86.4, 92.5],
    "GPT-OSS-120B":   [88.7, 89.7, 82.9, 93.5],
    "Prometheus-2":   [71.6, 43.5, 70.0, 56.4],
}

WITHOUT_GT = {
    "GPT-5.4":        [84.7, 89.8, 80.7, 91.0],
    "Claude":         [83.2, 88.2, 80.1, 91.3],
    "Gemini-2.5-Pro": [82.9, 89.5, 80.4, 92.3],
    "QwQ-32B":        [82.0, 89.9, 79.9, 91.5],
    "GPT-OSS-20B":    [81.7, 89.2, 79.5, 89.5],
    "GPT-OSS-120B":   [82.1, 89.9, 79.4, 91.6],
    "Prometheus-2":   [67.5, 49.7, 73.3, 60.9],
}

# Matplotlib's default "tab10" cycle -- unchanged from the original 6-judge
# figure; Prometheus-2 simply takes the next (7th) colour in the same cycle.
COLORS = plt.rcParams["axes.prop_cycle"].by_key()["color"][: len(JUDGES)]


def _grouped_bars(ax, data, title, annotate_spread=None, annotate_box=None):
    n_groups = len(METRICS)
    n_bars = len(JUDGES)
    x = np.arange(n_groups)
    width = 0.8 / n_bars

    for i, judge in enumerate(JUDGES):
        offsets = x - 0.4 + width / 2 + i * width
        values = data[judge]
        ax.bar(offsets, values, width, label=judge, color=COLORS[i], zorder=3)
        for xi, v in zip(offsets, values):
            ax.text(
                xi, v + 0.4, f"{v:.1f}",
                ha="center", va="bottom", rotation=90, fontsize=8.5, zorder=4,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(METRICS, fontsize=15, fontweight="bold")
    ax.set_ylabel("Alignment (%)", fontsize=15, fontweight="bold")
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.tick_params(axis="both", labelsize=13)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)

    if annotate_spread is not None:
        gx, ylo, yhi, color, label = annotate_spread
        ax.annotate(
            "", xy=(gx, yhi), xytext=(gx, ylo),
            arrowprops=dict(arrowstyle="<->", color=color, lw=1.5, mutation_scale=10),
        )
        ax.text(
            gx + 0.06, (ylo + yhi) / 2, label,
            fontsize=10, style="italic", color=color,
            ha="left", va="center",
        )

    if annotate_box is not None:
        ax.text(
            0.98, 0.03, annotate_box, transform=ax.transAxes,
            fontsize=10, style="italic", ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="0.92", edgecolor="0.6"),
        )

    return ax.get_ylim()


def main():
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Left panel: With GT. Sequence-accuracy spread (Gemini-2.5-Pro 64.2 -> GPT-OSS-20B 86.4)
    seq_idx = METRICS.index("Sequence\nAccuracy")
    seq_gap_x = (np.arange(len(METRICS)) - 0.4)[seq_idx] + 0.8 + 0.03  # just right of the group
    _grouped_bars(
        axes[0], WITH_GT, "With GT",
        annotate_spread=(seq_gap_x, 64.2, 86.4, "black", "22 pp\nspread"),
    )
    axes[0].set_ylim(bottom=min(WITH_GT["Prometheus-2"]) - 5, top=101)

    # Right panel: Without GT. Sequence-accuracy spread across the six main judges
    # (79.4 -> 80.7 = 1.3 pp) plus the "<=3pp on every metric" note (six-judge scope).
    _grouped_bars(
        axes[1], WITHOUT_GT, "Without GT",
        annotate_spread=(seq_gap_x, 79.4, 80.7, "firebrick", "1.3 pp"),
        annotate_box="All judges within ≤3 pp on every metric\n(six main judges)",
    )
    axes[1].set_ylim(bottom=min(WITHOUT_GT["Prometheus-2"]) - 5, top=98.5)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.06),
        ncol=len(JUDGES), frameon=True, fontsize=11,
    )

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig("per_metric_both.pdf", bbox_inches="tight")
    print("Wrote per_metric_both.pdf")


if __name__ == "__main__":
    main()
