# 100 MHz target clock (10 ns). Real timing is reported after routing.
create_clock -name clk -period 10.0 [get_ports clk]
set_input_delay  2.0 -clock clk [delete_from_list [all_inputs] [get_ports clk]]
set_output_delay 2.0 -clock clk [all_outputs]
set_load 0.02 [all_outputs]
