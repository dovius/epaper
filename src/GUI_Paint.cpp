/******************************************************************************
* | File      	:   GUI_Paint.c
* | Author      :   Waveshare electronics
* | Function    :	Achieve drawing: draw points, lines, boxes, circles and
*                   their size, solid dotted line, solid rectangle hollow
*                   rectangle, solid circle hollow circle.
* | Info        :
*   Achieve display characters: Display a single character, string, number
*   Achieve time display: adaptive size display time minutes and seconds
*----------------
* |	This version:   V3.2
* | Date        :   2020-07-23
* | Info        :
* -----------------------------------------------------------------------------
* V3.2(2020-07-23):
* 1. Change: Paint_SetScale(UBYTE scale)
*			Add scale 7 for 5.65f e-Parper
* 2. Change: Paint_SetPixel(UWORD Xpoint, UWORD Ypoint, UWORD Color)  
* 			Add the branch for scale 7
* 3. Change: Paint_Clear(UWORD Color)
*			Add the branch for scale 7
*
* V3.1(2019-10-10):
* 1. Add gray level
*   PAINT Add Scale
* 2. Add void Paint_SetScale(UBYTE scale);
*
* V3.0(2019-04-18):
* 1.Change: 
*    Paint_DrawPoint(..., DOT_STYLE DOT_STYLE)
* => Paint_DrawPoint(..., DOT_STYLE Dot_Style)
*    Paint_DrawLine(..., LINE_STYLE Line_Style, DOT_PIXEL Dot_Pixel)
* => Paint_DrawLine(..., DOT_PIXEL Line_width, LINE_STYLE Line_Style)
*    Paint_DrawRectangle(..., DRAW_FILL Filled, DOT_PIXEL Dot_Pixel)
* => Paint_DrawRectangle(..., DOT_PIXEL Line_width, DRAW_FILL Draw_Fill)
*    Paint_DrawCircle(..., DRAW_FILL Draw_Fill, DOT_PIXEL Dot_Pixel)
* => Paint_DrawCircle(..., DOT_PIXEL Line_width, DRAW_FILL Draw_Filll)
*
* -----------------------------------------------------------------------------
* V2.0(2018-11-15):
* 1.add: Paint_NewImage()
*    Create an image's properties
* 2.add: Paint_SelectImage()
*    Select the picture to be drawn
* 3.add: Paint_SetRotate()
*    Set the direction of the cache    
* 4.add: Paint_RotateImage() 
*    Can flip the picture, Support 0-360 degrees, 
*    but only 90.180.270 rotation is better
* 4.add: Paint_SetMirroring() 
*    Can Mirroring the picture, horizontal, vertical, origin
* 5.add: Paint_DrawString_CN() 
*    Can display Chinese(GB1312)   
*
* ----------------------------------------------------------------------------- 
* V1.0(2018-07-17):
*   Create library
*
* Permission is hereby granted, free of charge, to any person obtaining a copy
* of this software and associated documnetation files (the "Software"), to deal
* in the Software without restriction, including without limitation the rights
* to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
* copies of the Software, and to permit persons to  whom the Software is
* furished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in
* all copies or substantial portions of the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
* IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
* FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
* LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
* OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
* THE SOFTWARE.
*
******************************************************************************/
#include "GUI_Paint.h"
#include "DEV_Config.h"
#include "utility/Debug.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h> //memset()
#include <math.h>
#include <stdio.h>

PAINT Paint;

