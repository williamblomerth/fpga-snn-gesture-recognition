# FPGA SNN Gesture Recognition

This repository contains the Vivado source files for a Zynq-based Real time video display project

## Vivado version compatibility

The files in `EC551_project.srcs/` were created using **AMD Vivado 2024.2**. The project uses IP cores from that version, so Vivado 2024.2 is the recommended version for working with these sources.

Opening or rebuilding the design in another Vivado version may not work directly. Differences in IP versions and block design compatibility may require IP upgrades, regeneration of output products, or manual changes. Compatibility with other Vivado versions is not guaranteed.

## Zynq hardware requirement

This is a **Zynq-based project**. The included `system` block design uses the Zynq Processing System and connects it to the programmable logic through AXI interfaces. The block design targets the `xc7z020clg484-2` device.

The complete design therefore cannot be programmed directly onto a conventional FPGA that lacks the Zynq Processing System. Porting it to such a device would require replacing or redesigning the processing-system-dependent components and interfaces. Use compatible Zynq hardware and verify the device, board connections, and constraints before building or programming the design.

## Repository contents

- `EC551_project.srcs/`: Vivado design sources, IP configuration files, block design, and constraints.
- `EC551_project.srcs/sources_1/bd/system/system.bd`: Zynq system block design.
- `EC551_project.srcs/constrs_1/new/constraint_1.xdc`: Hardware constraints.

The repository currently contains the source directory rather than a complete Vivado project (`.xpr`). To work with the design, create a project in Vivado 2024.2 for the appropriate Zynq device, add the supplied sources and constraints, and validate the block design and IP configuration before synthesis and implementation.

## Source file descriptions

The following tables describe the source and constraint files, excluding IP cores and block design files. Paths are relative to `EC551_project.srcs/`.

### Camera capture and top-level integration

| File | Description |
| --- | --- |
| `sources_1/new/ov5640_top.v` | Top-level module connecting camera initialization and capture, DDR frame buffering through AXI, display output, HDMI transmitter initialization, and the Zynq system wrapper. |
| `sources_1/new/ov5640_init.v` | Sequences camera reset and I2C register configuration using the selected RGB or JPEG initialization table. |
| `sources_1/new/DVP_Capture.v` | Captures the camera's 8-bit parallel DVP stream, combines bytes into 16-bit pixels, and generates pixel-valid, synchronization, and coordinate signals. |

### Camera configuration tables

| File | Description |
| --- | --- |
| `sources_1/imports/ov5640_init_table_rgb.v` | Register lookup table for OV5640 RGB565 output, with configurable image dimensions, flip, and mirror settings. |
| `sources_1/imports/ov5640_init_table_jpeg.v` | Register lookup table used by the camera initialization module when JPEG mode is selected, with configurable image dimensions, flip, and mirror settings. |

### I2C communication

| File | Description |
| --- | --- |
| `sources_1/imports/i2c_control.v` | Handles register read/write transactions, device addressing, register address modes, and delays using the low-level I2C engine. |
| `sources_1/imports/i2c_bit_shift.v` | Implements I2C clock generation, byte transmission and reception, start/stop conditions, and ACK/NACK handling. |

### Frame buffering and memory access

| File | Description |
| --- | --- |
| `sources_1/imports/fifo_axi4_adapter.v` | Connects camera and display FIFO interfaces to an AXI4 master through FIFO buffering and data-width conversion. |
| `sources_1/imports/fifo2axi4.v` | Controls AXI4 burst reads and writes, arbitrates FIFO transfer requests, and manages addresses within configured memory ranges. |

### Display and HDMI configuration

| File | Description |
| --- | --- |
| `sources_1/imports/disp_driver.v` | Generates display timing, horizontal and vertical synchronization, pixel coordinates, data requests, and RGB output. |
| `sources_1/imports/disp_parameter_cfg.v` | Defines display resolution, color depth, and timing macros; currently selects an 800 x 480 TFT with RGB565 color. |
| `sources_1/imports/SII9022_init.v` | Configures the SiI9022 HDMI transmitter over I2C using its initialization lookup table. |
| `sources_1/imports/SII9022_init_table.v` | Stores the SiI9022 register settings for video input/output configuration and TMDS output enable. |

### Hardware constraints

| File | Description |
| --- | --- |
| `constrs_1/new/constraint_1.xdc` | Assigns board pins and I/O standards for the camera, display, HDMI control, reset, and LED signals, and overrides dedicated clock routing for the camera pixel clock. |

## IP cores and source connections

Paths below are relative to `EC551_project.srcs/sources_1/`. The `.xci` files store Vivado IP configurations; generate their output products in Vivado 2024.2 when rebuilding the project.

