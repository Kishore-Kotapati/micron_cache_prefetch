// ============================================================================
// tag_array.v  -  Tag / valid / prefetched-bit storage for an N-way cache
// ----------------------------------------------------------------------------
// * Flip-flop based (small cache), so it offers 3 combinational read ports:
//     A : demand lookup   (tags, valid, prefetched bits)
//     B : prefetch probe  (tags, valid)  - filters useless prefetches
//     C : fill victim     (valid, prefetched bits of the set being filled)
// * One full write port (line install on fill) + one "clear prefetched bit"
//   port (used on the first demand hit to a prefetched line).
// * The controller guarantees the install and the clear never collide.
// Synthesizable Verilog-2005.
// ============================================================================
module tag_array #(
    parameter SETS  = 64,
    parameter WAYS  = 4,
    parameter TAG_W = 22,
    parameter IDX_W = $clog2(SETS),
    parameter WAY_W = $clog2(WAYS)
)(
    input  wire                   clk,
    input  wire                   rst,
    // Read port A : demand lookup
    input  wire [IDX_W-1:0]       ra_idx,
    output wire [WAYS*TAG_W-1:0]  ra_tags,
    output wire [WAYS-1:0]        ra_valid,
    output wire [WAYS-1:0]        ra_pf,
    // Read port B : prefetch probe
    input  wire [IDX_W-1:0]       rb_idx,
    output wire [WAYS*TAG_W-1:0]  rb_tags,
    output wire [WAYS-1:0]        rb_valid,
    // Read port C : fill set status
    input  wire [IDX_W-1:0]       rc_idx,
    output wire [WAYS-1:0]        rc_valid,
    output wire [WAYS-1:0]        rc_pf,
    // Install port
    input  wire                   we,
    input  wire [IDX_W-1:0]       w_idx,
    input  wire [WAY_W-1:0]       w_way,
    input  wire [TAG_W-1:0]       w_tag,
    input  wire                   w_pf,
    // Clear-prefetched-bit port
    input  wire                   pfc_en,
    input  wire [IDX_W-1:0]       pfc_idx,
    input  wire [WAY_W-1:0]       pfc_way
);
    reg [TAG_W-1:0]     tag_mem [0:SETS*WAYS-1];
    reg [SETS*WAYS-1:0] valid_bits;
    reg [SETS*WAYS-1:0] pf_bits;     // 1 = filled by prefetch, not yet used

    genvar g;
    generate
        for (g = 0; g < WAYS; g = g + 1) begin : g_rd
            assign ra_tags [g*TAG_W +: TAG_W] = tag_mem[ra_idx*WAYS + g];
            assign ra_valid[g]                = valid_bits[ra_idx*WAYS + g];
            assign ra_pf   [g]                = pf_bits[ra_idx*WAYS + g];
            assign rb_tags [g*TAG_W +: TAG_W] = tag_mem[rb_idx*WAYS + g];
            assign rb_valid[g]                = valid_bits[rb_idx*WAYS + g];
            assign rc_valid[g]                = valid_bits[rc_idx*WAYS + g];
            assign rc_pf   [g]                = pf_bits[rc_idx*WAYS + g];
        end
    endgenerate

    // Control bits (reset)
    always @(posedge clk) begin
        if (rst) begin
            valid_bits <= {(SETS*WAYS){1'b0}};
            pf_bits    <= {(SETS*WAYS){1'b0}};
        end else begin
            if (we) begin
                valid_bits[w_idx*WAYS + w_way] <= 1'b1;
                pf_bits   [w_idx*WAYS + w_way] <= w_pf;
            end
            if (pfc_en)
                pf_bits[pfc_idx*WAYS + pfc_way] <= 1'b0;
        end
    end

    // Tag storage (no reset needed, qualified by valid bit)
    always @(posedge clk) begin
        if (we)
            tag_mem[w_idx*WAYS + w_way] <= w_tag;
    end
endmodule
