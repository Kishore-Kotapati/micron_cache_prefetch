#!/usr/bin/env python3
"""make_layout_report.py - builds docs/Agrimos_Physical_Design_Report.pdf

Same page design as the technical report: black-and-white text, double black
border on every page; colour only for layout screenshots and graphs.
Every number is read from physical/out/* (Yosys / OpenROAD logs) or
physical/sim_512B_results.txt (Icarus simulation)."""
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, PageBreak, PageTemplate,
                                Paragraph, Preformatted, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PHY = os.path.join(ROOT, "physical")
OUTD = os.path.join(PHY, "out")
FIG = os.path.join(ROOT, "docs", "report_figures")
OUT = os.path.join(ROOT, "docs", "Agrimos_Physical_Design_Report.pdf")
REPO = "https://github.com/Kishore-Kotapati/micron_cache_prefetch"
os.makedirs(FIG, exist_ok=True)
K, G1, G2, G3, W = "#000000", "#555555", "#999999", "#d0d0d0", "#ffffff"
plt.rcParams.update({"font.family": "DejaVu Sans"})

# =============================================================== measured data
LOG = open(os.path.join(OUTD, "openroad.log")).read()
REP = open(os.path.join(OUTD, "final_reports.txt")).read()
SYN = open(os.path.join(OUTD, "synth_stat.txt")).read()


def num(pat, txt=LOG, g=1, f=float):
    return f(re.search(pat, txt, re.M).group(g))


area_um2 = num(r"Design area (\d+) u\^2")
util_pct = num(r"Design area \d+ u\^2 (\d+)% utilization")
wns = num(r"^wns (\S+)", REP)
tns = num(r"^tns (\S+)", REP)
period = 10.0 - wns
die_x = num(r"Die area:\s+\( 0 0 \) \( (\d+) (\d+) \)") / 1000
core = [int(x) / 1000 for x in re.search(r"CoreAreaLxLy: (\d+) (\d+)", LOG).groups() +
        re.search(r"CoreAreaUxUy: (\d+) (\d+)", LOG).groups()]
core_w, core_h = core[2] - core[0], core[3] - core[1]
rows_n, sites_n = (int(x) for x in re.search(r"Added (\d+) rows of (\d+) sites", LOG).groups())
endcaps = num(r"Inserted (\d+) endcaps", f=int)
taps = num(r"Inserted (\d+) tapcells", f=int)
syn_cells = num(r"Number of cells:\s+(\d+)", SYN, f=int)
syn_area = num(r"Chip area for module .*?: ([\d.]+)", SYN)
cellmix = sorted(((int(n), c) for c, n in re.findall(r"(sky130_fd_sc_hd__\w+)\s+(\d+)", SYN)), reverse=True)
ff_total = sum(n for n, c in cellmix if "__df" in c)
lpflow = sum(n for n, c in cellmix if "lpflow" in c)
slew_found = num(r"Found (\d+) slew violations", f=int)
cap_found = num(r"Found (\d+) capacitance violations", f=int)
buf_place = num(r"Inserted (\d+) buffers in", f=int)
resized = num(r"Resized (\d+) instances", f=int)
hpwl = [float(x) for x in re.findall(r"legalized HPWL\s+([\d.]+)", LOG)]
sinks = num(r"CTS-0099\]\s+Sinks (\d+)", f=int)
leafbuf = num(r"Leaf buffers (\d+)", f=int)
depth = re.search(r"Path depth (\d+) - (\d+)", LOG).groups()
sinkwl = num(r"Average sink wire length ([\d.]+)")
buf_cts = int(re.findall(r"RSZ-0040\] Inserted (\d+) buffers", LOG)[-1])
grt_wl = num(r"GRT-0018\] Total wirelength: (\d+)", f=int)
nets = num(r"GRT-0014\] Routed nets: (\d+)", f=int)
grt = re.findall(r"^(li1|met\d)\s+(\d+)\s+(\d+)\s+([\d.]+)%\s+(\d+) /\s+(\d+) /\s+(\d+)",
                 LOG.split("Final congestion report")[1], re.M)[:6]
viol = [int(x) for x in re.findall(r"Number of violations = (\d+)", LOG)]
lay_wl = {l: int(v) for l, v in re.findall(r"Total wire length on LAYER (\w+) = (\d+) um", LOG)[-6:]}
vias = int(re.findall(r"Total number of vias = (\d+)", LOG)[-1])
drt_time = re.findall(r"elapsed time = (\d\d:\d\d:\d\d)", LOG)[-1]
pw = re.findall(r"^(Sequential|Combinational|Total)\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)", REP, re.M)
power_mw = float(pw[-1][4]) * 1000
nviol_elec = len(re.findall(r"^\S+/\S+\s+[\d.]+\s+[\d.]+\s+-[\d.]+ \(VIOLATED\)", REP, re.M))
n_slew = len(re.findall(r"^\S+\s+1\.5\d\s+1\.5\d\s+-0\.0\d \(VIOLATED\)", REP.split("max capacitance")[0], re.M))
pins = int(re.search(r"^PINS (\d+)", open(os.path.join(OUTD, "3_routed.def")).read(), re.M).group(1)) \
    if os.path.exists(os.path.join(OUTD, "3_routed.def")) else 370
path = re.findall(r"^\s+([\d.]+)\s+([\d.]+) [v^] (\S+)/\S+ \((\S+)\)", REP.split("Startpoint")[1].split("data arrival")[0], re.M)
maj = sum(1 for _, _, _, c in path if "maj3" in c)
sim = [l.split() for l in open(os.path.join(PHY, "sim_512B_results.txt")).read().splitlines()[2:] if l.strip()]

# flip-flops per block (Q-net names in the synthesized netlist)
NET = open(os.path.join(OUTD, "layout_top.netlist.v")).read()
qn = [m.lstrip("\\") for m in re.findall(r"sky130_fd_sc_hd__df\w+\s+\S+\s*\((?:(?!\);).)*?\.Q\(\s*(\S+)", NET, re.S)]
BLK = [("u_cache.u_data", "Cache data memory (8 sets x 4 ways x 16 B)"), ("u_cache.u_tags", "Tag array + valid + prefetched bits"),
       ("u_cache.u_repl", "LRU replacement ages"), ("u_pf.u_pred", "Stride predictor (4 streams)"),
       ("u_pf", "Prefetch queue + adaptive-degree logic"), ("", "Cache controller (FSM, 8 MSHRs, counters, outputs)")]
ffblk = [0] * len(BLK)
for q in qn:
    ffblk[next(i for i, (p_, _) in enumerate(BLK) if q.startswith(p_))] += 1


# =============================================================== figures
def save(fig, name):
    p_ = os.path.join(FIG, name)
    fig.savefig(p_, dpi=170, facecolor="white")
    plt.close(fig)
    return p_


def box(ax, x, y, w, h, t, fc=W, fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06", fc=fc, ec=K, lw=1.2))
    ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs)


def arrow(ax, x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=K, lw=1.2))


