# AI-Aware Cache & Prefetch Engine — Final Technical Report

Micron RTL Challenge · Kotapati Kishore · 1 November 2026

## 1. Problem statement
AI workloads (LLMs, CNNs, recommenders) are fast at math but stall waiting for
data from DRAM. The task: build hardware that **watches** the addresses a
program reads, **guesses** the next ones, and **fetches them early** into the
cache, and prove it is faster than a cache without prefetching.

## 2. Objectives and what was delivered
| Level | Delivered |
|---|---|
| 1 Trace analysis | Python generator for 9 synthetic workloads (6 basic + CNN/LLM/recsys-inspired), analysis of locality/strides, plots |
| 2 Cache architecture | 4 KB, 4-way, 64 sets, 16 B lines, true LRU, 8 MSHRs, baseline cache |
| 3 Prefetch strategy | next-line, stride, adaptive stride, and a hybrid adaptive design (final) |
| 4 RTL | 7 synthesizable Verilog-2005 modules + DRAM model + self-checking testbench |
| 5 Validation | 54 RTL simulations (9 traces × 6 architectures), golden-model check, measured metrics |

## 3. System architecture
See `docs/architecture.md` (block diagram, FSM, arbitration rules, interfaces).

## 4. Cache architecture
4 KB, 4-way set associative, 64 sets, 16-byte lines, 32-bit addresses
(tag 31:10, index 9:4, word 3:2). True LRU with a per-line *prefetched* bit.
Blocking for the CPU (one outstanding load) but non-blocking for prefetches
(8 MSHRs). 1-cycle hit. DRAM model: 40-cycle latency, one new request every
4 cycles, in-order responses.

## 5. Prefetching algorithm
See `docs/algorithm.md`. Summary: a 4-entry address-region stride table with
2-bit confidence, byte-granular strides, page-bounded candidate generation,
duplicate filtering, plus three adaptive mechanisms: accuracy-feedback degree
(1…7), accuracy-gated next-line kick-off for new streams, and accuracy-adaptive
insertion position.

## 6. RTL modules
| File | Role | Synthesizable |
|---|---|---|
| `rtl/cache_controller.v` | demand FSM, MSHRs, probe filter, arbitration, counters | yes |
| `rtl/tag_array.v` | tags, valid and prefetched bits, 3 read ports | yes |
| `rtl/cache_memory.v` | data array | yes |
| `rtl/replacement_policy.v` | true LRU + LRU/MRU insertion | yes |
| `rtl/stride_predictor.v` | stream table, confidence, triggers, adaptive degree, accuracy flag | yes |
| `rtl/prefetch_engine.v` | predictor + candidate generator + 8-entry queue | yes |
| `rtl/top_module.v` | integration, run-time configuration | yes |
| `rtl/memory_model.v` | behavioural DRAM | simulation model |
| `testbench/tb_system.v` | trace-driven CPU model + self-checks | testbench |

Verilator 5.020 `--lint-only -Wall` on the RTL: **0 warnings, 0 errors**
(`results/verilator_lint.txt`).

**Synthesis check (Yosys 0.33, generic gates, `synth/`):** the design
synthesizes cleanly (`check -assert` passes) to 99,234 logic cells and 40,771
flip-flops. The prefetch engine (predictor + queue) is only 4.6 % of the cells
and 1.7 % of the flip-flops; the rest is cache storage. Generic gates give no
area, timing or power numbers, and no placement was done.

## 7. Simulation methodology
* Icarus Verilog 12.0, `-g2005`. One compiled simulator; the architecture is
  chosen with plusargs, so A and B use **identical RTL, traces and DRAM timing**.
* CPU model: waits the trace's compute gap, issues a load, waits for data.
  Execution cycles = cycles from the first issue to the last response.
* AMAT (measured) = sum of every load's latency / number of loads.
  AMAT (formula, also in the CSV) = 1 + miss-rate × baseline miss penalty.