namespace {

constexpr UBYTE kScaleMonochrome = 2;
constexpr UBYTE kScaleGray4 = 4;
constexpr UBYTE kScaleFiveInch65 = 7;
constexpr UBYTE kScaleGray16 = 16;

inline bool paint_ready()
{
    if (Paint.Image != NULL) {
        return true;
    }
    Debug("Paint image buffer not initialized\r\n");
    return false;
}

inline bool within_canvas(UWORD x, UWORD y)
{
    return x < Paint.Width && y < Paint.Height;
}

bool transform_to_memory(UWORD& x, UWORD& y)
{
    UWORD x_mem = x;
    UWORD y_mem = y;

    switch (Paint.Rotate) {
    case ROTATE_0:
        break;
    case ROTATE_90:
        x_mem = Paint.WidthMemory - y - 1;
        y_mem = x;
        break;
    case ROTATE_180:
        x_mem = Paint.WidthMemory - x - 1;
        y_mem = Paint.HeightMemory - y - 1;
        break;
    case ROTATE_270:
        x_mem = y;
        y_mem = Paint.HeightMemory - x - 1;
        break;
    default:
        return false;
    }

    switch (Paint.Mirror) {
    case MIRROR_NONE:
        break;
    case MIRROR_HORIZONTAL:
        x_mem = Paint.WidthMemory - x_mem - 1;
        break;
    case MIRROR_VERTICAL:
        y_mem = Paint.HeightMemory - y_mem - 1;
        break;
    case MIRROR_ORIGIN:
        x_mem = Paint.WidthMemory - x_mem - 1;
        y_mem = Paint.HeightMemory - y_mem - 1;
        break;
    default:
        return false;
    }

    if (x_mem >= Paint.WidthMemory || y_mem >= Paint.HeightMemory) {
        return false;
    }

    x = x_mem;
    y = y_mem;
    return true;
}

inline void write_pixel_to_buffer(UWORD x, UWORD y, UWORD color)
{
    switch (Paint.Scale) {
    case kScaleMonochrome: {
        UDOUBLE addr = x / 8 + static_cast<UDOUBLE>(y) * Paint.WidthByte;
        UBYTE mask = static_cast<UBYTE>(0x80 >> (x % 8));
        UBYTE& target = Paint.Image[addr];
        if (color == BLACK) {
            target = static_cast<UBYTE>(target & ~mask);
        } else {
            target = static_cast<UBYTE>(target | mask);
        }
        break;
    }
    case kScaleGray4: {
        UDOUBLE addr = x / 4 + static_cast<UDOUBLE>(y) * Paint.WidthByte;
        UBYTE shift = static_cast<UBYTE>((x % 4) * 2);
        UBYTE mask = static_cast<UBYTE>(0xC0 >> shift);
        UBYTE encoded = static_cast<UBYTE>(((color & 0x03U) << 6) >> shift);
        UBYTE& target = Paint.Image[addr];
        target = static_cast<UBYTE>((target & ~mask) | (encoded & mask));
        break;
    }
    case kScaleFiveInch65:
    case kScaleGray16: {
        UDOUBLE addr = x / 2 + static_cast<UDOUBLE>(y) * Paint.WidthByte;
        UBYTE shift = static_cast<UBYTE>((x % 2) * 4);
        UBYTE mask = static_cast<UBYTE>(0xF0 >> shift);
        UBYTE encoded = static_cast<UBYTE>(((color & 0x0FU) << 4) >> shift);
        UBYTE& target = Paint.Image[addr];
        target = static_cast<UBYTE>((target & ~mask) | (encoded & mask));
        break;
    }
    default:
        break;
    }
}

inline UDOUBLE total_buffer_size()
{
    return static_cast<UDOUBLE>(Paint.WidthByte) * Paint.HeightByte;
}

inline void clamp_window(UWORD& start, UWORD& end, UWORD limit)
{
    if (start > end) {
        UWORD tmp = start;
        start = end;
        end = tmp;
    }
    if (start >= limit) {
        start = limit;
    }
    if (end > limit) {
        end = limit;
    }
}

} // namespace

/******************************************************************************
function: Create Image
parameter:
    image   :   Pointer to the image cache
    width   :   The width of the picture
    Height  :   The height of the picture
    Color   :   Whether the picture is inverted
******************************************************************************/
void Paint_NewImage(UBYTE *image, UWORD Width, UWORD Height, UWORD Rotate, UWORD Color)
{
    Paint.Image = image;
    Paint.WidthMemory = Width;
    Paint.HeightMemory = Height;
    Paint.Color = Color;
    Paint.Scale = kScaleMonochrome;
    Paint_SetScale(kScaleMonochrome);
    Paint.HeightByte = Height;
    Paint.Rotate = ROTATE_0;
    Paint.Mirror = MIRROR_NONE;

    if (image == NULL) {
        Debug("Paint_NewImage image buffer is null\r\n");
        return;
    }

    Paint_SetRotate(Rotate);
}

/******************************************************************************
function: Select Image
parameter:
    image : Pointer to the image cache
******************************************************************************/
void Paint_SelectImage(UBYTE *image)
{
    Paint.Image = image;
    if (image == NULL) {
        Debug("Paint_SelectImage image buffer is null\r\n");
    }
}

/******************************************************************************
function: Select Image Rotate
parameter:
    Rotate : 0,90,180,270
******************************************************************************/
void Paint_SetRotate(UWORD Rotate)
{
    switch (Rotate) {
    case ROTATE_0:
    case ROTATE_180:
        Paint.Rotate = Rotate;
        Paint.Width = Paint.WidthMemory;
        Paint.Height = Paint.HeightMemory;
        break;
    case ROTATE_90:
    case ROTATE_270:
        Paint.Rotate = Rotate;
        Paint.Width = Paint.HeightMemory;
        Paint.Height = Paint.WidthMemory;
        break;
    default:
        Debug("rotate = 0, 90, 180, 270\r\n");
        break;
    }
}

/******************************************************************************
function:	Select Image mirror
parameter:
    mirror   :Not mirror,Horizontal mirror,Vertical mirror,Origin mirror
******************************************************************************/
void Paint_SetMirroring(UBYTE mirror)
{
    if(mirror == MIRROR_NONE || mirror == MIRROR_HORIZONTAL || 
        mirror == MIRROR_VERTICAL || mirror == MIRROR_ORIGIN) {
        // Debug("mirror image x:%s, y:%s\r\n",(mirror & 0x01)? "mirror":"none", ((mirror >> 1) & 0x01)? "mirror":"none");
        Paint.Mirror = mirror;
    } else {
        Debug("mirror should be MIRROR_NONE, MIRROR_HORIZONTAL, \
        MIRROR_VERTICAL or MIRROR_ORIGIN\r\n");
    }    
}