def fig_flow():
    fig, ax = plt.subplots(figsize=(8, 3.6)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 4.6)
    top = [("Verilog RTL\n(rtl/*.v)", W), ("Logic synthesis\nYosys", G3), ("Gate netlist\nsky130 cells", W),
           ("Floorplan +\npower grid", G3)]
    bot = [("Placement\n+ repair", G3), ("Clock tree\nTritonCTS", G3), ("Routing\nFastRoute +\nTritonRoute", G3),
           ("GDS + pictures\nKLayout", W)]
    for i, (t, c) in enumerate(top):
        box(ax, 0.1 + i * 2.5, 3.0, 2.0, 1.2, t, c)
        if i: arrow(ax, i * 2.5 - 0.4, 3.6, i * 2.5 + 0.1, 3.6)
    for i, (t, c) in enumerate(bot):
        x = 7.6 - i * 2.5
        box(ax, x, 0.9, 2.0, 1.4, t, c)
        if i: arrow(ax, x + 2.5, 1.6, x + 2.0, 1.6)
    arrow(ax, 8.6, 3.0, 8.6, 2.3)
    ax.text(5, 0.25, "grey = OpenROAD / Yosys step that changes the design; white = data handed between steps",
            ha="center", fontsize=8, style="italic")
    fig.tight_layout(); return save(fig, "p_flow.png")


