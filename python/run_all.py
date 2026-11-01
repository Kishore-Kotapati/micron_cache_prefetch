#!/usr/bin/env python3
"""
run_all.py - Level 4/5: compile the RTL with Icarus Verilog, run every trace on
every architecture, check correctness, compute metrics, write results.

Architectures (identical RTL + DRAM model, only run-time config differs):
  baseline      : no prefetching                                   (A)
  nextline      : classic sequential prefetcher, degree 1
  stride        : stride prefetcher, fixed degree 2, normal insertion
  stride_adapt  : + accuracy-feedback adaptive degree
  smart_noins   : + hybrid next-line kick-off for new streams (ablation)
  smart         : + adaptive prefetch-aware insertion  (final design, B)

Every number written comes from a simulation log (simulation/logs/*.log).
Baseline hit/miss counts are cross-checked against ref_cache_model.py.
"""
import csv
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from ref_cache_model import load_trace, simulate

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BUILD = os.path.join(ROOT, "simulation", "build")
LOGS = os.path.join(ROOT, "simulation", "logs")
RES = os.path.join(ROOT, "results")

TRACES = ["sequential", "stride", "random", "repeated", "mixed",
          "capacity", "cnn", "llm", "recsys"]
CONFIGS = {
    "baseline":     dict(mode=0, adaptive=0, degree=1, inslru=0),
    "nextline":     dict(mode=1, adaptive=0, degree=1, inslru=0),
    "stride":       dict(mode=2, adaptive=0, degree=2, inslru=0),
    "stride_adapt": dict(mode=2, adaptive=1, degree=2, inslru=0),
    "smart_noins":  dict(mode=3, adaptive=1, degree=2, inslru=0),
    "smart":        dict(mode=3, adaptive=1, degree=2, inslru=1),
}
HIT_TIME = 1


def compile_rtl():
    os.makedirs(BUILD, exist_ok=True)
    src = ["testbench/tb_system.v"] + sorted(
        os.path.join("rtl", f) for f in os.listdir(os.path.join(ROOT, "rtl")) if f.endswith(".v"))
    cmd = ["iverilog", "-g2005", "-Wall", "-o", "simulation/build/sim.vvp"] + src
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr); sys.exit("COMPILATION FAILED")
    errs = [l for l in p.stderr.splitlines() if "error" in l.lower()]
    if errs:
        print("\n".join(errs)); sys.exit("COMPILATION FAILED")
    print("compile OK:", " ".join(cmd))


def run_one(trace, cfg_name):
    cfg = CONFIGS[cfg_name]
    args = ["vvp", "-n", "simulation/build/sim.vvp", f"+trace=traces/{trace}.trace",
            f"+tag={cfg_name}"] + [f"+{k}={v}" for k, v in cfg.items()]
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    with open(os.path.join(LOGS, f"{trace}__{cfg_name}.log"), "w") as f:
        f.write(" ".join(args) + "\n" + p.stdout + p.stderr)
    m = re.search(r"^RESULT (.*)$", p.stdout, re.M)
    if not m or "TEST PASSED" not in p.stdout:
        return trace, cfg_name, None
    kv = dict(x.split("=", 1) for x in m.group(1).split())
    for k, v in kv.items():
        if v.lstrip("-").isdigit():
            kv[k] = int(v)
    return trace, cfg_name, kv


