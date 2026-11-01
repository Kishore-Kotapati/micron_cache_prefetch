"""
test_cache.py - Cocotb directed + random tests for top_module (cache +
prefetch engine + DRAM model), written in Python, simulated on Icarus Verilog.

Each test drives the CPU port directly and checks data, latency and the RTL
performance counters.  Run with:  python3 python/run_cocotb.py
"""
import os
import random
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "python"))
from ref_cache_model import simulate  # noqa: E402  (golden LRU model)

LINE, SETS, WAYS = 16, 64, 4
SET_STRIDE = LINE * SETS          # 1 KB: addresses this far apart share a set
MEM_LAT = 40


def mem_word(addr):
    a = addr & ~3
    return ((a ^ 0x5A5A5A5A) * 0x9E3779B1) & 0xFFFFFFFF


def cnt(dut, name):
    return int(getattr(dut.u_cache, name).value)


async def reset(dut, mode=0, adaptive=0, degree=1, inslru=0):
    cocotb.start_soon(Clock(dut.clk, 10, "ns").start())
    dut.pf_mode.value = mode
    dut.pf_adaptive.value = adaptive
    dut.pf_degree.value = degree
    dut.pf_insert_lru.value = inslru
    dut.cpu_req_valid.value = 0
    dut.cpu_req_addr.value = 0
    dut.rst.value = 1
    for _ in range(5):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst.value = 0


async def idle(dut, n):
    for _ in range(n):
        await FallingEdge(dut.clk)


async def load(dut, addr):
    """Issue one load on a falling edge; return (data, latency in cycles)."""
    await FallingEdge(dut.clk)
    while not int(dut.cpu_req_ready.value):
        await FallingEdge(dut.clk)
    dut.cpu_req_valid.value = 1
    dut.cpu_req_addr.value = addr
    lat = 0
    while True:
        await FallingEdge(dut.clk)
        dut.cpu_req_valid.value = 0
        lat += 1
        if int(dut.cpu_resp_valid.value):
            data = int(dut.cpu_resp_data.value)
            assert data == mem_word(addr), f"data error @{addr:#x}: {data:#x} != {mem_word(addr):#x}"
            return data, lat
        assert lat < 2000, f"timeout on load {addr:#x}"


async def drain(dut):
    for _ in range(3000):
        await FallingEdge(dut.clk)
        if int(dut.u_cache.mshr_busy.value) == 0 and not int(dut.u_pf.cand_valid.value):
            return
    raise AssertionError("MSHRs did not drain")


@cocotb.test()
async def test_hit_and_miss_latency(dut):
    """Cold miss pays the DRAM latency, the rest of the line hits in 1 cycle."""
    await reset(dut, mode=0)
    _, lat_miss = await load(dut, 0x1000)
    assert MEM_LAT <= lat_miss <= MEM_LAT + 5, f"miss latency {lat_miss}"
    for off in (4, 8, 12):
        _, lat = await load(dut, 0x1000 + off)
        assert lat == 1, f"hit latency {lat}"
    assert cnt(dut, "cnt_hit") == 3 and cnt(dut, "cnt_miss") == 1
    assert cnt(dut, "cnt_dem_mem") == 1
    dut._log.info(f"miss latency = {lat_miss} cycles, hit latency = 1 cycle")


@cocotb.test()
async def test_lru_replacement(dut):
    """5 lines in one 4-way set: the least recently used one is evicted."""
    await reset(dut, mode=0)
    lines = [0x2000 + i * SET_STRIDE for i in range(5)]
    for a in lines[:4]:
        await load(dut, a)
    await load(dut, lines[0])                 # touch line0 -> line1 becomes LRU
    await load(dut, lines[4])                 # evicts line1
    _, lat0 = await load(dut, lines[0])
    _, lat1 = await load(dut, lines[1])
    assert lat0 == 1, "line0 (recently used) must still hit"
    assert lat1 > 1, "line1 (LRU) must have been evicted"


@cocotb.test()
async def test_random_vs_golden_model(dut):
    """1500 constrained-random loads, baseline cache: hits/misses must equal
    the Python golden LRU model exactly and every data word must be correct."""
    await reset(dut, mode=0)
    rng = random.Random(7)
    pool = [0x40000 + rng.randrange(0, 16384) * 4 for _ in range(300)]   # 64 KB region
    addrs = [rng.choice(pool) if rng.random() < 0.6 else 0x40000 + rng.randrange(0, 2048) * 4
             for _ in range(1500)]
    for a in addrs:
        await load(dut, a)
    h, m = simulate(addrs)
    assert cnt(dut, "cnt_hit") == h and cnt(dut, "cnt_miss") == m, \
        f"RTL {cnt(dut, 'cnt_hit')}/{cnt(dut, 'cnt_miss')} vs model {h}/{m}"
    dut._log.info(f"random test: hits={h} misses={m} match golden model")


