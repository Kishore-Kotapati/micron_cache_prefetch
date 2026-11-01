# AI-Aware Cache & Prefetch Engine — Micron RTL Challenge

A 4 KB, 4-way cache with an intelligent hardware prefetch engine, written in
synthesizable Verilog, simulated with Icarus Verilog and measured against the
same cache without prefetching.

**Measured result (RTL simulation, 9 workloads):** 2.23× geometric-mean
speedup over the baseline cache, 2.01× on the CNN / LLM / recommendation-inspired
workloads, never slower than the baseline. 54/54 simulations pass all
self-checks; the baseline matches an independent Python cache model exactly.
Full numbers: `results/comparison.txt`, `docs/final_report.md`.

## How it works (in short)
1. **Watch** – every load the CPU makes is sent to a small stream table.
2. **Guess** – the table learns the step size (stride) of up to 4 address
   streams and how sure it is (confidence).
3. **Fetch early** – when sure, it loads the next lines into the cache before
   the CPU asks. It measures its own accuracy and automatically goes further
   ahead when it is right, backs off when it is wrong, and protects useful
   cache data when its guesses are poor.

## Folder map
| Folder | Contents |
|---|---|
| `rtl/` | Verilog design (`top_module.v` = top) + DRAM model |
| `testbench/` | `tb_system.v` trace-driven self-checking testbench |
| `python/` | trace generator, trace analysis, golden model, regression, plots, report tables |
| `traces/` | generated workloads (`<gap> <hex address>` per line) |
| `simulation/logs/` | one log per simulation (54) |
| `simulation/waveforms/` | GTKWave demo waveforms + `demo.gtkw` signal layout |
| `results/` | `performance_summary.csv`, `comparison.txt`, `summary_tables.md`, `trace_analysis.*`, `verilator_lint.txt`, `plots/` |
| `synth/` | Yosys synthesis: block diagram, gate/flip-flop counts (`bash synth/run_synth.sh`) |
| `docs/` | `architecture.md`, `algorithm.md`, `final_report.md` |

## Reproduce everything (one command)
```bash
./run_all.sh          # about 1 minute
```

## Step-by-step commands
```bash
python3 python/generate_traces.py                    # Level 1: make traces
cd python && python3 analyze_traces.py && cd ..      # Level 1: analysis + plots
iverilog -g2005 -Wall -o simulation/build/sim.vvp testbench/tb_system.v rtl/*.v
# one run:  mode 0=baseline 1=next-line 2=stride 3=final hybrid
vvp -n simulation/build/sim.vvp +trace=traces/llm.trace +mode=3 +adaptive=1 +degree=2 +inslru=1
vvp -n simulation/build/sim.vvp +trace=traces/llm.trace +mode=0
python3 python/run_all.py                            # all 54 runs + metrics + golden check
python3 python/visualize_results.py                  # plots
python3 python/evaluate_results.py                   # markdown tables
# waveform
vvp -n simulation/build/sim.vvp +trace=traces/demo.trace +mode=3 +vcd=simulation/waveforms/demo_final.vcd
gtkwave simulation/waveforms/demo_final.vcd simulation/waveforms/demo.gtkw
```
Each run prints a `RESULT ...` line and `TEST PASSED` or `TEST FAILED`.

## Tool setup
Required: Python 3 (+ pandas, matplotlib for plots), Icarus Verilog, GTKWave, Git.
Optional: Verilator (lint).

**Ubuntu / WSL (recommended on Windows):**
```bash
sudo apt update
sudo apt install -y iverilog gtkwave git python3-pandas python3-matplotlib verilator
cd /mnt/c/Users/"KOTAPATI KISHORE"/workplace/micron_cache_prefetch
bash run_all.sh
```
(GTKWave from WSL opens a window through WSLg on Windows 11.)

**Native Windows alternative:** install Icarus Verilog for Windows (it ships
with GTKWave), Python 3 with `pip install pandas matplotlib`, and Git for
Windows; then run the step-by-step commands in Git Bash.

Note: the `oss-cad-suite` folder in the home directory is the Linux build — it
works inside WSL (`source ~/oss-cad-suite/environment` after copying it into the
WSL file system), not in native Windows.

Versions used for the reported results: Ubuntu 24.04, Python 3.13, Icarus
Verilog 12.0, Verilator 5.020, pandas 3.0, matplotlib 3.11.

## Honest limitations
Synthetic traces (not real AI model traces), read-only cache, single cache
level, simple fixed-latency DRAM model, generic-gate synthesis only (no area/timing/power/placement). See
`docs/final_report.md` §12.
