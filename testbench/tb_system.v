// ============================================================================
// tb_system.v  -  Trace-driven system testbench (simulation only)
// ----------------------------------------------------------------------------
// CPU model: in-order, one outstanding load.  For each trace entry it waits
// <gap> compute cycles, issues the load, and waits for the data.
//
// Plusargs:
//   +trace=<file>   trace file, one "<gap_dec> <addr_hex>" per line
//   +mode=<0|1|2>   0 baseline, 1 next-line, 2 stride prefetcher
//   +adaptive=<0|1> +degree=<1..4> +inslru=<0|1>
//   +vcd=<file>     dump waveform (GTKWave)
//   +tag=<name>     label printed in the RESULT line
//
// Self-checks (any failure -> "TEST FAILED"):
//   1. every returned word equals the DRAM content function of its address
//   2. hits + misses == accesses
//   3. no duplicate tags inside any set at the end
//   4. prefetch accounting closes:
//        issued == useful + late + evicted_unused + resident_unused
//   5. all MSHRs drain (no lost memory responses)
// ============================================================================
`timescale 1ns/1ps
module tb_system;
    localparam MAX_TRACE = 65536;
    localparam SETS = 64, WAYS = 4, TAG_W = 22;

    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg         rst;
    reg  [1:0]  mode;
    reg         adaptive, inslru;
    reg  [2:0]  degree;
    reg         cpu_req_valid;
    reg  [31:0] cpu_req_addr;
    wire        cpu_req_ready, cpu_resp_valid;
    wire [31:0] cpu_resp_data;

    top_module dut (
        .clk(clk), .rst(rst),
        .pf_mode(mode), .pf_adaptive(adaptive), .pf_degree(degree), .pf_insert_lru(inslru),
        .cpu_req_valid(cpu_req_valid), .cpu_req_ready(cpu_req_ready),
        .cpu_req_addr(cpu_req_addr),
        .cpu_resp_valid(cpu_resp_valid), .cpu_resp_data(cpu_resp_data)
    );

    reg [31:0] cycle;
    always @(posedge clk) cycle <= rst ? 32'd0 : cycle + 32'd1;

    // trace storage
    reg [31:0] tr_addr [0:MAX_TRACE-1];
    reg [15:0] tr_gap  [0:MAX_TRACE-1];
    integer n, fd, r, g, k, j, s, w1, w2;
    reg [31:0] a;
    reg [1023:0] tracefile, vcdfile, tag;

    function [31:0] expected_word;
        input [31:0] byte_addr;
        reg   [31:0] al;
        begin
            al = {byte_addr[31:2], 2'b00};
            expected_word = (al ^ 32'h5A5A5A5A) * 32'h9E3779B1;
        end
    endfunction

    integer errors, issue_cycle, start_cycle, end_cycle, lat, max_lat, timeout;
    integer total_lat, miss_lat_sum, miss_cnt_tb, resident_unused, dups;
    reg     hit_now;
    reg     misslog;

    initial begin
        // ---------------- configuration ----------------
        if (!$value$plusargs("trace=%s", tracefile)) tracefile = "traces/sequential.trace";
        if (!$value$plusargs("mode=%d", mode))         mode = 2'd2;
        if (!$value$plusargs("adaptive=%d", adaptive)) adaptive = 1'b1;
        if (!$value$plusargs("degree=%d", degree))     degree = 3'd2;
        if (!$value$plusargs("inslru=%d", inslru))     inslru = 1'b1;
        if (!$value$plusargs("tag=%s", tag))           tag = "run";
        misslog = $test$plusargs("misslog");   // print every slow load (analysis only)

        // ---------------- load trace -------------------
        n = 0;
        fd = $fopen(tracefile, "r");
        if (fd == 0) begin
            $display("ERROR: cannot open trace %0s", tracefile);
            $finish;
        end
        while (!$feof(fd) && n < MAX_TRACE) begin
            r = $fscanf(fd, "%d %h\n", g, a);
            if (r == 2) begin
                tr_gap[n]  = g[15:0];
                tr_addr[n] = a;
                n = n + 1;
            end
        end
        $fclose(fd);

        if ($value$plusargs("vcd=%s", vcdfile)) begin
            $dumpfile(vcdfile);
            $dumpvars(0, tb_system);
        end

        // ---------------- reset ------------------------
        errors = 0; total_lat = 0; max_lat = 0; miss_lat_sum = 0; miss_cnt_tb = 0;
        cpu_req_valid = 1'b0; cpu_req_addr = 32'd0;
        rst = 1'b1;
        repeat (5) @(posedge clk);
        #1 rst = 1'b0;
        @(posedge clk); #1;
        start_cycle = cycle;

        // ---------------- run trace --------------------
        for (k = 0; k < n; k = k + 1) begin
            repeat (tr_gap[k]) begin @(posedge clk); #1; end
            if (!cpu_req_ready) begin
                $display("ERROR: cache not ready at access %0d", k);
                errors = errors + 1;
                while (!cpu_req_ready) begin @(posedge clk); #1; end
            end
            cpu_req_valid = 1'b1;
            cpu_req_addr  = tr_addr[k];
            issue_cycle   = cycle;
            @(posedge clk); #1;
            cpu_req_valid = 1'b0;
            timeout = 0;
            while (!cpu_resp_valid) begin
                @(posedge clk); #1;
                timeout = timeout + 1;
                if (timeout > 10000) begin
                    $display("ERROR: response timeout at access %0d addr %h", k, tr_addr[k]);
                    $display("TEST FAILED");
                    $finish;
                end
            end
            lat = cycle - issue_cycle;
            total_lat = total_lat + lat;
            if (lat > 1) begin miss_lat_sum = miss_lat_sum + lat; miss_cnt_tb = miss_cnt_tb + 1; end
            if (lat > max_lat) max_lat = lat;
            if (misslog && lat > 1) $display("MISS %0d %h %0d", k, tr_addr[k], lat);
            if (cpu_resp_data !== expected_word(tr_addr[k])) begin
                errors = errors + 1;
                if (errors < 10)
                    $display("DATA MISMATCH access %0d addr %h got %h exp %h",
                             k, tr_addr[k], cpu_resp_data, expected_word(tr_addr[k]));
            end
        end
        end_cycle = cycle;

        // ---------------- drain outstanding prefetches -
        timeout = 0;
        while ((dut.u_cache.mshr_busy != 0 || dut.u_pf.cand_valid) && timeout < 20000) begin
            @(posedge clk); #1; timeout = timeout + 1;
        end
        if (dut.u_cache.mshr_busy != 0) begin
            $display("ERROR: MSHRs did not drain");
            errors = errors + 1;
        end

        // ---------------- end-of-test structural checks
        resident_unused = 0; dups = 0;
        for (s = 0; s < SETS; s = s + 1) begin
            for (w1 = 0; w1 < WAYS; w1 = w1 + 1) begin
                if (dut.u_cache.u_tags.valid_bits[s*WAYS+w1] && dut.u_cache.u_tags.pf_bits[s*WAYS+w1])
                    resident_unused = resident_unused + 1;
                for (w2 = w1 + 1; w2 < WAYS; w2 = w2 + 1)
                    if (dut.u_cache.u_tags.valid_bits[s*WAYS+w1] && dut.u_cache.u_tags.valid_bits[s*WAYS+w2] &&
                        dut.u_cache.u_tags.tag_mem[s*WAYS+w1] == dut.u_cache.u_tags.tag_mem[s*WAYS+w2])
                        dups = dups + 1;
            end
        end
        if (dups != 0) begin $display("ERROR: %0d duplicate lines in cache", dups); errors = errors + 1; end
        if (dut.u_cache.cnt_hit + dut.u_cache.cnt_miss != dut.u_cache.cnt_access || dut.u_cache.cnt_access != n) begin
            $display("ERROR: hit/miss/access counters inconsistent"); errors = errors + 1;
        end
        if (dut.u_cache.cnt_pf_issued != dut.u_cache.cnt_pf_useful + dut.u_cache.cnt_pf_late +
                                         dut.u_cache.cnt_pf_evict_unused + resident_unused) begin
            $display("ERROR: prefetch accounting does not close"); errors = errors + 1;
        end

        $display("RESULT tag=%0s trace=%0s mode=%0d adaptive=%0d degree=%0d inslru=%0d accesses=%0d hits=%0d misses=%0d dem_mem=%0d pf_issued=%0d pf_useful=%0d pf_late=%0d pf_evict_unused=%0d pf_resident_unused=%0d pf_filtered=%0d cand_pushed=%0d final_degree=%0d cycles=%0d total_latency=%0d miss_latency_sum=%0d max_latency=%0d errors=%0d",
            tag, tracefile, mode, adaptive, degree, inslru, n,
            dut.u_cache.cnt_hit, dut.u_cache.cnt_miss, dut.u_cache.cnt_dem_mem,
            dut.u_cache.cnt_pf_issued, dut.u_cache.cnt_pf_useful, dut.u_cache.cnt_pf_late,
            dut.u_cache.cnt_pf_evict_unused, resident_unused, dut.u_cache.cnt_pf_filtered,
            dut.u_pf.cnt_cand_pushed, dut.u_pf.degree,
            end_cycle - start_cycle, total_lat, miss_lat_sum, max_lat, errors);
        if (errors == 0) $display("TEST PASSED");
        else             $display("TEST FAILED");
        $finish;
    end
endmodule
