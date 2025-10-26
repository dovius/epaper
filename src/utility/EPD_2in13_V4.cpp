/*****************************************************************************
* | File      :   EPD_2in13_V4.cpp
* | Author    :   Waveshare team (original), refactored for robustness
* | Function  :   2.13inch e-paper V4
* | Info      :
*----------------
* |   This version:   V1.0
* |   Date        :   2023-8-11
* |   Info        :
* -----------------------------------------------------------------------------
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
******************************************************************************/
#include "EPD_2in13_V4.h"
#include "Debug.h"

namespace {

constexpr UWORD kWidth = EPD_2in13_V4_WIDTH;
constexpr UWORD kHeight = EPD_2in13_V4_HEIGHT;
constexpr UWORD kRowBytes = (kWidth + 7U) / 8U;
constexpr UDOUBLE kFrameBufferSize = static_cast<UDOUBLE>(kRowBytes) * kHeight;
constexpr uint32_t kBusyPollIntervalMs = 2U;
constexpr uint32_t kBusyDefaultTimeoutMs = 4000U;

void hardware_reset()
{
    DEV_Digital_Write(EPD_RST_PIN, 1);
    DEV_Delay_ms(20);
    DEV_Digital_Write(EPD_RST_PIN, 0);
    DEV_Delay_ms(2);
    DEV_Digital_Write(EPD_RST_PIN, 1);
    DEV_Delay_ms(20);
}

inline void send_command(UBYTE command)
{
    DEV_Digital_Write(EPD_DC_PIN, 0);
    DEV_SPI_WriteByte(command);
}

inline void send_data_byte(UBYTE data)
{
    DEV_Digital_Write(EPD_DC_PIN, 1);
    DEV_SPI_WriteByte(data);
}

inline void send_data_buffer(const UBYTE *data, UDOUBLE length)
{
    if (data == nullptr || length == 0) {
        return;
    }
    DEV_Digital_Write(EPD_DC_PIN, 1);
    DEV_SPI_Write_nByte(data, length);
}

inline void send_command_with_data(UBYTE command, const UBYTE *data, size_t length)
{
    send_command(command);
    if (data != nullptr && length > 0) {
        send_data_buffer(data, static_cast<UDOUBLE>(length));
    }
}

bool wait_while_busy(uint32_t timeout_ms = kBusyDefaultTimeoutMs)
{
    Debug("e-Paper busy\r\n");
    const uint32_t start = millis();
    while (DEV_Digital_Read(EPD_BUSY_PIN) == 1) {
        DEV_Delay_ms(kBusyPollIntervalMs);
        if (timeout_ms > 0 && (millis() - start) >= timeout_ms) {
            Debug("e-Paper busy timeout\r\n");
            return false;
        }
    }
    DEV_Delay_ms(10);
    Debug("e-Paper busy release\r\n");
    return true;
}

inline void trigger_display_update(UBYTE control)
{
    send_command_with_data(0x22, &control, 1);
    send_command(0x20);
    wait_while_busy();
}

void set_window(UWORD x_start, UWORD y_start, UWORD x_end, UWORD y_end)
{
    const UBYTE x_data[] = {
        static_cast<UBYTE>((x_start >> 3) & 0xFF),
        static_cast<UBYTE>((x_end >> 3) & 0xFF)
    };
    const UBYTE y_data[] = {
        static_cast<UBYTE>(y_start & 0xFF),
        static_cast<UBYTE>((y_start >> 8) & 0xFF),
        static_cast<UBYTE>(y_end & 0xFF),
        static_cast<UBYTE>((y_end >> 8) & 0xFF)
    };
    send_command_with_data(0x44, x_data, sizeof(x_data));
    send_command_with_data(0x45, y_data, sizeof(y_data));
}

void set_cursor(UWORD x, UWORD y)
{
    const UBYTE x_data = static_cast<UBYTE>(x & 0xFF);
    const UBYTE y_data[] = {
        static_cast<UBYTE>(y & 0xFF),
        static_cast<UBYTE>((y >> 8) & 0xFF)
    };
    send_command_with_data(0x4E, &x_data, 1);
    send_command_with_data(0x4F, y_data, sizeof(y_data));
}

inline void set_full_window()
{
    set_window(0, 0, kWidth - 1, kHeight - 1);
    set_cursor(0, 0);
}

void write_image_ram(UBYTE command, const UBYTE *image)
{
    if (image == nullptr) {
        return;
    }
    send_command(command);
    send_data_buffer(image, kFrameBufferSize);
}

void fill_image_ram(UBYTE command, UBYTE value)
{
    UBYTE line[kRowBytes];
    for (UWORD col = 0; col < kRowBytes; ++col) {
        line[col] = value;
    }
    send_command(command);
    DEV_Digital_Write(EPD_DC_PIN, 1);
    for (UWORD row = 0; row < kHeight; ++row) {
        DEV_SPI_Write_nByte(line, kRowBytes);
    }
}

}  // namespace