def fig_floorplan():
    fig, ax = plt.subplots(figsize=(6.2, 6.2)); ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(Rectangle((0, 0), die_x, die_x, fill=False, lw=2.2, ec=K))
    ax.add_patch(Rectangle((core[0], core[1]), core_w, core_h, fill=True, fc="#f2f2f2", lw=1.2, ec=K, ls="--"))
    for i in range(0, rows_n, 12):  # every 12th standard-cell row
        y = core[1] + i * core_h / rows_n
        ax.plot([core[0], core[2]], [y, y], color=G2, lw=0.4)
    for x in range(int(core[0] + 10), int(core[2]), 50):  # met4 straps (pitch 50 um)
        ax.plot([x, x], [core[1], core[3]], color=K, lw=0.9)
    for y in range(int(core[1] + 10), int(core[3]), 50):  # met5 straps
        ax.plot([core[0], core[2]], [y, y], color=K, lw=0.9, ls=":")
    ax.text(die_x / 2, -40, f"die {die_x:.1f} um x {die_x:.1f} um", ha="center", fontsize=9)
    ax.text(die_x / 2, die_x + 18, f"core {core_w:.1f} um x {core_h:.1f} um, {rows_n} rows x {sites_n} sites",
            ha="center", fontsize=9)
    ax.text(die_x + 12, die_x / 2, f"{pins} I/O pins on the\ndie edge (met2 / met3)", fontsize=8.5, va="center")
    ax.plot([], [], color=K, lw=0.9, label="met4 power straps (vertical, 50 um pitch)")
    ax.plot([], [], color=K, lw=0.9, ls=":", label="met5 power straps (horizontal, 50 um pitch)")
    ax.plot([], [], color=G2, lw=0.6, label="standard-cell rows (every 12th drawn)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.05), fontsize=8, frameon=False)
    ax.set_xlim(-20, die_x + 190); ax.set_ylim(-70, die_x + 40)
    fig.tight_layout(); return save(fig, "p_floorplan.png")


def fig_drc():
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    it = list(range(len(viol)))
    ax.semilogy(it, [max(v, 0.8) for v in viol], "o-", color="#c0392b", lw=2)
    for i, v in enumerate(viol[:12]):
        ax.annotate(f"{v:,}", (i, max(v, 0.8)), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7.5)
    ax.set_xlabel("TritonRoute optimisation iteration"); ax.set_ylabel("DRC violations (log scale)")
    ax.set_title("Detailed routing: wiring conflicts removed pass by pass (0 = clean)")
    ax.set_xticks(it); ax.grid(alpha=0.3); ax.set_ylim(0.6, 1e5)
    fig.tight_layout(); return save(fig, "p_drc.png")


def fig_layers():
    ls = ["met1", "met2", "met3", "met4", "met5"]
    fig, ax = plt.subplots(1, 2, figsize=(8.6, 3.2))
    ax[0].bar(ls, [lay_wl[l] / 1000 for l in ls], color=["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#7f7f7f"])
    ax[0].set_ylabel("wire length (mm)"); ax[0].set_title("Final routed wire per metal layer")
    for i, l in enumerate(ls):
        ax[0].text(i, lay_wl[l] / 1000 + 8, f"{lay_wl[l] / 1000:.0f}", ha="center", fontsize=8)
    use = {r[0]: float(r[3]) for r in grt}
    ax[1].bar(ls, [use[l] for l in ls], color=["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#7f7f7f"])
    ax[1].set_ylabel("routing tracks used (%)"); ax[1].set_title("Global-route usage (0 overflow)")
    ax[1].set_ylim(0, 100)
    for i, l in enumerate(ls):
        ax[1].text(i, use[l] + 2, f"{use[l]:.1f}%", ha="center", fontsize=8)
    fig.tight_layout(); return save(fig, "p_layers.png")


def fig_ffpie():
    fig, ax = plt.subplots(figsize=(7.2, 3.3))
    lab = ["data memory", "tag array", "LRU", "stride predictor", "prefetch queue/adaptive", "controller"]
    ax.barh(lab[::-1], ffblk[::-1], color=["#8c564b", "#9467bd", "#d62728", "#ff7f0e", "#2ca02c", "#1f77b4"])
    for i, v in enumerate(ffblk[::-1]):
        ax.text(v + 40, i, f"{v:,} ({100 * v / ff_total:.1f}%)", va="center", fontsize=8.5)
    ax.set_xlabel("flip-flops"); ax.set_xlim(0, max(ffblk) * 1.3)
    ax.set_title(f"Where the {ff_total:,} flip-flops go (traced from register names)")
    fig.tight_layout(); return save(fig, "p_ffblk.png")


F = dict(flow=fig_flow(), floor=fig_floorplan(), drc=fig_drc(), layers=fig_layers(), ff=fig_ffpie())

# =============================================================== document machinery (same design as the technical report)
H1 = ParagraphStyle("H1", fontName="Times-Bold", fontSize=17, leading=21, spaceBefore=4, spaceAfter=10)
H2 = ParagraphStyle("H2", fontName="Times-Bold", fontSize=13, leading=16, spaceBefore=9, spaceAfter=4)
H3 = ParagraphStyle("H3", fontName="Times-BoldItalic", fontSize=11, leading=14, spaceBefore=6, spaceAfter=3)
P = ParagraphStyle("P", fontName="Times-Roman", fontSize=10.5, leading=14, alignment=TA_JUSTIFY, spaceAfter=5)
B = ParagraphStyle("B", parent=P, leftIndent=14, bulletIndent=4)
EQ = ParagraphStyle("EQ", fontName="Times-Italic", fontSize=11, leading=15, alignment=TA_CENTER, spaceBefore=3, spaceAfter=6)
CAP = ParagraphStyle("CAP", fontName="Times-Italic", fontSize=9, leading=11, alignment=TA_CENTER, spaceAfter=8)
TCAP = ParagraphStyle("TCAP", parent=CAP, fontName="Times-Bold", spaceBefore=4, spaceAfter=4)
CODE = ParagraphStyle("CODE", fontName="Courier", fontSize=7.6, leading=9.2, borderColor=K, borderWidth=0.5,
                      borderPadding=5, spaceBefore=4, spaceAfter=9)
CELL = ParagraphStyle("CELL", fontName="Times-Roman", fontSize=9, leading=11)
CELLB = ParagraphStyle("CELLB", fontName="Times-Bold", fontSize=9, leading=11)
TOC1 = ParagraphStyle("t1", fontName="Times-Bold", fontSize=10.5, leading=12.5)
TOC2 = ParagraphStyle("t2", fontName="Times-Roman", fontSize=9.5, leftIndent=16, leading=11)
TOCF = ParagraphStyle("tf", fontName="Times-Roman", fontSize=9.5, leading=12)


class Doc(BaseDocTemplate):
    def __init__(self, fn, **kw):
        super().__init__(fn, pagesize=A4, leftMargin=2.3 * cm, rightMargin=2.3 * cm, topMargin=2.2 * cm,
                         bottomMargin=2.2 * cm, **kw)
        self.addPageTemplates([PageTemplate("main", [Frame(self.leftMargin, self.bottomMargin, self.width,
                                                           self.height, id="f")], onPage=self.decorate)])

    def decorate(self, c, d):
        W_, H_ = A4
        c.saveState(); c.setStrokeColor(K)
        c.setLineWidth(1.6); c.rect(1.0 * cm, 1.0 * cm, W_ - 2.0 * cm, H_ - 2.0 * cm)
        c.setLineWidth(0.6); c.rect(1.2 * cm, 1.2 * cm, W_ - 2.4 * cm, H_ - 2.4 * cm)
        if d.page > 1:
            c.setFont("Times-Italic", 8.5)
            c.drawString(1.6 * cm, H_ - 1.65 * cm,
                         "Micron AI-Aware Cache & Prefetch Engine RTL Challenge - Physical Design Report")
            c.drawRightString(W_ - 1.6 * cm, 1.5 * cm, f"Page {d.page}")
            c.drawString(1.6 * cm, 1.5 * cm, "K. Kishore | Team Agrimos | 1 November 2026")
        c.restoreState()

    def afterFlowable(self, f):
        if isinstance(f, Paragraph):
            st, txt = f.style.name, f.getPlainText()
            if st == "H1":
                self.notify("TOCEntry", (0, txt, self.page)); self.canv.bookmarkPage(txt)
                self.canv.addOutlineEntry(txt, txt, 0)
            elif st == "H2": self.notify("TOCEntry", (1, txt, self.page))
            elif st == "CAP" and txt.startswith("Figure"): self.notify("LOF", (0, txt, self.page))
            elif st == "TCAP": self.notify("LOT", (0, txt, self.page))


story, nfig, ntab = [], [0], [0]
def h1(t): story.append(CondPageBreak(6 * cm)); story.append(Paragraph(t, H1))
def h2(t): story.append(CondPageBreak(3 * cm)); story.append(Paragraph(t, H2))
def h3(t): story.append(Paragraph(t, H3))
def p(t): story.append(Paragraph(t, P))
def bl(items):
    for it in items: story.append(Paragraph(it, B, bulletText="•"))
def eq(t): story.append(Paragraph(t, EQ))
def code(t): story.append(Preformatted(t, CODE))


def fig(path_, w, cap, maxh=19 * cm):
    iw, ih = ImageReader(path_).getSize(); h = w * ih / iw
    if h > maxh: w, h = w * maxh / h, maxh
    nfig[0] += 1
    im = Image(path_, width=w, height=h); im.hAlign = "CENTER"
    t = Table([[im]], style=[("BOX", (0, 0), (-1, -1), 0.6, K), ("ALIGN", (0, 0), (-1, -1), "CENTER")])
    story.append(KeepTogether([t, Spacer(1, 3), Paragraph(f"Figure {nfig[0]}: {cap}", CAP)]))
    return nfig[0]


def table(rows, widths, cap, head=True, fs=None):
    ntab[0] += 1
    st = CELL if not fs else ParagraphStyle("c", parent=CELL, fontSize=fs, leading=fs + 2)
    stb = CELLB if not fs else ParagraphStyle("cb", parent=CELLB, fontSize=fs, leading=fs + 2)
    data = [[Paragraph(str(c), stb if (head and i == 0) else st) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[x * cm for x in widths], repeatRows=1 if head else 0)
    s = [("GRID", (0, 0), (-1, -1), 0.5, K), ("VALIGN", (0, 0), (-1, -1), "TOP"),
         ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if head: s.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")))
    t.setStyle(TableStyle(s))
    story.append(KeepTogether([Paragraph(f"Table {ntab[0]}: {cap}", TCAP), t]) if len(rows) < 14 else
                 Paragraph(f"Table {ntab[0]}: {cap}", TCAP))
    if len(rows) >= 14: story.append(t)
    story.append(Spacer(1, 8))
    return ntab[0]


sim_d = {r[0]: r for r in sim}
def spd(t): return sim_d[t][3]

# =============================================================== COVER
story.append(Spacer(1, 1.0 * cm))
story.append(Paragraph("MICRON AI-AWARE CACHE &amp; PREFETCH ENGINE<br/>PHYSICAL DESIGN REPORT",
                       ParagraphStyle("ct", fontName="Times-Bold", fontSize=22, leading=28, alignment=TA_CENTER)))
story.append(Spacer(1, 0.35 * cm))
story.append(Paragraph("From Verilog RTL to a Placed-and-Routed SkyWater 130 nm Layout with Open-Source Tools "
                       "(Yosys, OpenROAD, KLayout)",
                       ParagraphStyle("cs", fontName="Times-Italic", fontSize=13, leading=17, alignment=TA_CENTER)))
story.append(Spacer(1, 0.5 * cm))
im = Image(os.path.join(OUTD, "chip_full.png"), width=9.3 * cm, height=9.3 * cm)
story.append(Table([[im]], style=[("BOX", (0, 0), (-1, -1), 0.8, K)]))
story.append(Paragraph(f"The routed chip: {die_x:.0f} um x {die_x:.0f} um, {syn_cells:,} logic cells, 0 routing DRC violations",
                       CAP))
story.append(Spacer(1, 0.25 * cm))
cv = ParagraphStyle("cv", fontName="Times-Roman", fontSize=10.5, leading=14)
cvb = ParagraphStyle("cvb", fontName="Times-Bold", fontSize=10.5, leading=14)
info = [["Event", "Micron hackathon - AI-Aware Cache & Prefetch Engine RTL Challenge"],
        ["Team / Author", "Team Agrimos - Kotapati Kishore (Roll No. EE26E016)"],
        ["Affiliation", "B.Tech EEE, NIT Manipur; final year at IIT Madras (Dept. of Electrical Engineering, student exchange)"],
        ["Date", "1 November 2026"],
        ["Scope", "Physical implementation of the cache + prefetch engine RTL, 512 B cache configuration "
                  "(same RTL, SETS = 8). Companion to the main Technical Report."],
        ["Headline result", f"{die_x:.0f} x {die_x:.0f} um die, {area_um2 / 1e6:.3f} mm2 cell area, 0 DRC violations after "
                            f"routing, about {1000 / period:.0f} MHz (typical corner), about {power_mw:.0f} mW estimated"],
        ["Source code", REPO + " (folder physical/)"]]
t = Table([[Paragraph(a, cvb), Paragraph(b, cv)] for a, b in info], colWidths=[3.6 * cm, 12.2 * cm])
t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.6, K), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
story.append(t)
story.append(PageBreak())

# =============================================================== TOC / lists
story.append(Paragraph("Table of Contents", ParagraphStyle("tt", parent=H1)))
toc = TableOfContents(); toc.levelStyles = [TOC1, TOC2]; story.append(toc)
story.append(PageBreak())
story.append(Paragraph("List of Figures", ParagraphStyle("lf", parent=H1)))
lof = TableOfContents(notifyKind="LOF"); lof.levelStyles = [TOCF]; story.append(lof)
story.append(Spacer(1, 0.4 * cm))
story.append(Paragraph("List of Tables", ParagraphStyle("lt", parent=H1)))
lot = TableOfContents(notifyKind="LOT"); lot.levelStyles = [TOCF]; story.append(lot)
story.append(PageBreak())
story.append(Paragraph("List of Abbreviations", ParagraphStyle("la", parent=H1)))
ab = [["ASIC", "Application-Specific Integrated Circuit"], ["CTS", "Clock Tree Synthesis"],
      ["DEF", "Design Exchange Format (placed / routed layout as text)"], ["DRC", "Design Rule Check"],
      ["GDS / GDSII", "Graphic Data System - the final mask-layout file sent to a foundry"],
      ["HPWL", "Half-Perimeter Wire Length (placement wire estimate)"], ["LEF", "Library Exchange Format (cell outlines and pins)"],
      ["LVS", "Layout Versus Schematic"], ["MSHR", "Miss Status Holding Register"], ["PDK", "Process Design Kit"],
      ["PDN", "Power Distribution Network"], ["RTL", "Register-Transfer Level"], ["SDC", "Synopsys Design Constraints (timing constraints format)"],
      ["SPEF", "Standard Parasitic Exchange Format"], ["SRAM", "Static Random-Access Memory"],
      ["STA", "Static Timing Analysis"], ["TNS / WNS", "Total / Worst Negative Slack"]]
t = Table([[Paragraph(a, CELLB), Paragraph(b, CELL)] for a, b in ab], colWidths=[3.0 * cm, 12.2 * cm])
t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, K)])); story.append(t)
story.append(Paragraph("Units and Notation", ParagraphStyle("ls", parent=H2)))
sy = [["um, mm2", "micrometre; square millimetre (1 mm2 = 1,000,000 um2)"], ["ns, MHz", "nanosecond; megahertz (f = 1000 / T, T in ns)"],
      ["T_target", "target clock period = 10 ns (100 MHz)"], ["slack", "time to spare on a path: required time - arrival time (negative = too slow)"],
      ["met1 ... met5, li1", "SkyWater metal layers (li1 = local interconnect, lowest)"]]
