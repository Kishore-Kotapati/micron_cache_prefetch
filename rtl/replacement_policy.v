// ============================================================================
// replacement_policy.v  -  True-LRU with prefetch-aware insertion
// ----------------------------------------------------------------------------
// Each set keeps one age per way (0 = most recently used, WAYS-1 = LRU).
// Ages always form a permutation of 0..WAYS-1.
//
// Update operations (one per cycle):
//   upd_lru = 0 : promote way to MRU   (demand hit, demand fill)
//   upd_lru = 1 : insert way at LRU    (prefetch fill when the
//                                       "prefetch-aware insertion" policy is
//                                       on - an unused prefetch is the first
//                                       line to be evicted, so wrong guesses
//                                       cannot push out useful demand data)
//
// Victim selection: first invalid way, otherwise the way whose age is WAYS-1.
// Synthesizable Verilog-2005.
// ============================================================================
module replacement_policy #(
    parameter SETS  = 64,
    parameter WAYS  = 4,
    parameter IDX_W = $clog2(SETS),
    parameter WAY_W = $clog2(WAYS)
)(
    input  wire              clk,
    input  wire              rst,
    // victim query
    input  wire [IDX_W-1:0]  q_idx,
    input  wire [WAYS-1:0]   q_valid,
    output reg  [WAY_W-1:0]  victim_way,
    // age update
    input  wire              upd_en,
    input  wire [IDX_W-1:0]  upd_idx,
    input  wire [WAY_W-1:0]  upd_way,
    input  wire              upd_lru
);
    localparam AGE_MAX = WAYS - 1;

    reg [WAYS*WAY_W-1:0] age [0:SETS-1];

    integer i, s;
    reg found;
    wire [WAYS*WAY_W-1:0] q_age = age[q_idx];

    // ---------------- victim selection (combinational) -----------------
    always @* begin
        victim_way = {WAY_W{1'b0}};
        found      = 1'b0;
        for (i = 0; i < WAYS; i = i + 1)
            if (!found && !q_valid[i]) begin
                victim_way = i[WAY_W-1:0];
                found      = 1'b1;
            end
        for (i = 0; i < WAYS; i = i + 1)
            if (!found && (q_age[i*WAY_W +: WAY_W] == AGE_MAX[WAY_W-1:0])) begin
                victim_way = i[WAY_W-1:0];
                found      = 1'b1;
            end
    end

    // ---------------- next-age computation (combinational) -------------
    wire [WAYS*WAY_W-1:0] cur_age = age[upd_idx];
    wire [WAY_W-1:0]      ref_age = cur_age[upd_way*WAY_W +: WAY_W];
    reg  [WAYS*WAY_W-1:0] nxt_age;
    reg  [WAYS*WAY_W-1:0] init_age;
    reg  [WAY_W-1:0]      a;

    always @* begin
        for (i = 0; i < WAYS; i = i + 1) begin
            a = cur_age[i*WAY_W +: WAY_W];
            if (i[WAY_W-1:0] == upd_way)
                nxt_age[i*WAY_W +: WAY_W] = upd_lru ? AGE_MAX[WAY_W-1:0] : {WAY_W{1'b0}};
            else if (!upd_lru && (a < ref_age))
                nxt_age[i*WAY_W +: WAY_W] = a + 1'b1;   // older by one
            else if (upd_lru && (a > ref_age))
                nxt_age[i*WAY_W +: WAY_W] = a - 1'b1;   // younger by one
            else
                nxt_age[i*WAY_W +: WAY_W] = a;
            init_age[i*WAY_W +: WAY_W] = i[WAY_W-1:0];
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            for (s = 0; s < SETS; s = s + 1)
                age[s] <= init_age;
        end else if (upd_en) begin
            age[upd_idx] <= nxt_age;
        end
    end
endmodule
