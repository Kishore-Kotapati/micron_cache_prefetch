#!/usr/bin/env python3
"""evaluate_results.py - turn results/performance_summary.csv (simulation data)
into markdown tables for the report: results/summary_tables.md"""
import math, os
import pandas as pd
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
df = pd.read_csv(os.path.join(ROOT, "results", "performance_summary.csv"))
ORDER = ["sequential", "stride", "random", "repeated", "mixed", "capacity", "cnn", "llm", "recsys"]
out = []
out.append("### Baseline (A) vs final design (B)\n")
out.append("| Trace | Hit % A → B | Miss % A → B | AMAT (cyc) A → B | Cycles A → B | Speedup | Improvement | DRAM txns A → B | PF issued | PF accuracy (useful / +late) | Coverage |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|")
for t in ORDER:
    a = df[(df.trace == t) & (df.config == "baseline")].iloc[0]
    b = df[(df.trace == t) & (df.config == "smart")].iloc[0]
    out.append(f"| {t} | {a.hit_rate_pct:.2f} → {b.hit_rate_pct:.2f} | {a.miss_rate_pct:.2f} → {b.miss_rate_pct:.2f} | "
               f"{a.amat_measured:.2f} → {b.amat_measured:.2f} | {a.cycles} → {b.cycles} | {b.speedup:.2f}× | "
               f"{b.improvement_pct:.1f} % | {a.dram_transactions} → {b.dram_transactions} | {b.prefetch_dram} | "
               f"{b.pf_accuracy_pct:.1f} % / {b.pf_accuracy_incl_late_pct:.1f} % | {b.pf_coverage_pct:.1f} % |")
out.append("\n### Speedup of every architecture (execution cycles, baseline = 1.00)\n")
cfgs = list(dict.fromkeys(df.config))
out.append("| Trace | " + " | ".join(cfgs) + " |")
out.append("|---|" + "---|" * len(cfgs))
for t in ORDER:
    out.append(f"| {t} | " + " | ".join(f"{df[(df.trace==t)&(df.config==c)].speedup.iloc[0]:.2f}" for c in cfgs) + " |")
def gm(c, ts):
    v = df[(df.config == c) & (df.trace.isin(ts))].speedup
    return math.exp(sum(map(math.log, v)) / len(v))
out.append("| **geo-mean, all 9** | " + " | ".join(f"**{gm(c, ORDER):.2f}**" for c in cfgs) + " |")
out.append("| **geo-mean, cnn/llm/recsys** | " + " | ".join(f"**{gm(c, ['cnn','llm','recsys']):.2f}**" for c in cfgs) + " |")
out.append("\n### DRAM traffic relative to baseline (cost of prefetching)\n")
out.append("| Trace | " + " | ".join(cfgs) + " |")
out.append("|---|" + "---|" * len(cfgs))
for t in ORDER:
    out.append(f"| {t} | " + " | ".join(f"{df[(df.trace==t)&(df.config==c)].dram_traffic_vs_base.iloc[0]:.2f}" for c in cfgs) + " |")
txt = "\n".join(out) + "\n"
open(os.path.join(ROOT, "results", "summary_tables.md"), "w").write(txt)
print(txt)
