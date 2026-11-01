`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company:
// Engineer:
//
// Create Date: 2026/06/21 07:49:33
// Design Name:
// Module Name: SII9022_init
// Project Name:
// Target Devices:
// Tool Versions:
// Description:
//
// Dependencies:
//
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
//
//////////////////////////////////////////////////////////////////////////////////


module SII9022_init(
    input clk,
    input rst_n,
    input Go,
    input [15:0] device_id,
    output reg Init_Done,
    output i2c_sclk,
    inout i2c_sdat
    );

    localparam lut_size = 42;
	localparam addr_mode = 1'b0;

    wire [7:0] addr;
    reg wrreg_req;
	reg rdreg_req;

    wire [15:0]lut;
    reg [7:0] cnt;

    wire [7:0]wrdata;
	wire [7:0]rddata;
	wire RW_Done;
	wire ack;

    SII9022_init_table SII9022_init_table(
        .addr(cnt),
        .clk(clk),
        .q(lut)
    );
    assign addr = lut[15:8];
	assign wrdata = lut[7:0];

    i2c_control i2c_control(
		.Clk(clk),
		.Rst_n(rst_n),
		.wrreg_req(wrreg_req),
		.rdreg_req(0),
		.addr(addr),
		.addr_mode(addr_mode),
		.wrdata(wrdata),
		.rddata(rddata),
		.device_id(device_id),
		.RW_Done(RW_Done),
		.ack(ack),
		.dly_cnt_max(0),
		.i2c_sclk(i2c_sclk),
		.i2c_sdat(i2c_sdat)
	);

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)
            cnt <= 0;
        else if(Go)
            cnt <= 0;
        else if(cnt < lut_size) begin
            if(RW_Done && !ack)
                cnt <= cnt + 1'b1;
            else
                cnt <= cnt;
        end
        else
            cnt <= 0;
    end

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)
            Init_Done <= 0;
        else if(Go)
            Init_Done <= 0;
        else if(cnt == lut_size)
            Init_Done <= 1;
    end

    reg [1:0] state;

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state <= 0;
            wrreg_req <= 1'b0;
        end
        else if(cnt < lut_size) begin
            case(state)
                0: begin
                    if(Go)
                        state <= 1;
                    else
                        state <= 0;
                end
                1: begin
                    wrreg_req <= 1'b1;
                    state <= 2;
                end
                2: begin
                    wrreg_req <= 1'b0;
                    if(RW_Done)
                        state <= 1;
                    else
                        state <= 2;
                end
            endcase
        end
        else
            state <= 0;
    end
endmodule
