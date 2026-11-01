#!/usr/bin/env python3
"""
generate_traces.py - Level 1: synthetic memory-trace generator.

No starter traces are provided by the challenge, so every workload here is a
SYNTHETIC model of an access pattern (not a trace captured from a real AI
model).  Each trace line is:   <compute_gap_cycles> <byte_address_hex>
All accesses are 32-bit loads (word aligned).  Fixed seed -> reproducible.

Basic patterns : sequential, stride, random, repeated, mixed, capacity
AI-inspired    : cnn, llm, recsys
"""
import os
import random

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "traces")
SEED = 2026
W = 4  # bytes per word


def gaps(rng, n, lo, hi):
    return [rng.randint(lo, hi) for _ in range(n)]


def sequential(rng):
    """Stream through a 32 KB tensor once (8x the cache)."""
    base = 0x0010_0000
    addrs = [base + W * i for i in range(8192)]
    return addrs, gaps(rng, len(addrs), 1, 4)


def stride(rng):
    """Fixed 48-byte stride (3 cache lines, not line aligned)."""
    base = 0x0020_0000
    addrs = [base + 48 * i for i in range(3000)]
    return addrs, gaps(rng, len(addrs), 1, 4)


def random_trace(rng):
    """Uniform random words in a 1 MB region (no exploitable pattern)."""
    base = 0x0040_0000
    addrs = [base + W * rng.randrange(0, (1 << 20) // W) for _ in range(4000)]
    return addrs, gaps(rng, len(addrs), 1, 4)


def repeated(rng):
    """A 1.5 KB working set read in the same shuffled order 10 times
    (temporal locality, fits in the 4 KB cache)."""
    base = 0x0050_0000
    order = [base + W * i for i in range(384)]
    rng.shuffle(order)
    addrs = order * 10
    return addrs, gaps(rng, len(addrs), 1, 4)


def mixed(rng):
    """Two streams (sequential + 32 B stride) interleaved with 25 % random."""
    a, b, rnd = 0x0060_0000, 0x0070_0000, 0x0080_0000
    ia = ib = 0
    addrs = []
    for _ in range(6000):
        p = rng.random()
        if p < 0.45:
            addrs.append(a + W * ia); ia += 1
        elif p < 0.75:
            addrs.append(b + 32 * ib); ib += 1
        else:
            addrs.append(rnd + W * rng.randrange(0, (1 << 18) // W))
    return addrs, gaps(rng, len(addrs), 1, 4)


def capacity(rng):
    """8 KB array (2x the cache) read sequentially 3 times -> LRU thrashing."""
    base = 0x0090_0000
    one = [base + W * i for i in range(2048)]
    addrs = one * 3
    return addrs, gaps(rng, len(addrs), 1, 4)


def cnn(rng):
    """CNN-inspired layer.
    Phase A (3x3 conv, line-buffer style): for each output row and channel,
    read the 3 input rows (contiguous in NCHW) + 9 reused weights.
    Phase B (1x1 / pointwise conv): for each pixel read all 16 channels
    -> fixed stride of one channel plane (256 B)."""
    addrs = []
    fmap, wts = 0x00A0_0000, 0x00B0_0000
    H = Wd = 16; C = 8
    for r in range(H - 2):
        for c in range(C):
            plane = fmap + c * H * Wd * W
            for kr in range(3):
                row = plane + (r + kr) * Wd * W
                addrs += [row + W * x for x in range(Wd)]
            addrs += [wts + (c * 9 + k) * W for k in range(9)]
    pw, pw_w = 0x00C0_0000, 0x00D0_0000
    P, C2 = 64, 16                         # 8x8 pixels, 16 channels
    for oc in range(2):
        for p in range(P):
            for c in range(C2):
                addrs.append(pw + c * P * W + p * W)
            addrs.append(pw_w + (oc * C2) * W)
    return addrs, gaps(rng, len(addrs), 2, 6)


def llm(rng):
    """LLM-decoder-inspired.
    Phase A (GEMV y = W x): weight matrix streamed row by row (never reused),
    activation vector x re-read for every row (stays in cache).
    Phase B (attention): scan K then V cache of 32 past tokens (sequential)."""
    addrs = []
    Wm, x = 0x0100_0000, 0x0110_0000
    rows, cols = 48, 64
    for i in range(rows):
        for j in range(cols):
            addrs.append(Wm + (i * cols + j) * W)
            addrs.append(x + j * W)
    K, V = 0x0120_0000, 0x0130_0000
    T, D = 32, 32
    q = 0x0140_0000
    for t in range(T):
        for d in range(D):
            addrs.append(K + (t * D + d) * W)
            if d % 8 == 0:
                addrs.append(q + d * W)
    for t in range(T):
        for d in range(D):
            addrs.append(V + (t * D + d) * W)
    return addrs, gaps(rng, len(addrs), 1, 4)


def recsys(rng):
    """Recommendation-model-inspired (DLRM-like).
    Embedding lookups: 8 rows per sample from a 4096 x 64 B table, row index
    Zipf-skewed (a few hot rows); each row read fully (4 cache lines).
    Then a small dense MLP weight block (reused)."""
    addrs = []
    emb, mlp = 0x0200_0000, 0x0210_0000
    rows = 4096
    hot = [rng.randrange(rows) for _ in range(32)]
    for _ in range(50):
        for _ in range(8):
            r = rng.choice(hot) if rng.random() < 0.5 else rng.randrange(rows)
            addrs += [emb + r * 64 + W * k for k in range(16)]
        addrs += [mlp + W * k for k in range(64)]
    return addrs, gaps(rng, len(addrs), 1, 4)


WORKLOADS = {
    "sequential": sequential,
    "stride": stride,
    "random": random_trace,
    "repeated": repeated,
    "mixed": mixed,
    "capacity": capacity,
    "cnn": cnn,
    "llm": llm,
    "recsys": recsys,
}


def demo(rng):
    """Short trace used for the GTKWave demonstration waveform."""
    base = 0x0010_0000
    addrs = [base + W * i for i in range(96)] + [0x0040_0000 + 0x1230, 0x0040_8000]
    return addrs, gaps(rng, len(addrs), 1, 3)


def write_trace(name, addrs, gaps_):
    path = os.path.join(OUT_DIR, f"{name}.trace")
    with open(path, "w") as f:
        for g, a in zip(gaps_, addrs):
            assert a % 4 == 0 and 0 <= a < (1 << 32)
            f.write(f"{g} {a:08x}\n")
    return path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, fn in WORKLOADS.items():
        rng = random.Random(f"{SEED}-{name}")
        addrs, g = fn(rng)
        p = write_trace(name, addrs, g)
        print(f"{name:11s} {len(addrs):6d} accesses -> {os.path.relpath(p)}")
    rng = random.Random(f"{SEED}-demo")
    write_trace("demo", *demo(rng))


if __name__ == "__main__":
    main()
