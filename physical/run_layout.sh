#!/usr/bin/env bash
# Physical design (RTL -> real chip layout) with free tools only:
#   Yosys (sky130 cells) -> OpenROAD (floorplan, power, place, clock tree, route) -> KLayout (GDS + pictures)
# Needs: yosys, openroad, python3 + klayout module, and the SkyWater sky130A PDK.
#   PDK_ROOT_SKY130 = folder that contains libs.ref/ and libs.tech/   (e.g. .../share/pdk/sky130A)
#   OPENROAD        = path to the openroad binary (default: openroad on PATH)
set -e
cd "$(dirname "$0")"
: "${PDK_ROOT_SKY130:?set PDK_ROOT_SKY130 to your sky130A folder}"
OPENROAD=${OPENROAD:-openroad}
export PDK_ROOT_SKY130
export PDK_REF=$PDK_ROOT_SKY130/libs.ref/sky130_fd_sc_hd
export LIB=$PDK_REF/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
mkdir -p out

echo "== 1. synthesis to SkyWater 130 nm standard cells (Yosys)"
yosys -q -l out/yosys.log -c synth_sky130.tcl
grep -E "Number of cells|Chip area" out/synth_stat.txt

echo "== 2. place and route (OpenROAD) - about 15-30 minutes"
"$OPENROAD" -no_init -exit flow.tcl > out/openroad.log 2>&1
grep -E "Design area|wns|tns|Total Power" out/openroad.log || true

echo "== 3. GDS + pictures (KLayout)"
python3 render_layout.py out/3_routed.def out/chip --gds
python3 block_map.py out/layout_top.netlist.v out/3_routed.def out/block_map.png
echo "Done. Open the chip with:  klayout out/chip.gds"
