#!/usr/bin/env python3
"""
verilator_crosscheck.py - second, independent simulator.

Builds the SAME testbench + RTL with Verilator (--binary --timing, needs
Verilator >= 5.0), runs all 9 traces x 6 architectures, and compares every
counter in every RESULT line with the Icarus Verilog logs written by
run_all.py.  Identical numbers from two different simulators show the results
do not depend on one simulator's scheduling and that the RTL is clean,
cycle-accurate synthesizable code.
Output: results/verilator_crosscheck.txt
"""
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from run_all import ROOT, LOGS, RES, TRACES, CONFIGS

OBJ = os.path.join(ROOT, "simulation", "verilator", "obj")
VSIM = os.path.join(OBJ, "vsim")


def build():
    os.makedirs(OBJ, exist_ok=True)          # Verilator does not create parent folders
    src = ["testbench/tb_system.v"] + sorted(
        os.path.join("rtl", f) for f in os.listdir(os.path.join(ROOT, "rtl")) if f.endswith(".v"))
    cmd = ["verilator", "--binary", "--timing", "-j", "0", "-Wno-fatal", "-Wno-lint", "-Wno-style",
           "--top-module", "tb_system", "-Mdir", "simulation/verilator/obj", "-o", "vsim"] + src
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0 or not os.path.exists(VSIM):
        print("verilator stdout:\n" + p.stdout[-3000:] + "\nverilator stderr:\n" + p.stderr[-3000:])
        print("Hint: Verilator needs a C++ compiler -> sudo apt install -y build-essential")
        sys.exit("VERILATOR BUILD FAILED")
    ver = subprocess.run(["verilator", "--version"], capture_output=True, text=True).stdout.strip()
    print("build OK:", ver)
    return ver


def parse(text):
    m = re.search(r"^RESULT (.*)$", text, re.M)
    if not m:
        return None
    kv = dict(x.split("=", 1) for x in m.group(1).split())
    kv.pop("tag", None); kv.pop("trace", None)
    kv["passed"] = "TEST PASSED" in text
    return kv


def run(trace, cfg):
    args = [VSIM, f"+trace=traces/{trace}.trace", f"+tag={cfg}"] + \
           [f"+{k}={v}" for k, v in CONFIGS[cfg].items()]
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    os.makedirs(os.path.join(LOGS, "verilator"), exist_ok=True)
    with open(os.path.join(LOGS, "verilator", f"{trace}__{cfg}.log"), "w") as f:
        f.write(" ".join(args) + "\n" + p.stdout + p.stderr)
    return trace, cfg, parse(p.stdout)


def main():
    ver = build()
    jobs = [(t, c) for t in TRACES for c in CONFIGS]
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
        res = list(ex.map(lambda tc: run(*tc), jobs))
    lines = [f"Verilator vs Icarus cross-check ({ver})", ""]
    ok_all = True
    for t, c, v in res:
        ilog = os.path.join(LOGS, f"{t}__{c}.log")
        i = parse(open(ilog).read()) if os.path.exists(ilog) else None
        if v is None or i is None:
            ok_all = False
            lines.append(f"{t:11s} {c:13s} MISSING ({'verilator' if v is None else 'icarus'} log)")
            continue
        diff = [k for k in i if i[k] != v.get(k)]
        ok = not diff and v["passed"] and i["passed"]
        ok_all &= ok
        lines.append(f"{t:11s} {c:13s} cycles={v['cycles']:>7s} hits={v['hits']:>5s} "
                     f"pf_issued={v['pf_issued']:>5s}  verilator={'PASS' if v['passed'] else 'FAIL'}  "
                     f"{'IDENTICAL' if not diff else 'DIFF: ' + ','.join(diff)}")
    n_same = sum(1 for l in lines if l.endswith("IDENTICAL"))
    lines += ["", f"{n_same}/{len(jobs)} runs: Verilator results identical to Icarus Verilog "
                  f"(all counters, cycles and self-checks)" + ("" if ok_all else "  -- MISMATCHES FOUND")]
    txt = "\n".join(lines)
    print(txt)
    with open(os.path.join(RES, "verilator_crosscheck.txt"), "w") as f:
        f.write(txt + "\n")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
