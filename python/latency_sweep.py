#!/usr/bin/env python3
"""latency_sweep.py - sensitivity to DRAM latency (20/40/80/120 cycles).
Same RTL; only the DRAM model's MEM_LAT parameter changes.  Runs baseline and
the final design on all 9 traces.  Output: results/latency_sweep.csv and
results/plots/latency_sweep.png"""
import math, os, re, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TRACES = ["sequential", "stride", "random", "repeated", "mixed", "capacity", "cnn", "llm", "recsys"]
AI = ["cnn", "llm", "recsys"]
LATS = [20, 40, 80, 120]
CFG = {"baseline": "+mode=0", "final": "+mode=3 +adaptive=1 +degree=2 +inslru=1"}

def run(vvp, t, cfg):
    p = subprocess.run(["vvp", "-n", vvp, f"+trace={ROOT}/traces/{t}.trace"] + CFG[cfg].split(),
                       capture_output=True, text=True)
    assert "TEST PASSED" in p.stdout, p.stdout[-400:]
    return int(re.search(r"cycles=(\d+)", p.stdout).group(1))

rows = []
for lat in LATS:
    with tempfile.TemporaryDirectory() as d:
        tb = open(os.path.join(ROOT, "testbench", "tb_system.v")).read().replace(
            "top_module dut (", f"top_module #(.MEM_LAT({lat})) dut (")
        open(os.path.join(d, "tb.v"), "w").write(tb)
        vvp = os.path.join(d, "sim.vvp")
        rtl = [os.path.join(ROOT, "rtl", f) for f in os.listdir(os.path.join(ROOT, "rtl")) if f.endswith(".v")]
        subprocess.run(["iverilog", "-g2005", "-o", vvp, os.path.join(d, "tb.v")] + rtl, check=True)
        jobs = [(t, c) for t in TRACES for c in CFG]
        with ThreadPoolExecutor(os.cpu_count() or 2) as ex:
            cyc = dict(zip(jobs, ex.map(lambda j: run(vvp, *j), jobs)))
    for t in TRACES:
        rows.append(dict(latency=lat, trace=t, base_cycles=cyc[(t, "baseline")], final_cycles=cyc[(t, "final")],
                         speedup=round(cyc[(t, "baseline")] / cyc[(t, "final")], 3)))
    print(f"latency {lat}: done", flush=True)
df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "results", "latency_sweep.csv"), index=False)
gm = lambda s: math.exp(sum(map(math.log, s)) / len(s))
summ = [(lat, gm(df[df.latency == lat].speedup), gm(df[(df.latency == lat) & df.trace.isin(AI)].speedup)) for lat in LATS]
for lat, a, b in summ:
    print(f"DRAM {lat:3d} cycles: geo-mean speedup all={a:.2f}x  AI={b:.2f}x")
fig, ax = plt.subplots(figsize=(8, 4))
for t in TRACES:
    sub = df[df.trace == t]; ax.plot(sub.latency, sub.speedup, marker="o", lw=1, alpha=0.6, label=t)
ax.plot(LATS, [s[1] for s in summ], color="#c2185b", lw=3, marker="s", label="geo-mean (all)")
ax.set_xlabel("DRAM latency (cycles)"); ax.set_ylabel("speedup vs baseline (x)")
ax.set_title("Final design: speedup grows as memory gets slower"); ax.grid(alpha=0.3); ax.legend(fontsize=7, ncol=2)
fig.tight_layout(); fig.savefig(os.path.join(ROOT, "results", "plots", "latency_sweep.png"), dpi=130)
