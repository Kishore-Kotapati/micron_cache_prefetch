#!/usr/bin/env python3
"""
visualize_results.py - plots from results/performance_summary.csv
(all values come from RTL simulation logs written by run_all.py).
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RES = os.path.join(ROOT, "results")
PLOTS = os.path.join(RES, "plots")
ORDER = ["sequential", "stride", "random", "repeated", "mixed", "capacity", "cnn", "llm", "recsys"]
CFGS = ["baseline", "nextline", "stride", "stride_adapt", "smart"]
COLORS = {"baseline": "#9aa0a6", "nextline": "#7fb3d5", "stride": "#5dade2",
          "stride_adapt": "#2e86c1", "smart": "#c2185b"}
LABEL = {"baseline": "A: baseline (no prefetch)", "nextline": "next-line prefetch",
         "stride": "stride, fixed degree", "stride_adapt": "stride + adaptive degree",
         "smart": "B: final design (hybrid stride + adaptive degree + adaptive insertion)"}


def grouped(df, col, ylabel, title, fname, cfgs=CFGS, ref=None):
    fig, ax = plt.subplots(figsize=(12, 4.2))
    w = 0.8 / len(cfgs)
    for i, c in enumerate(cfgs):
        sub = df[df.config == c].set_index("trace").reindex(ORDER)
        ax.bar([x + i * w for x in range(len(ORDER))], sub[col], w, label=LABEL[c], color=COLORS[c])
    ax.set_xticks([x + w * (len(cfgs) - 1) / 2 for x in range(len(ORDER))])
    ax.set_xticklabels(ORDER)
    ax.set_ylabel(ylabel); ax.set_title(title)
    if ref is not None:
        ax.axhline(ref, color="k", lw=0.8, ls="--")
    ax.legend(fontsize=8, ncol=2); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, fname), dpi=130); plt.close(fig)


def main():
    df = pd.read_csv(os.path.join(RES, "performance_summary.csv"))
    os.makedirs(PLOTS, exist_ok=True)
    grouped(df, "speedup", "speedup vs baseline (x)", "Execution-time speedup (RTL simulation)", "speedup.png", ref=1.0)
    grouped(df, "hit_rate_pct", "demand hit rate (%)", "Cache hit rate", "hit_rate.png")
    grouped(df, "amat_measured", "cycles", "Average memory access latency (measured)", "amat.png")
    grouped(df, "dram_traffic_vs_base", "DRAM transactions / baseline", "DRAM traffic (cost of prefetching)",
            "dram_traffic.png", ref=1.0)
    grouped(df, "pf_accuracy_incl_late_pct", "useful (+late) / issued (%)", "Prefetch accuracy",
            "pf_accuracy.png", cfgs=CFGS[1:])
    # A vs B headline chart
    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    a = df[df.config == "baseline"].set_index("trace").reindex(ORDER)
    b = df[df.config == "smart"].set_index("trace").reindex(ORDER)
    x = range(len(ORDER))
    ax[0].bar([i - 0.2 for i in x], a.miss_rate_pct, 0.4, label="A baseline", color=COLORS["baseline"])
    ax[0].bar([i + 0.2 for i in x], b.miss_rate_pct, 0.4, label="B final design", color=COLORS["smart"])
    ax[0].set_title("Demand miss rate (%)"); ax[0].set_xticks(list(x)); ax[0].set_xticklabels(ORDER, rotation=30)
    ax[0].legend()
    ax[1].bar([i - 0.2 for i in x], a.cycles / 1000, 0.4, label="A baseline", color=COLORS["baseline"])
    ax[1].bar([i + 0.2 for i in x], b.cycles / 1000, 0.4, label="B final design", color=COLORS["smart"])
    ax[1].set_title("Total execution cycles (thousands)"); ax[1].set_xticks(list(x))
    ax[1].set_xticklabels(ORDER, rotation=30); ax[1].legend()
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, "baseline_vs_final.png"), dpi=130); plt.close(fig)
    print("plots written to", os.path.relpath(PLOTS))


if __name__ == "__main__":
    main()
