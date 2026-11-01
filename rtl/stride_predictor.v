// ============================================================================
// stride_predictor.v  -  Multi-stream, confidence-gated stride predictor
//                        with accuracy-feedback (adaptive) prefetch degree
// ----------------------------------------------------------------------------
// WATCH : every demand access (address, hit/miss, prefetched-hit) is
//         registered here one cycle after the cache lookup.
// GUESS : a small stream table (NSTREAM entries) learns one byte stride per
//         address region.  An access belongs to a stream if it lies within
//         +/-WINDOW bytes of that stream's last address (no PC needed).
//           - same stride again  -> confidence++ (2-bit saturating)
//           - different stride   -> confidence--, re-learn when confidence<=1
//           - no stream matches  -> allocate (free entry, else a
//             zero-confidence entry, else round-robin), so random accesses
//             cannot evict a well-trained stream.
// TRIGGER: when confidence >= CONF_TH and the access moved to a new cache
//         line, emit (base, step, count).  Strides smaller than a line are
//         rounded up to one line in the stream direction.
//
// Modes : 0 = off, 1 = next-line (classic sequential, on miss/prefetch-hit),
//         2 = stride (this design).
//
// Adaptive degree (innovation): every EPOCH issued prefetches the hit-rate of
// those prefetches is checked.  >= 75 % useful -> degree+1 (up to DEG_MAX),
// < 50 % useful -> degree-1 (down to 1).  This throttles the prefetcher on
// irregular (recommendation-like) traffic and pushes it further ahead on
// streaming (CNN/LLM-like) traffic.
// Synthesizable Verilog-2005.
// ============================================================================
module stride_predictor #(
    parameter ADDR_W     = 32,
    parameter LINE_BYTES = 16,
    parameter NSTREAM    = 4,
    parameter STR_W      = 12,      // signed stride width (bytes)
    parameter WINDOW     = 1024,    // stream-match window (bytes)
    parameter CONF_TH    = 2,
    parameter DEG_MAX    = 4,
    parameter EPOCH      = 32,
    parameter OFF_W      = $clog2(LINE_BYTES)
)(
    input  wire               clk,
    input  wire               rst,
    input  wire [1:0]         mode,
    input  wire               adaptive_en,
    input  wire [2:0]         base_degree,
    // training (from cache controller, lookup cycle)
    input  wire               train_valid,
    input  wire [ADDR_W-1:0]  train_addr,
    input  wire               train_miss,
    input  wire               train_pfhit,
    // feedback
    input  wire               fb_issued,
    input  wire               fb_useful,
    // trigger to candidate generator
    output reg                trig_valid,
    output reg  [ADDR_W-1:0]  trig_base,
    output reg  [ADDR_W-1:0]  trig_step,     // two's complement byte step
    output reg  [2:0]         trig_count,
    output reg  [2:0]         degree
);
    localparam MODE_OFF = 2'd0, MODE_NEXT = 2'd1, MODE_STRIDE = 2'd2;
    localparam IW     = (NSTREAM > 1) ? $clog2(NSTREAM) : 1;
    localparam HI_TH  = (EPOCH * 3) / 4;
    localparam LO_TH  = EPOCH / 2;
    localparam CW     = $clog2(EPOCH) + 1;

    // ---------------- registered training input -----------------------
    reg              tr_v, tr_miss, tr_pfhit;
    reg [ADDR_W-1:0] tr_addr;
    always @(posedge clk) begin
        if (rst) begin
            tr_v <= 1'b0; tr_miss <= 1'b0; tr_pfhit <= 1'b0; tr_addr <= 0;
        end else begin
            tr_v     <= train_valid;
            tr_addr  <= train_addr;
            tr_miss  <= train_miss;
            tr_pfhit <= train_pfhit;
        end
    end

    // ---------------- stream table -------------------------------------
    reg [NSTREAM-1:0]      s_valid;
    reg [ADDR_W-1:0]       s_last   [0:NSTREAM-1];
    reg [STR_W-1:0]        s_stride [0:NSTREAM-1];
    reg [1:0]              s_conf   [0:NSTREAM-1];
    reg [IW-1:0]           rr_ptr;

    // ---------------- combinational match / victim ---------------------
    integer i;
    reg              match;
    reg [IW-1:0]     midx;
    reg [ADDR_W-1:0] mdiff, d;
    reg              vfound;
    reg [IW-1:0]     vidx;

    always @* begin
        match = 1'b0; midx = {IW{1'b0}}; mdiff = {ADDR_W{1'b0}};
        for (i = 0; i < NSTREAM; i = i + 1) begin
            d = tr_addr - s_last[i];
            if (!match && s_valid[i] &&
                ($signed(d) <= WINDOW) && ($signed(d) >= -WINDOW)) begin
                match = 1'b1; midx = i[IW-1:0]; mdiff = d;
            end
        end
        vfound = 1'b0; vidx = rr_ptr;
        for (i = 0; i < NSTREAM; i = i + 1)
            if (!vfound && !s_valid[i]) begin vfound = 1'b1; vidx = i[IW-1:0]; end
        for (i = 0; i < NSTREAM; i = i + 1)
            if (!vfound && (s_conf[i] == 2'd0)) begin vfound = 1'b1; vidx = i[IW-1:0]; end
    end

    wire [STR_W-1:0]  m_stride     = s_stride[midx];
    wire [ADDR_W-1:0] m_stride_ext = {{(ADDR_W-STR_W){m_stride[STR_W-1]}}, m_stride};
    wire [1:0]        m_conf       = s_conf[midx];
    wire              m_same       = (mdiff == m_stride_ext);
    wire [1:0]        m_conf_inc   = (m_conf == 2'd3) ? 2'd3 : m_conf + 2'd1;
    wire              m_line_chg   = (tr_addr[ADDR_W-1:OFF_W] != s_last[midx][ADDR_W-1:OFF_W]);
    // effective step: at least one cache line in the stream direction
    wire              m_neg        = m_stride[STR_W-1];
    wire [STR_W-1:0]  m_abs        = m_neg ? (~m_stride + 1'b1) : m_stride;
    wire [ADDR_W-1:0] line_pos     = LINE_BYTES;
    wire [ADDR_W-1:0] eff_step     = (m_abs < LINE_BYTES) ? (m_neg ? (~line_pos + 1'b1) : line_pos)
                                                          : m_stride_ext;
    wire [2:0]        deg_clamped  = (base_degree == 3'd0) ? 3'd1 :
                                     (base_degree > DEG_MAX) ? DEG_MAX[2:0] : base_degree;

    // ---------------- table update + trigger ---------------------------
    always @(posedge clk) begin
        if (rst) begin
            s_valid    <= {NSTREAM{1'b0}};
            rr_ptr     <= {IW{1'b0}};
            trig_valid <= 1'b0;
            trig_base  <= 0;
            trig_step  <= 0;
            trig_count <= 3'd0;
            for (i = 0; i < NSTREAM; i = i + 1) begin
                s_last[i] <= 0; s_stride[i] <= 0; s_conf[i] <= 2'd0;
            end
        end else begin
            trig_valid <= 1'b0;
            if (tr_v && mode == MODE_NEXT) begin
                if (tr_miss || tr_pfhit) begin
                    trig_valid <= 1'b1;
                    trig_base  <= {tr_addr[ADDR_W-1:OFF_W], {OFF_W{1'b0}}};
                    trig_step  <= LINE_BYTES;
                    trig_count <= degree;
                end
            end else if (tr_v && mode == MODE_STRIDE) begin
                if (match) begin
                    if (mdiff != 0) begin
                        s_last[midx] <= tr_addr;
                        if (m_same) begin
                            s_conf[midx] <= m_conf_inc;
                            if ((m_conf_inc >= CONF_TH) && m_line_chg) begin
                                trig_valid <= 1'b1;
                                trig_base  <= tr_addr;
                                trig_step  <= eff_step;
                                trig_count <= degree;
                            end
                        end else begin
                            if (m_conf != 2'd0) s_conf[midx] <= m_conf - 2'd1;
                            if (m_conf <= 2'd1) s_stride[midx] <= mdiff[STR_W-1:0];
                        end
                    end
                end else begin
                    s_valid[vidx]  <= 1'b1;
                    s_last[vidx]   <= tr_addr;
                    s_stride[vidx] <= {STR_W{1'b0}};
                    s_conf[vidx]   <= 2'd0;
                    if (!vfound) rr_ptr <= rr_ptr + 1'b1;
                end
            end
        end
    end

    // ---------------- adaptive degree (accuracy feedback) --------------
    reg  [CW-1:0] ep_issued, ep_useful;
    wire [CW-1:0] iss_n = ep_issued + (fb_issued ? 1'b1 : 1'b0);
    wire [CW-1:0] use_n = (ep_useful >= EPOCH) ? ep_useful : ep_useful + (fb_useful ? 1'b1 : 1'b0);

    always @(posedge clk) begin
        if (rst) begin
            degree    <= deg_clamped;
            ep_issued <= 0;
            ep_useful <= 0;
        end else if (!adaptive_en) begin
            degree    <= deg_clamped;
            ep_issued <= 0;
            ep_useful <= 0;
        end else begin
            if (iss_n >= EPOCH) begin
                if (use_n >= HI_TH && degree < DEG_MAX)      degree <= degree + 3'd1;
                else if (use_n < LO_TH && degree > 3'd1)     degree <= degree - 3'd1;
                ep_issued <= 0;
                ep_useful <= 0;
            end else begin
                ep_issued <= iss_n;
                ep_useful <= use_n;
            end
        end
    end
endmodule