void Paint_SetScale(UBYTE scale)
{
    switch (scale) {
    case kScaleMonochrome:
        Paint.Scale = kScaleMonochrome;
        Paint.WidthByte = (Paint.WidthMemory % 8 == 0)? (Paint.WidthMemory / 8 ): (Paint.WidthMemory / 8 + 1);
        break;
    case kScaleGray4:
        Paint.Scale = kScaleGray4;
        Paint.WidthByte = (Paint.WidthMemory % 4 == 0)? (Paint.WidthMemory / 4 ): (Paint.WidthMemory / 4 + 1);
        break;
    case kScaleFiveInch65:
    case kScaleGray16:
        Paint.Scale = scale;
        Paint.WidthByte = (Paint.WidthMemory % 2 == 0)? (Paint.WidthMemory / 2 ): (Paint.WidthMemory / 2 + 1);
        break;
    default:
        Debug("Set Scale Input parameter error\r\n");
        Debug("Scale Only support: 2 4 7 16\r\n");
        break;
    }
}
/******************************************************************************
function: Draw Pixels
parameter:
    Xpoint : At point X
    Ypoint : At point Y
    Color  : Painted colors
******************************************************************************/
void Paint_SetPixel(UWORD Xpoint, UWORD Ypoint, UWORD Color)
{
    if (!paint_ready()) {
        return;
    }
    if (!within_canvas(Xpoint, Ypoint)) {
        Debug("Exceeding display boundaries\r\n");
        return;
    }

    if (!transform_to_memory(Xpoint, Ypoint)) {
        Debug("Exceeding display boundaries\r\n");
        return;
    }

    write_pixel_to_buffer(Xpoint, Ypoint, Color);
}

/******************************************************************************
function: Clear the color of the picture
parameter:
    Color : Painted colors
******************************************************************************/
void Paint_Clear(UWORD Color)
{
    if (!paint_ready()) {
        return;
    }

    const UDOUBLE size = total_buffer_size();
    if (size == 0) {
        return;
    }

    switch (Paint.Scale) {
    case kScaleMonochrome: {
        UBYTE pattern = static_cast<UBYTE>(Color);
        memset(Paint.Image, pattern, static_cast<size_t>(size));
        break;
    }
    case kScaleGray4: {
        UBYTE shade = static_cast<UBYTE>(Color & 0x03U);
        UBYTE pattern = static_cast<UBYTE>((shade << 6) | (shade << 4) | (shade << 2) | shade);
        for (UDOUBLE i = 0; i < size; ++i) {
            Paint.Image[i] = pattern;
        }
        break;
    }
    case kScaleFiveInch65:
    case kScaleGray16: {
        UBYTE shade = static_cast<UBYTE>(Color & 0x0FU);
        UBYTE pattern = static_cast<UBYTE>((shade << 4) | shade);
        for (UDOUBLE i = 0; i < size; ++i) {
            Paint.Image[i] = pattern;
        }
        break;
    }
    default:
        break;
    }
}

/******************************************************************************
function: Clear the color of a window
parameter:
    Xstart : x starting point
    Ystart : Y starting point
    Xend   : x end point
    Yend   : y end point
    Color  : Painted colors
******************************************************************************/
void Paint_ClearWindows(UWORD Xstart, UWORD Ystart, UWORD Xend, UWORD Yend, UWORD Color)
{
    if (!paint_ready()) {
        return;
    }
    clamp_window(Xstart, Xend, Paint.Width);
    clamp_window(Ystart, Yend, Paint.Height);

    if (Xstart >= Xend || Ystart >= Yend) {
        return;
    }

    for (UWORD y = Ystart; y < Yend; ++y) {
        for (UWORD x = Xstart; x < Xend; ++x) {
            Paint_SetPixel(x, y, Color);
        }
    }
}

