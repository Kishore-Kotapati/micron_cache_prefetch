#!/usr/bin/env bash
# Reproduce the whole project: traces -> analysis -> RTL lint -> 54 simulations
# -> metrics -> plots -> report tables -> demo waveforms.
set -e
cd "$(dirname "$0")"

echo "== Tool versions"
python3 --version
iverilog -V 2>&1 | head -1
command -v verilator >/dev/null && verilator --version || echo "verilator: not installed (optional)"

echo "== Level 1: generate and analyze traces"
python3 python/generate_traces.py
(cd python && python3 analyze_traces.py)

if command -v verilator >/dev/null; then
  echo "== Lint (Verilator)"
  verilator --lint-only -Wall -Wno-DECLFILENAME -Wno-PINCONNECTEMPTY -Wno-UNUSEDSIGNAL \
            --top-module top_module rtl/*.v && echo "lint clean" || echo "lint step failed (older Verilator?)"
fi

echo "== Level 4/5: compile RTL, run all simulations, compute metrics"
python3 python/run_all.py | tee results/regression_log.txt

# Second simulator: Verilator >= 5 can run the same testbench (--binary --timing)
if command -v verilator >/dev/null && verilator --version | grep -qE "Verilator [5-9]"; then
  echo "== Verilator cross-check (same testbench, second simulator)"
  python3 python/verilator_crosscheck.py > results/verilator_log.txt 2>&1 && tail -1 results/verilator_log.txt || { echo "Verilator step failed - see results/verilator_log.txt"; tail -5 results/verilator_log.txt; }
else
  echo "== Verilator cross-check skipped (needs Verilator 5 or newer)"
fi

# Cocotb directed / random tests (Python testbench on Icarus)
if python3 -c "import cocotb" 2>/dev/null; then
  echo "== Cocotb tests"
  python3 python/run_cocotb.py > results/cocotb_log.txt 2>&1 || true
  grep -E "\*\* (test_cache|TESTS)" results/cocotb_log.txt | sed 's/  \+/ /g'
  grep -q "TESTS=" results/cocotb_log.txt || { echo "Cocotb step failed - see results/cocotb_log.txt"; tail -8 results/cocotb_log.txt; }
else
  echo "== Cocotb tests skipped (pip install cocotb)"
fi

echo "== Plots and report tables"
python3 python/visualize_results.py
python3 python/evaluate_results.py > /dev/null

echo "== Demo waveforms for GTKWave"
mkdir -p simulation/waveforms
vvp -n simulation/build/sim.vvp +trace=traces/demo.trace +mode=0 +adaptive=0 +degree=1 +inslru=0 \
    +tag=demo_baseline +vcd=simulation/waveforms/demo_baseline.vcd | grep -E "TEST"
vvp -n simulation/build/sim.vvp +trace=traces/demo.trace +mode=3 +adaptive=1 +degree=2 +inslru=1 \
    +tag=demo_final +vcd=simulation/waveforms/demo_final.vcd | grep -E "TEST"
echo "Done. Open the waveform with:  gtkwave simulation/waveforms/demo_final.vcd simulation/waveforms/demo.gtkw"
