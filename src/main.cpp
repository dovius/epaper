/*****************************************************************************
 * | Project     :  EPD 2.13" showcase
 * | Author      :  Refactored demo
 * | Description :  Rich, looped scenes highlighting drawing, charts,
 *                  partial updates, and bitmap overlays.
 *****************************************************************************/

#include <Arduino.h>
#include <stdio.h>

#include "DEV_Config.h"
#include "EPD.h"
#include "GUI_Paint.h"
#include "ImageData.h"

namespace demo {

constexpr UWORD kPanelWidth = EPD_2in13_V4_WIDTH;
constexpr UWORD kPanelHeight = EPD_2in13_V4_HEIGHT;
constexpr UWORD kDefaultRotate = ROTATE_90;
constexpr uint32_t kShortHoldMs = 2500;
constexpr uint32_t kMediumHoldMs = 3200;
constexpr uint32_t kLongHoldMs = 4000;

UBYTE *sFrame = nullptr;
constexpr UWORD imageSize()
{
    return ((kPanelWidth + 7U) / 8U) * kPanelHeight;
}

bool ensureFrame()
{
    if (sFrame != nullptr) {
        return true;
    }
    sFrame = static_cast<UBYTE *>(malloc(imageSize()));
    if (sFrame == nullptr) {
        Debug("Frame allocation failed\r\n");
        return false;
    }
    return true;
}

void prepareCanvas(UWORD color = WHITE)
{
    Paint_NewImage(sFrame, kPanelWidth, kPanelHeight, kDefaultRotate, color);
    Paint_SelectImage(sFrame);
    Paint_Clear(color);
}

void pushFull(bool fast = false)
{
    if (fast) {
        EPD_2in13_V4_Init_Fast();
        EPD_2in13_V4_Display_Fast(sFrame);
    } else {
        EPD_2in13_V4_Init();
        EPD_2in13_V4_Display_Base(sFrame);
    }
}

void drawHeader(const char *title)
{
    Paint_DrawRectangle(0, 0, Paint.Width - 1, 26, BLACK, DOT_PIXEL_1X1, DRAW_FILL_FULL);
    Paint_DrawString_EN(6, 4, title, &Font16, WHITE, BLACK);
}

void sceneWelcome()
{
    prepareCanvas();
    drawHeader("EPD Showcase");
    Paint_DrawRectangle(0, 0, Paint.Width - 1, Paint.Height - 1, BLACK, DOT_PIXEL_1X1, DRAW_FILL_EMPTY);
    Paint_DrawString_EN(12, 38, "2.13\" e-Paper", &Font24, BLACK, WHITE);
    Paint_DrawString_EN(12, 68, "Feature tour", &Font20, BLACK, WHITE);
    Paint_DrawString_EN(16, 92, "- Shapes, charts, widgets", &Font12, BLACK, WHITE);
    Paint_DrawString_EN(16, 106, "- Partial refresh updates", &Font12, BLACK, WHITE);
    pushFull(false);
    DEV_Delay_ms(kLongHoldMs);
}

void sceneShapeGallery()
{
    prepareCanvas();
    drawHeader("Vector Gallery");
    Paint_DrawRectangle(10, 32, Paint.Width - 10, Paint.Height - 10, BLACK, DOT_PIXEL_1X1, DRAW_FILL_EMPTY);
    Paint_DrawLine(10, 82, Paint.Width - 10, 82, BLACK, DOT_PIXEL_1X1, LINE_STYLE_DOTTED);
    Paint_DrawLine(Paint.Width / 2, 32, Paint.Width / 2, Paint.Height - 10, BLACK, DOT_PIXEL_1X1, LINE_STYLE_DOTTED);

    // Left column
    Paint_DrawCircle(40, 60, 18, BLACK, DOT_PIXEL_1X1, DRAW_FILL_EMPTY);
    Paint_DrawCircle(40, 106, 16, BLACK, DOT_PIXEL_1X1, DRAW_FILL_FULL);
    Paint_DrawLine(24, 96, 56, 118, BLACK, DOT_PIXEL_1X1, LINE_STYLE_SOLID);
    Paint_DrawLine(56, 96, 24, 118, BLACK, DOT_PIXEL_1X1, LINE_STYLE_SOLID);

    // Right column
    Paint_DrawRectangle(138, 46, 188, 96, BLACK, DOT_PIXEL_1X1, DRAW_FILL_FULL);
    Paint_DrawRectangle(200, 46, 240, 96, BLACK, DOT_PIXEL_1X1, DRAW_FILL_EMPTY);
    Paint_DrawLine(205, 102, 235, 120, BLACK, DOT_PIXEL_1X1, LINE_STYLE_SOLID);
    Paint_DrawLine(235, 102, 205, 120, BLACK, DOT_PIXEL_1X1, LINE_STYLE_SOLID);

    Paint_DrawString_EN(16, 108, "Solid + outline primitives", &Font8, BLACK, WHITE);
    pushFull(true);
    DEV_Delay_ms(kShortHoldMs);
}

void sceneDataWidgets()
{
    prepareCanvas();
    drawHeader("Data Widgets");

    struct Card {
        const char *title;
        const char *value;
        const char *unit;
    };
    constexpr Card cards[] = {
        {"Temp", "24", "C"},
        {"Hum", "48", "%"},
        {"Battery", "3.92", "V"},
    };

    constexpr UWORD cardTop = 36;
    constexpr UWORD cardBottom = 112;
    constexpr UWORD cardWidth = 72;
    constexpr UWORD gap = 8;
    UWORD x = 12;

    for (const auto &card : cards) {
        UWORD right = x + cardWidth;
        Paint_DrawRectangle(x, cardTop, right, cardBottom, BLACK, DOT_PIXEL_1X1, DRAW_FILL_EMPTY);
        Paint_DrawString_EN(x + 6, cardTop + 6, card.title, &Font12, BLACK, WHITE);
        Paint_DrawString_EN(x + 6, cardTop + 30, card.value, &Font20, BLACK, WHITE);
        Paint_DrawString_EN(x + 6, cardBottom - 20, card.unit, &Font12, BLACK, WHITE);
        x = right + gap;
    }

    Paint_DrawString_EN(14, cardBottom + 2, "Compact widgets for dashboards", &Font8, BLACK, WHITE);
    pushFull(true);
    DEV_Delay_ms(kShortHoldMs);
}

void sceneTrend()
{
    prepareCanvas();
    drawHeader("24h Trend");

    constexpr int values[] = {12, 34, 28, 46, 60, 52, 38, 22};
    int maxValue = 0;
    for (int value : values) {
        if (value > maxValue) {
            maxValue = value;
        }
    }
    if (maxValue == 0) {
        maxValue = 1;
    }

    constexpr UWORD originX = 28;
    constexpr UWORD originY = 110;
    constexpr UWORD chartHeight = 64;
    constexpr UWORD barWidth = 16;
    constexpr UWORD spacing = 6;

    Paint_DrawLine(originX, originY - chartHeight, originX, originY, BLACK, DOT_PIXEL_1X1, LINE_STYLE_SOLID);
    Paint_DrawLine(originX, originY, originX + (barWidth + spacing) * (sizeof(values) / sizeof(values[0])) + 8,
                   originY, BLACK, DOT_PIXEL_1X1, LINE_STYLE_SOLID);

    for (size_t i = 0; i < sizeof(values) / sizeof(values[0]); ++i) {
        UWORD barHeight = static_cast<UWORD>((values[i] * chartHeight) / maxValue);
        UWORD left = originX + spacing + i * (barWidth + spacing);
        UWORD right = left + barWidth;
        UWORD barBottom = originY - 2;
        UWORD barTop = (barHeight >= 2U) ? static_cast<UWORD>(originY - barHeight) : static_cast<UWORD>(barBottom - 1);
        Paint_DrawRectangle(left, barTop, right, barBottom, BLACK, DOT_PIXEL_1X1, DRAW_FILL_FULL);

        char label[4];
        snprintf(label, sizeof(label), "%02u", static_cast<unsigned>(i * 3));
        Paint_DrawString_EN(left, originY + 4, label, &Font8, BLACK, WHITE);
    }

    Paint_DrawString_EN(originX, originY - chartHeight - 14, "Hourly samples (0-60)", &Font12, BLACK, WHITE);
    pushFull(true);
    DEV_Delay_ms(kMediumHoldMs);
}

void sceneBitmapShowcase()
{
    prepareCanvas();
    Paint_DrawBitMap(gImage_2in13);

    Paint_DrawRectangle(0, 0, Paint.Width - 1, 26, BLACK, DOT_PIXEL_1X1, DRAW_FILL_FULL);
    Paint_DrawString_EN(6, 4, "Bitmap Overlay", &Font16, WHITE, BLACK);

    Paint_ClearWindows(Paint.Width - 120, 34, Paint.Width - 12, 118, WHITE);
    Paint_DrawRectangle(Paint.Width - 120, 34, Paint.Width - 12, 118, BLACK, DOT_PIXEL_1X1, DRAW_FILL_EMPTY);
    Paint_DrawString_EN(Paint.Width - 112, 42, "Blend raw bitmaps", &Font12, BLACK, WHITE);
    Paint_DrawString_EN(Paint.Width - 112, 56, "with live widgets", &Font12, BLACK, WHITE);
    Paint_DrawString_EN(Paint.Width - 112, 70, "for rich layouts.", &Font12, BLACK, WHITE);
    Paint_DrawString_EN(Paint.Width - 112, 92, "Try icons, maps,", &Font12, BLACK, WHITE);
    Paint_DrawString_EN(Paint.Width - 112, 106, "and photo frames.", &Font12, BLACK, WHITE);

    pushFull(false);
    DEV_Delay_ms(kLongHoldMs);
}

void sceneProgressPartial()
{
    prepareCanvas();
    drawHeader("Partial Refresh");
    Paint_DrawString_EN(20, 40, "Progress indicator", &Font16, BLACK, WHITE);
    Paint_DrawString_EN(20, 58, "Fast updates without flicker", &Font12, BLACK, WHITE);

    constexpr UWORD barLeft = 32;
    constexpr UWORD barTop = 72;
    constexpr UWORD barRight = Paint.Width - 32;
    constexpr UWORD barBottom = 92;
    Paint_DrawRectangle(barLeft, barTop, barRight, barBottom, BLACK, DOT_PIXEL_1X1, DRAW_FILL_EMPTY);

    EPD_2in13_V4_Init();
    EPD_2in13_V4_Display_Base(sFrame);
    DEV_Delay_ms(250);

    for (int percent = 0; percent <= 100; percent += 20) {
        Paint_ClearWindows(barLeft + 2, barTop + 2, barRight - 2, barBottom - 2, WHITE);
        UWORD fillWidth = static_cast<UWORD>((barRight - barLeft - 4) * percent / 100);
        if (fillWidth > 0) {
            Paint_DrawRectangle(barLeft + 2, barTop + 2, barLeft + 2 + fillWidth, barBottom - 2,
                                BLACK, DOT_PIXEL_1X1, DRAW_FILL_FULL);
        }

        char label[8];
        snprintf(label, sizeof(label), "%3d%%", percent);
        Paint_ClearWindows(barRight - 58, barTop + 4, barRight - 8, barBottom - 4, WHITE);
        Paint_DrawString_EN(barRight - 58, barTop + 4, label, &Font12, BLACK, WHITE);

        EPD_2in13_V4_Display_Partial(sFrame);
        DEV_Delay_ms(600);
    }

    DEV_Delay_ms(900);
}

void sceneClockPartial()
{
    prepareCanvas();
    drawHeader("Live Clock");
    Paint_DrawString_EN(20, 40, "Digital time", &Font16, BLACK, WHITE);

    constexpr UWORD timeBoxLeft = 110;
    constexpr UWORD timeBoxTop = 50;
    constexpr UWORD timeBoxRight = Paint.Width - 18;
    constexpr UWORD timeBoxBottom = timeBoxTop + Font24.Height + 12;
    Paint_DrawRectangle(timeBoxLeft - 6, timeBoxTop - 6, timeBoxRight, timeBoxBottom,
                        BLACK, DOT_PIXEL_1X1, DRAW_FILL_EMPTY);

    constexpr UWORD secondsLeft = 20;
    constexpr UWORD secondsTop = 78;
    constexpr UWORD secondsRight = 100;
    constexpr UWORD secondsBottom = 110;
    Paint_DrawRectangle(secondsLeft, secondsTop, secondsRight, secondsBottom,
                        BLACK, DOT_PIXEL_1X1, DRAW_FILL_EMPTY);
    Paint_DrawString_EN(secondsLeft + 4, secondsTop - 16, "Second fill", &Font12, BLACK, WHITE);

    EPD_2in13_V4_Init();
    EPD_2in13_V4_Display_Base(sFrame);
    DEV_Delay_ms(250);

    PAINT_TIME clock{};
    clock.Year = 2024;
    clock.Month = 1;
    clock.Day = 1;
    clock.Hour = 10;
    clock.Min = 58;
    clock.Sec = 50;

    for (int tick = 0; tick < 12; ++tick) {
        clock.Sec += 1;
        if (clock.Sec >= 60) {
            clock.Sec = 0;
            clock.Min += 1;
            if (clock.Min >= 60) {
                clock.Min = 0;
                clock.Hour = (clock.Hour + 1) % 24;
            }
        }

        Paint_ClearWindows(timeBoxLeft, timeBoxTop, timeBoxRight - 6, timeBoxBottom - 6, WHITE);
        Paint_DrawTime(timeBoxLeft, timeBoxTop, &clock, &Font24, BLACK, WHITE);

        Paint_ClearWindows(secondsLeft + 2, secondsTop + 2, secondsRight - 2, secondsBottom - 2, WHITE);
        UWORD secFill = static_cast<UWORD>((secondsRight - secondsLeft - 4) * clock.Sec / 59);
        if (secFill > 0) {
            Paint_DrawRectangle(secondsLeft + 2, secondsTop + 2,
                                secondsLeft + 2 + secFill, secondsBottom - 2,
                                BLACK, DOT_PIXEL_1X1, DRAW_FILL_FULL);
        }

        EPD_2in13_V4_Display_Partial(sFrame);
        DEV_Delay_ms(750);
    }

    DEV_Delay_ms(1200);
}

void cycleCleanup()
{
    EPD_2in13_V4_Init();
    EPD_2in13_V4_Clear();
    EPD_2in13_V4_Sleep();
    DEV_Delay_ms(1500);
}

void init()
{
    if (!ensureFrame()) {
        while (true) {
            DEV_Delay_ms(1000);
        }
    }
    EPD_2in13_V4_Init();
    EPD_2in13_V4_Clear();
    EPD_2in13_V4_Sleep();
    DEV_Delay_ms(500);
}

void runCycle()
{
    if (!ensureFrame()) {
        DEV_Delay_ms(1000);
        return;
    }

    printf("Running EPD scene cycle\r\n");

    sceneWelcome();
    sceneShapeGallery();
    sceneDataWidgets();
    sceneTrend();
    sceneBitmapShowcase();
    sceneProgressPartial();
    sceneClockPartial();

    cycleCleanup();
}

} // namespace demo

void setup()
{
    printf("EPD 2.13\" multi-scene demo\r\n");
    DEV_Module_Init();
    demo::init();
}

void loop()
{
    demo::runCycle();
}