/******************************************************************************
function: Draw Point(Xpoint, Ypoint) Fill the color
parameter:
    Xpoint		: The Xpoint coordinate of the point
    Ypoint		: The Ypoint coordinate of the point
    Color		: Painted color
    Dot_Pixel	: point size
    Dot_Style	: point Style
******************************************************************************/
void Paint_DrawPoint(UWORD Xpoint, UWORD Ypoint, UWORD Color,
                     DOT_PIXEL Dot_Pixel, DOT_STYLE Dot_Style)
{
    if (!paint_ready()) {
        return;
    }

    if (!within_canvas(Xpoint, Ypoint)) {
        Debug("Paint_DrawPoint Input exceeds the normal display range\r\n");
        return;
    }

    if (Dot_Pixel < DOT_PIXEL_1X1) {
        Dot_Pixel = DOT_PIXEL_1X1;
    }

    int32_t radius = static_cast<int32_t>(Dot_Pixel);
    int32_t base_x = static_cast<int32_t>(Xpoint);
    int32_t base_y = static_cast<int32_t>(Ypoint);

    if (Dot_Style == DOT_FILL_AROUND) {
        for (int32_t dx = 0; dx < 2 * radius - 1; ++dx) {
            for (int32_t dy = 0; dy < 2 * radius - 1; ++dy) {
                int32_t px = base_x + dx - radius;
                int32_t py = base_y + dy - radius;
                if (px < 0 || py < 0 ||
                    px >= static_cast<int32_t>(Paint.Width) ||
                    py >= static_cast<int32_t>(Paint.Height)) {
                    continue;
                }
                Paint_SetPixel(static_cast<UWORD>(px), static_cast<UWORD>(py), Color);
            }
        }
    } else {
        for (int32_t dx = 0; dx < radius; ++dx) {
            for (int32_t dy = 0; dy < radius; ++dy) {
                int32_t px = base_x + dx - 1;
                int32_t py = base_y + dy - 1;
                if (px < 0 || py < 0 ||
                    px >= static_cast<int32_t>(Paint.Width) ||
                    py >= static_cast<int32_t>(Paint.Height)) {
                    continue;
                }
                Paint_SetPixel(static_cast<UWORD>(px), static_cast<UWORD>(py), Color);
            }
        }
    }
}

/******************************************************************************
function: Draw a line of arbitrary slope
parameter:
    Xstart ：Starting Xpoint point coordinates
    Ystart ：Starting Xpoint point coordinates
    Xend   ：End point Xpoint coordinate
    Yend   ：End point Ypoint coordinate
    Color  ：The color of the line segment
    Line_width : Line width
    Line_Style: Solid and dotted lines
******************************************************************************/
void Paint_DrawLine(UWORD Xstart, UWORD Ystart, UWORD Xend, UWORD Yend,
                    UWORD Color, DOT_PIXEL Line_width, LINE_STYLE Line_Style)
{
    if (!paint_ready()) {
        return;
    }

    if (!within_canvas(Xstart, Ystart) || !within_canvas(Xend, Yend)) {
        Debug("Paint_DrawLine Input exceeds the normal display range\r\n");
        return;
    }

    int32_t x0 = static_cast<int32_t>(Xstart);
    int32_t y0 = static_cast<int32_t>(Ystart);
    const int32_t x1 = static_cast<int32_t>(Xend);
    const int32_t y1 = static_cast<int32_t>(Yend);

    int32_t dx = abs(x1 - x0);
    int32_t sx = x0 < x1 ? 1 : -1;
    int32_t dy = -abs(y1 - y0);
    int32_t sy = y0 < y1 ? 1 : -1;
    int32_t err = dx + dy;
    int dotted_len = 0;

    while (true) {
        ++dotted_len;
        if (Line_Style == LINE_STYLE_DOTTED && dotted_len % 3 == 0) {
            Paint_DrawPoint(static_cast<UWORD>(x0), static_cast<UWORD>(y0),
                            IMAGE_BACKGROUND, Line_width, DOT_STYLE_DFT);
            dotted_len = 0;
        } else {
            Paint_DrawPoint(static_cast<UWORD>(x0), static_cast<UWORD>(y0),
                            Color, Line_width, DOT_STYLE_DFT);
        }

        if (x0 == x1 && y0 == y1) {
            break;
        }

        int32_t e2 = err << 1;
        if (e2 >= dy) {
            err += dy;
            x0 += sx;
        }
        if (e2 <= dx) {
            err += dx;
            y0 += sy;
        }
    }
}

/******************************************************************************
function: Draw a rectangle
parameter:
    Xstart ：Rectangular  Starting Xpoint point coordinates
    Ystart ：Rectangular  Starting Xpoint point coordinates
    Xend   ：Rectangular  End point Xpoint coordinate
    Yend   ：Rectangular  End point Ypoint coordinate
    Color  ：The color of the Rectangular segment
    Line_width: Line width
    Draw_Fill : Whether to fill the inside of the rectangle
******************************************************************************/
void Paint_DrawRectangle(UWORD Xstart, UWORD Ystart, UWORD Xend, UWORD Yend,
                         UWORD Color, DOT_PIXEL Line_width, DRAW_FILL Draw_Fill)
{
    if (!paint_ready()) {
        return;
    }

    if (!within_canvas(Xstart, Ystart) || !within_canvas(Xend, Yend)) {
        Debug("Input exceeds the normal display range\r\n");
        return;
    }

    if (Xstart > Xend) {
        UWORD tmp = Xstart;
        Xstart = Xend;
        Xend = tmp;
    }
    if (Ystart > Yend) {
        UWORD tmp = Ystart;
        Ystart = Yend;
        Yend = tmp;
    }

    if (Draw_Fill) {
        for (UWORD y = Ystart; y < Yend; ++y) {
            Paint_DrawLine(Xstart, y, Xend, y, Color , Line_width, LINE_STYLE_SOLID);
        }
    } else {
        Paint_DrawLine(Xstart, Ystart, Xend, Ystart, Color, Line_width, LINE_STYLE_SOLID);
        Paint_DrawLine(Xstart, Ystart, Xstart, Yend, Color, Line_width, LINE_STYLE_SOLID);
        Paint_DrawLine(Xend, Yend, Xend, Ystart, Color, Line_width, LINE_STYLE_SOLID);
        Paint_DrawLine(Xend, Yend, Xstart, Yend, Color, Line_width, LINE_STYLE_SOLID);
    }
}

