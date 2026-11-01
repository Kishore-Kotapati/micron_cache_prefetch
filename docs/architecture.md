# Architecture

## 1. Block diagram

```
          +-----------------------------+
          |  CPU model (testbench)      |  in-order, 1 outstanding load,
          |  reads trace: gap + address |  <gap> compute cycles between loads
          +--------------+--------------+
                 req/ack |  ^ data (1-cycle hit)
                         v  |
 +-------------------------------------------------------+
 | cache_controller                                      |
 |  +-----------+  +--------------+  +----------------+  |
 |  | tag_array |  | cache_memory |  | replacement_   |  |
 |  | tag/valid |  | (data lines) |  | policy (LRU +  |  |
 |  | /pf bits  |  |              |  | pf insertion)  |  |
 |  +-----------+  +--------------+  +----------------+  |
 |  demand FSM | 8 MSHRs | probe filter | arbitration    |
 +----+-------------------^-------------+--------^-------+
      | training          | candidates  | DRAM   | fills
      | (addr, hit/miss,  | (line addr) | req    |
      v  pf-hit)          |             v        |
 +-----------------------------+   +-----------------------+
 | prefetch_engine             |   | memory_model (DRAM)   |
 |  stride_predictor (4 streams|   | 40-cycle latency      |
 |  + adaptive degree)         |   | 1 new request / 4 cyc |
 |  generator -> 8-entry queue |   | in-order, 16 deep     |
 +-----------------------------+   +-----------------------+
```

`cache_controller` + `prefetch_engine` (and the arrays inside) are the
synthesizable design. `memory_model` is a behavioural DRAM for simulation.

## 2. Cache parameters (all are Verilog parameters)

| Item | Value | Why |
|---|---|---|
| Capacity | 4 KB | small enough that the workloads (8–60 KB) create real pressure |
| Line size | 16 B (4 × 32-bit words) | |
| Associativity | 4-way set associative | good hit rate, cheap 4-way compare |
| Sets | 64 | |
| Address | 32-bit byte address | tag = [31:10], index = [9:4], word = [3:2] |
| Replacement | true LRU (2-bit age per way) + prefetch-aware insertion | |
| Write policy | read-only (loads) | AI inference reads weights/activations; writes are a stated limitation |
| Valid bit | 1 per line | |
| Prefetched bit | 1 per line | marks a line brought by prefetch and not yet used |
| Dirty bit | not needed (read-only) | |
| MSHRs | 8 (1 always kept for demand) | many prefetches in flight hide 40-cycle DRAM latency |
| Hit time | 1 cycle | |
| DRAM | 40 cycles latency, 1 request accepted every 4 cycles | bandwidth limit makes useless prefetches costly |

Organization choice: direct-mapped is cheapest but suffers conflict misses
between interleaved AI streams (weights vs activations); fully associative
needs 256 tag comparators. 4-way set associative is the standard middle
ground and is easy to verify against a Python golden model.

`{index, way}` concatenation is used to address the arrays, so `SETS` and
`WAYS` must be powers of two.

## 3. Demand FSM (cache_controller)

```
            req & hit  (respond next cycle)
          +-------+
          v       |
      +--------+  |   req & miss & line in flight (late prefetch: merge)
 ---->| S_IDLE |--+-------------------------------------------+
      +--------+                                              |
          |  req & miss & not in flight                       v
          v                                            +-------------+
     +------------+  DRAM accepts, MSHR allocated      |   S_WAIT    |
     | S_MISS_REQ |----------------------------------->| wait fill   |
     +------------+                                    +-------------+
                                                              |
             waited line filled -> respond to CPU             |
      S_IDLE <------------------------------------------------+
```

## 4. Arbitration rules (correctness of demand vs prefetch)

1. **Demand first on the DRAM port.** In `S_MISS_REQ`, and in any cycle with
   a demand lookup, prefetches may not issue.
2. **One array update per cycle.** Fills are accepted only in cycles without a
   demand lookup (`mem_resp_ready = !do_lookup`), so tag/data/LRU never see two
   writers. The DRAM model holds responses until accepted.
3. **One MSHR always free for demand.** A prefetch issues only if ≥ 2 MSHRs
   are free.
4. **No duplicates.** A prefetch candidate is dropped if it is already in the
   cache (probe on tag port B) or already in flight (MSHR search). The MSHR is
   cleared in the same edge as the line is installed, so there is no window in
   which a line is neither.
5. **Late prefetch merge.** A demand miss to a line already in flight as a
   prefetch re-uses that MSHR (no second DRAM request), converts it to a
   demand fill, and waits for it.

## 5. Interfaces

| Interface | Signals | Protocol |
|---|---|---|
| CPU → cache | `cpu_req_valid/ready/addr`, `cpu_resp_valid/data` | valid/ready request, 1-cycle response pulse |
| cache → DRAM | `mem_req_valid/ready/line/id` | valid/ready; `id` = MSHR index |
| DRAM → cache | `mem_resp_valid/ready/id/data` | valid/ready, full 128-bit line, in order |
| cache → prefetcher | `train_valid/addr/miss/pfhit`, `fb_issued/useful` | single-cycle pulses |
| prefetcher → cache | `cand_valid/line`, `cand_pop` | FIFO head + pop |

## 6. Performance counters (in RTL)

accesses, hits, misses, demand DRAM requests, prefetches issued, useful
(demand hit on a prefetched line), late (demand merged into an in-flight
prefetch), evicted-unused, filtered (dropped as redundant), fills.
At the end of every simulation the testbench checks
`issued == useful + late + evicted_unused + still_resident_unused`.
