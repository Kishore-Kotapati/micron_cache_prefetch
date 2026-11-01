#!/usr/bin/env python3
"""make_learning_guide.py - builds docs/Project_Learning_Guide.pdf
(simple-language explanation of the whole project, with diagrams and the
measured results read from results/performance_summary.csv)."""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FIG = os.path.join(ROOT, "docs", "guide_figures")
OUT = os.path.join(ROOT, "docs", "Project_Learning_Guide.pdf")
os.makedirs(FIG, exist_ok=True)

PINK = "#c2185b"; BLUE = "#2e86c1"; GREY = "#9aa0a6"; DARK = "#222222"

# ------------------------------------------------------------------ figures
def box(ax, x, y, w, h, text, fc, fs=10, tc="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec="none"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc, wrap=True)


def arrow(ax, x1, y1, x2, y2, text="", c="#444", at=None, ha="center", rad=0.0):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=c, lw=1.6, connectionstyle=f"arc3,rad={rad}"))
    if text:
        lx, ly = at if at else ((x1 + x2) / 2, (y1 + y2) / 2 + 0.15)
        ax.text(lx, ly, text, fontsize=8, color=c, ha=ha, va="center")


def fig_hierarchy():
    fig, ax = plt.subplots(figsize=(8, 3)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 3)
    box(ax, 0.2, 1.0, 2.2, 1.0, "CPU / AI core\n(very fast math)", DARK)
    box(ax, 3.6, 1.0, 2.2, 1.0, "Cache\nsmall, fast\n1 cycle", PINK)
    box(ax, 7.4, 1.0, 2.4, 1.0, "DRAM\nbig, slow\n40 cycles here", GREY)
    arrow(ax, 2.4, 1.5, 3.6, 1.5); arrow(ax, 5.8, 1.5, 7.4, 1.5)
    ax.text(3.0, 2.3, "asks for data", fontsize=8, ha="center")
    ax.text(6.6, 2.3, "only on a miss", fontsize=8, ha="center")
    ax.text(5.0, 0.35, "Prefetch engine: brings data from DRAM into the cache BEFORE the CPU asks",
            fontsize=9, ha="center", color=PINK)
    fig.tight_layout(); p = os.path.join(FIG, "hierarchy.png"); fig.savefig(p, dpi=160); plt.close(fig); return p


def fig_address():
    fig, ax = plt.subplots(figsize=(8, 1.9)); ax.axis("off"); ax.set_xlim(0, 32); ax.set_ylim(0, 2)
    parts = [(0, 22, "TAG  (bits 31..10)\nwhich block of memory", BLUE),
             (22, 6, "INDEX (9..4)\nwhich set (0-63)", PINK),
             (28, 2, "WORD\n(3..2)", "#7fb3d5"), (30, 2, "BYTE\n(1..0)", GREY)]
    for x, w, t, c in parts:
        ax.add_patch(plt.Rectangle((x, 0.6), w, 1.0, fc=c, ec="white", lw=2))
        ax.text(x + w / 2, 1.1, t, ha="center", va="center", fontsize=8, color="white")
    ax.text(16, 0.2, "32-bit address split inside the cache", ha="center", fontsize=9)
    fig.tight_layout(); p = os.path.join(FIG, "address.png"); fig.savefig(p, dpi=160); plt.close(fig); return p


def fig_cache():
    fig, ax = plt.subplots(figsize=(8, 3.4)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 5)
    ax.text(0.2, 4.6, "64 sets  x  4 ways  =  256 lines  x  16 bytes  =  4 KB", fontsize=10)
    for r, s in enumerate([0, 1, 2, "...", 63]):
        y = 3.6 - r * 0.8
        ax.text(0.3, y + 0.25, f"set {s}", fontsize=8)
        if s == "...":
            continue
        for w in range(4):
            x = 1.3 + w * 2.1
            ax.add_patch(plt.Rectangle((x, y), 2.0, 0.55, fc="#f4d6e2" if (s == 1 and w == 2) else "#e8eef4",
                                       ec="#777"))
            ax.text(x + 1.0, y + 0.27, "V | P | tag | 16 B data", fontsize=6.5, ha="center", va="center")
    for w in range(4):
        ax.text(2.3 + w * 2.1, 4.25, f"way {w}", fontsize=8, ha="center")
    ax.text(5.0, 0.05, "V = valid bit, P = 'prefetched, not yet used' bit, plus an LRU age per way",
            fontsize=8, ha="center")
    fig.tight_layout(); p = os.path.join(FIG, "cache.png"); fig.savefig(p, dpi=160); plt.close(fig); return p


def fig_timeline():
    fig, ax = plt.subplots(figsize=(8, 2.8)); ax.set_xlim(0, 100); ax.set_ylim(0, 3); ax.axis("off")
    ax.text(0, 2.7, "Without prefetch:", fontsize=9, weight="bold")
    t = 0
    for i in range(2):
        ax.add_patch(plt.Rectangle((t, 2.0), 6, 0.4, fc=BLUE)); t += 6
        ax.add_patch(plt.Rectangle((t, 2.0), 40, 0.4, fc=GREY)); ax.text(t + 20, 2.2, "wait for DRAM", fontsize=7, ha="center", va="center"); t += 40
    ax.text(0, 1.3, "With prefetch:", fontsize=9, weight="bold")
    t = 0
    for i in range(7):
        ax.add_patch(plt.Rectangle((t, 0.6), 6, 0.4, fc=BLUE)); t += 7
    ax.add_patch(plt.Rectangle((7, 0.1), 40, 0.25, fc=PINK)); ax.text(27, 0.22, "prefetch travels while CPU works", fontsize=7, ha="center", va="center", color="white")
    ax.text(60, 0.8, "same work finished much earlier", fontsize=8, color=PINK)
    ax.add_patch(plt.Rectangle((70, 2.55), 3, 0.25, fc=BLUE)); ax.text(74, 2.67, "CPU working", fontsize=7, va="center")
    fig.tight_layout(); p = os.path.join(FIG, "timeline.png"); fig.savefig(p, dpi=160); plt.close(fig); return p