/******************************************************************************
function: Use the 8-point method to draw a circle of the
            specified size at the specified position->
parameter:
    X_Center  ：Center X coordinate
    Y_Center  ：Center Y coordinate
    Radius    ：circle Radius
    Color     ：The color of the ：circle segment
    Line_width: Line width
    Draw_Fill : Whether to fill the inside of the Circle
******************************************************************************/
void Paint_DrawCircle(UWORD X_Center, UWORD Y_Center, UWORD Radius,
                      UWORD Color, DOT_PIXEL Line_width, DRAW_FILL Draw_Fill)
{
    if (!paint_ready()) {
        return;
    }

    if (!within_canvas(X_Center, Y_Center)) {
        Debug("Paint_DrawCircle Input exceeds the normal display range\r\n");
        return;
    }

    //Draw a circle from(0, R) as a starting point
    int16_t XCurrent, YCurrent;
    XCurrent = 0;
    YCurrent = Radius;

    //Cumulative error,judge the next point of the logo
    int16_t Esp = 3 - (Radius << 1 );

    auto draw_point_safe = [&](int32_t x, int32_t y, DOT_PIXEL width) {
        if (x < 0 || y < 0 ||
            x >= static_cast<int32_t>(Paint.Width) ||
            y >= static_cast<int32_t>(Paint.Height)) {
            return;
        }
        Paint_DrawPoint(static_cast<UWORD>(x), static_cast<UWORD>(y), Color, width, DOT_STYLE_DFT);
    };

    int16_t sCountY;
    if (Draw_Fill == DRAW_FILL_FULL) {
        while (XCurrent <= YCurrent ) { //Realistic circles
            for (sCountY = XCurrent; sCountY <= YCurrent; sCountY ++ ) {
                draw_point_safe(X_Center + XCurrent, Y_Center + sCountY, DOT_PIXEL_DFT);
                draw_point_safe(X_Center - XCurrent, Y_Center + sCountY, DOT_PIXEL_DFT);
                draw_point_safe(X_Center - sCountY, Y_Center + XCurrent, DOT_PIXEL_DFT);
                draw_point_safe(X_Center - sCountY, Y_Center - XCurrent, DOT_PIXEL_DFT);
                draw_point_safe(X_Center - XCurrent, Y_Center - sCountY, DOT_PIXEL_DFT);
                draw_point_safe(X_Center + XCurrent, Y_Center - sCountY, DOT_PIXEL_DFT);
                draw_point_safe(X_Center + sCountY, Y_Center - XCurrent, DOT_PIXEL_DFT);
                draw_point_safe(X_Center + sCountY, Y_Center + XCurrent, DOT_PIXEL_DFT);
            }
            if (Esp < 0 )
                Esp += 4 * XCurrent + 6;
            else {
                Esp += 10 + 4 * (XCurrent - YCurrent );
                YCurrent --;
            }
            XCurrent ++;
        }
    } else { //Draw a hollow circle
        while (XCurrent <= YCurrent ) {
            draw_point_safe(X_Center + XCurrent, Y_Center + YCurrent, Line_width);
            draw_point_safe(X_Center - XCurrent, Y_Center + YCurrent, Line_width);
            draw_point_safe(X_Center - YCurrent, Y_Center + XCurrent, Line_width);
            draw_point_safe(X_Center - YCurrent, Y_Center - XCurrent, Line_width);
            draw_point_safe(X_Center - XCurrent, Y_Center - YCurrent, Line_width);
            draw_point_safe(X_Center + XCurrent, Y_Center - YCurrent, Line_width);
            draw_point_safe(X_Center + YCurrent, Y_Center - XCurrent, Line_width);
            draw_point_safe(X_Center + YCurrent, Y_Center + XCurrent, Line_width);

            if (Esp < 0 )
                Esp += 4 * XCurrent + 6;
            else {
                Esp += 10 + 4 * (XCurrent - YCurrent );
                YCurrent --;
            }
            XCurrent ++;
        }
    }
}