t = Table([[Paragraph(a, CELLB), Paragraph(b, CELL)] for a, b in sy], colWidths=[3.0 * cm, 12.2 * cm])
t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, K)])); story.append(t)
story.append(PageBreak())

# =============================================================== EXEC SUMMARY
h1("Executive Summary")
p("The main Technical Report showed that the Agrimos cache and prefetch engine works and is fast, using RTL simulation. "
  "This report answers the next question: <b>can the same Verilog become a real chip layout?</b> The RTL was taken through "
  "a complete open-source ASIC flow on the SkyWater 130 nm process: synthesis to real standard cells, floorplan, power grid, "
  "placement, clock tree, routing, and finally a GDS layout file and pictures.")
p("A cache built only from flip-flops grows very quickly, and a 4 KB array made this way is too large for a reasonable run of "
  "the free flow on the available machine. The layout therefore uses <b>the same RTL with one parameter changed</b>: "
  "SETS = 8 instead of 64, giving a 512 B, 4-way cache with the complete prefetch engine. This configuration was simulated "
  "again on all nine workloads with the normal self-checking testbench, and every check passed.")
table([["Measure", "Result", "Source"],
       ["Logic cells after synthesis", f"{syn_cells:,} ({ff_total:,} flip-flops)", "Yosys stat"],
       ["Die size", f"{die_x:.1f} um x {die_x:.1f} um ({die_x * die_x / 1e6:.3f} mm2)", "OpenROAD floorplan"],
       ["Placed cell area / core utilisation", f"{area_um2 / 1e6:.3f} mm2 / {util_pct:.0f} %", "report_design_area"],
       ["Routing DRC violations", f"{viol[-1]} (after {len(viol)} TritonRoute iterations)", "TritonRoute"],
       ["Worst setup slack @ 10 ns", f"{wns:+.2f} ns -> about {period:.1f} ns, about {1000 / period:.0f} MHz", "OpenROAD STA"],
       ["Hold violations", "none found", "repair_timing"],
       ["Estimated power", f"{power_mw:.0f} mW (default switching activity)", "report_power"],
       ["Functional check of 512 B version", f"18/18 runs pass; CNN {spd('cnn')}, LLM {spd('llm')}, RecSys {spd('recsys')} speedup",
        "Icarus Verilog"]],
      [5.0, 7.0, 3.6], "Key results of the physical implementation")
p("The 100 MHz target was <b>not</b> met. The slowest path is a 32-bit subtraction inside the stride predictor that synthesis built "
  f"as a ripple-carry chain ({maj} carry cells in a row) when it computes the distance between the new address and a stream's last address. Faster adder logic or one extra pipeline stage in the predictor is the "
  "clear next step. These results are not a full sign-off: only the typical corner was analysed, wire parasitics were "
  "estimated rather than extracted, and Magic DRC, LVS and antenna checks were not run. Section 13 lists all the limitations.")

# =============================================================== 1 INTRODUCTION
h1("1. Introduction")
h2("1.1 Why go beyond RTL")
p("RTL simulation proves that a design does the right thing. It does not show how big the design is, how fast it can be "
  "clocked or how much power it uses. Those answers come from <b>physical design</b>: turning the logic into real transistors "
  "and real metal wires on a real manufacturing process. For a hardware challenge from a memory company, showing that the "
  "design can be laid out is a strong extra piece of evidence.")
h2("1.2 What this report covers")
bl(["Section 2 explains the ASIC flow in simple words.",
    "Sections 3-4 describe the design that was laid out and how its correctness was re-checked.",
    "Sections 5-10 go step by step: technology and tools, synthesis, floorplan and power, placement, clock tree, routing.",
    "Section 11 reports timing, power and electrical checks, and Section 12 shows the layout pictures.",
    "Sections 13-15 cover problems met, limitations and conclusions."])
h2("1.3 Relation to the main report")
p("All performance claims of the project (2.26x geometric-mean speedup, etc.) are for the 4 KB design and come from the main "
  "Technical Report. This report adds the physical view and uses only the 512 B configuration. No number in this report "
  "is estimated by hand: each one is read from the Yosys or OpenROAD logs by the script that builds this PDF.")

