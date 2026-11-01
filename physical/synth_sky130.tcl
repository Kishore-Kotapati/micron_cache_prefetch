# Yosys (tcl mode): map the design onto real SkyWater 130 nm standard cells.
# Called by run_layout.sh as:  yosys -c synth_sky130.tcl   (LIB env var = liberty file)
yosys -import
set lib $::env(LIB)
read_liberty -lib -ignore_miss_dir -setattr blackbox $lib
read_verilog -sv ../rtl/cache_controller.v ../rtl/tag_array.v ../rtl/cache_memory.v \
                 ../rtl/replacement_policy.v ../rtl/stride_predictor.v ../rtl/prefetch_engine.v layout_top.v
hierarchy -check -top layout_top
synth -top layout_top -flatten
dfflibmap -liberty $lib
abc -D 10000 -liberty $lib
opt_clean -purge
hilomap -singleton -hicell sky130_fd_sc_hd__conb_1 HI -locell sky130_fd_sc_hd__conb_1 LO
setundef -zero
splitnets
opt_clean -purge
insbuf -buf sky130_fd_sc_hd__buf_2 A X
tee -o out/synth_stat.txt stat -liberty $lib
check -assert
write_verilog -noattr -noexpr -nohex -nodec out/layout_top.netlist.v