/******************************************************************************
function: Show English characters
parameter:
    Xpoint           ：X coordinate
    Ypoint           ：Y coordinate
    Acsii_Char       ：To display the English characters
    Font             ：A structure pointer that displays a character size
    Color_Foreground : Select the foreground color
    Color_Background : Select the background color
******************************************************************************/
void Paint_DrawChar(UWORD Xpoint, UWORD Ypoint, const char Acsii_Char,
                    sFONT* Font, UWORD Color_Foreground, UWORD Color_Background)
{
    if (!paint_ready()) {
        return;
    }

    if (Font == NULL || Font->table == NULL) {
        Debug("Paint_DrawChar font data is null\r\n");
        return;
    }

    if (!within_canvas(Xpoint, Ypoint)) {
        Debug("Paint_DrawChar Input exceeds the normal display range\r\n");
        return;
    }

    if ((Xpoint + Font->Width > Paint.Width) || (Ypoint + Font->Height > Paint.Height)) {
        Debug("Paint_DrawChar exceeds display bounds\r\n");
        return;
    }

    uint32_t char_offset = (Acsii_Char - ' ') * Font->Height *
                           (Font->Width / 8 + (Font->Width % 8 ? 1 : 0));
    const UBYTE *ptr = &Font->table[char_offset];

    for (UWORD page = 0; page < Font->Height; ++page) {
        for (UWORD column = 0; column < Font->Width; ++column) {
            bool pixel_on = (*ptr & (0x80 >> (column % 8))) != 0;
            if (pixel_on) {
                Paint_SetPixel(Xpoint + column, Ypoint + page, Color_Foreground);
            } else if (Color_Background != FONT_BACKGROUND) {
                Paint_SetPixel(Xpoint + column, Ypoint + page, Color_Background);
            }

            if (column % 8 == 7) {
                ++ptr;
            }
        }
        if (Font->Width % 8 != 0) {
            ++ptr;
        }
    }
}

/******************************************************************************
function:	Display the string
parameter:
    Xstart           ：X coordinate
    Ystart           ：Y coordinate
    pString          ：The first address of the English string to be displayed
    Font             ：A structure pointer that displays a character size
    Color_Foreground : Select the foreground color
    Color_Background : Select the background color
******************************************************************************/
void Paint_DrawString_EN(UWORD Xstart, UWORD Ystart, const char * pString,
                         sFONT* Font, UWORD Color_Foreground, UWORD Color_Background)
{
    UWORD Xpoint = Xstart;
    UWORD Ypoint = Ystart;

    if (!paint_ready()) {
        return;
    }

    if (pString == NULL || Font == NULL) {
        Debug("Paint_DrawString_EN invalid input\r\n");
        return;
    }

    if (!within_canvas(Xstart, Ystart)) {
        Debug("Paint_DrawString_EN Input exceeds the normal display range\r\n");
        return;
    }

    while (* pString != '\0') {
        //if X direction filled , reposition to(Xstart,Ypoint),Ypoint is Y direction plus the Height of the character
        if ((Xpoint + Font->Width ) > Paint.Width ) {
            Xpoint = Xstart;
            Ypoint += Font->Height;
        }

        // If the Y direction is full, reposition to(Xstart, Ystart)
        if ((Ypoint  + Font->Height ) > Paint.Height ) {
            Xpoint = Xstart;
            Ypoint = Ystart;
        }
        Paint_DrawChar(Xpoint, Ypoint, * pString, Font, Color_Foreground, Color_Background);

        //The next character of the address
        pString ++;

        //The next word of the abscissa increases the font of the broadband
        Xpoint += Font->Width;
    }
}