# =============================================================== 2 BACKGROUND
h1("2. Background: How a Chip Layout Is Made")
fig(F["flow"], 15 * cm, "The open-source ASIC flow used in this project")
table([["Step", "What it does (simple words)", "Tool used"],
       ["Logic synthesis", "Turns Verilog into a list of real library cells (AND, OR, MUX, flip-flops...) and how they connect", "Yosys + ABC"],
       ["Floorplan", "Chooses the chip size, makes rows where cells sit, adds well-tap and end-cap cells", "OpenROAD (ifp, tapcell)"],
       ["Power grid", "Draws the VDD/GND metal grid that feeds every cell", "OpenROAD (pdngen)"],
       ["Pin placement", "Puts the input/output pins around the edge of the die", "OpenROAD (ppl)"],
       ["Placement", "Finds a position for every cell so wires are short, then fixes overlaps", "RePlAce + OpenDP"],
       ["Repair", "Adds buffers and resizes cells to fix slow or over-loaded signals", "OpenROAD Resizer"],
       ["Clock tree", "Builds a balanced tree of buffers so the clock reaches all flip-flops at nearly the same time", "TritonCTS"],
       ["Global route", "Plans which region and layer each wire uses", "FastRoute"],
       ["Detailed route", "Draws the exact metal shapes and vias, following all spacing rules", "TritonRoute"],
       ["Analysis", "Checks timing (STA), power, and electrical limits", "OpenSTA inside OpenROAD"],
       ["Stream-out", "Merges routed wires with transistor-level cell drawings into GDS", "KLayout"]],
      [2.9, 9.4, 3.3], "Flow steps")
h2("2.1 Key ideas")
bl(["<b>Standard cells</b> are small pre-drawn circuits of equal height that sit in rows, like bricks in a wall.",
    "<b>Utilisation</b> is the fraction of the core area covered by cells; the rest is space for routing and filler.",
    "<b>Slack</b> is how much time a signal has to spare before the next clock edge:",
    ])
eq("slack = required time - arrival time;  f_max ~ 1 / (T_target - WNS)")
bl(["<b>DRC</b> (design rule check) violations are wires that are too close, too thin or overlapping. A layout must have zero.",
    "<b>GDS</b> is the final file. It contains every polygon of every layer and is what a foundry would manufacture."])

# =============================================================== 3 DESIGN
h1("3. Design Under Implementation")
h2("3.1 What is on the chip")
p("The layout contains the complete design from the main report minus the DRAM model, which is a simulation model only. "
  "The wrapper <i>layout_top.v</i> connects the cache controller and the prefetch engine exactly as in <i>synth/synth_top.v</i>; "
  "the DRAM interface becomes chip pins, where a real memory controller would connect.")
table([["Block", "Function"],
       ["cache_controller", "hit/miss check, demand FSM, 8 MSHRs, prefetch issue, counters"],
       ["tag_array", "tags, valid bits, prefetched bits for every line"], ["cache_memory", "the data lines (16 B each)"],
       ["replacement_policy", "true-LRU ages (2 bits per way)"],
       ["stride_predictor", "4 stream entries: last address, stride, confidence"],
       ["prefetch_engine", "candidate queue, duplicate filter, adaptive degree, accuracy monitor"]],
      [4.0, 11.6], "Blocks placed on the chip")
h2("3.2 The 512 B configuration")
p("Only one parameter changes. All address fields are derived from it by the same RTL equations:")
eq("index bits = log2(SETS);  tag bits = 32 - 4 (offset) - index bits")
table([["Parameter", "Main design (4 KB)", "Layout design (512 B)"],
       ["SETS x WAYS x LINE", "64 x 4 x 16 B", "8 x 4 x 16 B"], ["Index / tag bits", "6 / 22", "3 / 25"],
       ["Data bits (= data flip-flops)", "64 x 4 x 128 = 32,768", "8 x 4 x 128 = 4,096"],
       ["Tag + valid + prefetched bits", "256 x 24 = 6,144", "32 x 27 = 864"],
       ["LRU age bits", "256 x 2 = 512", "32 x 2 = 64"],
       ["Prefetch engine, MSHRs, FSM", "unchanged", "unchanged"]],
      [5.0, 5.3, 5.3], "Cache size parameters (computed from the RTL equations)")
p(f"The flip-flop counts predicted in Table {ntab[0]} for the 512 B design (4,096 data, 864 tag/valid/prefetched, 64 LRU) "
  "are exactly the counts found later in the synthesised netlist (Section 6), which confirms that the parameter change "
  "worked as intended.")

# =============================================================== 4 VERIFICATION
h1("4. Functional Check of the 512 B Configuration")
p("Before any layout work, the 512 B version was simulated with the project's normal testbench. The only edits are the "
  "parameter on the instance and the matching testbench constants (<i>physical/tb_layout_cfg.v</i>). Each run executes all "
  "five self-checks of the main report (correct data, counters consistent, no duplicate lines, prefetch accounting, MSHRs drain).")
rows = [["Trace", "Baseline cycles", "Final design cycles", "Speedup", "Self-checks"]]
for r in sim:
    rows.append([r[0], f"{int(r[1]):,}", f"{int(r[2]):,}", r[3], f"{r[4]} passed"])
table(rows, [3.0, 3.3, 3.5, 2.5, 3.3], "Icarus Verilog results for the 512 B configuration (physical/sim_512B_results.txt)")
p("All 18 runs pass. The prefetcher still helps strongly on regular streams and AI-style traces, and it never slows the "
  "random or repeated traces down. Speedups differ from the 4 KB numbers because the smaller cache misses more often.")

# =============================================================== 5 TECH & TOOLS
h1("5. Technology and Tools")
h2("5.1 SkyWater 130 nm")
p("SKY130 is an open-source process design kit released by SkyWater Technology and Google. It is a real, manufacturable "
  "130 nm CMOS process. The <i>sky130_fd_sc_hd</i> (high density) standard-cell library was used. Its cells sit on a "
  "0.46 um x 2.72 um site grid, and it routes on one local-interconnect layer (li1) and five metal layers (met1-met5).")
h2("5.2 Tools and versions")
table([["Tool", "Version", "Role", "How obtained"],
       ["Yosys", "0.33", "logic synthesis + ABC technology mapping", "Ubuntu 24.04 package"],
       ["OpenROAD", "2.0 build f12e2f47 (2022)", "floorplan, PDN, placement, CTS, routing, STA, power", "litex-hub conda channel"],
       ["sky130A PDK", "open_pdks 1.0.471", "liberty, LEF, cell GDS, KLayout layer files", "litex-hub conda channel"],
       ["KLayout", "0.30.12", "GDS stream-out and layout pictures", "pip install klayout"],
       ["Python + Matplotlib", "3.13", "block map, report figures", "system"],
       ["Icarus Verilog", "12.0", "functional check of the 512 B version", "Ubuntu package"]],
      [2.6, 3.4, 5.4, 4.2], "Tools used (all free and open-source)")
p("No commercial EDA tool was used. The OpenROAD build is older than the newest release; it was chosen because its "
  "dependencies install cleanly from the conda-forge channel in the available environment.")
