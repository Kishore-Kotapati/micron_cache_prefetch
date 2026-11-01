#!/usr/bin/env python3
"""block_map.py - where did each design block land on the chip?

Every flip-flop keeps the name of the RTL register it stores (its Q net in the
Yosys netlist), so it can be traced back to its block. Positions come from the
OpenROAD DEF. Logic gates lost their names in synthesis, so they are drawn grey.
usage: python3 block_map.py <netlist.v> <placed.def> <out.png>
"""
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BLOCKS = [  # (prefix of register name, label, colour)
    ("u_cache.u_data", "cache data memory (512 B)", "#1f77b4"),
    ("u_cache.u_tags", "tag array + valid/prefetched bits", "#2ca02c"),
    ("u_cache.u_repl", "LRU replacement ages", "#ff7f0e"),
    ("u_pf.u_pred", "stride predictor (4 streams)", "#d62728"),
    ("u_pf", "prefetch queue + adaptive-degree logic", "#9467bd"),
    ("", "cache controller (FSM, 8 MSHRs, counters)", "#8c564b"),
]


def block_of(q):
    for i, (p, _, _) in enumerate(BLOCKS):
        if q.startswith(p):
            return i
    return len(BLOCKS) - 1


def main():
    net, dfile, out = sys.argv[1:4]
    text = open(net).read()
    ff = {m.group(1): block_of(m.group(2).lstrip("\\"))
          for m in re.finditer(r"sky130_fd_sc_hd__df\w+\s+(\S+)\s*\((?:(?!\);).)*?\.Q\(\s*(\S+)", text, re.S)}
    d = open(dfile).read()
    units = int(re.search(r"UNITS DISTANCE MICRONS (\d+)", d).group(1))
    die = [int(x) / units for x in re.search(r"DIEAREA \( (\d+) (\d+) \) \( (\d+) (\d+) \)", d).groups()]
    comp = re.search(r"^COMPONENTS.*?^END COMPONENTS", d, re.S | re.M).group(0)
    pts = {i: ([], []) for i in range(len(BLOCKS))}
    logic = ([], [])
    for m in re.finditer(r"- (\S+) (\S+) .*?(?:PLACED|FIXED) \( (\d+) (\d+) \)", comp):
        name, cell, x, y = m.group(1), m.group(2), int(m.group(3)) / units, int(m.group(4)) / units
        if any(k in cell for k in ("tapvpwrvgnd", "decap", "fill")):
            continue
        if name in ff:
            pts[ff[name]][0].append(x); pts[ff[name]][1].append(y)
        else:
            logic[0].append(x); logic[1].append(y)

    fig, ax = plt.subplots(figsize=(9.2, 8))
    ax.add_patch(Rectangle((die[0], die[1]), die[2] - die[0], die[3] - die[1], fill=False, lw=2, ec="black"))
    ax.scatter(*logic, s=0.6, c="#c8c8c8", label=f"logic gates ({len(logic[0]):,})", rasterized=True)
    for i, (_, lab, col) in enumerate(BLOCKS):
        if pts[i][0]:
            ax.scatter(*pts[i], s=2.2, c=col, label=f"{lab}: {len(pts[i][0]):,} flip-flops", rasterized=True)
    ax.set_xlim(die[0] - 5, die[2] + 5); ax.set_ylim(die[1] - 5, die[3] + 5); ax.set_aspect("equal")
    ax.set_xlabel("x (µm)"); ax.set_ylabel("y (µm)")
    ax.set_title(f"Where each block sits on the die ({die[2]:.0f} µm × {die[3]:.0f} µm, SkyWater 130 nm)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2, fontsize=8, markerscale=5, frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=170)
    print("wrote", out, {BLOCKS[i][1]: len(pts[i][0]) for i in pts}, "logic", len(logic[0]))


if __name__ == "__main__":
    main()