* Prefetch accuracy = useful / issued (timely hits). Because late prefetches
  still cut latency, accuracy including late is also reported.
  Coverage = (baseline misses − misses) / baseline misses.
  Prefetches are never counted as demand accesses.

**Self-checks run in every simulation** (any failure marks the run FAILED):
1. every word returned to the CPU equals the DRAM content function of its address;
2. hits + misses = accesses = trace length;
3. no line is present twice in any set;
4. prefetch accounting closes: issued = useful + late + evicted-unused + resident-unused;
5. all MSHRs drain (no lost responses).

**Golden model:** without prefetching, hit/miss outcome does not depend on
timing, so the RTL baseline is compared with an independent Python LRU model
(`python/ref_cache_model.py`). It matches **exactly on all 9 traces**.

## 8. Test scenarios
| Required scenario | Covered by |
|---|---|
| Sequential | `sequential` |
| Fixed stride | `stride` (48 B, not line aligned), CNN pointwise phase (256 B) |
| Random | `random` |
| Repeated | `repeated` (shuffled 1.5 KB set ×10) |
| Mixed | `mixed` (2 streams + 25 % random) |
| Cold cache | every run starts from reset (empty cache) |
| Capacity pressure | `capacity` (8 KB array ×3 on a 4 KB cache) |
| Prefetch usefulness / accuracy | counters on every run |
| Demand during ongoing prefetch | happens constantly: `late` merges (e.g. 16 in the demo trace) and demand hits/misses while 7 prefetch MSHRs are busy, all data-checked |

Result: **54 / 54 simulations passed all self-checks.**

**Second simulator (Verilator 5.020, `python/verilator_crosscheck.py`):** the
same testbench and RTL compiled with `verilator --binary --timing` give
results **identical to Icarus in all 54 runs** — every counter, every cycle
count and every self-check (`results/verilator_crosscheck.txt`). Two
independent simulators agreeing means the results do not depend on one
simulator's event ordering.

**Cocotb tests (Cocotb 2.1 on Icarus, `testbench/cocotb/test_cache.py`) — 7/7 PASS:**

| Test | What it proves | Measured |
|---|---|---|
| hit_and_miss_latency | cold miss pays DRAM latency, rest of line hits in 1 cycle | miss 42 cyc, hit 1 cyc |
| lru_replacement | 5 lines in one 4-way set: the LRU line is the one evicted | pass |
| random_vs_golden_model | 1500 constrained-random loads, hits/misses equal Python model | 554 / 946, exact match |
| prefetch_removes_misses | 128-line stream: demand DRAM requests 128 → 1 | 22 misses (21 late merges), 1 demand request |
| demand_during_prefetch | load to an in-flight prefetched line merges (no 2nd DRAM request); unrelated miss not delayed while 3 prefetches are in flight | merge waited 11 cyc; miss 42 cyc |
| no_prefetch_across_page | stream ending at a 4 KB boundary never prefetches into the next page | 30 issued, 0 across |
| random_traffic_is_throttled | 600 random loads → accuracy gate limits waste | 32 prefetches |

Two of these tests failed on their first run because the test itself was wrong
(a too-strict miss limit that counted late merges as full misses, and a merge
test that loaded a line which had already arrived). The tests were corrected
to check the intended behaviour; the RTL was not changed.

## 9. Waveform observations (GTKWave, `simulation/waveforms/demo_final.vcd`)
Demo trace: 96 sequential loads then 2 random loads.
* First lines miss; the stream entry reaches confidence 2 after a few lines,
  `trig_valid` pulses and `cand_valid` fills the queue.
* `pf_issue` fires in the gaps between demand lookups, never in a lookup cycle
  and never while `state == S_MISS_REQ`; `m_v` shows several prefetches in flight.
* `pf_drop` removes candidates already cached/in flight.
* Later loads hit with 1-cycle latency on prefetched lines; demand misses that
  find their line in flight merge (`cnt_pf_late` increments) instead of a
  second DRAM request.
