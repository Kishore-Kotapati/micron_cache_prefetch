#!/usr/bin/env bash
# Draw the hardware block diagram and synthesize the design to logic gates (Yosys).
set -e
cd "$(dirname "$0")"
yosys -q block_diagram.ys                     # -> block_top.svg, block_prefetch.svg
dot -Tpng -Gdpi=110 block_top.dot -o block_top.png
yosys -q -l synth_log.txt synth.ys            # -> synth_stats.txt, synth_netlist.v (~1 min)
grep -A 30 "=== synth_top ===" synth_stats.txt | tail -25
echo "Done: open block_top.png / block_top.svg, read synth_stats.txt"