def fig_system():
    fig, ax = plt.subplots(figsize=(8, 4.4)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 6.2)
    box(ax, 0.2, 4.9, 4.2, 1.0, "CPU model (testbench)\nreads trace: gap + address", DARK, 8)
    box(ax, 0.2, 2.2, 4.2, 1.9, "cache_controller\nFSM + 8 MSHRs + arbitration\n\ntag_array | cache_memory\nreplacement_policy (LRU)", PINK, 8)
    box(ax, 6.0, 2.2, 3.8, 1.9, "prefetch_engine\n\nstride_predictor\n(4 streams, confidence,\nadaptive degree)\n+ candidate queue", BLUE, 8)
    box(ax, 0.2, 0.1, 4.2, 1.0, "memory_model (DRAM)\n40-cycle latency, 1 request / 4 cycles", GREY, 8)
    arrow(ax, 1.5, 4.9, 1.5, 4.1, "load request", at=(1.4, 4.5), ha="right")
    arrow(ax, 3.1, 4.1, 3.1, 4.9, "data", at=(3.2, 4.5), ha="left")
    arrow(ax, 4.4, 3.6, 6.0, 3.6, "watch: every load", at=(5.2, 3.85))
    arrow(ax, 6.0, 2.7, 4.4, 2.7, "guesses (lines)", at=(5.2, 2.95))
    arrow(ax, 1.5, 2.2, 1.5, 1.1, "demand + prefetch requests", at=(1.4, 1.65), ha="right")
    arrow(ax, 3.1, 1.1, 3.1, 2.2, "lines back", at=(3.2, 1.65), ha="left")
    fig.tight_layout(); p = os.path.join(FIG, "system.png"); fig.savefig(p, dpi=160); plt.close(fig); return p


def fig_fsm():
    fig, ax = plt.subplots(figsize=(8, 3.4)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 4.2)
    box(ax, 0.3, 1.5, 2.2, 0.9, "S_IDLE\nlook up tags", PINK, 9)
    box(ax, 3.9, 2.9, 2.4, 0.9, "S_MISS_REQ\nsend to DRAM", BLUE, 9)
    box(ax, 7.4, 1.5, 2.3, 0.9, "S_WAIT\nwait for line", GREY, 9)
    arrow(ax, 2.0, 2.4, 3.9, 3.3, "miss", at=(2.6, 3.15))
    arrow(ax, 6.3, 3.3, 8.2, 2.4, "DRAM accepted", at=(7.8, 3.15))
    arrow(ax, 2.5, 2.05, 7.4, 2.05, "miss, line already coming = merge", at=(4.95, 2.3))
    arrow(ax, 8.5, 1.5, 1.4, 1.5, "line arrived: give data to CPU", rad=-0.35, at=(4.95, 0.45))
    ax.annotate("", xy=(1.3, 2.42), xytext=(0.8, 2.42),
                arrowprops=dict(arrowstyle="->", color="#444", lw=1.6, connectionstyle="arc3,rad=-1.6"))
    ax.text(1.05, 3.35, "hit: data in 1 cycle", fontsize=8, ha="center")
    fig.tight_layout(); p = os.path.join(FIG, "fsm.png"); fig.savefig(p, dpi=160); plt.close(fig); return p


FIGS = dict(hier=fig_hierarchy(), addr=fig_address(), cache=fig_cache(), time=fig_timeline(),
            sys=fig_system(), fsm=fig_fsm())

# ------------------------------------------------------------------ styles
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], textColor=colors.HexColor(PINK), fontSize=17, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=colors.HexColor(BLUE), fontSize=13, spaceBefore=8, spaceAfter=4)
P = ParagraphStyle("P", parent=ss["BodyText"], fontSize=10, leading=14, spaceAfter=5)
B = ParagraphStyle("B", parent=P, leftIndent=12, bulletIndent=2)
NOTE = ParagraphStyle("N", parent=P, backColor=colors.HexColor("#fdf0f5"), borderPadding=6,
                      borderColor=colors.HexColor(PINK), borderWidth=0.6, spaceBefore=6, spaceAfter=10)
CODE = ParagraphStyle("C", parent=ss["Code"], fontSize=8, leading=10, backColor=colors.HexColor("#f4f4f4"),
                      borderPadding=5, spaceAfter=8)
CAP = ParagraphStyle("cap", parent=P, fontSize=8.5, textColor=colors.HexColor("#555"), alignment=TA_CENTER)
CELL = ParagraphStyle("cell", parent=P, fontSize=8.5, leading=11, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, textColor=colors.white, fontName="Helvetica-Bold")

story = []
def h1(t): story.append(Paragraph(t, H1))
def h2(t): story.append(Paragraph(t, H2))
def p(t): story.append(Paragraph(t, P))
def bl(items):
    for it in items:
        story.append(Paragraph(it, B, bulletText="•"))
def note(t): story.append(Paragraph(t, NOTE))
def code(t): story.append(Preformatted(t, CODE))
def img(path, w=16, cap=None):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(path).getSize()
    story.append(Image(path, width=w * cm, height=w * cm * ih / iw))
    if cap: story.append(Paragraph(cap, CAP))
    story.append(Spacer(1, 6))
def table(rows, widths=None, head=True):
    data = [[Paragraph(str(c), CELLB if (head and i == 0) else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * cm for w in widths] if widths else None, repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
          ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fa")])]
    if head: st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BLUE)))
    t.setStyle(TableStyle(st)); story.append(t); story.append(Spacer(1, 8))

df = pd.read_csv(os.path.join(ROOT, "results", "performance_summary.csv"))
ORDER = ["sequential", "stride", "random", "repeated", "mixed", "capacity", "cnn", "llm", "recsys"]
def R(t, c): return df[(df.trace == t) & (df.config == c)].iloc[0]
def gm(c, ts): v = df[(df.config == c) & (df.trace.isin(ts))].speedup; return math.exp(sum(map(math.log, v)) / len(v))
GM_ALL, GM_AI = gm("smart", ORDER), gm("smart", ["cnn", "llm", "recsys"])

# ------------------------------------------------------------------ cover
story.append(Spacer(1, 3 * cm))
story.append(Paragraph("AI-Aware Cache &amp; Prefetch Engine", ParagraphStyle("t", parent=H1, fontSize=26, alignment=TA_CENTER, leading=32)))
story.append(Paragraph("Micron RTL Challenge - complete learning guide", ParagraphStyle("st", parent=P, fontSize=14, alignment=TA_CENTER)))
story.append(Spacer(1, 1 * cm))
img(FIGS["hier"], 15)
story.append(Spacer(1, 0.6 * cm))
story.append(Paragraph(f"<b>Result:</b> {GM_ALL:.2f}x faster on average (geometric mean, 9 workloads), "
                       f"{GM_AI:.2f}x on the AI-inspired workloads, never slower than a normal cache.",
                       ParagraphStyle("r", parent=P, fontSize=12, alignment=TA_CENTER, leading=17)))
