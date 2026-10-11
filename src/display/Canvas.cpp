/*****************************************************************************
 * Canvas.cpp - High-level graphics implementation
 *****************************************************************************/
#include "Canvas.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// Include font definitions
#include "../fonts.h"

namespace display {

// Global instance
Canvas canvas;

Canvas::Canvas()
    : m_buffer(nullptr)
    , m_width(0)
    , m_height(0)
    , m_widthBytes(0)
    , m_rotation(Rotation::ROTATE_0)
    , m_initialized(false)
{
}

Canvas::~Canvas() {
    if (m_buffer) {
        free(m_buffer);
        m_buffer = nullptr;
    }
}

bool Canvas::begin(Rotation rotation) {
    // Allocate framebuffer
    m_buffer = static_cast<uint8_t*>(malloc(config::FRAME_BUFFER_SIZE));
    if (!m_buffer) {
        LOGLN("[Canvas] Failed to allocate framebuffer");
        return false;
    }

    m_rotation = rotation;
    
    // Set dimensions based on rotation
    if (rotation == Rotation::ROTATE_90 || rotation == Rotation::ROTATE_270) {
        m_width = config::DISPLAY_HEIGHT;   // 250
        m_height = config::DISPLAY_WIDTH;   // 122
    } else {
        m_width = config::DISPLAY_WIDTH;    // 122
        m_height = config::DISPLAY_HEIGHT;  // 250
    }
    
    m_widthBytes = config::DISPLAY_WIDTH_BYTES;
    
    // Clear to white
    clear(Color::WHITE);
    
    m_initialized = true;
    LOGF("[Canvas] Initialized %dx%d (rotation %d)\n", m_width, m_height, static_cast<int>(rotation));
    return true;
}

void Canvas::clear(uint8_t color) {
    if (m_buffer) {
        memset(m_buffer, color, config::FRAME_BUFFER_SIZE);
    }
}

bool Canvas::inBounds(int16_t x, int16_t y) const {
    return x >= 0 && x < m_width && y >= 0 && y < m_height;
}

void Canvas::transformCoords(int16_t& x, int16_t& y) {
    int16_t temp;
    
    switch (m_rotation) {
        case Rotation::ROTATE_90:
            temp = x;
            x = config::DISPLAY_WIDTH - 1 - y;
            y = temp;
            break;
        case Rotation::ROTATE_180:
            x = config::DISPLAY_WIDTH - 1 - x;
            y = config::DISPLAY_HEIGHT - 1 - y;
            break;
        case Rotation::ROTATE_270:
            temp = x;
            x = y;
            y = config::DISPLAY_HEIGHT - 1 - temp;
            break;
        default:
            // ROTATE_0 - no transformation
            break;
    }
}

void Canvas::setPixel(int16_t x, int16_t y, uint8_t color) {
    if (!m_buffer || !inBounds(x, y)) return;
    
    // Transform to memory coordinates
    transformCoords(x, y);
    
    // Calculate byte position and bit mask
    uint32_t addr = (x / 8) + y * m_widthBytes;
    uint8_t mask = 0x80 >> (x % 8);
    
    if (color == Color::BLACK) {
        m_buffer[addr] &= ~mask;
    } else {
        m_buffer[addr] |= mask;
    }
}

void Canvas::drawHLine(int16_t x, int16_t y, int16_t w, uint8_t color) {
    for (int16_t i = 0; i < w; ++i) {
        setPixel(x + i, y, color);
    }
}

void Canvas::drawVLine(int16_t x, int16_t y, int16_t h, uint8_t color) {
    for (int16_t i = 0; i < h; ++i) {
        setPixel(x, y + i, color);
    }
}

void Canvas::drawLine(int16_t x0, int16_t y0, int16_t x1, int16_t y1, 
                      uint8_t color, uint8_t thickness) {
    // Bresenham's line algorithm
    int16_t dx = abs(x1 - x0);
    int16_t dy = -abs(y1 - y0);
    int16_t sx = x0 < x1 ? 1 : -1;
    int16_t sy = y0 < y1 ? 1 : -1;
    int16_t err = dx + dy;

    while (true) {
        // Draw thick point
        if (thickness == 1) {
            setPixel(x0, y0, color);
        } else {
            fillCircle(x0, y0, thickness / 2, color);
        }

        if (x0 == x1 && y0 == y1) break;

        int16_t e2 = 2 * err;
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

void Canvas::drawRect(int16_t x, int16_t y, int16_t w, int16_t h, 
                      uint8_t color, uint8_t thickness) {
    // Top
    for (uint8_t t = 0; t < thickness; ++t) {
        drawHLine(x, y + t, w, color);
    }
    // Bottom
    for (uint8_t t = 0; t < thickness; ++t) {
        drawHLine(x, y + h - 1 - t, w, color);
    }
    // Left
    for (uint8_t t = 0; t < thickness; ++t) {
        drawVLine(x + t, y, h, color);
    }
    // Right
    for (uint8_t t = 0; t < thickness; ++t) {
        drawVLine(x + w - 1 - t, y, h, color);
    }
}

void Canvas::fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint8_t color) {
    for (int16_t j = 0; j < h; ++j) {
        drawHLine(x, y + j, w, color);
    }
}

void Canvas::drawCircle(int16_t cx, int16_t cy, int16_t r, 
                        uint8_t color, uint8_t thickness) {
    // Midpoint circle algorithm
    int16_t x = 0;
    int16_t y = r;
    int16_t d = 3 - 2 * r;

    while (x <= y) {
        // Draw 8 octants
        for (uint8_t t = 0; t < thickness; ++t) {
            int16_t rt = r - t;
            setPixel(cx + x, cy + y - t, color);
            setPixel(cx - x, cy + y - t, color);
            setPixel(cx + x, cy - y + t, color);
            setPixel(cx - x, cy - y + t, color);
            setPixel(cx + y - t, cy + x, color);
            setPixel(cx - y + t, cy + x, color);
            setPixel(cx + y - t, cy - x, color);
            setPixel(cx - y + t, cy - x, color);
        }

        if (d < 0) {
            d += 4 * x + 6;
        } else {
            d += 4 * (x - y) + 10;
            y--;
        }
        x++;
    }
}

void Canvas::fillCircle(int16_t cx, int16_t cy, int16_t r, uint8_t color) {
    for (int16_t y = -r; y <= r; ++y) {
        for (int16_t x = -r; x <= r; ++x) {
            if (x * x + y * y <= r * r) {
                setPixel(cx + x, cy + y, color);
            }
        }
    }
}

void Canvas::drawText(int16_t x, int16_t y, const char* text, sFONT* font,
                      uint8_t fg, uint8_t bg) {
    if (!text || !font || !font->table) return;

    uint16_t charWidth = font->Width;
    uint16_t charHeight = font->Height;
    uint16_t bytesPerRow = (charWidth + 7) / 8;
    int16_t startX = x;

    while (*text) {
        if (*text == '\n') {
            x = startX;
            y += charHeight;
            text++;
            continue;
        }
        if ((static_cast<uint8_t>(*text) & 0xC0) == 0x80) {
            text++;  // UTF-8 continuation byte, its lead byte already drew '?'
            continue;
        }
        if (x + charWidth > m_width) {
            // Wrap to next line
            x = startX;
            y += charHeight;
        }
        if (y + charHeight > m_height) {
            break;  // Off screen
        }

        // The fonts only cover printable ASCII; anything else (e.g. UTF-8
        // bytes of "ą") would index past the font table, so draw '?' instead
        char c = (*text >= ' ' && *text <= '~') ? *text : '?';

        // Calculate character offset in font table
        uint32_t charOffset = (c - ' ') * charHeight * bytesPerRow;
        const uint8_t* charData = &font->table[charOffset];

        // Draw character
        for (uint16_t row = 0; row < charHeight; ++row) {
            for (uint16_t col = 0; col < charWidth; ++col) {
                bool pixelOn = (charData[row * bytesPerRow + col / 8] & (0x80 >> (col % 8))) != 0;
                
                if (pixelOn) {
                    setPixel(x + col, y + row, fg);
                } else if (bg != Color::WHITE) {
                    setPixel(x + col, y + row, bg);
                }
            }
        }

        x += charWidth;
        text++;
    }
}

uint16_t Canvas::drawTextWrapped(int16_t x, int16_t y, const char* text,
                                  uint16_t maxWidth, sFONT* font,
                                  uint8_t fg, uint8_t bg) {
    if (!text || !font) return 0;

    uint16_t charWidth = font->Width;
    uint16_t lineHeight = font->Height + 2;
    uint16_t maxChars = maxWidth / charWidth;
    uint16_t linesDrawn = 0;
    
    char lineBuf[80];
    const char* ptr = text;

    while (*ptr) {
        // Find how many characters fit
        size_t len = 0;
        size_t lastSpace = SIZE_MAX;
        
        while (ptr[len] && len < maxChars && len < sizeof(lineBuf) - 1) {
            if (ptr[len] == ' ') lastSpace = len;
            len++;
        }

        // If we hit a word boundary, break there
        size_t copyLen = len;
        if (ptr[len] && lastSpace != SIZE_MAX) {
            copyLen = lastSpace;
        }

        // Copy and draw line
        strncpy(lineBuf, ptr, copyLen);
        lineBuf[copyLen] = '\0';
        
        drawText(x, y, lineBuf, font, fg, bg);
        linesDrawn++;

        // Move to next line
        ptr += copyLen;
        while (*ptr == ' ') ptr++;  // Skip spaces
        
        y += lineHeight;
        if (y + font->Height > m_height) break;
    }

    return linesDrawn;
}

void Canvas::drawTextCentered(int16_t y, const char* text, sFONT* font,
                               uint8_t fg, uint8_t bg) {
    if (!text || !font) return;
    
    uint16_t textWidth = getTextWidth(text, font);
    int16_t x = (m_width - textWidth) / 2;
    if (x < 0) x = 0;
    
    drawText(x, y, text, font, fg, bg);
}

void Canvas::drawNumber(int16_t x, int16_t y, int32_t number, sFONT* font,
                        uint8_t fg, uint8_t bg) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%ld", static_cast<long>(number));
    drawText(x, y, buf, font, fg, bg);
}

void Canvas::drawBitmap(int16_t x, int16_t y, const uint8_t* bitmap,
                        uint16_t w, uint16_t h) {
    if (!bitmap) return;
    
    uint16_t bytesPerRow = (w + 7) / 8;
    
    for (uint16_t row = 0; row < h; ++row) {
        for (uint16_t col = 0; col < w; ++col) {
            bool pixelOn = (bitmap[row * bytesPerRow + col / 8] & (0x80 >> (col % 8))) == 0;
            if (pixelOn) {
                setPixel(x + col, y + row, Color::BLACK);
            }
        }
    }
}

bool Canvas::loadRawBitmap(const uint8_t* data, size_t length) {
    if (!data || !m_buffer) return false;
    
    if (length != config::FRAME_BUFFER_SIZE) {
        LOGF("[Canvas] Invalid bitmap size: %d (expected %d)\n", 
             length, config::FRAME_BUFFER_SIZE);
        return false;
    }
    
    memcpy(m_buffer, data, length);
    return true;
}

uint16_t Canvas::getTextWidth(const char* text, sFONT* font) {
    if (!text || !font) return 0;
    return strlen(text) * font->Width;
}

}  // namespace display