| IP configuration | Purpose and source connection |
| --- | --- |
| `ip/pll/pll.xci` | Clock generation IP instantiated as `pll` in `ov5640_top.v`. Uses the block design's 50 MHz PS fabric clock to generate the 100 MHz AXI clock, approximately 33.33 MHz display clock, and 24 MHz camera reference clock. Its `locked` output participates in reset control. |
| `ip/wr_ddr3_fifo/wr_ddr3_fifo.xci` | Independent-clock block RAM FIFO instantiated in `fifo_axi4_adapter.v`. Buffers 16-bit pixels from `DVP_Capture.v` in the camera pixel clock domain and packs them into 64-bit words for `fifo2axi4.v` in the 100 MHz AXI domain. Configured for 256 input words / 64 output words. |
| `ip/rd_ddr3_fifo/rd_ddr3_fifo.xci` | Independent-clock block RAM FIFO instantiated in `fifo_axi4_adapter.v`. Buffers 64-bit words returned by `fifo2axi4.v` and unpacks them into 16-bit pixels consumed by `disp_driver.v` in the display clock domain. Configured for 64 input words / 256 output words. |

`fifo2axi4.v` implements the AXI master control in RTL; it connects to the FIFO IPs through `fifo_axi4_adapter.v`. `ov5640_top.v` connects that adapter's 64-bit AXI interface to the block design through `system_wrapper`. The FIFO widths are fixed by the supplied IP configurations, so changes to the adapter's width parameters must be matched by changes to the FIFO IP configurations.

The camera initialization tables, I2C modules, and SiI9022 initialization modules are RTL modules connected by `ov5640_top.v`; they do not directly instantiate the configured IP cores. `DVP_Capture.v` and `disp_driver.v` exchange pixels with the FIFO IPs through the adapter. The top level also instantiates a `BUFG` device primitive to buffer the incoming camera pixel clock.

## Zynq block design

`sources_1/bd/system/system.bd` defines the Zynq processing system, AXI connection to PS memory, and reset infrastructure. Its generated HDL wrapper, `system_wrapper`, is instantiated by `ov5640_top.v`. Create or regenerate that wrapper and the block design output products in Vivado before building.

| Block design IP | Purpose and connections |
| --- | --- |
| `processing_system7_0` (`bd/system/ip/system_processing_system7_0_0/`) | Configures the Zynq-7000 Processing System, including its DDR controller and enabled PS peripherals. Exposes DDR and fixed I/O signals to the top level, supplies the 50 MHz fabric clock and PS reset, and accepts programmable-logic memory transactions through its `S_AXI_HP0` high-performance slave port. |
| `smartconnect_0` (`bd/system/ip/system_smartconnect_0_0/`) | Connects the external `pl2ps_axi_0` interface to the Processing System's `S_AXI_HP0` port, providing the AXI interconnect between the RTL frame-buffer controller and PS memory. Uses the 100 MHz AXI clock supplied by the top level. |
| `proc_sys_reset_0` (`bd/system/ip/system_proc_sys_reset_0_0/`) | Generates the reset used by SmartConnect. Its synchronization clock comes from the PS 50 MHz fabric clock; its external reset input is connected to `pl2ps_axi_reset_n`, driven by the PLL lock signal in the top level. |

The block design maps a 1 GiB PS DDR/OCM address window starting at `0x00000000` into the PL AXI address space. Frame-buffer transfers use the address range configured in `ov5640_top.v`. DDR access uses the Zynq PS DDR controller through `S_AXI_HP0`.

### Main data and clock paths

```text
OV5640 camera
  -> DVP_Capture.v (16-bit pixels)
  -> fifo_axi4_adapter.v / wr_ddr3_fifo (16 -> 64 bits)
  -> fifo2axi4.v (AXI writes)
  -> system_wrapper / SmartConnect / PS S_AXI_HP0
  -> PS DDR memory

PS DDR memory
  -> PS S_AXI_HP0 / SmartConnect / system_wrapper
  -> fifo2axi4.v (AXI reads)
  -> fifo_axi4_adapter.v / rd_ddr3_fifo (64 -> 16 bits)
  -> disp_driver.v
  -> TFT RGB, sync, and pixel-clock outputs

PS fabric clock (50 MHz) -> pll
  -> 100 MHz: AXI controller, FIFO AXI sides, and block design AXI interface
  -> ~33.33 MHz: display driver and display-side FIFO reads
  -> 24 MHz: camera reference clock (camera_xclk)

Camera pixel clock -> BUFG -> DVP capture and camera-side FIFO writes
```