story.append(Spacer(1, 2 * cm))
story.append(Paragraph("Kotapati Kishore  |  1 November 2026", ParagraphStyle("a", parent=P, alignment=TA_CENTER)))
story.append(Paragraph("Everything in this guide uses numbers measured from the project's own simulations.", CAP))
story.append(PageBreak())

# ------------------------------------------------------------------ contents
h1("Contents")
for i, t in enumerate(["The project in one page", "Background: why memory is the bottleneck",
                       "How a cache works", "What prefetching is", "Our system - the big picture",
                       "The life of one load (step by step)", "The prediction engine in detail",
                       "Our three innovations", "The workloads (test inputs)", "How we proved it works",
                       "Results and how to read them", "Going further: perfect cache, slow DRAM, tuning", "Hardware size (synthesis)",
                       "Every file explained", "How to run everything", "Demo script for the judges",
                       "Questions judges may ask (with answers)", "Limitations and future work", "Glossary"], 1):
    p(f"{i}. {t}")
story.append(PageBreak())

# ------------------------------------------------------------------ 1
h1("1. The project in one page")
p("<b>The challenge (from Micron's slides):</b> AI models like LLMs, CNNs and recommenders are fast at math, "
  "but they waste time waiting for data from memory. Build hardware that fetches data <i>before</i> it is "
  "needed: <b>Watch</b> which addresses the program reads, <b>Guess</b> the next address, <b>Fetch early</b> "
  "into the cache. Result: fewer slow DRAM trips, more cache hits, faster AI.")
p("<b>What we built:</b>")
bl(["A <b>cache</b> (4 KB, 4-way, 16-byte lines) written in Verilog - the hardware description language chips are designed in.",
    "A <b>prefetch engine</b> that learns the step size (stride) of up to 4 memory streams, decides how sure it is, "
    "and loads the next lines early.",
    "Three <b>adaptive tricks</b>: it measures its own accuracy and (1) goes further ahead when right, "
    "(2) gives short new streams a quick start, (3) protects useful data when its guesses are poor.",
    "A <b>DRAM model</b> (40-cycle delay) and a <b>CPU model</b> that replays memory traces.",
    "<b>9 test workloads</b> made in Python, including CNN-, LLM- and recommender-like patterns.",
    "A full <b>verification</b> flow: self-checking testbench, Python golden model, a second simulator "
    "(Verilator), Cocotb Python tests, lint and synthesis."])
table([["Question", "Answer"],
       ["How much faster?", f"{GM_ALL:.2f}x average over 9 workloads, {GM_AI:.2f}x on AI-inspired ones, up to {R('stride','smart').speedup:.1f}x"],
       ["Is it correct?", "54/54 simulations pass; matches Python model exactly; identical on 2 simulators; 7/7 Cocotb tests"],
       ["How big is the prefetcher?", "4.9 % of the logic, 1.8 % of the flip-flops"],
       ["Slower DRAM (120 cycles)?", "3.03x average, 2.97x on AI-inspired workloads"],
       ["Tools", "Python 3, Icarus Verilog, GTKWave, Git, Verilator, Cocotb, Pandas, Matplotlib (+ Yosys)"]],
      [4.5, 12])
story.append(PageBreak())

# ------------------------------------------------------------------ 2
h1("2. Background: why memory is the bottleneck")
p("A processor can do one calculation every clock cycle. But reading data from main memory (DRAM) takes "
  "tens to hundreds of cycles. If the processor must wait for every piece of data, it sits idle most of the time. "
  "This is called the <b>memory wall</b>.")
p("AI workloads make it worse: a large language model reads millions of weights for every word it produces, "
  "and a recommender jumps around huge embedding tables. The math units are fast; the data supply is slow.")
note("<b>Simple analogy.</b> DRAM is a big library far away. The cache is your small desk. Working from the desk is "
     "instant; walking to the library takes a long time. A prefetcher is a helper who notices which books you are "
     "reading in order and puts the next ones on your desk before you ask.")
img(FIGS["time"], 16, "Prefetching overlaps the slow DRAM trip with useful work.")
h2("Key numbers in our model")
table([["Item", "Value", "Meaning"],
       ["Cache hit", "1 cycle", "data is already in the cache"],
       ["Cache miss", "about 42 cycles", "40-cycle DRAM delay + a few control cycles"],
       ["DRAM bandwidth", "1 new request every 4 cycles", "so useless prefetches really cost something"],
       ["CPU compute gap", "1-6 cycles between loads", "the 'math' the AI does between memory reads"]],
      [3.5, 4.5, 8.5])
p("<b>AMAT</b> (Average Memory Access Time) = hit time + miss rate x miss penalty. "
  "Example: with 25 % misses, AMAT = 1 + 0.25 x 41 = about 11 cycles. If prefetching cuts misses to 1 %, "
  "AMAT drops to about 1.4 cycles. That is exactly what we measured on the sequential workload (11.25 -> 1.07).")
story.append(PageBreak())

# ------------------------------------------------------------------ 3
h1("3. How a cache works")
h2("Lines")
p("The cache does not store single bytes. It stores <b>lines</b> of 16 bytes (4 words of 32 bits). When you read "
  "one word, the whole line comes from DRAM, so the next 3 words are free hits. That is <b>spatial locality</b>. "
  "Reading the same data again soon is <b>temporal locality</b>.")
h2("Where does a line go? - the address split")
img(FIGS["addr"], 16)
p("<b>Worked example:</b> address <font face='Courier'>0x00100A34</font>")
bl(["WORD = bits 3..2 = 1 (the second word in the line)",
    "INDEX = bits 9..4 = 35, so the line can only live in <b>set 35</b>",
    "TAG = bits 31..10 = 0x402. The cache stores the tag to remember <i>which</i> memory block is in that slot."])
h2("Sets and ways")
img(FIGS["cache"], 16)
p("Each set has <b>4 ways</b> (4 slots), so 4 different lines with the same index can live together. "
  "On a lookup the cache reads all 4 tags of the set at once and compares them with the address tag. "
  "Equal tag + valid bit = <b>hit</b>. Otherwise <b>miss</b>.")
h2("Which line is thrown out? - LRU")
p("When a set is full and a new line arrives, we evict the <b>Least Recently Used</b> line. Each way has a 2-bit "
  "age (0 = just used, 3 = oldest). On a hit the line becomes age 0 and the younger ones age by one. "
  "Example: lines A, B, C, D fill a set; you touch A again; then E arrives. B is now the oldest, so B is evicted. "
  "(This exact case is one of our Cocotb tests.)")