/******************************************************************************
function: Display the string
parameter:
    Xstart  ：X coordinate
    Ystart  ：Y coordinate
    pString ：The first address of the Chinese string and English
              string to be displayed
    Font    ：A structure pointer that displays a character size
    Color_Foreground : Select the foreground color
    Color_Background : Select the background color
******************************************************************************/
void Paint_DrawString_CN(UWORD Xstart, UWORD Ystart, const char * pString, cFONT* font,
                        UWORD Color_Foreground, UWORD Color_Background)
{
    if (!paint_ready()) {
        return;
    }
    if (pString == NULL || font == NULL || font->table == NULL) {
        Debug("Paint_DrawString_CN invalid input\r\n");
        return;
    }
    if (!within_canvas(Xstart, Ystart)) {
        Debug("Paint_DrawString_CN Input exceeds the normal display range\r\n");
        return;
    }

    const char* p_text = pString;
    int x = Xstart, y = Ystart;
    int i, j,Num;

    /* Send the string character by character on EPD */
    while (*p_text != 0) {
        if(*p_text <= 0x7F) {  //ASCII < 126
            for(Num = 0; Num < font->size; Num++) {
                if(*p_text== font->table[Num].index[0]) {
                    const char* ptr = &font->table[Num].matrix[0];

                    for (j = 0; j < font->Height; j++) {
                        for (i = 0; i < font->Width; i++) {
                            int draw_x = x + i;
                            int draw_y = y + j;
                            if (draw_x < 0 || draw_y < 0 ||
                                draw_x >= static_cast<int>(Paint.Width) ||
                                draw_y >= static_cast<int>(Paint.Height)) {
                                if (i % 8 == 7) {
                                    ptr++;
                                }
                                continue;
                            }
                            if (FONT_BACKGROUND == Color_Background) { //this process is to speed up the scan
                                if (*ptr & (0x80 >> (i % 8))) {
                                    Paint_SetPixel(static_cast<UWORD>(draw_x), static_cast<UWORD>(draw_y), Color_Foreground);
                                    // Paint_DrawPoint(x + i, y + j, Color_Foreground, DOT_PIXEL_DFT, DOT_STYLE_DFT);
                                }
                            } else {
                                if (*ptr & (0x80 >> (i % 8))) {
                                    Paint_SetPixel(static_cast<UWORD>(draw_x), static_cast<UWORD>(draw_y), Color_Foreground);
                                    // Paint_DrawPoint(x + i, y + j, Color_Foreground, DOT_PIXEL_DFT, DOT_STYLE_DFT);
                                } else {
                                    Paint_SetPixel(static_cast<UWORD>(draw_x), static_cast<UWORD>(draw_y), Color_Background);
                                    // Paint_DrawPoint(x + i, y + j, Color_Background, DOT_PIXEL_DFT, DOT_STYLE_DFT);
                                }
                            }
                            if (i % 8 == 7) {
                                ptr++;
                            }
                        }
                        if (font->Width % 8 != 0) {
                            ptr++;
                        }
                    }
                    break;
                }
            }
            /* Point on the next character */
            p_text += 1;
            /* Decrement the column position by 16 */
            x += font->ASCII_Width;
        } else {        //Chinese
            for(Num = 0; Num < font->size; Num++) {
                if ((*p_text == font->table[Num].index[0]) && \
                    (*(p_text + 1) == font->table[Num].index[1]) && \
                    (*(p_text + 2) == font->table[Num].index[2])) {
                    const char* ptr = &font->table[Num].matrix[0];

                    for (j = 0; j < font->Height; j++) {
                        for (i = 0; i < font->Width; i++) {
                            int draw_x = x + i;
                            int draw_y = y + j;
                            if (draw_x < 0 || draw_y < 0 ||
                                draw_x >= static_cast<int>(Paint.Width) ||
                                draw_y >= static_cast<int>(Paint.Height)) {
                                if (i % 8 == 7) {
                                    ptr++;
                                }
                                continue;
                            }
                            if (FONT_BACKGROUND == Color_Background) { //this process is to speed up the scan
                                if (*ptr & (0x80 >> (i % 8))) {
                                    Paint_SetPixel(static_cast<UWORD>(draw_x), static_cast<UWORD>(draw_y), Color_Foreground);
                                    // Paint_DrawPoint(x + i, y + j, Color_Foreground, DOT_PIXEL_DFT, DOT_STYLE_DFT);
                                }
                            } else {
                                if (*ptr & (0x80 >> (i % 8))) {
                                    Paint_SetPixel(static_cast<UWORD>(draw_x), static_cast<UWORD>(draw_y), Color_Foreground);
                                    // Paint_DrawPoint(x + i, y + j, Color_Foreground, DOT_PIXEL_DFT, DOT_STYLE_DFT);
                                } else {
                                    Paint_SetPixel(static_cast<UWORD>(draw_x), static_cast<UWORD>(draw_y), Color_Background);
                                    // Paint_DrawPoint(x + i, y + j, Color_Background, DOT_PIXEL_DFT, DOT_STYLE_DFT);
                                }
                            }
                            if (i % 8 == 7) {
                                ptr++;
                            }
                        }
                        if (font->Width % 8 != 0) {
                            ptr++;
                        }
                    }
                    break;
                }
            }
            /* Point on the next character */
            p_text += 3;
            /* Decrement the column position by 16 */
            x += font->Width;
        }
    }
}

/******************************************************************************
function:	Display nummber
parameter:
    Xstart           ：X coordinate
    Ystart           : Y coordinate
    Nummber          : The number displayed
    Font             ：A structure pointer that displays a character size
    Color_Foreground : Select the foreground color
    Color_Background : Select the background color
******************************************************************************/
#define  ARRAY_LEN 255
void Paint_DrawNum(UWORD Xpoint, UWORD Ypoint, int32_t Nummber,
                   sFONT* Font, UWORD Color_Foreground, UWORD Color_Background)
{
    if (!paint_ready()) {
        return;
    }

    if (Font == NULL) {
        Debug("Paint_DrawNum font pointer is null\r\n");
        return;
    }

    if (!within_canvas(Xpoint, Ypoint)) {
        Debug("Paint_DisNum Input exceeds the normal display range\r\n");
        return;
    }

    char buffer[ARRAY_LEN];
    int written = snprintf(buffer, sizeof(buffer), "%ld", static_cast<long>(Nummber));
    if (written < 0) {
        Debug("Paint_DrawNum snprintf failed\r\n");
        return;
    }
    if (written >= static_cast<int>(sizeof(buffer))) {
        buffer[sizeof(buffer) - 1] = '\0';
    }

    Paint_DrawString_EN(Xpoint, Ypoint, buffer, Font, Color_Foreground, Color_Background);
}

