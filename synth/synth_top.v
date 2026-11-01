// ============================================================================
// synth_top.v - synthesis wrapper: the DESIGN only (cache + prefetch engine).
// The DRAM model is left out (it is a simulation model); its interface
// becomes top-level ports, exactly where a real memory controller connects.
// ============================================================================
module synth_top (
    input  wire         clk,
    input  wire         rst,
    input  wire [1:0]   pf_mode,
    input  wire         pf_adaptive,
    input  wire [2:0]   pf_degree,
    input  wire         pf_insert_lru,
    input  wire         cpu_req_valid,
    output wire         cpu_req_ready,
    input  wire [31:0]  cpu_req_addr,
    output wire         cpu_resp_valid,
    output wire [31:0]  cpu_resp_data,
    output wire         mem_req_valid,
    input  wire         mem_req_ready,
    output wire [27:0]  mem_req_line,
    output wire [2:0]   mem_req_id,
    input  wire         mem_resp_valid,
    output wire         mem_resp_ready,
    input  wire [2:0]   mem_resp_id,
    input  wire [127:0] mem_resp_data,
    output wire [31:0]  cnt_hit,
    output wire [31:0]  cnt_miss,
    output wire [31:0]  cnt_pf_issued,
    output wire [31:0]  cnt_pf_useful
);
    wire        train_valid, train_miss, train_pfhit, cand_valid, cand_pop, fb_issued, fb_useful, low_acc;
    wire [31:0] train_addr;
    wire [27:0] cand_line;

    cache_controller u_cache (
        .clk(clk), .rst(rst),
        .cpu_req_valid(cpu_req_valid), .cpu_req_ready(cpu_req_ready), .cpu_req_addr(cpu_req_addr),
        .cpu_resp_valid(cpu_resp_valid), .cpu_resp_data(cpu_resp_data),
        .mem_req_valid(mem_req_valid), .mem_req_ready(mem_req_ready),
        .mem_req_line(mem_req_line), .mem_req_id(mem_req_id),
        .mem_resp_valid(mem_resp_valid), .mem_resp_ready(mem_resp_ready),
        .mem_resp_id(mem_resp_id), .mem_resp_data(mem_resp_data),
        .train_valid(train_valid), .train_addr(train_addr), .train_miss(train_miss), .train_pfhit(train_pfhit),
        .cand_valid(cand_valid), .cand_line(cand_line), .cand_pop(cand_pop),
        .fb_issued(fb_issued), .fb_useful(fb_useful),
        .pf_insert_lru(pf_insert_lru), .pf_low_accuracy(low_acc),
        .cnt_access(), .cnt_hit(cnt_hit), .cnt_miss(cnt_miss), .cnt_dem_mem(),
        .cnt_pf_issued(cnt_pf_issued), .cnt_pf_useful(cnt_pf_useful), .cnt_pf_late(),
        .cnt_pf_evict_unused(), .cnt_pf_filtered(), .cnt_fills(), .mshr_busy()
    );

    prefetch_engine u_pf (
        .clk(clk), .rst(rst), .mode(pf_mode), .adaptive_en(pf_adaptive), .base_degree(pf_degree),
        .train_valid(train_valid), .train_addr(train_addr), .train_miss(train_miss), .train_pfhit(train_pfhit),
        .fb_issued(fb_issued), .fb_useful(fb_useful),
        .cand_valid(cand_valid), .cand_line(cand_line), .cand_pop(cand_pop),
        .degree(), .low_accuracy(low_acc),
        .cnt_cand_pushed(), .cnt_cand_dup(), .cnt_page_stop()
    );
endmodule