h2("Why 4 KB, 4-way?")
table([["Option", "Good", "Bad"],
       ["Direct-mapped (1 way)", "cheapest, fastest", "two streams with the same index keep evicting each other"],
       ["Fully associative", "no conflicts", "needs 256 tag comparators - expensive"],
       ["<b>4-way set associative (chosen)</b>", "few conflicts, only 4 comparators", "a bit more logic than direct-mapped"]],
      [5, 5, 6.5])
p("4 KB is deliberately small so that our workloads (8-60 KB) do not fit, exactly like real AI models do not fit "
  "in real caches.")
story.append(PageBreak())

# ------------------------------------------------------------------ 4
h1("4. What prefetching is")
p("Prefetching = loading data into the cache before the program asks for it. A good prefetcher must guess "
  "<b>what</b> to fetch, <b>when</b> (early enough to arrive in time, not so early that it is evicted before use) "
  "and <b>how much</b> (too much wastes DRAM bandwidth and pushes out useful data).")
h2("Common strategies")
table([["Strategy", "Idea", "Works well for", "Fails on"],
       ["Next-line (sequential)", "after using line L, fetch L+1", "simple streams, very short streams", "any jump bigger than one line; wastes bandwidth on random data"],
       ["Stride", "learn the step between accesses (e.g. +48 B) and continue it", "array walks, matrix rows, channels", "short streams (needs time to learn)"],
       ["Adaptive stride", "stride + adjust distance/amount by measured accuracy", "long regular AI streams", "nothing new for random data"],
       ["Pattern-based / ML", "learn complex sequences", "irregular repeat patterns", "large and complex hardware"]],
      [3.2, 4.4, 4.3, 4.6])
h2("Measuring a prefetcher")
bl(["<b>Useful prefetch:</b> the line was used by the CPU while it was still waiting in the cache (on time).",
    "<b>Late prefetch:</b> the CPU asked while the line was still on its way from DRAM. It still saves part of the wait.",
    "<b>Unused prefetch:</b> fetched but never used - wasted DRAM bandwidth.",
    "<b>Accuracy</b> = useful / issued.  <b>Coverage</b> = share of the baseline misses that were removed.",
    "Important: prefetches are <i>never</i> counted as CPU accesses, so hit rate is always about real CPU loads."])
story.append(PageBreak())

# ------------------------------------------------------------------ 5
h1("5. Our system - the big picture")
img(FIGS["sys"], 16, "Blocks of the design. Pink and blue are the real hardware; grey is the DRAM simulation model.")
table([["Block", "Job"],
       ["cache_controller", "the brain of the cache: looks up tags, handles hits and misses, sends requests to DRAM, decides who goes first"],
       ["tag_array", "stores for every line: tag, valid bit, 'prefetched' bit"],
       ["cache_memory", "stores the 16-byte data of every line"],
       ["replacement_policy", "keeps the LRU ages; picks which line to evict; can insert a line as 'oldest'"],
       ["stride_predictor", "the WATCH and GUESS part: stream table, confidence, triggers, accuracy monitor"],
       ["prefetch_engine", "turns a guess into a list of line addresses and keeps them in an 8-entry queue"],
       ["memory_model", "fake DRAM for simulation: 40-cycle delay, limited bandwidth, data = a formula of the address"],
       ["top_module", "connects everything; settings choose baseline or a prefetch mode"]],
      [4, 12.5])
h2("MSHRs - many requests in flight")
p("An <b>MSHR</b> (Miss Status Holding Register) remembers one request that has gone to DRAM and not come back yet. "
  "We have 8. The CPU can only wait for one load at a time, but the prefetcher can keep up to 7 requests travelling "
  "at once - that is how the 40-cycle delay gets hidden. One MSHR is always kept free for the CPU.")
story.append(PageBreak())

# ------------------------------------------------------------------ 6
h1("6. The life of one load (step by step)")
img(FIGS["fsm"], 16, "The demand state machine inside cache_controller.")
h2("Case A - hit")
bl(["Cycle 0: the CPU puts the address on the bus. The cache splits it, reads the 4 tags of the set and compares them.",
    "A tag matches: the data word is returned in the next cycle. The line becomes most recently used.",
    "If the line was brought by the prefetcher, the 'prefetched' bit is cleared and the 'useful' counter goes up."])
h2("Case B - miss")
bl(["No tag matches and the line is not on its way: go to S_MISS_REQ and send the request to DRAM "
    "(demand requests always go before prefetches).",
    "S_WAIT: about 40 cycles later the line comes back, is written into the victim way chosen by LRU, "
    "and the word goes to the CPU."])
h2("Case C - late prefetch (merge)")
bl(["No tag matches, but an MSHR shows the line is already coming because of a prefetch.",
    "The cache does <b>not</b> send a second request. It marks that MSHR as 'CPU is waiting' and waits only "
    "for the remaining time (our Cocotb test measured 11 cycles instead of 42)."])
h2("Meanwhile - the prefetch path")
bl(["Every access is also sent to the predictor (WATCH).",
    "When it is confident it puts line addresses into the queue (GUESS).",
    "Each cycle the controller checks the queue head: already in cache or already coming? drop it. "
    "Otherwise, if the DRAM port is free and at least 2 MSHRs are free, send it (FETCH EARLY).",
    "When the line returns it is stored with the 'prefetched' bit set."])
h2("Rules that keep it correct")
table([["Rule", "Why"],
       ["Demand first on the DRAM port", "prefetching must never slow down the CPU's own misses"],
       ["Only one write to the cache arrays per cycle (fills wait during a CPU lookup)", "no two writers can corrupt the same line"],
       ["One MSHR always free for the CPU", "a burst of prefetches can never block a demand miss"],
       ["Drop candidates already cached or in flight", "no duplicate lines, no wasted DRAM trips"],
       ["No prefetch across a 4 KB page", "never guess into unrelated memory"]],
      [8, 8.5])
story.append(PageBreak())

# ------------------------------------------------------------------ 7
h1("7. The prediction engine in detail")
p("The stride predictor has a table of <b>4 streams</b>. Each entry remembers: last address, stride (step in bytes) "
  "and a 2-bit <b>confidence</b> (0-3). Our traces only contain addresses (no program counter), so a load belongs to "
  "the stream whose last address is within 1 KB of it. Streams far apart (weights, activations, KV cache) "
  "get separate entries.")
