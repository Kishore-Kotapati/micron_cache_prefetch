// ============================================================================
// memory_model.v  -  DRAM model (SIMULATION MODEL, not part of the design)
// ----------------------------------------------------------------------------
// * Fixed access latency LAT cycles, in-order responses.
// * Pipelined, but bandwidth-limited: at most one new request every
//   INTERVAL cycles (so useless prefetches really cost bandwidth).
// * Up to DEPTH requests in flight; responses wait (resp_ready) if the cache
//   is busy with a demand lookup.
// * Data content is a deterministic function of the byte address, so the
//   testbench can check every word returned to the CPU:
//       word(addr) = (addr ^ 32'h5A5A5A5A) * 32'h9E3779B1
// ============================================================================
module memory_model #(
    parameter LADDR_W  = 28,          // line-address width
    parameter LINE_W   = 128,         // line size in bits
    parameter ID_W     = 3,           // request tag width (MSHR index)
    parameter LAT      = 40,          // DRAM latency in cycles
    parameter INTERVAL = 4,           // min cycles between accepted requests
    parameter DEPTH    = 16           // max requests in flight
)(
    input  wire               clk,
    input  wire               rst,
    input  wire               req_valid,
    output wire               req_ready,
    input  wire [LADDR_W-1:0] req_line,
    input  wire [ID_W-1:0]    req_id,
    output wire               resp_valid,
    input  wire               resp_ready,
    output wire [ID_W-1:0]    resp_id,
    output reg  [LINE_W-1:0]  resp_data
);
    localparam PTR_W   = $clog2(DEPTH);
    localparam WORDS   = LINE_W / 32;
    localparam OFF_W   = $clog2(LINE_W / 8);

    reg [31:0]        cycle;
    reg [ID_W-1:0]    q_id   [0:DEPTH-1];
    reg [LADDR_W-1:0] q_line [0:DEPTH-1];
    reg [31:0]        q_due  [0:DEPTH-1];
    reg [PTR_W-1:0]   head, tail;
    reg [PTR_W:0]     count;
    reg [7:0]         busy;
    reg [31:0]        total_reqs;

    assign req_ready  = (busy == 8'd0) && (count < DEPTH);
    wire   push       = req_valid && req_ready;
    assign resp_valid = (count != 0) && (cycle >= q_due[head]);
    wire   pop        = resp_valid && resp_ready;
    assign resp_id    = q_id[head];

    function [31:0] mem_word;
        input [31:0] byte_addr;
        begin
            mem_word = (byte_addr ^ 32'h5A5A5A5A) * 32'h9E3779B1;
        end
    endfunction

    integer w;
    always @* begin
        for (w = 0; w < WORDS; w = w + 1)
            resp_data[w*32 +: 32] = mem_word({q_line[head], {OFF_W{1'b0}}} | (w << 2));
    end

    always @(posedge clk) begin
        if (rst) begin
            cycle <= 0; head <= 0; tail <= 0; count <= 0; busy <= 0; total_reqs <= 0;
        end else begin
            cycle <= cycle + 1;
            if (push) begin
                q_id  [tail] <= req_id;
                q_line[tail] <= req_line;
                q_due [tail] <= cycle + LAT;
                tail         <= tail + 1'b1;
                total_reqs   <= total_reqs + 1;
                busy         <= INTERVAL - 1;
            end else if (busy != 0) begin
                busy <= busy - 1'b1;
            end
            if (pop)
                head <= head + 1'b1;
            count <= count + {{PTR_W{1'b0}}, push} - {{PTR_W{1'b0}}, pop};
        end
    end
endmodule
