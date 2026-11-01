# Hardware view (Yosys synthesis)

Yosys is a free, open-source synthesis tool (included in OSS CAD Suite, or
`sudo apt install yosys graphviz`). It is an extra beyond the four tools the
challenge requires.

```bash
cd synth
bash run_synth.sh
```

| Output | What it shows |
|---|---|
| `block_top.png` / `.svg` | how the cache controller and the prefetch engine are wired together |
| `block_prefetch.svg` | the inside of the prefetch engine (registers, adders, comparators) |
| `synth_stats.txt` | number of logic gates and flip-flops per block |
| `synth_netlist.v` | the whole design as a gate-level netlist |

`synth_top.v` contains only the design (cache + prefetch engine). The DRAM
model is left out because it is a simulation model; its signals become top-level
ports, which is where a real memory controller would connect.

## Measured hardware breakdown (Yosys 0.33, generic gates)

| Block | Logic cells | Flip-flops |
|---|---|---|
| cache_memory (4 KB data) | 65,968 | 32,768 |
| tag_array (tags + valid + prefetched bits) | 22,953 | 6,144 |
| cache_controller (FSM, 8 MSHRs, counters) | 3,872 | 634 |
| replacement_policy (LRU ages) | 1,855 | 512 |
| stride_predictor (stream table, adaptive logic) | 2,825 | 309 |
| prefetch_engine (generator + queue) | 2,002 | 424 |
| **Total** | **99,471** | **40,791** |

The whole prefetch engine (predictor + queue) is **4,827 cells (4.9 %)** and
**733 flip-flops (1.8 %)** of the design. Almost all hardware is the cache
storage itself, so the 2.26× speedup costs very little extra logic.

`check -assert` passes (no combinational loops, no multiple drivers).

## What this is NOT
* These are generic gates, not a real standard-cell library, so there is no
  chip area (µm²), timing (MHz) or power number.
* No placement or routing was done. Physical placement needs a place-and-route
  tool (nextpnr for FPGAs, OpenROAD for chips). The cache storage is built from
  flip-flops (fine for simulation); a real chip would use an SRAM macro, and
  that is the step to take before place-and-route.