def main():
    os.makedirs(LOGS, exist_ok=True)
    os.makedirs(os.path.join(RES, "plots"), exist_ok=True)
    compile_rtl()
    jobs = [(t, c) for t in TRACES for c in CONFIGS]
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
        results = list(ex.map(lambda tc: run_one(*tc), jobs))
    raw = {}
    failed = []
    for t, c, kv in results:
        if kv is None:
            failed.append(f"{t}/{c}")
        raw[(t, c)] = kv
    print(f"simulations: {len(jobs)} run, {len(jobs) - len(failed)} PASSED, {len(failed)} FAILED")
    if failed:
        print("FAILED:", failed)

    # ---- golden-model cross-check of the baseline ----
    ref_ok = True
    for t in TRACES:
        h, m = simulate([a for _, a in load_trace(os.path.join(ROOT, "traces", f"{t}.trace"))])
        b = raw[(t, "baseline")]
        ok = b is not None and b["hits"] == h and b["misses"] == m
        ref_ok &= ok
        print(f"  ref-model check {t:11s}: python hits={h:5d} misses={m:5d} | "
              f"rtl hits={b['hits'] if b else '-':>5} misses={b['misses'] if b else '-':>5}  "
              f"{'MATCH' if ok else 'MISMATCH'}")

    # ---- metrics ----
    rows = []
    for t in TRACES:
        b = raw[(t, "baseline")]
        base_pen = b["miss_latency_sum"] / b["misses"] - HIT_TIME if b["misses"] else 0
        for c in CONFIGS:
            r = raw[(t, c)]
            if r is None:
                continue
            n = r["accesses"]
            dram = r["dem_mem"] + r["pf_issued"]
            iss = r["pf_issued"]
            rows.append({
                "trace": t, "config": c,
                "accesses": n, "hits": r["hits"], "misses": r["misses"],
                "hit_rate_pct": round(100 * r["hits"] / n, 2),
                "miss_rate_pct": round(100 * r["misses"] / n, 2),
                "dram_transactions": dram,
                "demand_dram": r["dem_mem"], "prefetch_dram": iss,
                "pf_useful": r["pf_useful"], "pf_late": r["pf_late"],
                "pf_unused": iss - r["pf_useful"] - r["pf_late"],
                "pf_filtered": r["pf_filtered"],
                "pf_accuracy_pct": round(100 * r["pf_useful"] / iss, 1) if iss else 0.0,
                "pf_accuracy_incl_late_pct": round(100 * (r["pf_useful"] + r["pf_late"]) / iss, 1) if iss else 0.0,
                "pf_coverage_pct": round(100 * (b["misses"] - r["misses"]) / b["misses"], 1) if b["misses"] else 0.0,
                "amat_measured": round(r["total_latency"] / n, 3),
                "amat_formula": round(HIT_TIME + (r["misses"] / n) * base_pen, 3),
                "avg_miss_latency": round(r["miss_latency_sum"] / max(1, r["misses"]), 2),
                "cycles": r["cycles"],
                "speedup": round(b["cycles"] / r["cycles"], 3),
                "improvement_pct": round(100 * (b["cycles"] - r["cycles"]) / b["cycles"], 2),
                "dram_traffic_vs_base": round(dram / max(1, b["dem_mem"]), 3),
                "final_degree": r["final_degree"],
                "errors": r["errors"],
            })
    with open(os.path.join(RES, "performance_summary.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader(); wr.writerows(rows)

    # ---- text comparison: baseline (A) vs smart (B) ----
    lines = []
    lines.append("Micron AI-Aware Cache & Prefetch Engine - measured RTL simulation results")
    lines.append("Cache 4KB 4-way 64 sets 16B lines LRU | DRAM latency 40 cyc, 1 req / 4 cyc | 8 MSHRs")
    lines.append(f"Simulations: {len(jobs)} run, {len(jobs)-len(failed)} passed all self-checks; "
                 f"baseline vs Python golden model: {'ALL MATCH' if ref_ok else 'MISMATCH'}")
    lines.append("")
    hdr = (f"{'trace':11s} {'config':13s} {'hit%':>7s} {'miss%':>6s} {'AMAT':>7s} {'cycles':>8s} "
           f"{'speedup':>7s} {'impr%':>7s} {'DRAM':>6s} {'pfIss':>6s} {'acc%':>6s} {'acc+late%':>9s} {'cov%':>6s} {'deg':>3s}")
    lines.append(hdr); lines.append("-" * len(hdr))
    for r in rows:
        lines.append(f"{r['trace']:11s} {r['config']:13s} {r['hit_rate_pct']:7.2f} {r['miss_rate_pct']:6.2f} "
                     f"{r['amat_measured']:7.2f} {r['cycles']:8d} {r['speedup']:7.3f} {r['improvement_pct']:7.2f} "
                     f"{r['dram_transactions']:6d} {r['prefetch_dram']:6d} {r['pf_accuracy_pct']:6.1f} "
                     f"{r['pf_accuracy_incl_late_pct']:9.1f} {r['pf_coverage_pct']:6.1f} {r['final_degree']:3d}")
        if r["config"] == list(CONFIGS)[-1]:
            lines.append("")
    # geometric-mean speedups
    import math
    lines.append("Geometric-mean speedup over baseline (all 9 traces):")
    for c in CONFIGS:
        sp = [r["speedup"] for r in rows if r["config"] == c]
        lines.append(f"  {c:13s} {math.exp(sum(math.log(x) for x in sp) / len(sp)):.3f}x")
    lines.append("Geometric-mean speedup on AI-inspired traces (cnn, llm, recsys):")
    for c in CONFIGS:
        sp = [r["speedup"] for r in rows if r["config"] == c and r["trace"] in ("cnn", "llm", "recsys")]
        lines.append(f"  {c:13s} {math.exp(sum(math.log(x) for x in sp) / len(sp)):.3f}x")
    txt = "\n".join(lines)
    print(txt)
    with open(os.path.join(RES, "comparison.txt"), "w") as f:
        f.write(txt + "\n")
    if failed or not ref_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
