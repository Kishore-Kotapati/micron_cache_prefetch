#!/usr/bin/env python3
"""design_sweep.py - design-space exploration of the prefetcher parameters.
For every parameter combination: copy the RTL with new parameter defaults,
compile with Icarus, run all 9 traces with the final configuration (mode 3),
and record execution cycles.  Speedup is against the baseline cycles from
results/performance_summary.csv.  Output: results/design_sweep.csv"""
import csv, itertools, math, os, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TRACES = ["sequential", "stride", "random", "repeated", "mixed", "capacity", "cnn", "llm", "recsys"]
AI = ["cnn", "llm", "recsys"]
base = pd.read_csv(os.path.join(ROOT, "results", "performance_summary.csv"))
BASE = {t: int(base[(base.trace == t) & (base.config == "baseline")].cycles.iloc[0]) for t in TRACES}
BASE_DRAM = {t: int(base[(base.trace == t) & (base.config == "baseline")].dram_transactions.iloc[0]) for t in TRACES}

GRID = {"NSTREAM": [4, 8], "CONF_TH": [1, 2], "NEW_CNT": [2, 3], "EPOCH": [16, 32]}
FILES = {"NSTREAM": ("top_module.v", r"parameter NSTREAM    = \d+"),
         "CONF_TH": ("stride_predictor.v", r"parameter CONF_TH    = \d+"),
         "NEW_CNT": ("stride_predictor.v", r"parameter NEW_CNT    = 3'd\d"),
         "EPOCH":   ("stride_predictor.v", r"parameter EPOCH      = \d+")}

def build(params, d):
    shutil.copytree(os.path.join(ROOT, "rtl"), os.path.join(d, "rtl"))
    for k, v in params.items():
        f, pat = FILES[k]; p = os.path.join(d, "rtl", f); s = open(p).read()
        new = pat.split("=")[0].replace("\\", "") + "= " + (f"3'd{v}" if k == "NEW_CNT" else str(v))
        s2, n = re.subn(pat, new, s); assert n == 1, (k, f); open(p, "w").write(s2)
    out = os.path.join(d, "sim.vvp")
    src = [os.path.join(ROOT, "testbench", "tb_system.v")] + [os.path.join(d, "rtl", f) for f in os.listdir(os.path.join(d, "rtl"))]
    subprocess.run(["iverilog", "-g2005", "-o", out] + src, check=True, capture_output=True)
    return out

def run(vvp, t):
    p = subprocess.run(["vvp", "-n", vvp, f"+trace={ROOT}/traces/{t}.trace", "+mode=3", "+adaptive=1",
                        "+degree=2", "+inslru=1"], capture_output=True, text=True)
    m = re.search(r"cycles=(\d+)", p.stdout); dm = re.search(r"dem_mem=(\d+) pf_issued=(\d+)", p.stdout)
    assert m and "TEST PASSED" in p.stdout, p.stdout[-500:]
    return t, int(m.group(1)), int(dm.group(1)) + int(dm.group(2))

def gm(xs): return math.exp(sum(map(math.log, xs)) / len(xs))

rows = []
for combo in itertools.product(*GRID.values()):
    params = dict(zip(GRID, combo))
    with tempfile.TemporaryDirectory() as d:
        vvp = build(params, d)
        with ThreadPoolExecutor(os.cpu_count() or 2) as ex:
            res = list(ex.map(lambda t: run(vvp, t), TRACES))
    sp = {t: BASE[t] / c for t, c, _ in res}
    traffic = gm([dr / BASE_DRAM[t] for t, _, dr in res])
    row = dict(params, gm_all=round(gm(sp.values()), 4), gm_ai=round(gm([sp[t] for t in AI]), 4),
               min_speedup=round(min(sp.values()), 4), dram_gm=round(traffic, 4),
               **{f"sp_{t}": round(sp[t], 3) for t in TRACES})
    rows.append(row); print({k: row[k] for k in list(params) + ["gm_all", "gm_ai", "min_speedup", "dram_gm"]}, flush=True)
with open(os.path.join(ROOT, "results", "design_sweep.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
