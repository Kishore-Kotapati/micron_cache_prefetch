# Prefetch algorithm

The slide's three steps map directly onto the hardware.

## 1. Watch
Every demand lookup sends `(address, hit/miss, hit-on-prefetched-line)` to the
`stride_predictor`, which registers it (one pipeline stage, off the cache's
critical path).

## 2. Guess — multi-stream stride table (4 entries)

Each entry: `valid, last_address (32 b), stride (12 b signed, bytes), confidence (2 b)`.

* **Stream match without a PC.** The traces carry only addresses, so an access
  belongs to the entry whose last address is within ±1 KB. Interleaved
  streams that are far apart (weights vs activations vs KV cache) get
  separate entries.
* **Training.** `d = addr - last_address`
  * `d == 0` (same word): ignore.
  * `d == stride`: confidence + 1 (saturating at 3).
  * otherwise: confidence − 1, and when confidence ≤ 1 learn `d` as the new stride.
* **Allocation.** No match → take a free entry, else one with confidence 0,
  else round-robin. Random accesses therefore only replace untrained entries
  and cannot wipe out a good stream.
* **Byte-granular stride.** Strides that are not line multiples (e.g. 48 B)
  are tracked exactly; strides smaller than a line are rounded up to one line
  in the stream direction (so word-by-word streams prefetch whole next lines).

## 3. Fetch early

* **Trigger:** confidence ≥ 2 and the access moved into a new cache line.
* **Candidates:** `addr + k·step`, k = 1 … degree.
* **Safety:** candidates never cross a 4 KB page (no prediction into unrelated
  memory); duplicates are removed in the queue, and lines already cached or in
  flight are removed by the controller's probe before any DRAM request.
* Prefetches use spare DRAM slots only, never more than 7 of 8 MSHRs.

## 4. What makes it "intelligent" — the three innovations

### (a) Accuracy-feedback adaptive degree  *(Intelligent Prefetching)*
Every 32 issued prefetches, the hardware counts how many were used
(useful + late):

| measured accuracy | action |
|---|---|
| ≥ 75 % | degree + 1 (max 7) – run further ahead |
| < 25 % | degree − 1 (min 1) – back off |

Streaming CNN/LLM phases climb to degree 7, which hides the 40-cycle DRAM
latency; irregular phases stay low.  Measured effect (fixed degree 2 → adaptive):
sequential 2.75× → 3.85×, stride 2.69× → 5.20×.

### (b) Hybrid next-line kick-off for new streams  *(Novel Prediction Algorithm, AI-aware)*
Recommendation embedding rows are only 64 B (4 lines): the stride detector
needs ~5 accesses to train, so most of the row is gone before it fires.  When a
**new** stream starts **with a miss**, the predictor immediately issues 2
next-line prefetches. The kick-off is **gated by the measured accuracy**
(below 50 % it is switched off), so pure random traffic costs only one epoch of
wasted prefetches (32 out of 3 989 misses) instead of doubling DRAM traffic
like a plain next-line prefetcher does.

### (c) Adaptive prefetch-aware insertion  *(Adaptive Cache Policy)*
Each line has a *prefetched* bit. While measured accuracy is < 50 %, prefetched
lines are inserted at the **LRU** position — a wrong guess is the first line
evicted, so it cannot push out useful demand data. While accuracy is good they
are inserted at **MRU**, so useful prefetches survive until the CPU reaches
them. On the first demand hit the line is promoted to MRU and its bit is
cleared. We first tried *always* inserting at LRU: it lost performance on
multi-stream traffic (prefetches evicted before use), which is why the policy
is adaptive.

## 5. Strategies compared (same RTL, run-time `pf_mode`)

| Strategy | Good at | Weak at |
|---|---|---|
| Sequential (next-line) | very short streams, starts instantly | any stride > 1 line; random traffic doubles DRAM traffic |
| Stride, fixed degree | regular streams | too few lines ahead to hide latency; slow to train |
| Stride + adaptive degree | long CNN/LLM streams | short streams |
| **Final hybrid** | all of the above | truly random traffic (nothing can predict it) |

## 6. Which strategy suits which AI-inspired workload (measured)

* **CNN** (line-buffer row streams + channel-strided pointwise conv): stride
  with high degree; next-line cannot follow the 256 B channel stride. 2.02× vs 1.73×.
* **LLM** (GEMV weight streaming + KV-cache scans): long, perfectly regular
  streams; adaptive degree reaches 7 and removes 97 % of misses. 2.76× vs 1.89×.
* **Recommendation** (Zipf embedding lookups, 4-line rows): short irregular
  bursts; the hybrid kick-off is what helps. 1.46× vs 1.45× next-line, 1.34×
  plain stride.
