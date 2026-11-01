#!/usr/bin/env python3
"""render_layout.py - DEF (from OpenROAD) + sky130 cell GDS  ->  chip GDS + PNG pictures.

Uses the free KLayout Python module (pip install klayout).
usage: python3 render_layout.py <stage.def> <out_prefix> [--gds]
"""
import os
import sys

import klayout.db as db
import klayout.lay as lay

PDK = os.environ.get("PDK_ROOT_SKY130", "/home/claude/eda/pdk/share/pdk/sky130A")
REF = f"{PDK}/libs.ref/sky130_fd_sc_hd"
TECH = f"{PDK}/libs.tech/klayout/tech"


def load(def_file):
    opts = db.LoadLayoutOptions()
    c = opts.lefdef_config
    c.lef_files = [f"{REF}/techlef/sky130_fd_sc_hd__nom.tlef", f"{REF}/lef/sky130_fd_sc_hd.lef"]
    c.macro_layout_files = [f"{REF}/gds/sky130_fd_sc_hd.gds"]   # real transistor-level cell drawings
    c.map_file = f"{TECH}/sky130A.map"
    c.read_lef_with_def = False
    ly = db.Layout()
    ly.read(def_file, opts)
    return ly


def set_visible(view, keep):
    it = view.begin_layers()
    while not it.at_end():
        lp = it.current().dup()
        lp.visible = keep(lp.source.split("@")[0].strip())
        view.set_layer_properties(it, lp)
        it.next()


def snap(view, png, box, w, h):
    view.zoom_box(box)
    view.save_image_with_options(png, w, h, 0, 0, 0, db.DBox(), False)


def main():
    def_file, prefix = sys.argv[1], sys.argv[2]
    ly = load(def_file)
    top = ly.top_cell()
    if "--gds" in sys.argv:
        ly.write(prefix + ".gds")
        print("wrote", prefix + ".gds")
    tmp = prefix + "_tmp.gds"
    ly.write(tmp)

    view = lay.LayoutView()
    view.set_config("background-color", "#000000")
    view.set_config("grid-visible", "false")
    view.set_config("text-visible", "false")
    view.load_layout(tmp, True)
    view.load_layer_props(f"{TECH}/sky130A.lyp")
    view.max_hier()
    # hide marker layers (cell outlines / area ids) so the real geometry is visible
    set_visible(view, lambda s: not (s.startswith("81/") or s.startswith("235/")))
    bb = top.dbbox()
    snap(view, prefix + "_full.png", bb, 2400, 2400)
    # metal-only view: the wiring of the routed chip (met1..met5 + vias)
    metals = ("68/20", "68/44", "69/20", "69/44", "70/20", "70/44", "71/20", "71/44", "72/20")
    set_visible(view, lambda s: s.startswith(metals))
    snap(view, prefix + "_metal.png", bb, 2400, 2400)
    set_visible(view, lambda s: not (s.startswith("81/") or s.startswith("235/")))
    # zoom: a 40 um x 40 um window in the centre shows individual cells and wires
    cx, cy = bb.center().x, bb.center().y
    snap(view, prefix + "_zoom.png", db.DBox(cx - 20, cy - 20, cx + 20, cy + 20), 1600, 1600)
    # close-up: 12 um x 12 um - single cells, transistors (poly/diffusion) and metal wires
    snap(view, prefix + "_closeup.png", db.DBox(cx - 6, cy - 6, cx + 6, cy + 6), 1600, 1600)
    os.remove(tmp)
    print("die", round(bb.width(), 1), "x", round(bb.height(), 1), "um ->", prefix + "_full.png", prefix + "_zoom.png")


if __name__ == "__main__":
    main()
