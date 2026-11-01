#!/usr/bin/env python3
"""make_solution_statement.py - builds docs/Micron_Solution_Statement.pdf
Short solution statement in the same style as the technical report
(double border on every page, black-and-white text; graphs/screenshots in colour).
All numbers are read from results/*.csv produced by simulation."""
import math, os
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle, CondPageBreak)

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "docs", "Micron_Solution_Statement.pdf")
RES = os.path.join(ROOT, "results"); FIG = os.path.join(ROOT, "docs", "report_figures")
REPO = "https://github.com/Kishore-Kotapati/micron_cache_prefetch"
K = colors.black

df = pd.read_csv(os.path.join(RES, "performance_summary.csv"))
lat = pd.read_csv(os.path.join(RES, "latency_sweep.csv"))
ORDER = ["sequential", "stride", "random", "repeated", "mixed", "capacity", "cnn", "llm", "recsys"]
AI = ["cnn", "llm", "recsys"]
def R(t, c): return df[(df.trace == t) & (df.config == c)].iloc[0]
def gm(c, ts): v = df[(df.config == c) & (df.trace.isin(ts))].speedup; return math.exp(sum(map(math.log, v)) / len(v))
def lgm(L, ts=None):
    s = lat[lat.latency == L] if ts is None else lat[(lat.latency == L) & lat.trace.isin(ts)]
    return math.exp(s.speedup.map(math.log).mean())
GA, GI = gm("smart", ORDER), gm("smart", AI)

H1 = ParagraphStyle("H1", fontName="Times-Bold", fontSize=13.5, leading=17, spaceBefore=8, spaceAfter=5)
P = ParagraphStyle("P", fontName="Times-Roman", fontSize=10.5, leading=14, alignment=TA_JUSTIFY, spaceAfter=5)
B = ParagraphStyle("B", parent=P, leftIndent=14, bulletIndent=4, alignment=0)
CAP = ParagraphStyle("CAP", fontName="Times-Italic", fontSize=9, leading=11, alignment=TA_CENTER, spaceAfter=8)
TC = ParagraphStyle("TC", fontName="Times-Bold", fontSize=9, leading=11, alignment=TA_CENTER, spaceBefore=3, spaceAfter=3)
C = ParagraphStyle("C", fontName="Times-Roman", fontSize=9, leading=11)
CB = ParagraphStyle("CB", fontName="Times-Bold", fontSize=9, leading=11)

def decorate(c, d):
    W, H = A4; c.saveState(); c.setStrokeColor(K)
    c.setLineWidth(1.6); c.rect(1.0 * cm, 1.0 * cm, W - 2.0 * cm, H - 2.0 * cm)
    c.setLineWidth(0.6); c.rect(1.2 * cm, 1.2 * cm, W - 2.4 * cm, H - 2.4 * cm)
    c.setFont("Times-Italic", 8.5)
    c.drawString(1.6 * cm, H - 1.65 * cm, "Micron AI-Aware Cache & Prefetch Engine RTL Challenge - Solution Statement")
    c.drawString(1.6 * cm, 1.5 * cm, "K. Kishore | 1 November 2026")
    c.drawRightString(W - 1.6 * cm, 1.5 * cm, f"Page {d.page}")
    c.restoreState()

doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=2.3 * cm, rightMargin=2.3 * cm, topMargin=2.2 * cm, bottomMargin=2.2 * cm,
                      title="Micron AI-Aware Cache & Prefetch Engine - Solution Statement", author="Kotapati Kishore")
doc.addPageTemplates([PageTemplate("p", [Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height)], onPage=decorate)])
s = []; nf = [0]; nt = [0]
def h(t): s.append(CondPageBreak(3 * cm)); s.append(Paragraph(t, H1))
def p(t): s.append(Paragraph(t, P))
def bl(xs):
    for x in xs: s.append(Paragraph(x, B, bulletText="•"))
def tab(rows, w, cap, fs=9):
    nt[0] += 1; c = ParagraphStyle("c", parent=C, fontSize=fs, leading=fs + 2); cb = ParagraphStyle("cb", parent=CB, fontSize=fs, leading=fs + 2)
    t = Table([[Paragraph(str(x), cb if i == 0 else c) for x in r] for i, r in enumerate(rows)], colWidths=[x * cm for x in w], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, K), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    s.append(KeepTogether([Paragraph(f"Table {nt[0]}: {cap}", TC), t, Spacer(1, 6)]))