void EPD_2in13_V4_Init(void)
{
    hardware_reset();

    wait_while_busy();
    send_command(0x12);  // SWRESET
    wait_while_busy();

    const UBYTE driver_output[] = {0xF9, 0x00, 0x00};
    send_command_with_data(0x01, driver_output, sizeof(driver_output));

    const UBYTE data_entry_mode = 0x03;
    send_command_with_data(0x11, &data_entry_mode, 1);

    set_full_window();

    const UBYTE border_control = 0x05;
    send_command_with_data(0x3C, &border_control, 1);

    const UBYTE display_update_control[] = {0x00, 0x80};
    send_command_with_data(0x21, display_update_control, sizeof(display_update_control));

    const UBYTE temp_sensor_control = 0x80;
    send_command_with_data(0x18, &temp_sensor_control, 1);
    wait_while_busy();
}

void EPD_2in13_V4_Init_Fast(void)
{
    hardware_reset();

    send_command(0x12);  // SWRESET
    wait_while_busy();

    const UBYTE temp_sensor_control = 0x80;
    send_command_with_data(0x18, &temp_sensor_control, 1);

    const UBYTE data_entry_mode = 0x03;
    send_command_with_data(0x11, &data_entry_mode, 1);

    set_full_window();

    trigger_display_update(0xB1);  // Load temperature

    const UBYTE temp_register[] = {0x64, 0x00};
    send_command_with_data(0x1A, temp_register, sizeof(temp_register));

    trigger_display_update(0x91);  // Apply temperature
}

void EPD_2in13_V4_Init_GUI(void)
{
    EPD_2in13_V4_Init();
    const UBYTE border_control = 0x80;
    send_command_with_data(0x3C, &border_control, 1);
}

void EPD_2in13_V4_Clear(void)
{
    fill_image_ram(0x24, 0xFF);
    trigger_display_update(0xF7);
}

void EPD_2in13_V4_Clear_Black(void)
{
    fill_image_ram(0x24, 0x00);
    trigger_display_update(0xF7);
}

void EPD_2in13_V4_Display(const UBYTE *Image)
{
    write_image_ram(0x24, Image);
    trigger_display_update(0xF7);
}

void EPD_2in13_V4_Display_Fast(const UBYTE *Image)
{
    write_image_ram(0x24, Image);
    trigger_display_update(0xC7);
}

void EPD_2in13_V4_Display_Base(const UBYTE *Image)
{
    if (Image == nullptr) {
        return;
    }
    write_image_ram(0x24, Image);
    write_image_ram(0x26, Image);
    trigger_display_update(0xF7);
}

void EPD_2in13_V4_Display_Partial(const UBYTE *Image)
{
    if (Image == nullptr) {
        return;
    }

    DEV_Digital_Write(EPD_RST_PIN, 0);
    DEV_Delay_ms(1);
    DEV_Digital_Write(EPD_RST_PIN, 1);

    const UBYTE border_control = 0x80;
    send_command_with_data(0x3C, &border_control, 1);

    const UBYTE driver_output[] = {0xF9, 0x00, 0x00};
    send_command_with_data(0x01, driver_output, sizeof(driver_output));

    const UBYTE data_entry_mode = 0x03;
    send_command_with_data(0x11, &data_entry_mode, 1);

    set_full_window();

    write_image_ram(0x24, Image);
    trigger_display_update(0xFF);
}

void EPD_2in13_V4_Sleep(void)
{
    const UBYTE deep_sleep = 0x01;
    send_command_with_data(0x10, &deep_sleep, 1);
    DEV_Delay_ms(100);
}