/******************************************************************************
function:	Display time
parameter:
    Xstart           ：X coordinate
    Ystart           : Y coordinate
    pTime            : Time-related structures
    Font             ：A structure pointer that displays a character size
    Color_Foreground : Select the foreground color
    Color_Background : Select the background color
******************************************************************************/
void Paint_DrawTime(UWORD Xstart, UWORD Ystart, PAINT_TIME *pTime, sFONT* Font,
                    UWORD Color_Foreground, UWORD Color_Background)
{
    if (!paint_ready()) {
        return;
    }

    if (Font == NULL || pTime == NULL) {
        Debug("Paint_DrawTime invalid input\r\n");
        return;
    }

    if (!within_canvas(Xstart, Ystart)) {
        Debug("Paint_DrawTime Input exceeds the normal display range\r\n");
        return;
    }

    uint8_t value[10] = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'};

    UWORD Dx = Font->Width;

    //Write data into the cache
    Paint_DrawChar(Xstart                           , Ystart, value[pTime->Hour / 10], Font, Color_Foreground, Color_Background);
    Paint_DrawChar(Xstart + Dx                      , Ystart, value[pTime->Hour % 10], Font, Color_Foreground, Color_Background);
    Paint_DrawChar(Xstart + Dx  + Dx / 4 + Dx / 2   , Ystart, ':'                    , Font, Color_Foreground, Color_Background);
    Paint_DrawChar(Xstart + Dx * 2 + Dx / 2         , Ystart, value[pTime->Min / 10] , Font, Color_Foreground, Color_Background);
    Paint_DrawChar(Xstart + Dx * 3 + Dx / 2         , Ystart, value[pTime->Min % 10] , Font, Color_Foreground, Color_Background);
    Paint_DrawChar(Xstart + Dx * 4 + Dx / 2 - Dx / 4, Ystart, ':'                    , Font, Color_Foreground, Color_Background);
    Paint_DrawChar(Xstart + Dx * 5                  , Ystart, value[pTime->Sec / 10] , Font, Color_Foreground, Color_Background);
    Paint_DrawChar(Xstart + Dx * 6                  , Ystart, value[pTime->Sec % 10] , Font, Color_Foreground, Color_Background);
}

/******************************************************************************
function:	Display monochrome bitmap
parameter:
    image_buffer ：A picture data converted to a bitmap
info:
    Use a computer to convert the image into a corresponding array,
    and then embed the array directly into Imagedata.cpp as a .c file.
******************************************************************************/
void Paint_DrawBitMap(const UBYTE* image_buffer)
{
    if (!paint_ready()) {
        return;
    }
    if (image_buffer == NULL) {
        Debug("Paint_DrawBitMap image buffer is null\r\n");
        return;
    }

    const UDOUBLE size = total_buffer_size();
    memcpy(Paint.Image, image_buffer, static_cast<size_t>(size));
}

/******************************************************************************
function:	Display image
parameter:
    image            ：Image start address
    xStart           : X starting coordinates
    yStart           : Y starting coordinates
    xEnd             ：Image width
    yEnd             : Image height
******************************************************************************/
void Paint_DrawImage(const UBYTE *image_buffer, UWORD xStart, UWORD yStart, UWORD W_Image, UWORD H_Image) 
{
    if (!paint_ready()) {
        return;
    }
    if (image_buffer == NULL) {
        Debug("Paint_DrawImage image buffer is null\r\n");
        return;
    }
    if (!within_canvas(xStart, yStart)) {
        Debug("Paint_DrawImage start coordinate exceeds bounds\r\n");
        return;
    }

    if (W_Image == 0 || H_Image == 0) {
        return;
    }

    if (xStart >= Paint.Width || yStart >= Paint.Height) {
        return;
    }

    if (xStart + W_Image > Paint.Width) {
        W_Image = Paint.Width - xStart;
    }
    if (yStart + H_Image > Paint.Height) {
        H_Image = Paint.Height - yStart;
    }

    if (Paint.Scale != kScaleMonochrome) {
        Debug("Paint_DrawImage currently supports scale 2 bitmaps\r\n");
        return;
    }

    UWORD w_byte = (W_Image % 8 == 0)? (W_Image / 8 ): (W_Image / 8 + 1);
    if ((xStart % 8 != 0) || (W_Image % 8 != 0)) {
        for (UWORD y = 0; y < H_Image; ++y) {
            for (UWORD x = 0; x < W_Image; ++x) {
                UDOUBLE src = (x / 8) + static_cast<UDOUBLE>(y) * w_byte;
                UBYTE data = image_buffer[src];
                UWORD color = (data & (0x80 >> (x % 8))) ? WHITE : BLACK;
                Paint_SetPixel(xStart + x, yStart + y, color);
            }
        }
        return;
    }

    for (UWORD y = 0; y < H_Image; ++y) {
        for (UWORD x = 0; x < w_byte; ++x) {
            UDOUBLE src = x + static_cast<UDOUBLE>(y) * w_byte;
            UDOUBLE dst = x + (xStart / 8) + static_cast<UDOUBLE>(yStart + y) * Paint.WidthByte;
            if (dst < total_buffer_size()) {
                Paint.Image[dst] = image_buffer[src];
            }
        }
    }
}
