#!/usr/bin/env python3
"""run_cocotb.py - build top_module and run the Cocotb tests on Icarus Verilog.
Results: results/cocotb_results.xml and results/cocotb_log.txt"""
import os
import shutil
import sys

try:                                   # cocotb 2.x
    from cocotb_tools.runner import get_runner
except ImportError:                    # cocotb 1.8 / 1.9
    from cocotb.runner import get_runner

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RTL = sorted(os.path.join(ROOT, "rtl", f) for f in os.listdir(os.path.join(ROOT, "rtl")) if f.endswith(".v"))
TBDIR = os.path.join(ROOT, "testbench", "cocotb")
BUILD = os.path.join(ROOT, "simulation", "cocotb_build")


def main():
    shutil.rmtree(BUILD, ignore_errors=True)
    runner = get_runner("icarus")
    runner.build(sources=RTL, hdl_toplevel="top_module", build_dir=BUILD,
                 build_args=["-g2005"], timescale=("1ns", "1ps"), always=True)
    xml = runner.test(hdl_toplevel="top_module", test_module="test_cache",
                      test_dir=TBDIR, build_dir=BUILD,
                      results_xml=os.path.join(ROOT, "results", "cocotb_results.xml"))
    print("results:", os.path.relpath(xml, ROOT))


if __name__ == "__main__":
    sys.exit(main())
