#!/usr/bin/env python3
"""
analyze_traces.py - Level 1: memory-access-pattern analysis.

For every trace: unique lines (footprint), reuse (temporal locality),
same/next-line share (spatial locality), dominant byte strides, share of
accesses that follow a repeated stride (= how "prefetchable" it is), and the
ideal LRU hit rate of the 4 KB cache.  Writes results/trace_analysis.csv,
results/trace_analysis.txt and access-pattern plots.
"""
import csv
import os
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ref_cache_model import load_trace, simulate, LINE

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TRACES = ["sequential", "stride", "random", "repeated", "mixed",
          "capacity", "cnn", "llm", "recsys"]


def analyze(name):
    tr = load_trace(os.path.join(ROOT, "traces", f"{name}.trace"))
    addrs = [a for _, a in tr]
    lines = [a // LINE for a in addrs]
    n = len(addrs)
    uniq_addr, uniq_line = len(set(addrs)), len(set(lines))
    strides = [addrs[i] - addrs[i - 1] for i in range(1, n)]
    sc = Counter(strides)
    top = sc.most_common(3)
    # stride repeats (same stride as previous step)
    rep = sum(1 for i in range(1, len(strides)) if strides[i] == strides[i - 1])
    # spatial: next access in same or adjacent line
    spatial = sum(1 for i in range(1, n) if abs(lines[i] - lines[i - 1]) <= 1)
    # temporal: access to an address seen before
    seen, reuse = set(), 0
    for a in addrs:
        if a in seen:
            reuse += 1
        seen.add(a)
    h, m = simulate(addrs)
    return {
        "trace": name, "accesses": n,
        "unique_addresses": uniq_addr, "unique_lines": uniq_line,
        "footprint_KB": round(uniq_line * LINE / 1024, 2),
        "temporal_reuse_pct": round(100 * reuse / n, 1),
        "spatial_adjacent_pct": round(100 * spatial / max(1, n - 1), 1),
        "stride_repeat_pct": round(100 * rep / max(1, len(strides) - 1), 1),
        "top_strides": " ".join(f"{s:+d}B:{c}" for s, c in top),
        "lru_hit_rate_pct": round(100 * h / n, 2),
        "compulsory_misses": uniq_line,
    }


def plot(name, ax):
    tr = load_trace(os.path.join(ROOT, "traces", f"{name}.trace"))
    addrs = [a for _, a in tr][:4000]
    ax.scatter(range(len(addrs)), [a - min(addrs) for a in addrs], s=0.3)
    ax.set_title(name, fontsize=9)
    ax.set_xlabel("access #", fontsize=7)
    ax.set_ylabel("offset (B)", fontsize=7)
    ax.tick_params(labelsize=6)


def main():
    rows = [analyze(t) for t in TRACES]
    os.makedirs(os.path.join(ROOT, "results", "plots"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "trace_analysis.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader(); wr.writerows(rows)
    with open(os.path.join(ROOT, "results", "trace_analysis.txt"), "w") as f:
        hdr = f"{'trace':11s}{'acc':>6s}{'lines':>7s}{'KB':>7s}{'reuse%':>8s}{'spat%':>7s}{'strRep%':>8s}{'LRUhit%':>8s}  top strides"
        print(hdr); f.write(hdr + "\n")
        for r in rows:
            s = (f"{r['trace']:11s}{r['accesses']:6d}{r['unique_lines']:7d}{r['footprint_KB']:7.1f}"
                 f"{r['temporal_reuse_pct']:8.1f}{r['spatial_adjacent_pct']:7.1f}{r['stride_repeat_pct']:8.1f}"
                 f"{r['lru_hit_rate_pct']:8.2f}  {r['top_strides']}")
            print(s); f.write(s + "\n")
    fig, axs = plt.subplots(3, 3, figsize=(11, 8))
    for t, ax in zip(TRACES, axs.flat):
        plot(t, ax)
    fig.suptitle("Synthetic memory access patterns (address offset vs. access number)")
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "results", "plots", "access_patterns.png"), dpi=130)


if __name__ == "__main__":
    main()
