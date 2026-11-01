// ============================================================================
// prefetch_engine.v  -  Predictor + candidate generator + prefetch queue
// ----------------------------------------------------------------------------
//   stride_predictor --trigger--> generator --1 line/cycle--> prefetch queue
//                                                               |
//                                         cand_valid/cand_line  v
//                                                        cache_controller
// Generator : walks base+step, base+2*step, ... (count = current degree).
//             Stops at a 4 KB page boundary (no prediction of addresses in
//             another page = protection against invalid predictions).
// Queue     : QDEPTH-entry FIFO.  A candidate already waiting in the queue is
//             not pushed again (duplicate suppression).  Lines already in the
//             cache or already in flight are filtered later by the controller
//             probe.  Generator stalls when the queue is full; a new trigger
//             replaces any unfinished older one (newest prediction wins).
// Synthesizable Verilog-2005.
// ============================================================================
module prefetch_engine #(
    parameter ADDR_W     = 32,
    parameter LINE_BYTES = 16,
    parameter QDEPTH     = 8,
    parameter PAGE_BITS  = 12,
    parameter NSTREAM    = 4,
    parameter DEG_MAX    = 4,
    parameter OFF_W      = $clog2(LINE_BYTES),
    parameter LADDR_W    = ADDR_W - OFF_W
)(
    input  wire               clk,
    input  wire               rst,
    input  wire [1:0]         mode,
    input  wire               adaptive_en,
    input  wire [2:0]         base_degree,
    input  wire               train_valid,
    input  wire [ADDR_W-1:0]  train_addr,
    input  wire               train_miss,
    input  wire               train_pfhit,
    input  wire               fb_issued,
    input  wire               fb_useful,
    output wire               cand_valid,
    output wire [LADDR_W-1:0] cand_line,
    input  wire               cand_pop,
    output wire [2:0]         degree,
    output reg  [31:0]        cnt_cand_pushed,
    output reg  [31:0]        cnt_cand_dup,
    output reg  [31:0]        cnt_page_stop
);
    localparam QP_W = $clog2(QDEPTH);

    wire              trig_valid;
    wire [ADDR_W-1:0] trig_base, trig_step;
    wire [2:0]        trig_count;

    stride_predictor #(
        .ADDR_W(ADDR_W), .LINE_BYTES(LINE_BYTES), .NSTREAM(NSTREAM), .DEG_MAX(DEG_MAX)
    ) u_pred (
        .clk(clk), .rst(rst), .mode(mode), .adaptive_en(adaptive_en),
        .base_degree(base_degree),
        .train_valid(train_valid), .train_addr(train_addr),
        .train_miss(train_miss), .train_pfhit(train_pfhit),
        .fb_issued(fb_issued), .fb_useful(fb_useful),
        .trig_valid(trig_valid), .trig_base(trig_base), .trig_step(trig_step),
        .trig_count(trig_count), .degree(degree)
    );

    // ---------------- generator -----------------------------------------
    reg [ADDR_W-1:0]           g_addr, g_step;
    reg [2:0]                  g_left;
    reg [ADDR_W-PAGE_BITS-1:0] g_page;
    wire [LADDR_W-1:0] g_line      = g_addr[ADDR_W-1:OFF_W];
    wire               g_same_page = (g_addr[ADDR_W-1:PAGE_BITS] == g_page);

    // ---------------- queue ---------------------------------------------
    reg [LADDR_W-1:0] q_line [0:QDEPTH-1];
    reg [QDEPTH-1:0]  q_v;
    reg [QP_W-1:0]    q_head, q_tail;
    wire              q_full = q_v[q_tail];

    integer i;
    reg dup;
    always @* begin
        dup = 1'b0;
        for (i = 0; i < QDEPTH; i = i + 1)
            if (q_v[i] && (q_line[i] == g_line)) dup = 1'b1;
    end

    wire gen_active = (g_left != 3'd0) && !trig_valid;
    wire gen_step   = gen_active && g_same_page && !q_full;   // consume one candidate
    wire push       = gen_step && !dup;

    assign cand_valid = q_v[q_head];
    assign cand_line  = q_line[q_head];

    always @(posedge clk) begin
        if (rst) begin
            g_addr <= 0; g_step <= 0; g_left <= 0; g_page <= 0;
            q_v <= {QDEPTH{1'b0}}; q_head <= 0; q_tail <= 0;
            cnt_cand_pushed <= 0; cnt_cand_dup <= 0; cnt_page_stop <= 0;
        end else begin
            if (trig_valid) begin
                g_addr <= trig_base + trig_step;
                g_step <= trig_step;
                g_left <= trig_count;
                g_page <= trig_base[ADDR_W-1:PAGE_BITS];
            end else if (gen_active) begin
                if (!g_same_page) begin
                    g_left        <= 3'd0;                 // page boundary: stop
                    cnt_page_stop <= cnt_page_stop + 1;
                end else if (!q_full) begin
                    g_addr <= g_addr + g_step;
                    g_left <= g_left - 3'd1;
                    if (dup) cnt_cand_dup <= cnt_cand_dup + 1;
                end
            end
            if (push) begin
                q_line[q_tail]  <= g_line;
                q_v[q_tail]     <= 1'b1;
                q_tail          <= q_tail + 1'b1;
                cnt_cand_pushed <= cnt_cand_pushed + 1;
            end
            if (cand_pop && cand_valid) begin
                q_v[q_head] <= 1'b0;
                q_head      <= q_head + 1'b1;
            end
        end
    end
endmodule
