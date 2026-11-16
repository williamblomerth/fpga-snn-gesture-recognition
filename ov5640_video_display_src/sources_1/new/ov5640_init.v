`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company:
// Engineer:
//
// Create Date: 2026/07/22 17:50:52
// Design Name:
// Module Name: ov5640_init
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


module ov5640_init#(
    parameter CAMERA_TYPE     = "ov5640", //"ov5640" or "ov7725"
    parameter IMAGE_TYPE      = 0,        //0:RGB 1:JPEG
    parameter IMAGE_WIDTH     = 640,
    parameter IMAGE_HEIGHT    = 480,
    parameter IMAGE_FLIP_EN   = 0,
    parameter IMAGE_MIRROR_EN = 0

    )
    (
    input clk,
    input rst_n,
    output reg Init_Done,
    output camera_rst_n,
    output camera_pwdn,
    output i2c_sclk,
    inout i2c_sdat
    );

    localparam RGB = 0;
    localparam JPEG = 1;

    reg wrreg_req, rdreg_req;
    wire [7:0] wrdata, rddata;
    wire [15:0] addr;
    wire ack;
    wire RW_Done;
    wire addr_mode;
    reg [31:0] i2c_dly_cnt_max;
    reg [7:0] cnt;
    wire [23:0] lut;
    wire [7:0]lut_size;
    wire [7:0]device_id;

    assign camera_pwdn = 0;

    generate
        if(CAMERA_TYPE == "ov5640") begin
            assign device_id = 8'h78;
            assign addr_mode = 1'b1;
            assign addr = lut[23:8];
            assign wrdata = lut[7:0];
            if(IMAGE_TYPE == RGB) //------RGB------
            begin
            assign lut_size = 252;

            ov5640_init_table_rgb #(
                .IMAGE_WIDTH     (IMAGE_WIDTH     ),
                .IMAGE_HEIGHT    (IMAGE_HEIGHT    ),
                .IMAGE_FLIP_EN   (IMAGE_FLIP_EN   ),
                .IMAGE_MIRROR_EN (IMAGE_MIRROR_EN )
            )ov5640_init_table_rgb_inst
            (
                .addr (cnt ),
                .clk  (clk ),
                .q    (lut )
            );
            end
            else  //------JPEG------
            begin
            assign lut_size = 250;

            ov5640_init_table_jpeg #(
                .IMAGE_WIDTH     (IMAGE_WIDTH     ),
                .IMAGE_HEIGHT    (IMAGE_HEIGHT    ),
                .IMAGE_FLIP_EN   (IMAGE_FLIP_EN   ),
                .IMAGE_MIRROR_EN (IMAGE_MIRROR_EN )
            )ov5640_init_table_jpeg_inst
            (
                .addr (cnt ),
                .clk  (clk ),
                .q    (lut )
            );
            end
        end
        else if(CAMERA_TYPE == "ov7725")
        begin
            assign device_id = 8'h42;
            assign addr_mode = 1'b0;
            assign addr = lut[15:8];
            assign wrdata = lut[7:0];

            if(IMAGE_TYPE == RGB) //------RGB------
            begin
            assign lut_size  = 68;

            ov7725_init_table_rgb #(
                .IMAGE_WIDTH     (IMAGE_WIDTH     ),
                .IMAGE_HEIGHT    (IMAGE_HEIGHT    ),
                .IMAGE_FLIP_EN   (IMAGE_FLIP_EN   ),
                .IMAGE_MIRROR_EN (IMAGE_MIRROR_EN )
            )ov7725_init_table_rgb_inst
            (
                .addr (cnt ),
                .clk  (clk ),
                .q    (lut )
            );
            end
        end
    endgenerate

    i2c_control i2c_control(
    .Clk         (clk             ),
    .Rst_n       (rst_n           ),
    .wrreg_req   (wrreg_req       ),
    .rdreg_req   (0               ),
    .addr        (addr            ),
    .addr_mode   (addr_mode       ),
    .wrdata      (wrdata          ),
    .rddata      (rddata          ),
    .device_id   (device_id       ),
    .RW_Done     (RW_Done         ),
    .ack         (ack             ),
    .dly_cnt_max (i2c_dly_cnt_max ),
    .i2c_sclk    (i2c_sclk        ),
    .i2c_sdat    (i2c_sdat        )
    );

    wire Go;   //initial enable
    reg [20:0] delay_cnt;

    //wait 20ms after power on
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)
            delay_cnt <= 0;
        else if(delay_cnt == 21'h100800)
            delay_cnt <= 21'h100800;
        else
            delay_cnt <= delay_cnt + 1'b1;
    end

    assign Go = (delay_cnt == 21'h1007ff);

    assign camera_rst_n = 1'b1;

    //lut address increment
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)
            cnt <= 0;
        else if(Go)
            cnt <= 0;
        else if(cnt < lut_size) begin
            if(RW_Done & (!ack))
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
        else if (cnt == lut_size)
            Init_Done <= 1;
    end

    reg [1:0] state;

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state <= 0;
            wrreg_req <= 0;
            i2c_dly_cnt_max <= 0;
        end
        else if(cnt < lut_size)begin
            case(state)
                0: begin
                    wrreg_req <= 0;
                    if(Go)
                        state <= 1;
                    else
                        state <= 0;
                end

                1: begin
                    wrreg_req <= 1'b1;
                    state <= 2;
                    if(cnt == 1) //software camera reset rom[1]: wait 5ms after power on
                        i2c_dly_cnt_max <= 32'h40000;
                    else
                        i2c_dly_cnt_max <= 0;
                end

                2: begin
                    wrreg_req <= 1'b0;
                    if(RW_Done)
                        state <= 1;
                    else
                        state <= 2;
                end

                default: state <= 0;
            endcase
        end
        else begin
            state <= 0;
            wrreg_req <= 0;
        end
    end

endmodule
