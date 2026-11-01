// ============================================================================
// cache_memory.v  -  Cache data array (one full line per entry)
// ----------------------------------------------------------------------------
// * Combinational read (selected set + way), synchronous write on fill.
// * Whole line is written in one beat (wide DRAM bus model).
// Synthesizable Verilog-2005.
// ============================================================================
module cache_memory #(
    parameter SETS   = 64,
    parameter WAYS   = 4,
    parameter LINE_W = 128,
    parameter IDX_W  = $clog2(SETS),
    parameter WAY_W  = $clog2(WAYS)
)(
    input  wire              clk,
    input  wire [IDX_W-1:0]  r_idx,
    input  wire [WAY_W-1:0]  r_way,
    output wire [LINE_W-1:0] r_data,
    input  wire              we,
    input  wire [IDX_W-1:0]  w_idx,
    input  wire [WAY_W-1:0]  w_way,
    input  wire [LINE_W-1:0] w_data
);
    reg [LINE_W-1:0] data_mem [0:SETS*WAYS-1];

    assign r_data = data_mem[{r_idx, r_way}];

    always @(posedge clk) begin
        if (we)
            data_mem[{w_idx, w_way}] <= w_data;
    end
endmodule