h2("Learning rules")
bl(["Same stride as before -> confidence + 1 (max 3).",
    "Different stride -> confidence - 1; if confidence is 1 or less, learn the new stride.",
    "No stream matches -> start a new entry (replace a free or a confidence-0 entry first, so random loads "
    "cannot erase a good stream).",
    "Fire when confidence >= 2 and the load moved into a new cache line: prefetch addr + 1 x step ... addr + degree x step.",
    "Strides smaller than a line (e.g. 4 bytes) are rounded up to one line, so word-by-word streams fetch whole next lines."])
h2("Worked example: a 48-byte stride")
table([["Load", "Address", "Distance", "Stream state after", "Action"],
       ["1", "0x2000", "-", "new stream, stride 0, conf 0", "none"],
       ["2", "0x2030", "+48", "stride learned = 48, conf 0", "none"],
       ["3", "0x2060", "+48", "same stride, conf 1", "none (not sure yet)"],
       ["4", "0x2090", "+48", "conf 2, new line", "prefetch 0x20C0 and 0x20F0 (degree 2)"],
       ["5", "0x20C0", "+48", "conf 3", "load hits (was prefetched); prefetch 0x2120 (0x20F0 is filtered as duplicate)"]],
      [1.2, 2.0, 1.8, 5.0, 6.5])
note("The degree (how many lines ahead) is not fixed - see innovation 1. On long streams it climbs to 7, so the "
     "prefetch is started 7 steps before the data is needed, which is enough to hide the 40-cycle DRAM delay.")
story.append(PageBreak())

# ------------------------------------------------------------------ 8
h1("8. Our three innovations")
p("All three use one small <b>accuracy monitor</b>: two 6-bit counters that count, over every 32 issued prefetches, "
  "how many were used (on time or late).")
h2("Innovation 1 - accuracy-feedback adaptive degree  (slide: Intelligent Prefetching)")
table([["Measured accuracy (last 32 prefetches)", "Action"],
       [">= 75 % used", "degree + 1 (up to 7): run further ahead"],
       ["< 25 % used", "degree - 1 (down to 1): back off"]], [8, 8.5])
p(f"Effect (fixed degree 2 -> adaptive): sequential {R('sequential','stride').speedup:.2f}x -> {R('sequential','stride_adapt').speedup:.2f}x, "
  f"stride {R('stride','stride').speedup:.2f}x -> {R('stride','stride_adapt').speedup:.2f}x, average "
  f"{gm('stride',ORDER):.2f}x -> {gm('stride_adapt',ORDER):.2f}x. This is the biggest single gain.")
h2("Innovation 2 - hybrid quick start for new or jumping streams  (slide: Novel Prediction Algorithms, AI-Aware)")
p("Recommendation models read short embedding rows (64 bytes = 4 lines) at random places. The stride detector needs "
  "about 5 loads to become sure, so the row is almost finished before it helps. The same happens in a CNN each time it "
  "moves to the next feature-map row: the stream <i>jumps</i> and has to re-learn. Fix: when a <b>new</b> stream starts "
  "with a <b>miss</b>, or a known stream <b>jumps</b> on a miss, immediately prefetch the next 2 lines while the stride "
  "re-trains. To stop this from wasting bandwidth on random data, it is switched <b>off while measured accuracy is below 50 %</b>.")
p(f"Effect (adding this idea): CNN {R('cnn','stride_adapt').speedup:.2f}x -> {R('cnn','smart_noins').speedup:.2f}x, "
  f"recsys {R('recsys','stride_adapt').speedup:.2f}x -> {R('recsys','smart_noins').speedup:.2f}x, "
  f"repeated {R('repeated','stride_adapt').speedup:.2f}x -> {R('repeated','smart_noins').speedup:.2f}x. "
  f"On pure random data only {int(R('random','smart').prefetch_dram)} prefetches are issued in total, while a plain "
  f"next-line prefetcher doubles DRAM traffic. The jump case was found by logging every slow CNN load and seeing that "
  f"the first two lines of each new row always missed.")
h2("Innovation 3 - adaptive insertion  (slide: Adaptive Cache Policies)")
p("When guesses are poor (accuracy below 50 %), new prefetched lines are inserted as the <b>oldest</b> line in their set, "
  "so a wrong guess is the first thing thrown out and cannot push out useful data. When guesses are good they are "
  "inserted as newest, so they survive until used. We first tried 'always insert as oldest' and it hurt multi-stream "
  "workloads - that measurement is why the policy is adaptive.")
p(f"Effect: recsys {R('recsys','smart_noins').speedup:.2f}x -> {R('recsys','smart').speedup:.2f}x with "
  f"{100*(1-R('recsys','smart').dram_transactions/R('recsys','smart_noins').dram_transactions):.0f} % less DRAM traffic. "
  f"Honest cost: mixed {R('mixed','smart_noins').speedup:.2f}x -> {R('mixed','smart').speedup:.2f}x.")
story.append(PageBreak())

# ------------------------------------------------------------------ 9
h1("9. The workloads (test inputs)")
p("Micron gave no traces, so <font face='Courier'>python/generate_traces.py</font> creates them. Each line of a trace "
  "is '<i>compute gap</i>  <i>address</i>'. The same fixed random seed is used every time, so results are reproducible. "
  "These are <b>synthetic models</b> of access patterns, not recordings of real AI programs.")
table([["Trace", "Loads", "What it imitates"],
       ["sequential", "8192", "reading a 32 KB tensor from start to end"],
       ["stride", "3000", "every 48th byte (not line-aligned) - e.g. one field of a structure array"],
       ["random", "4000", "random words in 1 MB - nothing to predict"],
       ["repeated", "3840", "a 1.5 KB working set read 10 times in the same shuffled order (fits in cache)"],
       ["mixed", "6000", "two streams + 25 % random loads, interleaved"],
       ["capacity", "6144", "an 8 KB array (2x the cache) read 3 times - LRU keeps throwing out what comes next"],
       ["cnn", "8560", "3x3 convolution reading input rows + reused weights, then a 1x1 conv walking channels (256 B stride)"],
       ["llm", "8320", "matrix-vector product: weights streamed once, activation vector reused; then KV-cache scans"],
       ["recsys", "9600", "embedding lookups: 8 rows per sample, popular rows reused (Zipf), each row 4 lines; plus a small MLP"]],
      [2.4, 1.4, 12.7])