* The degree register climbs as accuracy is confirmed.
* Demo counters: baseline 26 misses / 26 demand DRAM requests → final design
  19 misses (16 of them late merges) / only 3 demand DRAM requests.

## 10. Performance comparison (measured)

### Baseline (A) vs final design (B)

| Trace | Hit % A → B | Miss % A → B | AMAT (cyc) A → B | Cycles A → B | Speedup | Improvement | DRAM txns A → B | PF issued | PF accuracy (useful / +late) | Coverage |
|---|---|---|---|---|---|---|---|---|---|---|
| sequential | 75.00 → 99.43 | 25.00 → 0.57 | 11.25 → 1.07 | 112571 → 29172 | 3.86× | 74.1 % | 2048 → 2048 | 2040 | 98.1 % / 100.0 % | 97.7 % |
| stride | 0.00 → 21.10 | 100.00 → 78.90 | 42.00 → 6.04 | 133557 → 25684 | 5.20× | 80.8 % | 3000 → 3009 | 2970 | 21.3 % / 99.7 % | 21.1 % |
| random | 0.28 → 0.28 | 99.72 → 99.72 | 41.89 → 41.89 | 177688 → 177688 | 1.00× | 0.0 % | 3989 → 4021 | 32 | 0.0 % / 0.0 % | 0.0 % |
| repeated | 97.50 → 97.60 | 2.50 → 2.40 | 2.02 → 1.98 | 17357 → 17193 | 1.01× | 0.9 % | 96 → 98 | 6 | 66.7 % / 66.7 % | 4.2 % |
| mixed | 34.55 → 72.97 | 65.45 → 27.03 | 27.83 → 11.80 | 182100 → 85886 | 2.12× | 52.8 % | 3927 → 5638 | 4108 | 56.1 % / 58.3 % | 58.7 % |
| capacity | 75.00 → 99.14 | 25.00 → 0.86 | 11.25 → 1.09 | 84464 → 22016 | 3.84× | 73.9 % | 1536 → 1536 | 1530 | 96.9 % / 100.0 % | 96.5 % |
| cnn | 80.16 → 95.41 | 19.84 → 4.59 | 9.13 → 2.48 | 112549 → 55596 | 2.02× | 50.6 % | 1698 → 2379 | 2105 | 62.6 % / 68.2 % | 76.9 % |
| llm | 84.38 → 99.51 | 15.62 → 0.49 | 7.41 → 1.10 | 82323 → 29855 | 2.76× | 63.7 % | 1300 → 1339 | 1330 | 94.7 % / 97.1 % | 96.8 % |
| recsys | 88.33 → 93.85 | 11.67 → 6.15 | 5.78 → 3.17 | 79479 → 54406 | 1.46× | 31.6 % | 1120 → 2001 | 1548 | 37.7 % / 46.6 % | 47.3 % |

### Speedup of every architecture (execution cycles, baseline = 1.00)

| Trace | baseline | nextline | stride | stride_adapt | smart_noins | smart |
|---|---|---|---|---|---|---|
| sequential | 1.00 | 1.89 | 2.75 | 3.85 | 3.86 | 3.86 |
| stride | 1.00 | 1.00 | 2.69 | 5.20 | 5.20 | 5.20 |
| random | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| repeated | 1.00 | 1.13 | 1.00 | 1.00 | 1.01 | 1.01 |
| mixed | 1.00 | 1.18 | 1.98 | 2.20 | 2.19 | 2.12 |
| capacity | 1.00 | 1.89 | 2.74 | 3.82 | 3.84 | 3.84 |
| cnn | 1.00 | 1.73 | 1.86 | 2.00 | 2.02 | 2.02 |
| llm | 1.00 | 1.89 | 2.40 | 2.74 | 2.76 | 2.76 |
| recsys | 1.00 | 1.45 | 1.34 | 1.34 | 1.36 | 1.46 |
| **geo-mean, all 9** | **1.00** | **1.41** | **1.84** | **2.21** | **2.22** | **2.23** |
| **geo-mean, cnn/llm/recsys** | **1.00** | **1.68** | **1.81** | **1.94** | **1.97** | **2.01** |