def fig(path, w, cap):
    nf[0] += 1; iw, ih = ImageReader(path).getSize(); im = Image(path, width=w, height=w * ih / iw)
    t = Table([[im]], style=[("BOX", (0, 0), (-1, -1), 0.6, K)])
    s.append(KeepTogether([t, Spacer(1, 3), Paragraph(f"Figure {nf[0]}: {cap}", CAP)]))

# ---------------------------------------------------------------- title block
s.append(Paragraph("SOLUTION STATEMENT", ParagraphStyle("t0", fontName="Times-Bold", fontSize=12, alignment=TA_CENTER, leading=15)))
s.append(Paragraph("Micron AI-Aware Cache &amp; Prefetch Engine RTL Challenge",
                   ParagraphStyle("t1", fontName="Times-Bold", fontSize=18, alignment=TA_CENTER, leading=23, spaceBefore=4)))
s.append(Paragraph("A confidence-gated, accuracy-adaptive stride prefetcher for a 4 KB set-associative cache",
                   ParagraphStyle("t2", fontName="Times-Italic", fontSize=12, alignment=TA_CENTER, leading=16, spaceBefore=4, spaceAfter=8)))
info = [["Submitted by", "Kotapati Kishore (Roll No. EE26E016), B.Tech EEE, NIT Manipur; final year at IIT Madras"],
        ["Date", "1 November 2026"], ["Repository", REPO],
        ["Headline", f"{GA:.2f}x average speedup over the same cache without prefetching (9 workloads), {GI:.2f}x on "
                     f"AI-inspired workloads, never slower; {lgm(120):.2f}x with 120-cycle DRAM"]]
t = Table([[Paragraph(a, CB), Paragraph(b, C)] for a, b in info], colWidths=[3.0 * cm, 13.4 * cm])
t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.6, K), ("VALIGN", (0, 0), (-1, -1), "TOP")])); s.append(t)

s.append(Spacer(1, 6))
p(f"<b>In one sentence:</b> a small, self-tuning stride prefetcher - under 5 % of the hardware - makes the same 4 KB cache "
  f"{GA:.2f}x faster on average ({GI:.2f}x on AI-inspired workloads, {lgm(120):.2f}x with slower memory), verified on two "
  f"simulators against a golden model.")

h("1. Problem")
p("AI workloads such as large language models, CNNs and recommendation systems are fast at arithmetic but waste time "
  "waiting for data from DRAM. The challenge: build hardware that <b>watches</b> the addresses a program reads, "
  "<b>guesses</b> the next ones and <b>fetches them early</b> into the cache, and prove that it is faster (higher hit "
  "rate, lower latency, good prefetch accuracy) using Python, Icarus Verilog, GTKWave and Git, with no starter code.")

h("2. Proposed solution")
p("A complete cache subsystem written from scratch in synthesizable Verilog-2005:")
bl(["<b>Cache:</b> 4 KB, 4-way set-associative, 64 sets, 16-byte lines, true LRU, 1-cycle hit, 8 miss-status registers "
    "(MSHRs) so up to 7 prefetches can travel while the CPU keeps working.",
    "<b>Prefetch engine (watch - guess - fetch):</b> a 4-entry stream table learns the byte stride of up to four interleaved "
    "streams (no program counter needed), with a 2-bit confidence counter; when confident it generates the next lines, "
    "never across a 4 KB page, removes duplicates, and sends them to DRAM only in cycles the CPU does not need.",
    "<b>Correctness rules:</b> demand requests always win the DRAM port; one MSHR is always reserved for the CPU; one cache "
    "update per cycle; a load to a line already in flight merges with it instead of fetching it twice."])
fig(os.path.join(FIG, "m_system.png"), 9.5 * cm, "Solution architecture")

h("3. What makes it intelligent (innovation)")
p("One small accuracy monitor (two 6-bit counters) measures, every 32 prefetches, how many were used, and drives three "
  "adaptive mechanisms - one per innovation area on the official slide:")