img(os.path.join(ROOT, "results", "plots", "access_patterns.png"), 15.5, "Address vs. time for every workload (from analyze_traces.py).")
story.append(PageBreak())

# ------------------------------------------------------------------ 10
h1("10. How we proved it works")
p("Wrong hardware that looks fast is worthless, so correctness was checked in five independent ways.")
table([["Check", "How", "Result"],
       ["1. Self-checks in every simulation", "testbench checks every returned word against the DRAM formula; hits+misses = loads; no line stored twice; "
        "every prefetch is accounted for (used, late, evicted unused, or still in cache); all MSHRs empty at the end", "54/54 runs PASS"],
       ["2. Golden model", "a separate Python LRU cache computes hits/misses for the baseline; the RTL must match exactly", "9/9 traces: exact match"],
       ["3. Second simulator", "the same testbench is compiled with Verilator and all 54 runs repeated; every number compared", "54/54 identical"],
       ["4. Cocotb tests", "7 Python tests poke the hardware directly (see below)", "7/7 PASS"],
       ["5. Lint", "Verilator -Wall looks for latches, width errors, multiple drivers", "0 warnings"]],
      [3.8, 9.2, 3.5])
h2("The 7 Cocotb tests")
table([["Test", "What it proves", "Measured"],
       ["hit_and_miss_latency", "first load misses, rest of the line hits", "miss 42 cycles, hit 1 cycle"],
       ["lru_replacement", "the least recently used line is evicted", "pass"],
       ["random_vs_golden_model", "1500 random loads, hits/misses equal the Python model", "554 hits / 946 misses, exact"],
       ["prefetch_removes_misses", "a 128-line stream", "demand DRAM requests 128 -> 1"],
       ["demand_during_prefetch", "a load to a line on its way merges; an unrelated miss is not delayed", "merge 11 cycles, miss 42 cycles with 3 prefetches in flight"],
       ["no_prefetch_across_page", "never guesses into the next 4 KB page", "30 prefetches, 0 across"],
       ["random_traffic_is_throttled", "accuracy gate stops waste on random data", "32 prefetches for 600 loads"]],
      [4.2, 7, 5.3])
note("Honesty note: two Cocotb tests failed on their first run because the <i>tests</i> were wrong (one counted late "
     "prefetches as full misses, one loaded a line that had already arrived). The tests were fixed; the hardware was not changed.")
h2("GTKWave waveforms")
p("<font face='Courier'>simulation/waveforms/demo_final.vcd</font> is a short run you can open in GTKWave. "
  "You can see prefetch requests (pf_issue) firing in the gaps between CPU loads and never in the same cycle as a "
  "CPU request, several MSHRs busy at once (m_v), duplicates dropped (pf_drop), and later loads hitting in 1 cycle. "
  "In this demo the baseline needs 26 demand DRAM requests; the final design needs 3.")
story.append(PageBreak())

# ------------------------------------------------------------------ 11
h1("11. Results and how to read them")
p("Both architectures use the <b>same</b> RTL, traces and DRAM timing - only the prefetch setting changes. "
  "A = baseline cache (no prefetch). B = final design.")
rows = [["Trace", "Hit % A -> B", "AMAT A -> B (cycles)", "Cycles A -> B", "Speedup", "DRAM traffic"]]
for t in ORDER:
    a, b = R(t, "baseline"), R(t, "smart")
    rows.append([t, f"{a.hit_rate_pct:.1f} -> {b.hit_rate_pct:.1f}", f"{a.amat_measured:.2f} -> {b.amat_measured:.2f}",
                 f"{a.cycles} -> {b.cycles}", f"<b>{b.speedup:.2f}x</b>", f"{b.dram_traffic_vs_base:.2f}x"])
rows.append(["<b>average</b>", "", "", "", f"<b>{GM_ALL:.2f}x</b>", ""])
table(rows, [2.4, 3.0, 3.6, 3.8, 1.8, 2.0])
img(os.path.join(ROOT, "results", "plots", "speedup.png"), 16.5, "Speedup of every architecture we compared.")
h2("What the results mean")
bl(["<b>Long regular streams</b> (sequential, capacity, LLM): almost every miss disappears and DRAM traffic stays the same "
    "- the same lines are just fetched earlier.",
    "<b>stride</b>: 5.2x faster even though most prefetches are 'late': the CPU wants a new line every ~3.5 cycles "
    "but DRAM accepts one only every 4, so this run is limited by DRAM bandwidth.",
    "<b>random</b>: nothing can be predicted; the design correctly stays quiet (1.00x, almost no extra traffic).",
    "<b>repeated</b>: everything already fits in the cache; only the 96 first-touch misses can be helped (1.08x).",
    "<b>CNN, recsys, mixed</b>: real speedups, paid for with more DRAM traffic (about 1.4-1.8x)."])
h2("Comparing all strategies (average speedup)")
table([["Architecture", "All 9 traces", "AI-inspired (cnn, llm, recsys)"]] +
      [[c, f"{gm(c, ORDER):.2f}x", f"{gm(c, ['cnn','llm','recsys']):.2f}x"] for c in
       ["baseline", "nextline", "stride", "stride_adapt", "smart_noins", "smart"]], [5, 4, 6])
p("smart = final design. Each row adds one idea to the row above, which shows how much every idea contributes.")
story.append(PageBreak())

# ------------------------------------------------------------------ 12 (going further)
h1("12. Going further: perfect cache, slow DRAM, tuning")
h2("How close are we to a perfect cache?")
p("A 'perfect' cache would answer every load in 1 cycle. Because the CPU model is the same, its run time can be "
  "computed exactly from the baseline run. This tells us how much of the <i>possible</i> gain we achieved.")
gap_rows = [["Trace", "Speedup now", "Max possible", "Share of possible gain"]]
for t in ORDER:
    a, b = R(t, "baseline"), R(t, "smart")
    ideal = a.cycles - a.amat_measured * a.accesses + a.accesses
    gap_rows.append([t, f"{b.speedup:.2f}x", f"{a.cycles/ideal:.2f}x", f"{100*(a.cycles-b.cycles)/(a.cycles-ideal):.0f} %"])
table(gap_rows, [3.5, 3.5, 3.5, 4.5])
p("Regular streams (sequential, capacity, LLM) reach 98-99 % of perfect: nothing left to win. Random addresses cannot be "
  "predicted by anyone (0 %), which also limits mixed and recsys. stride is limited by DRAM bandwidth.")
