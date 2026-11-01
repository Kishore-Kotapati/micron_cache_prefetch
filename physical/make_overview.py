#!/usr/bin/env python3
"""make_overview.py - one summary figure of the routed chip (all numbers read from out/ logs)."""
import re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

log = open("out/openroad.log").read()
area = re.search(r"Design area (\d+) u\^2 (\d+)% utilization", log)
wns = float(re.search(r"^wns (\S+)", log, re.M).group(1))
power = float(re.findall(r"^Total\s+[\d.e+-]+\s+[\d.e+-]+\s+[\d.e+-]+\s+([\d.e+-]+)", log, re.M)[-1])
drc = re.findall(r"Number of violations = (\d+)", log)[-1]
die = re.search(r"Die area:\s+\( 0 0 \) \( (\d+) (\d+) \)", log)
cells = re.search(r"Number of cells:\s+(\d+)", open("out/synth_stat.txt").read()).group(1)
period = 10.0 - wns
fig = plt.figure(figsize=(18, 12.5))
panels = [("out/chip_full.png", "1. Whole routed chip (all layers)"),
          ("out/chip_metal.png", "2. Metal wiring only (met1-met5)"),
          ("out/chip_closeup.png", "3. 12 µm close-up: transistors + wires"),
          ("out/block_map.png", "4. Where each block was placed")]
pos = [(0.01, 0.50, 0.32, 0.45), (0.34, 0.50, 0.32, 0.45), (0.67, 0.50, 0.32, 0.45), (0.01, 0.01, 0.50, 0.46)]
for (img, title), p in zip(panels, pos):
    ax = fig.add_axes(p); ax.imshow(mpimg.imread(img)); ax.set_axis_off(); ax.set_title(title, fontsize=12, weight="bold")
txt = (f"Agrimos cache + prefetch engine - real layout, SkyWater 130 nm (sky130_fd_sc_hd)\n\n"
       f"Configuration: 512 B, 4-way cache (8 sets) + full prefetch engine\n"
       f"Standard cells after synthesis: {int(cells):,}\n"
       f"Die: {int(die.group(1))/1000:.0f} µm x {int(die.group(2))/1000:.0f} µm   |   cell area {int(area.group(1))/1e6:.3f} mm², {area.group(2)}% of core\n"
       f"Detailed-route DRC violations (TritonRoute): {drc}\n"
       f"Timing (typical corner, estimated wires): target 10 ns -> worst slack {wns:+.2f} ns\n"
       f"   => runs at about {period:.1f} ns  ~ {1000/period:.0f} MHz; slowest path inside the stride predictor\n"
       f"Power estimate (OpenROAD, default activity): {power*1000:.0f} mW\n"
       f"Tools: Yosys -> OpenROAD -> KLayout (all free / open-source)")
fig.text(0.53, 0.12, txt, fontsize=11, family="monospace", va="bottom",
         bbox=dict(boxstyle="round", fc="#f7f0f0", ec="#7B1E2B", lw=1.5))
fig.savefig("out/chip_overview.png", dpi=130)
print(txt)