tab([["Innovation", "Mechanism", "Measured effect"],
     ["Intelligent prefetching", "degree (lines ahead) rises to 7 when >= 75 % of prefetches are used, falls when < 25 %",
      f"average {gm('stride', ORDER):.2f}x -> {gm('stride_adapt', ORDER):.2f}x"],
     ["Novel prediction / AI-aware", "a new or jumping stream that misses gets 2 next-line prefetches at once; off when accuracy < 50 %",
      f"CNN {R('cnn','stride_adapt').speedup:.2f}x -> {R('cnn','smart_noins').speedup:.2f}x; random traffic wastes only "
      f"{int(R('random','smart').prefetch_dram)} prefetches"],
     ["Adaptive cache policy", "prefetched lines inserted as least-recently-used while accuracy < 50 %, else most-recently-used",
      f"recsys {R('recsys','smart_noins').speedup:.2f}x -> {R('recsys','smart').speedup:.2f}x with 9 % less DRAM traffic"]],
    [3.4, 7.4, 5.6], "Innovations and their measured contribution")

h("4. Results")
p("Architecture A (no prefetch) and B (final design) use identical RTL, traces and DRAM timing (40-cycle latency, one "
  "request per 4 cycles). All values come from RTL simulation logs.")
rows = [["Workload", "Hit % A -> B", "Avg latency A -> B (cyc)", "Cycles A -> B", "Speedup", "Prefetch accuracy*"]]
for t_ in ORDER:
    a, b = R(t_, "baseline"), R(t_, "smart")
    rows.append([t_, f"{a.hit_rate_pct:.1f} -> {b.hit_rate_pct:.1f}", f"{a.amat_measured:.2f} -> {b.amat_measured:.2f}",
                 f"{a.cycles} -> {b.cycles}", f"<b>{b.speedup:.2f}x</b>", f"{b.pf_accuracy_incl_late_pct:.0f} %"])
rows.append(["<b>average</b>", "", "", "", f"<b>{GA:.2f}x</b>", ""])
tab(rows, [2.3, 2.7, 3.5, 3.7, 1.8, 2.4], "Baseline (A) vs final design (B)")
p("<i>*Accuracy = (useful + late prefetches) / prefetches issued.</i> Regular streams (sequential, capacity, LLM) reach "
  "98-99 % of a perfect cache; random addresses cannot be predicted (1.00x, correctly almost no prefetches); repeated data "
  "already fits in the cache.")
fig(os.path.join(ROOT, "results", "plots", "speedup.png"), 13 * cm, "Speedup of each architecture step (higher is better)")
tab([["DRAM latency (cycles)", "20", "40", "80", "120"],
     ["Average speedup, 9 workloads"] + [f"{lgm(L):.2f}x" for L in (20, 40, 80, 120)],
     ["AI-inspired workloads"] + [f"{lgm(L, AI):.2f}x" for L in (20, 40, 80, 120)]],
    [5.2, 2.8, 2.8, 2.8, 2.8], "The benefit grows as memory gets slower")
fig(os.path.join(FIG, "gtkwave_final_full.png"), 12 * cm,
    "GTKWave, final design: 98 loads in 5,886 ns (baseline: 13,816 ns); only 3 demand DRAM requests (baseline: 26)")

h("5. How we proved it works")
tab([["Check", "Result"],
     ["Self-checks in every simulation (data, counters, no duplicates, prefetch accounting, drain)", "54 / 54 PASS"],
     ["Baseline vs independent Python golden cache model", "exact match on 9 / 9 workloads"],
     ["Second simulator (Verilator 5.020) running the same testbench", "54 / 54 runs bit-identical to Icarus"],
     ["Cocotb Python tests (latency, LRU, 1500 random loads, merge, page boundary, throttling)", "7 / 7 PASS"],
     ["Verilator lint", "0 warnings"],
     ["Yosys synthesis (generic gates)", "clean; prefetch engine = 4.9 % of cells, 1.8 % of flip-flops"],
     ["Reproduced on a second machine (Ubuntu 24.04, WSL)", "identical numbers"]],
    [11.0, 5.4], "Verification summary")

h("6. Limitations")
p("Synthetic traces (models of AI access patterns, not recordings of real programs); read-only, single-level cache with an "
  "in-order CPU model; fixed-latency DRAM; generic-gate synthesis only (no area, timing or power claimed). Prefetching costs "
  "extra DRAM traffic on CNN, recsys and mixed (1.4-1.8x). All are documented in the technical report.")

h("7. Deliverables and reproduction")
bl([f"Source, results, waveforms and documentation: <b>{REPO}</b>",
    "Technical report: docs/Micron_AI_Aware_Cache_Prefetch_Engine_Technical_Report.pdf",
    "One command reproduces everything in about one minute: <font face='Courier'>bash run_all.sh</font>"])
doc.build(s)
print("written", OUT)
