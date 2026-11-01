# AI-Aware Cache & Prefetch Engine — Micron RTL Challenge

A 4 KB, 4-way cache with an intelligent hardware prefetch engine, written in
synthesizable Verilog, simulated with Icarus Verilog and measured against the
same cache without prefetching.

**Measured result (RTL simulation, 9 workloads):** 2.26× geometric-mean
speedup over the baseline cache, 2.06× on the CNN / LLM / recommendation-inspired
workloads, never slower than the baseline. With slower 120-cycle DRAM:
3.03× / 2.97×. On regular streams it reaches 98–99 % of a perfect cache.

**Verification:** 54/54 Icarus simulations pass all self-checks · the
baseline matches an independent Python cache model exactly · all 54 runs give
**identical** results on a second simulator (Verilator) · 7/7 Cocotb Python
tests pass · Verilator lint clean.

## Tools used
| Tool | What it does here |
|---|---|
| Python 3 | trace generation, analysis, golden model, regression, metrics |
| Icarus Verilog | main RTL simulator (54 runs, Cocotb tests) |
| GTKWave | waveform debugging / demo (`simulation/waveforms/`) |
| Git | version history |
| Verilator | lint (0 warnings) **and** second simulator: same testbench, results compared counter by counter |
| Cocotb | 7 Python tests: hit/miss latency, LRU, 1500 random loads vs golden model, prefetch benefit, demand during in-flight prefetch, page boundary, random-traffic throttling |
| Pandas | result tables (`evaluate_results.py`, `visualize_results.py`) |
| Matplotlib | all plots in `results/plots/` |
| Yosys (extra) | synthesis: block diagram + gate counts (`synth/`) |
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
| `testbench/` | `tb_system.v` trace-driven self-checking testbench; `cocotb/test_cache.py` Cocotb tests |
| `python/` | trace generator, trace analysis, golden model, regression, plots, report tables |
| `traces/` | generated workloads (`<gap> <hex address>` per line) |
| `simulation/logs/` | one log per simulation (54) |
| `simulation/waveforms/` | GTKWave demo waveforms + `demo.gtkw` signal layout |
| `results/` | `performance_summary.csv`, `comparison.txt`, `summary_tables.md`, `trace_analysis.*`, `verilator_lint.txt`, `plots/` |
| `synth/` | Yosys synthesis: block diagram, gate/flip-flop counts (`bash synth/run_synth.sh`) |
| `docs/` | `Project_Learning_Guide.pdf` (start here), `architecture.md`, `algorithm.md`, `final_report.md` |

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
python3 python/verilator_crosscheck.py               # same 54 runs on Verilator, compare
python3 python/run_cocotb.py                         # Cocotb tests (results/cocotb_log.txt)
python3 python/latency_sweep.py                      # DRAM 20/40/80/120-cycle sensitivity (~1 min)
python3 python/design_sweep.py                       # 16 parameter combinations (~2 min)
# waveform
vvp -n simulation/build/sim.vvp +trace=traces/demo.trace +mode=3 +vcd=simulation/waveforms/demo_final.vcd
gtkwave simulation/waveforms/demo_final.vcd simulation/waveforms/demo.gtkw
```
Each run prints a `RESULT ...` line and `TEST PASSED` or `TEST FAILED`.

## Tool setup (Ubuntu 24.04 / WSL) - recommended
Ubuntu 24.04's own packages have exactly the versions used for the reported
results. Verilator needs a C++ compiler (build-essential) because it turns
the Verilog into a C++ program.

```bash
sudo apt update
sudo apt install -y iverilog gtkwave git python3 python3-venv python3-pip \
                    python3-pandas python3-matplotlib verilator build-essential yosys graphviz unzip
python3 -m venv --system-site-packages ~/hackenv
source ~/hackenv/bin/activate
pip install cocotb
cd ~/micron_cache_prefetch && bash run_all.sh
```
(Open a new terminal later with `source ~/hackenv/bin/activate` before running.)

On Ubuntu 22.04 the packaged Verilator is too old for the second-simulator
step; there, use the OSS CAD Suite release (`source ~/oss-cad-suite/environment`).
Steps whose tool is missing are skipped with a message.

Versions used for the reported results: Ubuntu 24.04, Python 3.13, Icarus
Verilog 12.0, Verilator 5.020, Cocotb 2.1.0, Yosys 0.33, pandas 3.0,
matplotlib 3.11.

## Honest limitations
Synthetic traces (not real AI model traces), read-only cache, single cache
level, simple fixed-latency DRAM model, generic-gate synthesis only (no area/timing/power/placement). See
`docs/final_report.md` §12.