lat = pd.read_csv(os.path.join(ROOT, "results", "latency_sweep.csv"))
h2("What if DRAM is slower?")
p("Real DRAM is usually more than 100 CPU cycles away. We re-ran everything with 20, 40, 80 and 120-cycle DRAM "
  "(only the DRAM model changes):")
table([["DRAM latency", "Average speedup (9 traces)", "AI-inspired (cnn, llm, recsys)"]] +
      [[f"{L} cycles", f"{math.exp(lat[lat.latency==L].speedup.map(math.log).mean()):.2f}x",
        f"{math.exp(lat[(lat.latency==L)&lat.trace.isin(['cnn','llm','recsys'])].speedup.map(math.log).mean()):.2f}x"]
       for L in sorted(lat.latency.unique())], [4, 5.5, 6])
img(os.path.join(ROOT, "results", "plots", "latency_sweep.png"), 13, "The slower the memory, the more the prefetcher helps.")
sw = pd.read_csv(os.path.join(ROOT, "results", "design_sweep.csv"))
h2("Is the design tuned to death? - design-space exploration")
p(f"We tried 16 combinations of its settings (stream-table size, confidence threshold, quick-start length, accuracy "
  f"window). All 16 give between {sw.gm_all.min():.2f}x and {sw.gm_all.max():.2f}x: the design is robust, not fragile. "
  "The best one was under 1 % better and was tuned on the same traces, so we kept the simple defaults (no overfitting).")
h2("An idea we tested and rejected")
p("CNN channels 256 bytes apart all fall into the same 4 cache sets. Mixing higher address bits into the set number "
  "(XOR hashing) made CNN 3.4 % faster but recsys 1.3 % slower, and it changes the baseline cache too, so it was not "
  "adopted. Testing ideas and keeping only clear wins is part of good engineering.")
story.append(PageBreak())

# ------------------------------------------------------------------ 12
h1("13. Hardware size (synthesis)")
p("Yosys (a free synthesis tool) turned the Verilog into logic gates. This shows the design is real, buildable "
  "hardware, and how much each part costs.")
table([["Block", "Logic cells", "Flip-flops"],
       ["cache data (4 KB)", "65,968", "32,768"], ["tags + valid + prefetched bits", "22,953", "6,144"],
       ["cache controller", "3,872", "634"], ["LRU replacement", "1,855", "512"],
       ["<b>prefetch engine (predictor + queue)</b>", "<b>4,827 (4.9 %)</b>", "<b>733 (1.8 %)</b>"],
       ["<b>total</b>", "<b>99,471</b>", "<b>40,791</b>"]], [7, 4.5, 4.5])
note("The 'intelligence' is under 5 % of the hardware; almost everything is the cache storage itself. "
     "These are generic gates - no chip area, clock speed, power or placement is claimed.")
img(os.path.join(ROOT, "synth", "block_top.png"), 16, "Yosys drawing of how the cache controller and prefetch engine are wired.")
story.append(PageBreak())

# ------------------------------------------------------------------ 13
h1("14. Every file explained")
table([["File / folder", "What it is"],
       ["rtl/top_module.v", "connects cache, prefetch engine and DRAM; run-time settings pf_mode (0 base, 1 next-line, 2 stride, 3 final), adaptive, degree, insertion"],
       ["rtl/cache_controller.v", "demand FSM, MSHR table, prefetch probe/filter, arbitration, performance counters"],
       ["rtl/tag_array.v, cache_memory.v", "tag/valid/prefetched storage (3 read ports) and data storage"],
       ["rtl/replacement_policy.v", "true LRU with MRU or LRU insertion"],
       ["rtl/stride_predictor.v", "stream table, confidence, triggers, adaptive degree, accuracy flag, hybrid quick start"],
       ["rtl/prefetch_engine.v", "candidate generator (page-bounded), duplicate filter, 8-entry queue"],
       ["rtl/memory_model.v", "DRAM simulation model (not part of the design)"],
       ["testbench/tb_system.v", "CPU model reading a trace + all self-checks; prints RESULT line and TEST PASSED/FAILED"],
       ["testbench/cocotb/test_cache.py", "the 7 Cocotb tests"],
       ["python/generate_traces.py", "makes the 9 workloads + demo trace"],
       ["python/analyze_traces.py", "locality/stride statistics and access-pattern plot"],
       ["python/ref_cache_model.py", "golden Python LRU cache"],
       ["python/run_all.py", "compiles RTL, runs 54 simulations, golden check, computes all metrics"],
       ["python/verilator_crosscheck.py", "re-runs everything on Verilator and compares"],
       ["python/run_cocotb.py", "runs the Cocotb tests"],
       ["python/visualize_results.py, evaluate_results.py", "plots and report tables (Matplotlib, Pandas)"],
       ["synth/", "Yosys synthesis scripts, block diagrams, gate counts"],
       ["results/", "performance_summary.csv, comparison.txt, logs, plots, lint, cross-check, Cocotb results"],
       ["docs/", "architecture.md, algorithm.md, final_report.md, this guide"],
       ["run_all.sh", "one command that reproduces everything"]],
      [5.5, 11])
story.append(PageBreak())

# ------------------------------------------------------------------ 14
h1("15. How to run everything")
p("In Ubuntu (WSL), with the tools installed as described in README.md:")
code("""cd ~/micron_cache_prefetch
bash run_all.sh                 # traces, lint, 54 sims, Verilator check, Cocotb, plots (~1 min)

# look at the key lines again
grep -E "PASSED|MATCH" results/regression_log.txt
cat results/verilator_crosscheck.txt | tail -1
grep TESTS results/cocotb_log.txt

# one single run (mode 0 = baseline, 3 = final design)
iverilog -g2005 -o simulation/build/sim.vvp testbench/tb_system.v rtl/*.v
vvp -n simulation/build/sim.vvp +trace=traces/llm.trace +mode=0
vvp -n simulation/build/sim.vvp +trace=traces/llm.trace +mode=3 +adaptive=1 +degree=2 +inslru=1

# pictures and waveform
explorer.exe "$(wslpath -w results/plots/speedup.png)"
gtkwave simulation/waveforms/demo_final.vcd simulation/waveforms/demo.gtkw &

# hardware view
cd synth && bash run_synth.sh""")
p("Reading a RESULT line: <i>hits, misses</i> = CPU loads; <i>dem_mem</i> = DRAM requests caused by misses; "
  "<i>pf_issued</i> = prefetches sent; <i>pf_useful</i> = used on time; <i>pf_late</i> = used while still travelling; "
  "<i>cycles</i> = total run time; <i>errors</i> must be 0.")