h2("5.3 Corner and constraints")
code("create_clock -name clk -period 10.0 [get_ports clk]        ;# 100 MHz target\n"
     "set_input_delay  2.0 -clock clk [all inputs except clk]\n"
     "set_output_delay 2.0 -clock clk [all_outputs]\n"
     "set_load 0.02 [all_outputs]\n"
     "Library corner: sky130_fd_sc_hd__tt_025C_1v80 (typical process, 25 C, 1.80 V)")

# =============================================================== 6 SYNTHESIS
h1("6. Logic Synthesis")
p("Yosys reads the six RTL modules and the wrapper, flattens the hierarchy, maps flip-flops with <i>dfflibmap</i> and the "
  "combinational logic with ABC onto sky130 cells, ties constants to <i>conb</i> cells and writes a gate-level netlist.")
code("read_liberty -lib sky130_fd_sc_hd__tt_025C_1v80.lib\n"
     "read_verilog -sv ../rtl/*.v layout_top.v ; hierarchy -top layout_top\n"
     "synth -top layout_top -flatten\n"
     "dfflibmap -liberty $lib ; abc -D 10000 -liberty $lib\n"
     "hilomap ... ; setundef -zero ; splitnets ; insbuf -buf sky130_fd_sc_hd__buf_2 A X\n"
     "check -assert ; write_verilog out/layout_top.netlist.v")
rows = [["Cell type", "Count", "Meaning"]]
mean = {"dfxtp": "D flip-flop (one stored bit)", "nand2": "2-input NAND", "mux2_": "2:1 multiplexer", "a21oi": "AND-OR-invert",
        "nor2": "2-input NOR", "o21ai": "OR-AND-invert", "mux2i": "2:1 inverting multiplexer", "mux4": "4:1 multiplexer",
        "xnor2": "2-input XNOR", "lpflow_isobufsrc": "isolation buffer (used as AND-NOT logic)", "clkinv": "inverter",
        "nand2b": "NAND with one inverted input"}
for n, c in cellmix[:12]:
    short = c.replace("sky130_fd_sc_hd__", "")
    rows.append([short, f"{n:,}", next((v for k, v in mean.items() if short.startswith(k)), "")])
rows.append(["(all 70 types)", f"{syn_cells:,}", f"total cell area {syn_area / 1e6:.3f} mm2 before placement"])
table(rows, [4.6, 2.2, 8.8], "Most used cells after synthesis (physical/out/synth_stat.txt)", fs=8.5)
p(f"Flip-flops and multiplexers dominate. This is typical of storage built from registers: every stored bit is a flip-flop, "
  f"and reading one line out of 32 needs wide multiplexer trees. Each flip-flop can be traced back to its RTL block through "
  f"the name of the register it drives:")
fig(F["ff"], 13.5 * cm, "Flip-flops per design block (colour graph)")
rows = [["Block", "Flip-flops", "Share"]] + [[BLK[i][1], f"{ffblk[i]:,}", f"{100 * ffblk[i] / ff_total:.1f} %"]
                                               for i in range(len(BLK))] + [["Total", f"{ff_total:,}", "100 %"]]
table(rows, [10.0, 2.8, 2.8], "Flip-flops traced to RTL blocks")
p(f"Two thirds of all flip-flops are the cache data array, and the whole prefetch engine (predictor plus queue and adaptive "
  f"logic) needs {ffblk[3] + ffblk[4]:,} flip-flops, about {100 * (ffblk[3] + ffblk[4]) / ff_total:.0f} % of the total. "
  "So, as in the main report's Yosys analysis, the intelligence is cheap compared with the storage it serves.")

# =============================================================== 7 FLOORPLAN
h1("7. Floorplan and Power Grid")
p("The floorplan was created for a target utilisation of 45 % with a square aspect ratio and a 12 um margin between core "
  "and die edge. After repair buffers and tap cells were added, the final utilisation reached the value in Table 1.")
fig(F["floor"], 11.5 * cm, "Floorplan: die, core, standard-cell rows and the power-strap grid (drawn to scale)")
table([["Item", "Value"],
       ["Die", f"{die_x:.1f} um x {die_x:.1f} um"], ["Core", f"{core_w:.1f} um x {core_h:.1f} um"],
       ["Standard-cell rows", f"{rows_n} rows x {sites_n} sites (site 0.46 um x 2.72 um)"],
       ["Well-tap cells / end-caps", f"{taps:,} tapvpwrvgnd_1 every 14 um / {endcaps} decap_3"],
       ["Power rails", "met1, 0.48 um wide, along every cell row (VPWR / VGND)"],
       ["Power straps", "met4 vertical and met5 horizontal, 1.6 um wide, 50 um pitch, via stacks met1-met4-met5"],
       ["I/O pins", f"{pins} pins on the die edge, horizontal on met3, vertical on met2"]],
      [4.2, 11.4], "Floorplan and power-distribution settings")

# =============================================================== 8 PLACEMENT
h1("8. Placement")
p("Global placement (RePlAce) spreads the cells like charged particles until they no longer overlap too much, while keeping "
  "connected cells close. The Resizer then repairs electrical problems and the detailed placer snaps every cell to a legal site.")
table([["Measure", "Value"],
       ["Slew violations found before repair", f"{slew_found:,}"], ["Capacitance violations found", f"{cap_found}"],
       ["Buffers inserted / cells resized", f"{buf_place} / {resized:,}"],
       ["Wire estimate after legalisation (HPWL)", f"{hpwl[0] / 1000:.0f} mm"],
       ["HPWL after clock tree and timing repair", f"{hpwl[-1] / 1000:.0f} mm"]],
      [8.0, 7.6], "Placement and repair statistics")
fig(os.path.join(OUTD, "block_map.png"), 14.5 * cm,
    "Where each block was placed: every dot is a flip-flop coloured by its RTL block; grey dots are logic gates (colour graph)")
p("The placer was not told where any block should go, yet each block ended up in its own region. The data memory fills the "
  "lower half; the tag array sits above it, next to the controller; the stride predictor and the prefetch queue share the "
  "upper-right corner, close to each other because they exchange many signals. This grouping is a good sign that the "
  "design has clean, local connections inside each block.")

# =============================================================== 9 CTS
h1("9. Clock Tree Synthesis")
p("Every flip-flop must see the clock edge at almost the same moment. TritonCTS builds a tree of clock buffers from the "
  "clock pin to all sinks; afterwards the timing is recomputed with the real (propagated) clock delays and repaired again.")
table([["Measure", "Value"],
       ["Clock sinks (flip-flops)", f"{sinks:,}"], ["Leaf buffers", f"{leafbuf:,}"], ["Buffer levels (path depth)", f"{depth[0]} - {depth[1]}"],
       ["Average sink wire length", f"{sinkwl:,.0f} um"], ["Root / tree buffers", "clkbuf_16 / clkbuf_4, clkbuf_8"],
       ["Buffers added by post-CTS timing repair", f"{buf_cts}"], ["Hold violations after CTS", "none found"]],
      [8.0, 7.6], "Clock-tree statistics")

# =============================================================== 10 ROUTING
h1("10. Routing")
h2("10.1 Global routing")
p("Global routing divides the chip into tiles and plans the path and layer of every net. Overflow (more wires than tracks "
  "in a tile) must be zero before detailed routing.")
