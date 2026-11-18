`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company:
// Engineer:
//
// Create Date: 2026/07/23 17:40:20
// Design Name:
// Module Name: DVP_Capture
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


module DVP_Capture(
    input rst_p,
    input pclk,
    input Vsync,
    input Href,
    input [7:0] Data,
    output DataValid,
    output reg ImageState,
    output [11:0] Xaddr,
    output [11:0] Yaddr,
    output [15:0] DataPixel,
    output DataHs,
    output DataVs
    );

    reg r_Vsync;
    reg r_Href;
    reg [7:0] r_Data;
    reg [15:0] r_DataPixel;
    reg [3:0] FrameCnt;
    reg [12:0] Hcount;
    reg r_DataVs, r_DataHs;
    reg [11:0] Vcount;
    reg dump_frame;
    reg r_DataValid;

    always @(posedge pclk) begin
        r_Vsync <= Vsync;
        r_Href <= Href;
        r_Data <= Data;
    end

    always @(posedge pclk or posedge rst_p) begin
        if(rst_p)
            ImageState <= 1'b1;
        else
            ImageState <= 1'b0;
    end

    always @(posedge pclk or posedge rst_p) begin
        if(rst_p)
            Hcount <= 0;
        else if(r_Href)
            Hcount <= Hcount + 1'b1;
        else
            Hcount <= 0;
    end

    always @(posedge pclk or posedge rst_p) begin
        if(rst_p)
            r_DataPixel <= 0;
        else if(!Hcount[0])
            r_DataPixel [15:8] <= r_Data;
        else
            r_DataPixel [7:0] <= r_Data;
    end

    always @(posedge pclk or posedge rst_p) begin
        if(rst_p)
            r_DataValid <= 1'b0;
        else if(r_Href & Hcount[0])
            r_DataValid <= 1'b1;
        else
            r_DataValid <= 1'b0;
    end

    always @(posedge pclk) begin
        r_DataVs <= ~r_Vsync;
        r_DataHs <= r_Href;
    end

    always @(posedge pclk or posedge rst_p) begin
        if(rst_p)
            Vcount <= 0;
        else if(r_Vsync)
            Vcount <= 0;
        else if({Href, r_Href} == 2'b10)
            Vcount <= Vcount + 1'b1;
        else
            Vcount <= Vcount;
    end

    assign Yaddr = Vcount;
    assign Xaddr = Hcount >> 1;

    always @(posedge pclk or posedge rst_p) begin
        if(rst_p)
            FrameCnt <= 0;
        else if({r_Vsync, Vsync} == 2'b01) begin
            if(FrameCnt >= 4'd10)
                FrameCnt <= 4'd10;
            else
                FrameCnt <= FrameCnt + 1'b1;
        end
        else
            FrameCnt <= FrameCnt;
    end

    always @(posedge pclk or posedge rst_p) begin
        if(rst_p)
            dump_frame <= 1;
        else if(FrameCnt >= 4'd10)
            dump_frame <= 0;
        else
            dump_frame <= 1;
    end

    assign DataPixel = r_DataPixel;
    assign DataValid = r_DataValid & (!dump_frame);
    assign DataHs = r_DataHs & (!dump_frame);
    assign DataVs = r_DataVs & (!dump_frame);

endmodule