# ------------------------------------------------------------------ 15
h1("16. Demo script for the judges (about 5 minutes)")
table([["Step", "Show", "Say"],
       ["1", "slide 1 / section 1 of this guide", "AI waits for memory; we built a cache that guesses and fetches early"],
       ["2", "bash run_all.sh running", "54 simulations, golden model match, identical on two simulators, 7 Cocotb tests"],
       ["3", "speedup.png", f"{GM_ALL:.2f}x average, {GM_AI:.2f}x on AI-like workloads, never slower"],
       ["4", "GTKWave demo_final.vcd", "prefetches fire between CPU loads; demand always first; later loads hit in 1 cycle"],
       ["5", "section 8", "three adaptive ideas driven by one accuracy monitor"],
       ["6", "synthesis table", "prefetcher is under 5 % of the hardware"],
       ["7", "limitations", "synthetic traces, read-only cache - we say it openly"]],
      [1.2, 5, 10.3])
story.append(PageBreak())

# ------------------------------------------------------------------ 16
h1("17. Questions judges may ask (with answers)")
qa = [
 ("Why did you choose 4-way set associative?", "It removes most conflict misses between interleaved AI streams while needing only 4 tag comparators. Fully associative would need 256."),
 ("How do you know your results are not just a simulator effect?", "The same testbench gives identical numbers on two different simulators (Icarus and Verilator), and the baseline matches an independent Python model exactly."),
 ("How does the prefetcher avoid slowing down normal loads?", "Demand requests always win the DRAM port, one MSHR is always kept for the CPU, and fills never happen in the same cycle as a CPU lookup. The Cocotb test shows an unrelated miss still takes the normal 42 cycles with 3 prefetches in flight."),
 ("What happens on random data?", "Confidence never builds, and the quick-start is switched off by the accuracy gate, so only 32 prefetches are issued over 4000 random loads; speed is unchanged."),
 ("What is a late prefetch, and is it bad?", "The CPU asked while the line was still on its way. It is counted as a miss, but the CPU waits only the remaining time and no second DRAM request is sent, so it still helps."),
 ("Where does the prefetcher lose?", "It costs extra DRAM traffic on CNN and recsys (about 1.4-1.8x), and the adaptive insertion costs 3.8 % on the mixed trace. Both are shown in the results."),
 ("Why no program counter (PC) in the predictor?", "Our traces contain only addresses, so streams are separated by address region (1 KB window). A PC-indexed table is listed as future work."),
 ("Is this real hardware?", "Yes: synthesizable Verilog, lint clean, and it synthesizes with Yosys to about 99k gates. We do not claim area or clock speed because no real chip library was used."),
 ("Is it really 'AI-aware'?", "It adapts to the kind of traffic it sees: long regular streams (CNN/LLM) push it to run further ahead, short irregular bursts (recommenders) and stream jumps (new CNN rows) trigger the quick start, poor accuracy makes it cautious. The traces are synthetic models of these patterns, not real model runs."),
 ("How long did it take to run everything?", "The whole flow (traces, 54 simulations, Verilator check, Cocotb, plots) runs in under a minute."),
]
for q, a in qa:
    story.append(KeepTogether([Paragraph(f"<b>Q: {q}</b>", P), Paragraph(f"A: {a}", B), Spacer(1, 3)]))

# ------------------------------------------------------------------ 17
h1("18. Limitations and future work")
table([["Limitation", "Future improvement"],
       ["synthetic traces, not real AI programs", "replay traces captured from real model runs"],
       ["read-only cache (no stores)", "add write-back with dirty bits"],
       ["one cache level, CPU with one outstanding load", "multi-level hierarchy, out-of-order CPU model"],
       ["streams matched by address region", "PC-indexed stride table"],
       ["simple fixed-latency DRAM", "banks, rows and refresh"],
       ["generic-gate synthesis only", "SRAM macros + OpenROAD for real area, timing and placement"],
       ["global accuracy for all streams", "per-stream accuracy and degree"]], [8, 8.5])
story.append(PageBreak())

# ------------------------------------------------------------------ 18
h1("19. Glossary")
gl = [("AMAT", "average memory access time = hit time + miss rate x miss penalty"),
      ("Bandwidth", "how many requests DRAM can accept per unit of time"),
      ("Cache line", "the 16-byte block the cache moves at once"),
      ("Cocotb", "a Python library for writing hardware tests"),
      ("Confidence", "how sure the predictor is about a stream's stride (0-3)"),
      ("Coverage", "share of baseline misses removed by prefetching"),
      ("Degree", "how many lines ahead the prefetcher fetches (1-7, adaptive)"),
      ("Demand access", "a load the CPU actually asked for (not a prefetch)"),
      ("DRAM", "main memory: large but slow"),
      ("FSM", "finite-state machine: hardware that moves between states (IDLE, MISS_REQ, WAIT)"),
      ("Golden model", "an independent reference implementation used to check the hardware"),
      ("GTKWave", "a viewer for signal waveforms"),
      ("Hit / miss", "data found / not found in the cache"),
      ("Icarus Verilog", "free Verilog simulator (main simulator here)"),
      ("Index / tag", "address bits that choose the set / identify the block"),
      ("Late prefetch", "the CPU asked while the prefetched line was still on its way"),
      ("Lint", "automatic check of code for suspicious constructs"),
      ("LRU", "least recently used - the line evicted when a set is full"),
      ("MSHR", "register that tracks one request still waiting for DRAM"),
      ("Prefetch", "fetching data into the cache before it is asked for"),
      ("RTL", "register-transfer level: the hardware description in Verilog"),
      ("Set / way", "a group of slots chosen by the index / one slot in that group"),
      ("Stride", "the constant step between addresses of a stream"),
      ("Synthesis", "turning Verilog into logic gates (Yosys)"),
      ("Trace", "a list of memory addresses a program reads, used as test input"),
      ("Verilator", "a second, very fast Verilog simulator and lint tool"),
      ("Yosys", "free synthesis tool")]
table([["Term", "Meaning"]] + [[a, b] for a, b in gl], [3.5, 13])


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(2 * cm, 1.2 * cm, "AI-Aware Cache & Prefetch Engine - learning guide")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"page {doc.page}")
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                        bottomMargin=2 * cm, title="AI-Aware Cache & Prefetch Engine - Learning Guide",
                        author="Kotapati Kishore")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("written", OUT)
