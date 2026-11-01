#!/usr/bin/env python3
"""
ref_cache_model.py - Independent golden model of the BASELINE cache.

Functional 4 KB / 4-way / 64-set / 16 B-line true-LRU cache.  Without
prefetching, hit/miss outcome does not depend on timing, so the RTL baseline
must match this model EXACTLY (hits and misses) on every trace.
"""
import sys

LINE, SETS, WAYS = 16, 64, 4


def load_trace(path):
    out = []
    with open(path) as f:
        for ln in f:
            p = ln.split()
            if len(p) == 2:
                out.append((int(p[0]), int(p[1], 16)))
    return out


def simulate(addrs, line=LINE, sets=SETS, ways=WAYS):
    cache = [[] for _ in range(sets)]  # each set: list of tags, index 0 = MRU
    hits = misses = 0
    for a in addrs:
        la = a // line
        s, t = la % sets, la // sets
        st = cache[s]
        if t in st:
            hits += 1
            st.remove(t)
        else:
            misses += 1
            if len(st) == ways:
                st.pop()
        st.insert(0, t)
    return hits, misses


if __name__ == "__main__":
    tr = load_trace(sys.argv[1])
    h, m = simulate([a for _, a in tr])
    print(f"accesses={len(tr)} hits={h} misses={m}")
