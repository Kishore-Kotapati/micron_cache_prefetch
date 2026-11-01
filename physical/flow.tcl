# ============================================================================
# flow.tcl - OpenROAD place-and-route of layout_top on SkyWater 130 nm (sky130_fd_sc_hd)
# floorplan -> power grid -> pin placement -> placement -> clock tree -> routing
# Run through run_layout.sh (sets PDK and paths). All results go to out/.
# ============================================================================
set P      $::env(PDK_REF)
set LIB    $P/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
set TLEF   $P/techlef/sky130_fd_sc_hd__nom.tlef
set CLEF   $P/lef/sky130_fd_sc_hd.lef
set UTIL   [expr {[info exists ::env(UTIL)] ? $::env(UTIL) : 45}]
set_thread_count [exec nproc]

proc stage {name} { puts "\n================ $name ================"; flush stdout }

stage "read design"
read_lef $TLEF
read_lef $CLEF
read_liberty $LIB
read_verilog out/layout_top.netlist.v
link_design layout_top
read_sdc layout_top.sdc
set_dont_use {sky130_fd_sc_hd__probe_p_* sky130_fd_sc_hd__probec_p_* sky130_fd_sc_hd__lpflow_*}
set_wire_rc -signal -layer met2
set_wire_rc -clock  -layer met5

stage "floorplan"
initialize_floorplan -utilization $UTIL -aspect_ratio 1 -core_space 12 -site unithd
foreach {l d off pitch} {li1 X 0.23 0.46 li1 Y 0.17 0.34 met1 X 0.17 0.34 met1 Y 0.17 0.34
                         met2 X 0.23 0.46 met2 Y 0.23 0.46 met3 X 0.34 0.68 met3 Y 0.34 0.68
                         met4 X 0.46 0.92 met4 Y 0.46 0.92 met5 X 1.70 3.40 met5 Y 1.70 3.40} {
    if {$d == "X"} { set xo($l) $off; set xp($l) $pitch } else { set yo($l) $off; set yp($l) $pitch }
}
foreach l {li1 met1 met2 met3 met4 met5} {
    make_tracks $l -x_offset $xo($l) -x_pitch $xp($l) -y_offset $yo($l) -y_pitch $yp($l)
}
tapcell -distance 14 -tapcell_master sky130_fd_sc_hd__tapvpwrvgnd_1 -endcap_master sky130_fd_sc_hd__decap_3

stage "power grid"
set block [ord::get_db_block]
foreach {n t} {VPWR POWER VGND GROUND} {
    if {[$block findNet $n] == "NULL"} {
        set net [odb::dbNet_create $block $n]
        $net setSpecial
        $net setSigType $t
    }
}
add_global_connection -net VPWR -pin_pattern {^VPWR$} -power
add_global_connection -net VPWR -pin_pattern {^VPB$}
add_global_connection -net VGND -pin_pattern {^VGND$} -ground
add_global_connection -net VGND -pin_pattern {^VNB$}
if {[llength [info commands global_connect]]} { global_connect }
set_voltage_domain -name CORE -power VPWR -ground VGND
define_pdn_grid -name grid -voltage_domains CORE
add_pdn_stripe -grid grid -layer met1 -width 0.48 -followpins
add_pdn_stripe -grid grid -layer met4 -width 1.6 -pitch 50 -offset 10
add_pdn_stripe -grid grid -layer met5 -width 1.6 -pitch 50 -offset 10
add_pdn_connect -grid grid -layers {met1 met4}
add_pdn_connect -grid grid -layers {met4 met5}
pdngen

stage "pins"
place_pins -hor_layers met3 -ver_layers met2 -corner_avoidance 10 -min_distance 2

stage "global placement"
global_placement -density [expr {$UTIL / 100.0 + 0.15}] -pad_left 1 -pad_right 1
estimate_parasitics -placement
repair_design
stage "detailed placement"
detailed_placement
check_placement -verbose
write_def out/1_placed.def

stage "clock tree"
clock_tree_synthesis -root_buf sky130_fd_sc_hd__clkbuf_16 -buf_list {sky130_fd_sc_hd__clkbuf_4 sky130_fd_sc_hd__clkbuf_8} -sink_clustering_enable
set_propagated_clock [all_clocks]
estimate_parasitics -placement
repair_clock_nets
repair_timing
detailed_placement
check_placement -verbose
write_def out/2_cts.def

stage "global route"
set_routing_layers -signal met1-met5 -clock met3-met5
set_global_routing_layer_adjustment met1 0.3
set_global_routing_layer_adjustment met2 0.3
global_route -guide_file out/route.guide -congestion_iterations 50 -verbose
estimate_parasitics -global_routing

stage "fillers"
filler_placement {sky130_fd_sc_hd__decap_12 sky130_fd_sc_hd__decap_8 sky130_fd_sc_hd__decap_6 sky130_fd_sc_hd__decap_4 sky130_fd_sc_hd__decap_3 sky130_fd_sc_hd__fill_2 sky130_fd_sc_hd__fill_1}
check_placement -verbose

stage "detailed route"
detailed_route -guide out/route.guide -output_drc out/drc.rpt -bottom_routing_layer met1 -top_routing_layer met5 -verbose 1
write_def out/3_routed.def
write_db  out/3_routed.odb
write_verilog out/layout_top.final.v

stage "reports"
report_design_area
report_tns
report_wns
report_check_types -max_slew -max_capacitance -max_fanout -violators
report_checks -path_delay max -digits 3
report_power
