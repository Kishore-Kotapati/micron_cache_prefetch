// ============================================================================
// top_module.v  -  Cache + prefetch engine + DRAM model
// ----------------------------------------------------------------------------
//   CPU/trace --> cache_controller <--> memory_model (DRAM)
//                      |   ^
//            training  v   | prefetch candidates
//                  prefetch_engine (stride_predictor + queue)
//
// Run-time configuration (same RTL for every architecture compared):
//   pf_mode       0 = baseline (no prefetch), 1 = next-line, 2 = stride,
//                 3 = hybrid stride (final design)
//   pf_adaptive   1 = accuracy-feedback degree control
//   pf_degree     base / fixed prefetch degree (1..4)
//   pf_insert_lru 1 = adaptive prefetch-aware insertion (LRU when accuracy low)
// The design part is cache_controller + prefetch_engine (synthesizable);
// memory_model is a behavioural DRAM used only for simulation.
// ============================================================================
module top_module #(
    parameter ADDR_W     = 32,
    parameter LINE_BYTES = 16,
    parameter SETS       = 64,
    parameter WAYS       = 4,
    parameter NMSHR      = 8,
    parameter MEM_LAT    = 40,
    parameter MEM_INTV   = 4,
    parameter QDEPTH     = 8,
    parameter NSTREAM    = 4
)(
    input  wire              clk,
    input  wire              rst,
    input  wire [1:0]        pf_mode,
    input  wire              pf_adaptive,
    input  wire [2:0]        pf_degree,
    input  wire              pf_insert_lru,
    input  wire              cpu_req_valid,
    output wire              cpu_req_ready,
    input  wire [ADDR_W-1:0] cpu_req_addr,
    output wire              cpu_resp_valid,
    output wire [31:0]       cpu_resp_data
);
    localparam OFF_W   = $clog2(LINE_BYTES);
    localparam LADDR_W = ADDR_W - OFF_W;
    localparam LINE_W  = LINE_BYTES * 8;
    localparam ID_W    = $clog2(NMSHR);

    wire               mem_req_valid, mem_req_ready, mem_resp_valid, mem_resp_ready;
    wire [LADDR_W-1:0] mem_req_line;
    wire [ID_W-1:0]    mem_req_id, mem_resp_id;
    wire [LINE_W-1:0]  mem_resp_data;

    wire               train_valid, train_miss, train_pfhit;
    wire [ADDR_W-1:0]  train_addr;
    wire               cand_valid, cand_pop, fb_issued, fb_useful;
    wire [LADDR_W-1:0] cand_line;
    wire [2:0]         pf_cur_degree;
    wire               pf_low_acc;

    cache_controller #(
        .ADDR_W(ADDR_W), .LINE_BYTES(LINE_BYTES), .SETS(SETS), .WAYS(WAYS), .NMSHR(NMSHR)
    ) u_cache (
        .clk(clk), .rst(rst),
        .cpu_req_valid(cpu_req_valid), .cpu_req_ready(cpu_req_ready),
        .cpu_req_addr(cpu_req_addr),
        .cpu_resp_valid(cpu_resp_valid), .cpu_resp_data(cpu_resp_data),
        .mem_req_valid(mem_req_valid), .mem_req_ready(mem_req_ready),
        .mem_req_line(mem_req_line), .mem_req_id(mem_req_id),
        .mem_resp_valid(mem_resp_valid), .mem_resp_ready(mem_resp_ready),
        .mem_resp_id(mem_resp_id), .mem_resp_data(mem_resp_data),
        .train_valid(train_valid), .train_addr(train_addr),
        .train_miss(train_miss), .train_pfhit(train_pfhit),
        .cand_valid(cand_valid), .cand_line(cand_line), .cand_pop(cand_pop),
        .fb_issued(fb_issued), .fb_useful(fb_useful),
        .pf_insert_lru(pf_insert_lru), .pf_low_accuracy(pf_low_acc),
        .cnt_access(), .cnt_hit(), .cnt_miss(), .cnt_dem_mem(), .cnt_pf_issued(),
        .cnt_pf_useful(), .cnt_pf_late(), .cnt_pf_evict_unused(), .cnt_pf_filtered(),
        .cnt_fills(), .mshr_busy()
    );

    prefetch_engine #(
        .ADDR_W(ADDR_W), .LINE_BYTES(LINE_BYTES), .QDEPTH(QDEPTH), .NSTREAM(NSTREAM)
    ) u_pf (
        .clk(clk), .rst(rst),
        .mode(pf_mode), .adaptive_en(pf_adaptive), .base_degree(pf_degree),
        .train_valid(train_valid), .train_addr(train_addr),
        .train_miss(train_miss), .train_pfhit(train_pfhit),
        .fb_issued(fb_issued), .fb_useful(fb_useful),
        .cand_valid(cand_valid), .cand_line(cand_line), .cand_pop(cand_pop),
        .degree(pf_cur_degree), .low_accuracy(pf_low_acc),
        .cnt_cand_pushed(), .cnt_cand_dup(), .cnt_page_stop()
    );

    memory_model #(
        .LADDR_W(LADDR_W), .LINE_W(LINE_W), .ID_W(ID_W), .LAT(MEM_LAT), .INTERVAL(MEM_INTV)
    ) u_dram (
        .clk(clk), .rst(rst),
        .req_valid(mem_req_valid), .req_ready(mem_req_ready),
        .req_line(mem_req_line), .req_id(mem_req_id),
        .resp_valid(mem_resp_valid), .resp_ready(mem_resp_ready),
        .resp_id(mem_resp_id), .resp_data(mem_resp_data)
    );
endmodule