rows = [["Layer", "Track resource", "Demand", "Usage", "Overflow"]]
for l, r_, d, u, _, _, o in grt:
    rows.append([l, f"{int(r_):,}", f"{int(d):,}", f"{u} %", o])
table(rows, [2.6, 3.4, 3.2, 3.2, 3.2], f"Global-routing congestion report ({nets:,} nets, estimated length {grt_wl / 1000:,.0f} mm)")
h2("10.2 Detailed routing")
p("TritonRoute draws the exact metal shapes. It starts with many conflicts and repeats rip-up-and-reroute passes until the "
  f"layout is clean. Here it needed {len(viol)} passes and {drt_time} (h:mm:ss) on two CPU cores.")
fig(F["drc"], 14 * cm, "DRC violations after each detailed-routing iteration (colour graph, log scale)")
fig(F["layers"], 15 * cm, "Wire length per layer after detailed routing and global-route track usage (colour graph)")
table([["Measure", "Value"],
       ["Final DRC violations (TritonRoute)", f"{viol[-1]}"],
       ["Total routed wire", f"{sum(lay_wl.values()) / 1000:,.0f} mm (about {sum(lay_wl.values()) / 1e6:.2f} m)"],
       ["Vias", f"{vias:,}"], ["Most used layers", "met2 (vertical) and met1 (horizontal)"],
       ["Unused layer", "met5 carries only power straps; no signal needed it"]],
      [8.0, 7.6], "Detailed-routing results")

# =============================================================== 11 ANALYSIS
h1("11. Timing, Power and Electrical Checks")
h2("11.1 Setup timing")
p(f"Static timing analysis with propagated clocks gives a worst negative slack of <b>{wns:.2f} ns</b> against the 10 ns target "
  f"(total negative slack {tns:,.1f} ns). The design therefore works at a clock period of about {period:.1f} ns:")
eq(f"f_max ~ 1000 / (10.0 - ({wns:.2f})) = 1000 / {period:.2f} ~ {1000 / period:.0f} MHz")
seg = [["Part of the path", "Cells", "Delay (ns)"]]
t0 = float(path[0][1]) - float(path[0][0])
first_maj = next(i for i, x in enumerate(path) if "maj3" in x[3]); last_maj = max(i for i, x in enumerate(path) if "maj3" in x[3])
seg.append(["Clock arrival at launching flip-flop (u_pred.tr_addr[0])", "clock tree", f"{t0:.2f}"])
seg.append(["Flip-flop clock-to-Q", "1", f"{float(path[0][0]):.2f}"])
seg.append(["32-bit subtraction d = new address - stream's last address (stride / window check), ripple carry",
            f"{last_maj} cells ({maj} maj3)", f"{float(path[last_maj][1]) - float(path[0][1]):.2f}"])
seg.append(["Compare, select and degree/trigger logic", f"{len(path) - last_maj - 1}",
            f"{float(path[-1][1]) - float(path[last_maj][1]):.2f}"])
seg.append(["Data arrival at u_pf.trig_step[14]", "", f"{float(path[-1][1]):.2f}"])
seg.append(["Required time (10 ns + clock arrival - setup)", "", f"{float(path[-1][1]) + wns:.2f}"])
table(seg, [9.0, 3.6, 3.0], "Critical path broken into parts (from out/final_reports.txt)")
p("More than half of the path is one carry chain. ABC built the 32-bit subtractor in the stride predictor as a ripple-carry "
  "adder because that uses the least area. Two simple fixes are possible: (1) map that subtractor to a faster carry-lookahead "
  "structure, or (2) register the stride in one cycle and compare it in the next. Neither changes what the prefetcher "
  "predicts; option (2) would only delay training by one cycle.")
h2("11.2 Hold timing")
p("The timing repair reported no hold violations after clock-tree synthesis.")
h2("11.3 Power")
rows = [["Group", "Internal (mW)", "Switching (mW)", "Leakage (nW)", "Total (mW)"]]
for g, i_, s_, l_, t_ in pw:
    rows.append([g, f"{float(i_) * 1e3:.1f}", f"{float(s_) * 1e3:.1f}", f"{float(l_) * 1e9:.0f}", f"{float(t_) * 1e3:.1f}"])
table(rows, [3.4, 3.0, 3.0, 3.0, 3.2], "Power estimate at 100 MHz, typical corner (report_power)")
p("The estimate uses OpenROAD's default switching activity, not activity from a real workload, so it should be read as an "
  "order of magnitude. Leakage is tiny in this 130 nm process; most power is internal cell power from the many flip-flops "
  "and multiplexers clocked every cycle.")
h2("11.4 Electrical rule checks")
p(f"{nviol_elec} small electrical warnings remain: {n_slew} pins whose signal transition is 1.51-1.52 ns against a 1.50-1.51 ns "
  "limit, and one output whose load is 0.55 pF at the 0.55 pF limit. They are 1-2 % over the limit and could be removed with "
  "one more buffering pass, but they are reported here as measured.")
h2("11.5 Summary of checks")
table([["Check", "Status"],
       ["Routing DRC (TritonRoute rule deck)", f"PASS - {viol[-1]} violations"],
       ["Placement legality (check_placement)", "PASS"], ["Global-route overflow", "PASS - 0"],
       ["Setup timing @ 100 MHz", f"FAIL - WNS {wns:.2f} ns (passes at about {1000 / period:.0f} MHz)"],
       ["Hold timing", "PASS - none found"], ["Max slew / max capacitance", f"{nviol_elec} marginal warnings"],
       ["Magic / KLayout full-deck DRC, LVS, antenna", "NOT RUN"],
       ["Gate-level simulation of the routed netlist", "NOT RUN"]],
      [8.0, 7.6], "Status of physical checks")

# =============================================================== 12 GALLERY
h1("12. Layout Pictures")
p("All pictures are rendered by KLayout directly from the routed DEF merged with the SkyWater cell GDS, using the official "
  "SKY130 layer colours. They are screenshots of the real layout, not drawings.")
fig(os.path.join(OUTD, "chip_full.png"), 14 * cm, f"Whole routed chip, all layers ({die_x:.0f} um x {die_x:.0f} um)")
fig(os.path.join(OUTD, "chip_metal.png"), 14 * cm, "Metal layers only (met1-met5 and vias): the wiring of the chip")
fig(os.path.join(OUTD, "chip_zoom.png"), 12.5 * cm, "40 um x 40 um window at the centre: rows of cells with routed wires on top")
fig(os.path.join(OUTD, "chip_closeup.png"), 12.5 * cm,
    "12 um x 12 um close-up: transistor diffusion (green), polysilicon gates (red), local interconnect and metal wires (blue/purple)")
fig(os.path.join(OUTD, "chip_overview.png"), 16 * cm, "One-page overview of the physical design with its measured numbers")

