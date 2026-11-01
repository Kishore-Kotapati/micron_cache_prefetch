// ============================================================================
// cache_controller.v  -  Blocking-for-CPU, non-blocking-for-prefetch cache
// ----------------------------------------------------------------------------
// Organisation (default parameters):
//   4 KB, 4-way set associative, 64 sets, 16-byte lines, 32-bit addresses,
//   read-only (AI inference streams weights/activations), true LRU.
//   addr = [ tag 31:10 | index 9:4 | word 3:2 | byte 1:0 ]
//
// Demand FSM
//   S_IDLE     : accept CPU request, look up tags (1-cycle hit).
//                hit  -> respond next cycle, update LRU, if the line was
//                        prefetched: count "useful", clear its prefetch bit.
//                miss -> line already in flight as a prefetch?  merge into
//                        that MSHR ("late prefetch") and go to S_WAIT,
//                        otherwise go to S_MISS_REQ.
//   S_MISS_REQ : send the demand request to DRAM (demand has priority over
//                prefetches on the memory port), allocate MSHR, -> S_WAIT.
//   S_WAIT     : when the waited line is filled, respond, -> S_IDLE.
//
// Prefetch path (works in parallel, never blocks demand)
//   Each cycle the head of the prefetch queue is probed (tag port B + MSHR
//   table).  Already cached / already in flight -> dropped ("filtered").
//   Otherwise it is sent to DRAM if: no demand lookup this cycle, FSM is not
//   in S_MISS_REQ, and >= 2 MSHRs are free (one is always kept for demand).
//
// Fills: one per cycle, only in cycles without a demand lookup, so the tag,
// data and LRU arrays see a single update per cycle (no conflicts).
// Prefetch fills set the line's "prefetched" bit.  Adaptive insertion
// (pf_insert_lru = 1): while the prefetcher's measured accuracy is low, new
// prefetched lines are inserted at the LRU position (first to be evicted, so
// bad guesses cannot push out demand data); while accuracy is good they are
// inserted at MRU like demand lines (so good prefetches survive until used).
// Synthesizable Verilog-2005.
// ============================================================================
module cache_controller #(
    parameter ADDR_W     = 32,
    parameter LINE_BYTES = 16,
    parameter SETS       = 64,
    parameter WAYS       = 4,
    parameter NMSHR      = 8,
    parameter OFF_W      = $clog2(LINE_BYTES),
    parameter IDX_W      = $clog2(SETS),
    parameter WAY_W      = $clog2(WAYS),
    parameter TAG_W      = ADDR_W - OFF_W - IDX_W,
    parameter LADDR_W    = ADDR_W - OFF_W,
    parameter LINE_W     = LINE_BYTES * 8,
    parameter ID_W       = $clog2(NMSHR),
    parameter WS_W       = $clog2(LINE_BYTES / 4)
)(
    input  wire               clk,
    input  wire               rst,
    // CPU side
    input  wire               cpu_req_valid,
    output wire               cpu_req_ready,
    input  wire [ADDR_W-1:0]  cpu_req_addr,
    output reg                cpu_resp_valid,
    output reg  [31:0]        cpu_resp_data,
    // DRAM side
    output wire               mem_req_valid,
    input  wire               mem_req_ready,
    output wire [LADDR_W-1:0] mem_req_line,
    output wire [ID_W-1:0]    mem_req_id,
    input  wire               mem_resp_valid,
    output wire               mem_resp_ready,
    input  wire [ID_W-1:0]    mem_resp_id,
    input  wire [LINE_W-1:0]  mem_resp_data,
    // Prefetch engine side
    output wire               train_valid,
    output wire [ADDR_W-1:0]  train_addr,
    output wire               train_miss,
    output wire               train_pfhit,
    input  wire               cand_valid,
    input  wire [LADDR_W-1:0] cand_line,
    output wire               cand_pop,
    output wire               fb_issued,
    output wire               fb_useful,
    // Configuration
    input  wire               pf_insert_lru,
    input  wire               pf_low_accuracy,
    // Performance counters
    output reg  [31:0]        cnt_access,
    output reg  [31:0]        cnt_hit,
    output reg  [31:0]        cnt_miss,
    output reg  [31:0]        cnt_dem_mem,
    output reg  [31:0]        cnt_pf_issued,
    output reg  [31:0]        cnt_pf_useful,
    output reg  [31:0]        cnt_pf_late,
    output reg  [31:0]        cnt_pf_evict_unused,
    output reg  [31:0]        cnt_pf_filtered,
    output reg  [31:0]        cnt_fills,
    output wire [NMSHR-1:0]   mshr_busy
);
    localparam [1:0] S_IDLE = 2'd0, S_MISS_REQ = 2'd1, S_WAIT = 2'd2;

    reg [1:0]         state;
    reg [LADDR_W-1:0] miss_line_r;
    reg [WS_W-1:0]    miss_word_r;

    // MSHR table
    reg [NMSHR-1:0]   m_v, m_pf, m_wait;
    reg [LADDR_W-1:0] m_line [0:NMSHR-1];
    assign mshr_busy = m_v;

    integer i;

    // ---------------- request decode ------------------------------------
    wire [IDX_W-1:0]   rq_idx  = cpu_req_addr[OFF_W +: IDX_W];
    wire [TAG_W-1:0]   rq_tag  = cpu_req_addr[ADDR_W-1 -: TAG_W];
    wire [LADDR_W-1:0] rq_line = cpu_req_addr[ADDR_W-1:OFF_W];
    wire [WS_W-1:0]    rq_word = cpu_req_addr[OFF_W-1:2];

    assign cpu_req_ready = (state == S_IDLE);
    wire do_lookup = cpu_req_valid && cpu_req_ready;

    // ---------------- tag array -----------------------------------------
    wire [WAYS*TAG_W-1:0] a_tags, b_tags;
    wire [WAYS-1:0]       a_valid, a_pf, b_valid, c_valid, c_pf;

    // fill decode
    wire               do_fill;
    wire [LADDR_W-1:0] f_line = m_line[mem_resp_id];
    wire               f_pf   = m_pf[mem_resp_id];
    wire               f_wait = m_wait[mem_resp_id];
    wire [IDX_W-1:0]   f_idx  = f_line[IDX_W-1:0];
    wire [TAG_W-1:0]   f_tag  = f_line[LADDR_W-1 -: TAG_W];
    wire [WAY_W-1:0]   victim_way;

    // probe decode
    wire [IDX_W-1:0]   pb_idx = cand_line[IDX_W-1:0];
    wire [TAG_W-1:0]   pb_tag = cand_line[LADDR_W-1 -: TAG_W];

    // hit detection
    reg              hit;
    reg [WAY_W-1:0]  hit_way;
    always @* begin
        hit = 1'b0; hit_way = {WAY_W{1'b0}};
        for (i = 0; i < WAYS; i = i + 1)
            if (!hit && a_valid[i] && (a_tags[i*TAG_W +: TAG_W] == rq_tag)) begin
                hit = 1'b1; hit_way = i[WAY_W-1:0];
            end
    end
    wire hit_pf = a_pf[hit_way];

    tag_array #(.SETS(SETS), .WAYS(WAYS), .TAG_W(TAG_W)) u_tags (
        .clk(clk), .rst(rst),
        .ra_idx(rq_idx), .ra_tags(a_tags), .ra_valid(a_valid), .ra_pf(a_pf),
        .rb_idx(pb_idx), .rb_tags(b_tags), .rb_valid(b_valid),
        .rc_idx(f_idx),  .rc_valid(c_valid), .rc_pf(c_pf),
        .we(do_fill), .w_idx(f_idx), .w_way(victim_way), .w_tag(f_tag), .w_pf(f_pf),
        .pfc_en(do_lookup && hit && hit_pf), .pfc_idx(rq_idx), .pfc_way(hit_way)
    );

    // ---------------- data array ----------------------------------------
    wire [LINE_W-1:0] rd_line;
    wire [31:0]       rd_word = rd_line[rq_word*32 +: 32];

    cache_memory #(.SETS(SETS), .WAYS(WAYS), .LINE_W(LINE_W)) u_data (
        .clk(clk), .r_idx(rq_idx), .r_way(hit_way), .r_data(rd_line),
        .we(do_fill), .w_idx(f_idx), .w_way(victim_way), .w_data(mem_resp_data)
    );

    // ---------------- replacement ---------------------------------------
    replacement_policy #(.SETS(SETS), .WAYS(WAYS)) u_repl (
        .clk(clk), .rst(rst),
        .q_idx(f_idx), .q_valid(c_valid), .victim_way(victim_way),
        .upd_en((do_lookup && hit) || do_fill),
        .upd_idx(do_lookup ? rq_idx : f_idx),
        .upd_way(do_lookup ? hit_way : victim_way),
        .upd_lru(do_lookup ? 1'b0 : (f_pf && pf_insert_lru && pf_low_accuracy))
    );
    wire f_evict_unused = c_valid[victim_way] && c_pf[victim_way];

    // ---------------- MSHR search ---------------------------------------
    reg            dm_match;  reg [ID_W-1:0] dm_idx;     // demand line in flight?
    reg            pb_mshr;                               // probe line in flight?
    reg            pb_cache;                              // probe line cached?
    reg            have_free; reg [ID_W-1:0] free_idx;
    reg [ID_W:0]   free_cnt;
    always @* begin
        dm_match = 1'b0; dm_idx = {ID_W{1'b0}}; pb_mshr = 1'b0;
        have_free = 1'b0; free_idx = {ID_W{1'b0}}; free_cnt = 0;
        for (i = 0; i < NMSHR; i = i + 1) begin
            if (m_v[i] && (m_line[i] == rq_line) && !dm_match) begin
                dm_match = 1'b1; dm_idx = i[ID_W-1:0];
            end
            if (m_v[i] && (m_line[i] == cand_line)) pb_mshr = 1'b1;
            if (!m_v[i]) begin
                free_cnt = free_cnt + 1'b1;
                if (!have_free) begin have_free = 1'b1; free_idx = i[ID_W-1:0]; end
            end
        end
        pb_cache = 1'b0;
        for (i = 0; i < WAYS; i = i + 1)
            if (b_valid[i] && (b_tags[i*TAG_W +: TAG_W] == pb_tag)) pb_cache = 1'b1;
    end

    // ---------------- arbitration ---------------------------------------
    assign mem_resp_ready = !do_lookup;                   // demand lookup first
    assign do_fill        = mem_resp_valid && mem_resp_ready;

    wire pf_drop    = cand_valid && (pb_cache || pb_mshr);
    wire pf_port_ok = !do_lookup && (state != S_MISS_REQ);
    wire pf_req     = cand_valid && !pf_drop && pf_port_ok && (free_cnt >= 2);
    wire dem_req    = (state == S_MISS_REQ) && have_free;
    wire dem_issue  = dem_req && mem_req_ready;
    wire pf_issue   = (state != S_MISS_REQ) && pf_req && mem_req_ready;

    assign mem_req_valid = (state == S_MISS_REQ) ? dem_req : pf_req;
    assign mem_req_line  = (state == S_MISS_REQ) ? miss_line_r : cand_line;
    assign mem_req_id    = free_idx;
    assign cand_pop      = pf_drop || pf_issue;

    // ---------------- prefetch-engine interface -------------------------
    assign train_valid = do_lookup;
    assign train_addr  = cpu_req_addr;
    assign train_miss  = !hit;
    assign train_pfhit = hit && hit_pf;
    assign fb_issued   = pf_issue;
    assign fb_useful   = do_lookup && ((hit && hit_pf) || (!hit && dm_match));

    // ---------------- sequential control --------------------------------
    always @(posedge clk) begin
        if (rst) begin
            state <= S_IDLE; m_v <= 0; m_pf <= 0; m_wait <= 0;
            miss_line_r <= 0; miss_word_r <= 0;
            cpu_resp_valid <= 1'b0; cpu_resp_data <= 32'd0;
            cnt_access <= 0; cnt_hit <= 0; cnt_miss <= 0; cnt_dem_mem <= 0;
            cnt_pf_issued <= 0; cnt_pf_useful <= 0; cnt_pf_late <= 0;
            cnt_pf_evict_unused <= 0; cnt_pf_filtered <= 0; cnt_fills <= 0;
        end else begin
            cpu_resp_valid <= 1'b0;

            // ---- line fill (free MSHR) ----
            if (do_fill) begin
                m_v[mem_resp_id]    <= 1'b0;
                m_wait[mem_resp_id] <= 1'b0;
                cnt_fills           <= cnt_fills + 1;
                if (f_evict_unused) cnt_pf_evict_unused <= cnt_pf_evict_unused + 1;
                if (f_wait) begin
                    cpu_resp_valid <= 1'b1;
                    cpu_resp_data  <= mem_resp_data[miss_word_r*32 +: 32];
                    state          <= S_IDLE;
                end
            end

            // ---- DRAM request issue (allocate MSHR) ----
            if (dem_issue) begin
                m_v[free_idx] <= 1'b1; m_pf[free_idx] <= 1'b0; m_wait[free_idx] <= 1'b1;
                m_line[free_idx] <= miss_line_r;
                cnt_dem_mem <= cnt_dem_mem + 1;
                state <= S_WAIT;
            end else if (pf_issue) begin
                m_v[free_idx] <= 1'b1; m_pf[free_idx] <= 1'b1; m_wait[free_idx] <= 1'b0;
                m_line[free_idx] <= cand_line;
                cnt_pf_issued <= cnt_pf_issued + 1;
            end
            if (pf_drop) cnt_pf_filtered <= cnt_pf_filtered + 1;

            // ---- demand lookup ----
            if (do_lookup) begin
                cnt_access <= cnt_access + 1;
                if (hit) begin
                    cnt_hit        <= cnt_hit + 1;
                    cpu_resp_valid <= 1'b1;
                    cpu_resp_data  <= rd_word;
                    if (hit_pf) cnt_pf_useful <= cnt_pf_useful + 1;
                end else begin
                    cnt_miss    <= cnt_miss + 1;
                    miss_word_r <= rq_word;
                    if (dm_match) begin                 // late prefetch: merge
                        cnt_pf_late    <= cnt_pf_late + 1;
                        m_wait[dm_idx] <= 1'b1;
                        m_pf[dm_idx]   <= 1'b0;         // becomes a demand fill
                        state          <= S_WAIT;
                    end else begin
                        miss_line_r <= rq_line;
                        state       <= S_MISS_REQ;
                    end
                end
            end
        end
    end
endmodule