### DRAM traffic relative to baseline (cost of prefetching)

| Trace | baseline | nextline | stride | stride_adapt | smart_noins | smart |
|---|---|---|---|---|---|---|
| sequential | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| stride | 1.00 | 2.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| random | 1.00 | 2.00 | 1.00 | 1.00 | 1.01 | 1.01 |
| repeated | 1.00 | 1.01 | 1.00 | 1.00 | 1.02 | 1.02 |
| mixed | 1.00 | 1.82 | 1.00 | 1.00 | 1.36 | 1.44 |
| capacity | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| cnn | 1.00 | 1.09 | 1.14 | 1.45 | 1.46 | 1.40 |
| llm | 1.00 | 1.00 | 1.01 | 1.03 | 1.03 | 1.03 |
| recsys | 1.00 | 1.27 | 1.65 | 1.65 | 1.97 | 1.79 |

![speedup](../results/plots/speedup.png)
![baseline vs final](../results/plots/baseline_vs_final.png)

**Reading the results**
* Regular streams (sequential, capacity, LLM): misses almost disappear
  (≥ 96 % coverage) with at most 3 % extra DRAM traffic — the same lines are
  just fetched earlier.
* `stride`: 5.2× faster, yet only 21 % of prefetches are timely: the CPU needs
  a new line every ~3.5 cycles but DRAM accepts one every 4 cycles, so the run
  is bandwidth-bound and most prefetches arrive "late" (still saving most of
  the latency).
* `random`: nothing is predictable; the design correctly stays quiet (32
  prefetches in total, speedup 1.00×, DRAM +0.8 %). Plain next-line doubles
  DRAM traffic here.
* `repeated`: data already fits in the cache — no gain possible (1.01×).
* CNN / recsys / mixed: real speedups paid for with extra DRAM traffic
  (+40 % / +79 % / +44 %).

## 11. Innovation (what is new in this design)
1. **Accuracy-feedback degree control** in hardware (degree 1…7 every 32
   prefetches) — biggest single gain: geo-mean 1.84× → 2.21×.
2. **Accuracy-gated hybrid kick-off** — next-line prefetch only for newly born
   streams and only while accuracy is good: recsys 1.34× → 1.46× without the
   random-traffic penalty of next-line.
3. **Accuracy-adaptive insertion** (LRU when guesses are bad, MRU when good):
   recsys 1.36× → 1.46× and 9 % less DRAM traffic than the same design with
   normal insertion. Honest note: it costs 3.5 % on `mixed` (2.19× → 2.12×).

All three share one cheap accuracy monitor (two 6-bit counters).

## 12. Limitations (honest list)
* Synthetic traces, not captured from real LLM/CNN/recommender runs; no claim
  of accelerating real AI execution.
* Read-only cache (no stores, no dirty bits / write-back).
* Single-level cache, in-order CPU with one outstanding load.
* Streams are matched by address region (±1 KB) because traces carry no PC;
  two streams closer than 1 KB would interfere.
* Simple fixed-latency DRAM (no banks/rows/refresh).
* Generic-gate synthesis only: no standard-cell area, timing, power or placement.
* Flip-flop arrays (fine for 4 KB; SRAM macros would be needed for large caches).

## 13. Future improvements
PC-indexed stride table, write-back support, a multi-bank DRAM model,
spatial-pattern (bit-vector) prefetching for embedding rows, per-stream
instead of global accuracy, Yosys/OpenROAD flow with
an SRAM macro for real area, timing and placement.

## 14. Conclusion
A working, verified, reproducible RTL cache with an intelligent prefetch engine
was built from scratch with only Python, Icarus Verilog, GTKWave and Git
(+ Verilator, Cocotb, Pandas, Matplotlib). Across 9 workloads it is **2.23× faster
(geometric mean)** than the same cache without prefetching, **2.01× on the
AI-inspired workloads**, never slower than the baseline, and every reported
number comes from a passing, self-checked simulation.
