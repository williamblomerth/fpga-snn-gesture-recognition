`timescale 1ns / 1ps

module ov5640_to_32x32_gray (
    input  wire       pclk,       // pixel clock from camera
    input  wire       vsync,      // high between frames
    input  wire       href,       // high during a line
    input  wire [7:0] cam_data,   // RGB565, high byte first

    output reg  [7:0] gray_pixel, // average of a 20x15 block
    output reg  [9:0] mem_addr,   // {y, x}
    output reg        mem_we
);

    reg        byte_toggle = 0;
    reg [7:0]  first_byte  = 0;
    reg [4:0]  x_out  = 0;
    reg [4:0]  y_out  = 0;
    reg [4:0]  x_step = 0;
    reg [3:0]  y_step = 0;
    reg        prev_href = 0;
    reg [16:0] block_sum [0:31];  // 300*255 = 76500
    integer    i;

    wire [15:0] rgb565 = {first_byte, cam_data};
    wire [7:0]  R = {rgb565[15:11], rgb565[15:13]};
    wire [7:0]  G = {rgb565[10:5],  rgb565[10:9]};
    wire [7:0]  B = {rgb565[4:0],   rgb565[4:2]};

    wire [15:0] gray_x256 = R*77 + G*150 + B*29;    // BT.601
    wire [7:0]  gray_calc = gray_x256[15:8];

    wire [16:0] sum_calc = block_sum[x_out] + gray_calc;
    wire [7:0]  avg_calc = (sum_calc * 219) >> 16;  // /300

    always @(posedge pclk) begin
        mem_we    <= 1'b0;
        prev_href <= href;

        if (vsync) begin
            x_out       <= 0;
            y_out       <= 0;
            x_step      <= 0;
            y_step      <= 0;
            byte_toggle <= 0;
            for (i = 0; i < 32; i = i + 1)
                block_sum[i] <= 0;
        end

        else if (href) begin
            byte_toggle <= ~byte_toggle;

            if (!byte_toggle) begin
                first_byte <= cam_data;
            end else begin
                block_sum[x_out] <= sum_calc;

                if (x_step == 19 && y_step == 14) begin  // last pixel of block
                    gray_pixel       <= avg_calc;
                    mem_addr         <= {y_out, x_out};
                    mem_we           <= 1'b1;
                    block_sum[x_out] <= 0;
                end

                if (x_step == 19) begin
                    x_step <= 0;
                    x_out  <= x_out + 1;
                end else begin
                    x_step <= x_step + 1;
                end
            end
        end

        else if (prev_href && !href) begin  // end of line
            x_out       <= 0;
            x_step      <= 0;
            byte_toggle <= 0;

            if (y_step == 14) begin
                y_step <= 0;
                y_out  <= y_out + 1;
            end else begin
                y_step <= y_step + 1;
            end
        end
    end

endmodule