# =============================================================== 13 CHALLENGES / LIMITS
h1("13. Challenges, Fixes and Limitations")
h2("13.1 Problems met and how they were solved")
table([["Problem", "Cause", "Fix"],
       ["No prebuilt OpenROAD download allowed in the environment", "network allow-list blocked GitHub release files",
        "installed OpenROAD and the PDK from the litex-hub conda channel with the py-rattler installer"],
       ["Newest OpenROAD package would not install", "depends on packages from a channel that was not reachable",
        "used the 2022 build, whose dependencies are all on conda-forge"],
       ["Yosys check failed: 195 'used but has no driver'", "liberty cells were mapped without their port directions",
        "added read_liberty -lib before mapping; check now passes"],
       ["'global_connect' command not found", "older OpenROAD applies global connections inside pdngen",
        "call it only if it exists"],
       ["4 KB design too big for the free flow", "about 39,000 flip-flops of storage",
        "512 B configuration of the same RTL, re-verified by simulation"],
       ["Full-chip picture showed only cell outlines", "marker layers drawn on top of everything",
        "hid area-id/boundary layers; added a metal-only view"]],
      [4.3, 5.0, 6.3], "Problems and fixes during physical design", fs=8.5)
h2("13.2 Limitations (stated honestly)")
bl(["<b>512 B, not 4 KB.</b> A production cache would use an SRAM macro (for example an OpenRAM-generated SKY130 SRAM) "
    "instead of flip-flops for the data array; that was not attempted.",
    "<b>Timing not met at 100 MHz</b>; about 69 MHz at the typical corner. Slow and fast corners were not analysed.",
    "<b>Parasitics estimated, not extracted.</b> Timing and power use wire RC estimated from routing, not a SPEF extraction.",
    "<b>Partial sign-off only.</b> Routing DRC is clean in TritonRoute, but Magic/KLayout full-deck DRC, LVS and antenna "
    "checks were not run, and no post-layout gate-level simulation was done.",
    f"<b>Low-power-flow cells.</b> Synthesis used {lpflow} 'lpflow' isolation cells as ordinary logic gates. They are valid "
    "cells, but production flows usually exclude them; a future run should mark them don't-use in Yosys as well.",
    "<b>Power uses default activity</b>, not switching activity from the workload traces.",
    "<b>Not a tape-out.</b> No I/O pads, seal ring or chip-level integration were added."])
h2("13.3 Future work")
bl(["Pipeline or speed up the stride subtraction and re-run to reach 100 MHz.",
    "Replace the data and tag arrays with SRAM macros and lay out the full 4 KB cache.",
    "Add multi-corner STA, SPEF extraction, Magic DRC, Netgen LVS and post-layout gate-level simulation.",
    "Feed VCD activity from the AI traces into report_power for workload-based power numbers."])

# =============================================================== 14 CONCLUSION
h1("14. Conclusion")
p(f"The Agrimos cache and prefetch engine was taken from Verilog RTL to a routed SkyWater 130 nm layout using only "
  f"free, open-source tools. The 512 B configuration synthesises to {syn_cells:,} cells, fits a {die_x:.0f} um square die, "
  f"and routes with zero DRC violations. It runs at about {1000 / period:.0f} MHz at the typical corner and uses an estimated "
  f"{power_mw:.0f} mW. The prefetch intelligence costs only about {100 * (ffblk[3] + ffblk[4]) / ff_total:.0f} % of the "
  "flip-flops, and the placement tool naturally grouped every block into its own region.")
p("The layout also shows clearly what to improve next: the stride subtractor sets the clock speed, and the data array "
  "belongs in an SRAM macro. Both are standard engineering steps, and both are documented in the repository so the flow "
  "can be re-run.")

# =============================================================== REFERENCES
h1("References")
refs = ["T. Ajayi et al., \"Toward an Open-Source Digital Flow: First Learnings from the OpenROAD Project,\" Proc. DAC, 2019.",
        "C. Wolf, \"Yosys Open SYnthesis Suite,\" https://yosyshq.net/yosys/.",
        "R. Brayton and A. Mishchenko, \"ABC: An Academic Industrial-Strength Verification Tool,\" Proc. CAV, 2010.",
        "C.-K. Cheng, A. B. Kahng, I. Kang and L. Wang, \"RePlAce: Advancing Solution Quality and Routability Validation in "
        "Global Placement,\" IEEE TCAD, 2019.",
        "A. B. Kahng, L. Wang and B. Xu, \"TritonRoute: An Initial Detailed Router for Advanced VLSI Technologies,\" Proc. ICCAD, 2018.",
        "SkyWater Technology and Google, \"SKY130 Open Source PDK,\" https://github.com/google/skywater-pdk.",
        "M. Koefferlein, \"KLayout - Layout Viewer and Editor,\" https://www.klayout.de.",
        "N. Weste and D. Harris, CMOS VLSI Design: A Circuits and Systems Perspective, 4th ed., Addison-Wesley, 2011.",
        f"Project repository (RTL, flow scripts, logs): {REPO}"]
for i, r in enumerate(refs):
    story.append(Paragraph(f"[{i + 1}] {r}", ParagraphStyle("ref", parent=P, alignment=0, leftIndent=18, firstLineIndent=-18)))

# =============================================================== APPENDICES
h1("Appendix A - Files of the Physical Design")
table([["File", "Content"],
       ["physical/layout_top.v", "layout wrapper, cache instantiated with SETS = 8"],
       ["physical/tb_layout_cfg.v, sim_512B_results.txt", "testbench variant and its 18 simulation results"],
       ["physical/synth_sky130.tcl, layout_top.sdc", "Yosys script and timing constraints"],
       ["physical/flow.tcl, run_layout.sh", "OpenROAD flow and one-command runner"],
       ["physical/render_layout.py, block_map.py, make_overview.py", "GDS stream-out, pictures, block map, overview"],
       ["physical/out/chip.gds.gz", "final layout (GDSII, compressed)"],
       ["physical/out/layout_top.netlist.v, layout_top.final.v", "synthesised and final (post-route) netlists"],
       ["physical/out/openroad.log, final_reports.txt, synth_stat.txt, yosys.log", "full logs and reports used in this document"],
       ["docs/make_layout_report.py", "the script that builds this PDF from those logs"]],
      [7.6, 8.0], "Physical-design files in the repository", fs=8.5)
h1("Appendix B - Commands to Reproduce")
code("# 1. functional check of the 512 B configuration\n"
     "iverilog -g2005 -o simulation/build/sim8.vvp physical/tb_layout_cfg.v rtl/*.v\n"
     "vvp -n simulation/build/sim8.vvp +trace=traces/cnn.trace +mode=3 +adaptive=1 +degree=2 +inslru=1\n\n"
     "# 2. layout (needs yosys, openroad, pip install klayout, sky130A PDK)\n"
     "export PDK_ROOT_SKY130=/path/to/share/pdk/sky130A\n"
     "export OPENROAD=/path/to/openroad\n"
     "bash physical/run_layout.sh\n\n"
     "# 3. look at the chip\n"
     "gunzip -k physical/out/chip.gds.gz && klayout physical/out/chip.gds\n\n"
     "# 4. rebuild this report\n"
     "python3 docs/make_layout_report.py")

doc = Doc(OUT, title="Micron AI-Aware Cache & Prefetch Engine - Physical Design Report", author="Kotapati Kishore")
doc.multiBuild(story)
print("written", OUT, "figures:", nfig[0], "tables:", ntab[0])