@cocotb.test()
async def test_prefetch_removes_misses(dut):
    """A 2 KB sequential stream: the final design must remove most misses."""
    await reset(dut, mode=3, adaptive=1, degree=2, inslru=1)
    for i in range(512):
        await load(dut, 0x80000 + 4 * i)
        await idle(dut, 2)
    await drain(dut)
    miss, iss = cnt(dut, "cnt_miss"), cnt(dut, "cnt_pf_issued")
    useful, late = cnt(dut, "cnt_pf_useful"), cnt(dut, "cnt_pf_late")
    dem = cnt(dut, "cnt_dem_mem")
    dut._log.info(f"128 lines: misses={miss} (of which late-prefetch merges={late}), "
                  f"demand DRAM requests={dem}, pf issued={iss}, useful={useful}")
    # Baseline would take 128 misses and 128 demand DRAM requests.
    # Late merges count as misses but wait only for the remaining latency.
    assert dem <= 10, f"too many demand DRAM requests with prefetching: {dem}"
    assert miss <= 32, f"misses not reduced enough: {miss}"
    assert useful + late >= 100


@cocotb.test()
async def test_demand_during_prefetch(dut):
    """Demand loads arrive while prefetches are in flight:
    (a) a load to a line already being prefetched merges (late prefetch, no
        second DRAM request); (b) an unrelated miss is served correctly and
        before the CPU is starved."""
    await reset(dut, mode=3, adaptive=0, degree=4, inslru=0)
    base = 0xC0000
    issued = []                               # (line byte address, cycle) of every prefetch
    cyc = [0]

    async def monitor():
        while True:
            await RisingEdge(dut.clk)
            cyc[0] += 1
            if int(dut.u_cache.pf_issue.value):
                issued.append((int(dut.u_cache.mem_req_line.value) << 4, cyc[0]))
    cocotb.start_soon(monitor())
    for i in range(0, 4 * 16, 4):            # train: 4 lines, word by word
        await load(dut, base + i)
    assert issued, "no prefetch issued"
    assert int(dut.u_cache.mshr_busy.value) != 0, "no prefetch in flight"
    target, t_issue = issued[-1]              # newest prefetch: still travelling
    assert cyc[0] - t_issue < MEM_LAT - 5
    dem_before, late_before = cnt(dut, "cnt_dem_mem"), cnt(dut, "cnt_pf_late")
    _, lat = await load(dut, target)
    assert cnt(dut, "cnt_pf_late") == late_before + 1, "load to an in-flight line must merge (late)"
    assert cnt(dut, "cnt_dem_mem") == dem_before, "merged load must not send a 2nd DRAM request"
    assert 1 < lat < MEM_LAT, f"merged load should wait only the remaining latency, got {lat}"
    # (b) unrelated miss while other prefetches are still outstanding:
    #     train a second stream, then immediately miss somewhere else.
    for i in range(0, 4 * 16, 4):
        await load(dut, 0xD0000 + i)
    busy = int(dut.u_cache.mshr_busy.value)
    assert busy != 0, "prefetches should be in flight"
    _, lat2 = await load(dut, 0x7FF000)
    assert lat2 <= MEM_LAT + 8, f"demand miss was delayed by prefetches: {lat2}"
    dut._log.info(f"merged load latency={lat}, unrelated miss latency={lat2} "
                  f"with MSHRs busy={busy:#04x} (demand has priority)")
    await drain(dut)


@cocotb.test()
async def test_no_prefetch_across_page(dut):
    """A stream that ends at a 4 KB page boundary must not prefetch into the
    next page (protection against invalid predictions)."""
    await reset(dut, mode=2, adaptive=0, degree=4, inslru=0)
    page = 0x00300000
    issued_lines = []

    async def monitor():
        while True:
            await RisingEdge(dut.clk)
            if int(dut.u_cache.pf_issue.value):
                issued_lines.append(int(dut.u_cache.mem_req_line.value))
    cocotb.start_soon(monitor())
    for a in range(page + 4096 - 32 * LINE, page + 4096, 4):   # last 32 lines of the page
        await load(dut, a)
    await drain(dut)
    next_page = (page + 4096) >> 12
    bad = [l for l in issued_lines if (l << 4) >> 12 == next_page]
    dut._log.info(f"prefetches issued={len(issued_lines)}, into next page={len(bad)}")
    assert issued_lines, "stream should have produced prefetches"
    assert not bad, f"prefetched across the page boundary: {[hex(l << 4) for l in bad]}"


@cocotb.test()
async def test_random_traffic_is_throttled(dut):
    """Pure random loads: the accuracy gate must keep wasted prefetches tiny."""
    await reset(dut, mode=3, adaptive=1, degree=2, inslru=1)
    rng = random.Random(11)
    for _ in range(600):
        await load(dut, 0x01000000 + rng.randrange(0, 1 << 18) * 4)
    await drain(dut)
    iss, dem = cnt(dut, "cnt_pf_issued"), cnt(dut, "cnt_dem_mem")
    dut._log.info(f"random: demand DRAM={dem}, prefetches={iss}")
    assert iss <= 40, f"prefetcher not throttled on random traffic: {iss}"
